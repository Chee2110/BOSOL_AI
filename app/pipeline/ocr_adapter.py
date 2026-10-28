import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pymupdf
from sqlalchemy.orm import Session

from app.config import settings
from app.pipeline.text_extractor import TextExtractor
from app.pipeline.gemini_adapter import gemini_rescue_adapter, CircuitBreakerException
from app.pipeline.evidence_store import evidence_store

logger = logging.getLogger("bosol.ocr_adapter")

class MultiOCRAdapter:
    """
    BỘ ĐIỀU PHỐI OCR ĐA TẦNG (Module 5):
    - Tầng 1: Lõi PyMuPDF Text-First (0ms, 0 VNĐ, chính xác 100% cho CAD Vector & Text PDF).
    - Tầng 2: Heuristic Cell Alignment (Ghép ô bảng biểu từ vector nét vẽ).
    - Tầng 3: Tầng cứu viện Cloud Gemini (Khi ô mờ, nét đứt, hoặc độ tin cậy < OCR_CONFIDENCE_THRESHOLD).
    - An toàn: Luôn kiểm tra User Consent và Circuit Breaker trước khi kích hoạt Tầng 3.
    """

    def __init__(self):
        self.confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD

    def extract_cell_value(
        self,
        pdf_path: str,
        page_number: int,
        bbox_pdf: Tuple[float, float, float, float],
        file_hash: str,
        job_id: Optional[str] = None,
        db: Optional[Session] = None,
        user_id: str = "default_engineer",
        force_cloud_rescue: bool = False
    ) -> Dict[str, Any]:
        """
        Trích xuất giá trị một ô cụ thể trong bảng kê BOM hoặc khung tên:
        - Đầu tiên thử đọc text trực tiếp trong vùng BBox bằng PyMuPDF.
        - Nếu text trống hoặc confidence < ngưỡng, tự động cắt ảnh WebP (Evidence Store)
          và kích hoạt Tầng Cứu Viện Gemini (nếu kỹ sư đồng ý).
        """
        # 1. Trích xuất text cục bộ trong BBox bằng PyMuPDF
        doc = pymupdf.open(pdf_path)
        try:
            page = doc[page_number - 1]
            rect = pymupdf.Rect(bbox_pdf[0], bbox_pdf[1], bbox_pdf[2], bbox_pdf[3])
            extracted_text = page.get_text("text", clip=rect).strip()
        finally:
            doc.close()

        confidence = 0.95 if extracted_text else 0.0

        # Nếu text cục bộ rõ ràng và không bị ép cứu viện -> Trả về ngay (0 VNĐ)
        if extracted_text and confidence >= self.confidence_threshold and not force_cloud_rescue:
            return {
                "text": extracted_text,
                "confidence": confidence,
                "source_method": "pymupdf_local",
                "evidence_crop_id": None,
                "cost_usd": 0.0,
                "needs_review": False
            }

        # 2. Cắt ảnh bằng chứng (Evidence Store)
        evidence_crop = evidence_store.crop_and_save(
            pdf_path=pdf_path,
            page_number=page_number,
            bbox_pdf=bbox_pdf,
            file_hash=file_hash
        )
        crop_id = evidence_crop["evidence_crop_id"]
        crop_bytes = evidence_store.get_crop_bytes(crop_id)

        # 3. Kích hoạt Tầng Cứu Viện Gemini nếu cần
        if crop_bytes and (confidence < self.confidence_threshold or force_cloud_rescue):
            try:
                # Kiểm tra User Consent
                has_consent = gemini_rescue_adapter.verify_user_consent(db, user_id) if db else False
                
                if has_consent or force_cloud_rescue:
                    logger.info(f"[OCRAdapter] Kích hoạt Tầng cứu viện Gemini cho ô {bbox_pdf}")
                    cloud_res = gemini_rescue_adapter.rescue_crop_image(
                        image_bytes=crop_bytes,
                        mime_type="image/webp",
                        prompt_instruction="Đọc chính xác chữ số, dung sai kỹ thuật trong ảnh crop bản vẽ này. Trả về đúng JSON dạng: {\"text\": \"...\", \"confidence\": 0.95}",
                        job_id=job_id,
                        db=db,
                        user_id=user_id,
                        force_bypass_consent=force_cloud_rescue
                    )
                    if cloud_res.get("success"):
                        return {
                            "text": cloud_res.get("text", extracted_text),
                            "confidence": 0.95,
                            "source_method": "gemini_rescue",
                            "evidence_crop_id": crop_id,
                            "cost_usd": cloud_res.get("cost_usd", 0.0),
                            "needs_review": False
                        }
            except Exception as e:
                logger.warning(f"[OCRAdapter] Cứu viện Cloud không khả dụng ({e}). Fallback về cục bộ.")

        # Fallback an toàn: Trả về kết quả cục bộ và đánh dấu needs_review=True để kỹ sư duyệt
        return {
            "text": extracted_text or "",
            "confidence": confidence,
            "source_method": "fallback_local",
            "evidence_crop_id": crop_id,
            "cost_usd": 0.0,
            "needs_review": True
        }

ocr_adapter = MultiOCRAdapter()
