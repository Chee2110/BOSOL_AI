import pymupdf
from typing import Dict, Any
from pathlib import Path

class DocumentRouter:
    """
    Bộ định tuyến phân loại tài liệu PDF thành 4 nhánh:
    1. CAD_VECTOR: Bản vẽ kỹ thuật CAD có vector primitives (đường bao, gióng, ký hiệu)
    2. CAD_SCAN: Bản vẽ scan (ảnh raster lớn, khổ lớn A0-A3, đồ họa cơ khí mờ)
    3. TEXT_PDF: Tài liệu văn bản PDF gốc có text stream dày (đơn hàng, báo giá, thuyết minh)
    4. SCAN_TEXT: Tài liệu văn bản scan (ảnh chụp văn bản hành chính, hóa đơn)
    """

    @staticmethod
    def analyze_page(page: pymupdf.Page) -> Dict[str, Any]:
        """Phân tích các chỉ số mật độ trên 1 trang PDF"""
        rect = page.rect
        page_area = rect.width * rect.height
        if page_area <= 0:
            page_area = 1.0

        # 1. Trích xuất text
        text = page.get_text("text").strip()
        text_char_count = len(text)
        text_density = text_char_count / page_area

        # 2. Đếm các đối tượng đồ họa vector (đường gióng, hình chữ nhật, cung tròn, hatching)
        drawings = page.get_drawings()
        vector_count = len(drawings)
        vector_density = vector_count / page_area

        # 3. Phân tích ảnh raster
        images = page.get_images(full=True)
        image_count = len(images)
        
        raster_area = 0.0
        for img in images:
            xref = img[0]
            for img_rect in page.get_image_rects(xref):
                raster_area += img_rect.width * img_rect.height
        raster_ratio = min(1.0, raster_area / page_area)

        return {
            "width": rect.width,
            "height": rect.height,
            "page_area": page_area,
            "text_char_count": text_char_count,
            "text_density": text_density,
            "vector_count": vector_count,
            "vector_density": vector_density,
            "image_count": image_count,
            "raster_ratio": raster_ratio,
            "has_rotation": page.rotation != 0,
            "rotation": page.rotation,
        }

    @classmethod
    def route_document(cls, pdf_path: str | Path) -> Dict[str, Any]:
        """
        Phân loại toàn bộ tài liệu PDF dựa trên phân tích trang đại diện (trang 1)
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp PDF: {pdf_path}")

        doc = pymupdf.open(str(path))
        try:
            total_pages = len(doc)
            if total_pages == 0:
                raise ValueError("Tệp PDF rỗng không có trang nào!")

            page = doc[0]
            metrics = cls.analyze_page(page)

            # CÂY QUYẾT ĐỊNH PHÂN NHÁNH (DECISION TREE ĐÃ TINH CHỈNH ĐO KIỂM)
            # 1. Nhóm tệp Scan (Ảnh raster chiếm ưu thế >= 70% và text rất ít < 100 ký tự)
            if metrics["raster_ratio"] >= 0.70 and metrics["text_char_count"] < 100:
                is_large_paper = max(metrics["width"], metrics["height"]) >= 1000 or metrics["page_area"] >= 600000
                name_upper = path.name.upper()
                if "BAN VE" in name_upper or "BẢN VẼ" in name_upper or is_large_paper:
                    category = "CAD_SCAN"
                    reason = f"Bản vẽ Scan: raster={metrics['raster_ratio']:.1%}, khổ giấy lớn ({metrics['width']:.0f}x{metrics['height']:.0f})"
                else:
                    category = "SCAN_TEXT"
                    reason = f"Văn bản Scan: raster={metrics['raster_ratio']:.1%}, ít text ({metrics['text_char_count']} ký tự)"

            # 2. Nhóm Văn bản Text stream dày (Đơn hàng, Báo giá, Thuyết minh kỹ thuật)
            # Text dài (> 1200 ký tự) và nét vector chỉ là khung viền bảng biểu (< 150)
            elif metrics["text_char_count"] >= 1200 and metrics["vector_count"] < 150:
                category = "TEXT_PDF"
                reason = f"Văn bản Text stream dày: {metrics['text_char_count']} ký tự, đường kẻ bảng ({metrics['vector_count']} nét)"

            # 3. Nhóm Bản vẽ CAD Vector: Có nhiều nét đồ họa cơ khí (đường nét, gióng, ký hiệu)
            elif metrics["vector_count"] >= 150 or (metrics["vector_count"] >= 30 and metrics["vector_count"] > metrics["text_char_count"] * 0.2):
                category = "CAD_VECTOR"
                reason = f"Bản vẽ CAD Vector: {metrics['vector_count']} nét vẽ đồ họa, text: {metrics['text_char_count']} ký tự"

            # 4. Phân loại theo mật độ text còn lại
            elif metrics["text_char_count"] >= 200:
                category = "TEXT_PDF"
                reason = f"Văn bản Text: {metrics['text_char_count']} ký tự"
            else:
                category = "CAD_VECTOR"
                reason = f"Mặc định CAD Vector do có nét vẽ cơ khí ({metrics['vector_count']})"

            return {
                "file_path": str(path),
                "filename": path.name,
                "total_pages": total_pages,
                "category": category,
                "reason": reason,
                "metrics": metrics
            }
        finally:
            doc.close()

    # Alias tương thích
    inspect_pdf = route_document

