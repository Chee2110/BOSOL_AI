"""
==============================================================================
BOSOL AI CAD Engine - Lõi Toán Học & Hình Học Lốc Vòm (Arch Geometry Engine)
==============================================================================
Module tính toán, kiểm chứng sai số và bóc tách cấu kiện uốn vòm nhôm kính:
1. Quan hệ hình học giữa: Bán kính R, Dây cung L, Mũi tên vòm H, Chiều dài cung C, Góc uốn alpha.
2. Bù trừ độ dày & bản rộng profile nhôm (R_ngoài = R_trong + W).
3. Tính toán phôi cắt gia công (Chiều dài thành phẩm + Dung sai bù kẹp máy uốn lốc 3 rulo).
4. Kiểm toán chéo (Zero Hallucination Cross-Verification): Phát hiện kích thước bất hợp lý trên bản vẽ.
"""

import math
from typing import Dict, Any, Optional, Tuple

class ArchGeometryEngine:
    """
    Bộ động cơ giải toán và kiểm tra hình học cấu kiện Lốc Vòm:
    - Bán kính lưng ngoài: R_out
    - Bán kính bụng trong: R_in
    - Bản rộng profile nhôm: W (Profile width)
    - Góc ở tâm: alpha (độ) / theta (radian)
    - Chiều dài cung uốn: C (Arc length)
    - Chiều dài dây cung: L (Chord length)
    - Chiều cao mũi tên vòm: H (Sagitta)
    - Chiều dài đoạn chân thẳng: L_leg
    - Chiều cao tổng thể phủ bì: H_total
    - Chiều dài phôi cắt thô: L_blank
    """

    @staticmethod
    def deg_to_rad(deg: float) -> float:
        return deg * math.pi / 180.0

    @staticmethod
    def rad_to_deg(rad: float) -> float:
        return rad * 180.0 / math.pi

    @classmethod
    def compute_arch_from_radius_and_angle(
        cls, 
        r_out: float, 
        angle_deg: float = 90.0, 
        profile_width: float = 55.0,
        leg_length: float = 1650.0,
        clamp_allowance: float = 300.0
    ) -> Dict[str, Any]:
        """
        Tính toán toàn bộ thông số vòm từ Bán kính lưng ngoài (R_out) và Góc uốn (alpha):
        - Công thức cung uốn: C = (pi * R * alpha) / 180
        - Công thức dây cung: L = 2 * R * sin(alpha / 2)
        - Công thức mũi tên vòm (Sagitta): H = R * (1 - cos(alpha / 2))
        """
        r_in = r_out - profile_width
        theta = cls.deg_to_rad(angle_deg)
        half_theta = theta / 2.0

        # 1. Đoạn cong lưng ngoài
        c_out = r_out * theta
        chord_out = 2.0 * r_out * math.sin(half_theta)
        sagitta_out = r_out * (1.0 - math.cos(half_theta))

        # 2. Đoạn cong bụng trong
        c_in = r_in * theta
        chord_in = 2.0 * r_in * math.sin(half_theta)
        sagitta_in = r_in * (1.0 - math.cos(half_theta))

        # 3. Kích thước tổng thể
        # Với góc uốn 90 độ: Chiều cao phủ bì = Chân thẳng + R_ngoài
        if abs(angle_deg - 90.0) < 0.1:
            h_total = leg_length + r_out
        elif abs(angle_deg - 180.0) < 0.1:
            h_total = leg_length + r_out
        else:
            h_total = leg_length + sagitta_out

        finished_length = leg_length + c_out
        # Chiều dài phôi cắt nguyên liệu: Thêm đoạn bù đầu kẹp máy 3 rulo
        blank_length = finished_length + (clamp_allowance * 2.0)

        return {
            "r_out": round(r_out, 2),
            "r_in": round(r_in, 2),
            "profile_width": round(profile_width, 2),
            "angle_deg": round(angle_deg, 2),
            "c_out": round(c_out, 2),
            "c_out_rounded": round(c_out),
            "c_in": round(c_in, 2),
            "c_in_rounded": round(c_in),
            "chord_in": round(chord_in, 2),
            "chord_in_rounded": round(chord_in),
            "sagitta_in": round(sagitta_in, 2),
            "sagitta_in_rounded": round(sagitta_in),
            "leg_length": round(leg_length, 2),
            "h_total": round(h_total, 2),
            "finished_length": round(finished_length, 2),
            "blank_length": round(blank_length, 2),
            "blank_length_rounded": round(blank_length)
        }

    @classmethod
    def compute_radius_from_chord_and_sagitta(cls, chord: float, sagitta: float) -> Tuple[float, float]:
        """
        Nghịch đảo: Khi thợ xưởng đo Dây cung L và Mũi tên vòm H ngoài hiện trường,
        tính ra Bán kính R và Góc uốn alpha:
        R = (L^2 / (8 * H)) + (H / 2)
        alpha = 4 * arctan(2 * H / L)
        """
        if sagitta <= 0 or chord <= 0:
            raise ValueError("Dây cung và mũi tên vòm phải lớn hơn 0")

        r = (chord ** 2) / (8.0 * sagitta) + (sagitta / 2.0)
        alpha_rad = 4.0 * math.atan((2.0 * sagitta) / chord)
        alpha_deg = cls.rad_to_deg(alpha_rad)

        return round(r, 2), round(alpha_deg, 2)

    @classmethod
    def validate_arch_dimensions(
        cls,
        r_out: float,
        profile_width: float,
        r_in: Optional[float] = None,
        c_out: Optional[float] = None,
        c_in: Optional[float] = None,
        chord_in: Optional[float] = None,
        sagitta_in: Optional[float] = None,
        angle_deg: float = 90.0,
        leg_length: Optional[float] = None,
        h_total: Optional[float] = None,
        tolerance_mm: float = 2.0
    ) -> Dict[str, Any]:
        """
        Kiểm toán chéo đối soát số đo trên bản vẽ với công thức toán học lý thuyết.
        Trả về kết quả kiểm tra từng chỉ số và đánh giá toàn vẹn (Zero Hallucination Gate).
        """
        theoretical = cls.compute_arch_from_radius_and_angle(
            r_out=r_out,
            angle_deg=angle_deg,
            profile_width=profile_width,
            leg_length=leg_length or 0.0
        )

        checks = {}
        all_passed = True

        # 1. Kiểm tra R_in
        if r_in is not None:
            err = abs(r_in - theoretical["r_in"])
            ok = err <= tolerance_mm
            checks["r_in"] = {
                "measured": r_in,
                "theoretical": theoretical["r_in"],
                "error_mm": round(err, 2),
                "passed": ok
            }
            if not ok: all_passed = False

        # 2. Kiểm tra Cung ngoài C_out
        if c_out is not None:
            err = abs(c_out - theoretical["c_out"])
            ok = err <= tolerance_mm
            checks["c_out"] = {
                "measured": c_out,
                "theoretical": theoretical["c_out"],
                "error_mm": round(err, 2),
                "passed": ok
            }
            if not ok: all_passed = False

        # 3. Kiểm tra Cung trong C_in
        if c_in is not None:
            err = abs(c_in - theoretical["c_in"])
            ok = err <= tolerance_mm
            checks["c_in"] = {
                "measured": c_in,
                "theoretical": theoretical["c_in"],
                "error_mm": round(err, 2),
                "passed": ok
            }
            if not ok: all_passed = False

        # 4. Kiểm tra Dây cung trong Chord_in
        if chord_in is not None:
            err = abs(chord_in - theoretical["chord_in"])
            ok = err <= tolerance_mm
            checks["chord_in"] = {
                "measured": chord_in,
                "theoretical": theoretical["chord_in"],
                "error_mm": round(err, 2),
                "passed": ok
            }
            if not ok: all_passed = False

        # 5. Kiểm tra Mũi tên vòm Sagitta_in
        if sagitta_in is not None:
            err = abs(sagitta_in - theoretical["sagitta_in"])
            ok = err <= tolerance_mm
            checks["sagitta_in"] = {
                "measured": sagitta_in,
                "theoretical": theoretical["sagitta_in"],
                "error_mm": round(err, 2),
                "passed": ok
            }
            if not ok: all_passed = False

        # 6. Kiểm tra Tổng chiều cao
        if h_total is not None and leg_length is not None:
            err = abs(h_total - theoretical["h_total"])
            ok = err <= tolerance_mm
            checks["h_total"] = {
                "measured": h_total,
                "theoretical": theoretical["h_total"],
                "error_mm": round(err, 2),
                "passed": ok
            }
            if not ok: all_passed = False

        return {
            "is_valid": all_passed,
            "checks": checks,
            "theoretical_model": theoretical
        }
