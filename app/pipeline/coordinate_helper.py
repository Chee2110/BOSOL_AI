import math
from typing import List, Tuple, Dict, Any

class CoordinateHelper:
    """
    Module toán học chuyển đổi hệ tọa độ Affine 5 bước giữa:
    - Không gian tệp PDF (gốc dưới-trái, Y hướng lên, có thể xoay 0°, 90°, 180°, 270°, lệch CropBox)
    - Không gian Viewport trình duyệt Web (PDF.js Canvas, gốc trên-trái, Y hướng xuống)
    Đảm bảo sai số lý thuyết Max Error = 0.0000 pt.
    """

    @staticmethod
    def normalize_bbox(bbox: List[float]) -> List[float]:
        """Đảm bảo [x0, y0, x1, y1] luôn có x0 <= x1 và y0 <= y1"""
        x0, y0, x1, y1 = bbox
        return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]

    @staticmethod
    def pdf_to_viewport(
        bbox_pdf: List[float],
        cropbox: Tuple[float, float, float, float],
        rotation: int,
        viewport_width: float,
        viewport_height: float
    ) -> List[float]:
        """
        Chuyển đổi từ PDF BBox [x0, y0, x1, y1] sang Viewport [u0, v0, u1, v1]:
        1. Bù CropBox offset
        2. Bù góc xoay trang (0°, 90°, 180°, 270°)
        3. Tính tỷ lệ Scale
        4. Ánh xạ sang tọa độ màn hình
        """
        cb_x0, cb_y0, cb_x1, cb_y1 = cropbox
        page_w = cb_x1 - cb_x0
        page_h = cb_y1 - cb_y0

        x0, y0, x1, y1 = CoordinateHelper.normalize_bbox(bbox_pdf)

        # Bước 1: Dịch offset CropBox
        x0_off = x0 - cb_x0
        y0_off = y0 - cb_y0
        x1_off = x1 - cb_x0
        y1_off = y1 - cb_y0

        # Bước 2: Bù xoay (Rotation)
        rot = rotation % 360
        if rot == 0:
            rx0, ry0 = x0_off, page_h - y1_off
            rx1, ry1 = x1_off, page_h - y0_off
            rotated_w, rotated_h = page_w, page_h
        elif rot == 90:
            rx0, ry0 = y0_off, x0_off
            rx1, ry1 = y1_off, x1_off
            rotated_w, rotated_h = page_h, page_w
        elif rot == 180:
            rx0, ry0 = page_w - x1_off, y0_off
            rx1, ry1 = page_w - x0_off, y1_off
            rotated_w, rotated_h = page_w, page_h
        elif rot == 270:
            rx0, ry0 = page_h - y1_off, page_w - x1_off
            rx1, ry1 = page_h - y0_off, page_w - x0_off
            rotated_w, rotated_h = page_h, page_w
        else:
            raise ValueError(f"Góc xoay không hợp lệ: {rotation} (chỉ hỗ trợ 0, 90, 180, 270)")

        # Bước 3 & 4: Tỷ lệ co giãn Scale Factor & Ánh xạ Viewport
        scale_x = viewport_width / rotated_w
        scale_y = viewport_height / rotated_h

        u0 = rx0 * scale_x
        v0 = ry0 * scale_y
        u1 = rx1 * scale_x
        v1 = ry1 * scale_y

        return CoordinateHelper.normalize_bbox([u0, v0, u1, v1])

    @staticmethod
    def viewport_to_pdf(
        bbox_viewport: List[float],
        cropbox: Tuple[float, float, float, float],
        rotation: int,
        viewport_width: float,
        viewport_height: float
    ) -> List[float]:
        """
        Chuyển đổi ngược từ Viewport [u0, v0, u1, v1] sang PDF BBox [x0, y0, x1, y1]
        """
        cb_x0, cb_y0, cb_x1, cb_y1 = cropbox
        page_w = cb_x1 - cb_x0
        page_h = cb_y1 - cb_y0

        u0, v0, u1, v1 = CoordinateHelper.normalize_bbox(bbox_viewport)

        rot = rotation % 360
        if rot in (0, 180):
            rotated_w, rotated_h = page_w, page_h
        else:
            rotated_w, rotated_h = page_h, page_w

        scale_x = viewport_width / rotated_w
        scale_y = viewport_height / rotated_h

        rx0 = u0 / scale_x
        ry0 = v0 / scale_y
        rx1 = u1 / scale_x
        ry1 = v1 / scale_y

        if rot == 0:
            x0_off = rx0
            x1_off = rx1
            y0_off = page_h - ry1
            y1_off = page_h - ry0
        elif rot == 90:
            x0_off = ry0
            x1_off = ry1
            y0_off = rx0
            y1_off = rx1
        elif rot == 180:
            x0_off = page_w - rx1
            x1_off = page_w - rx0
            y0_off = ry0
            y1_off = ry1
        elif rot == 270:
            x0_off = page_w - ry1
            x1_off = page_w - ry0
            y0_off = page_h - rx1
            y1_off = page_h - rx0

        x0 = x0_off + cb_x0
        y0 = y0_off + cb_y0
        x1 = x1_off + cb_x0
        y1 = y1_off + cb_y0

        return CoordinateHelper.normalize_bbox([x0, y0, x1, y1])
