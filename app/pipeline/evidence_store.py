import os
import io
import hashlib
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import pymupdf as fitz
from PIL import Image

from app.config import settings

class EvidenceStore:
    """
    KHO QUẢN LÝ BẰNG CHỨNG ẢNH & VERSIONED CACHE (Module 4):
    - Cắt ảnh ô bảng biểu (Crop BBox) từ trang PDF với độ phân giải cao (DPI 200 - 300).
    - Nén WebP lossless/lossy nhẹ (< 35KB/file), lưu theo mã băm SHA-256.
    - Versioned Cache Key: sha256(file_hash + page + bbox + pipeline_version).
    - Cung cấp URL/Path truy cập tức thì cho Frontend đối soát song song.
    """

    PIPELINE_VERSION = "2.8.0"

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or settings.EVIDENCE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def compute_cache_key(
        cls, 
        file_hash: str, 
        page_number: int, 
        bbox_pdf: Tuple[float, float, float, float],
        extra_config: str = ""
    ) -> str:
        """
        Sinh khóa Cache phiên bản hóa không thể trùng lặp:
        sha256(file_hash + page_number + bbox + pipeline_version + extra_config)
        """
        raw_key = f"{file_hash}:{page_number}:{bbox_pdf[0]:.2f}_{bbox_pdf[1]:.2f}_{bbox_pdf[2]:.2f}_{bbox_pdf[3]:.2f}:{cls.PIPELINE_VERSION}:{extra_config}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def crop_and_save(
        self,
        pdf_path: str,
        page_number: int,
        bbox_pdf: Tuple[float, float, float, float],
        file_hash: str,
        dpi: int = 200,
        quality: int = 85
    ) -> Dict[str, Any]:
        """
        Cắt vùng BBox từ file PDF và lưu thành tệp WebP:
        - bbox_pdf: (x0, y0, x1, y1) tọa độ chuẩn điểm PDF (72 pt/inch).
        - dpi: Mặc định 200 để chữ sắc nét mà dung lượng chỉ ~15 - 35 KB.
        """
        cache_id = self.compute_cache_key(file_hash, page_number, bbox_pdf)
        target_filename = f"{cache_id}.webp"
        target_path = self.storage_dir / target_filename

        # 1. Kiểm tra nếu đã có trong Cache -> Trả về ngay lập tức (0.01ms)
        if target_path.exists():
            return {
                "evidence_crop_id": cache_id,
                "file_path": str(target_path),
                "relative_url": f"/evidence/{target_filename}",
                "file_size_bytes": target_path.stat().st_size,
                "cached": True
            }

        # 2. Cắt ảnh bằng PyMuPDF
        doc = fitz.open(pdf_path)
        try:
            page_idx = page_number - 1
            if page_idx < 0 or page_idx >= len(doc):
                raise IndexError(f"Trang {page_number} không tồn tại trong tài liệu (tổng số trang: {len(doc)})")
            
            page = doc[page_idx]
            rect = fitz.Rect(bbox_pdf[0], bbox_pdf[1], bbox_pdf[2], bbox_pdf[3])

            # Tính toán ma trận zoom tương ứng với DPI (72 pt chuẩn)
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)

            # Xuất pixmap vùng crop (clip=rect)
            pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)

            # Chuyển đổi sang PIL Image để lưu WebP tối ưu dung lượng
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Lưu tệp WebP nén
            img.save(str(target_path), format="WEBP", quality=quality, method=4)

            return {
                "evidence_crop_id": cache_id,
                "file_path": str(target_path),
                "relative_url": f"/evidence/{target_filename}",
                "file_size_bytes": target_path.stat().st_size,
                "cached": False,
                "width": pix.width,
                "height": pix.height
            }
        finally:
            doc.close()

    def get_crop_bytes(self, evidence_crop_id: str) -> Optional[bytes]:
        """Đọc raw bytes của ảnh crop từ ID"""
        target_path = self.storage_dir / f"{evidence_crop_id}.webp"
        if target_path.exists():
            return target_path.read_bytes()
        return None

evidence_store = EvidenceStore()
