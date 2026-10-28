import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.pipeline.arch_geometry import ArchGeometryEngine
from app.pipeline.text_extractor import TextExtractor

class TestArchGeometry(unittest.TestCase):
    """
    Bộ kiểm thử Lõi Toán Học & Hình Học Lốc Vòm (ArchGeometryEngine)
    Kiểm tra tính toán, đối soát sai số và trích xuất thực tế trên tệp 1.3 BV LỐC VÒM T12.A HÙNG.pdf
    """

    def test_01_arch_formulas_forward(self):
        """Kiểm tra các công thức thuận: Bán kính uốn R450, bản rộng 55mm, góc 90 độ"""
        model = ArchGeometryEngine.compute_arch_from_radius_and_angle(
            r_out=450.0,
            angle_deg=90.0,
            profile_width=55.0,
            leg_length=1650.0
        )
        self.assertEqual(model["r_in"], 395.0)
        self.assertAlmostEqual(model["c_out"], 706.86, places=1)
        self.assertEqual(model["c_out_rounded"], 707)
        self.assertAlmostEqual(model["c_in"], 620.46, places=1)
        self.assertEqual(model["c_in_rounded"], 620)
        self.assertAlmostEqual(model["chord_in"], 558.61, places=1)
        self.assertEqual(model["chord_in_rounded"], 559)
        self.assertAlmostEqual(model["sagitta_in"], 115.69, places=1)
        self.assertEqual(model["sagitta_in_rounded"], 116)
        self.assertEqual(model["h_total"], 2100.0)

    def test_02_arch_formulas_inverse(self):
        """Kiểm tra công thức nghịch đảo: Từ Dây cung 559mm và Mũi tên 116mm giải ra Bán kính R và Góc alpha"""
        r, alpha = ArchGeometryEngine.compute_radius_from_chord_and_sagitta(
            chord=559.0,
            sagitta=116.0
        )
        self.assertAlmostEqual(r, 394.73, places=1)
        self.assertAlmostEqual(round(r), 395)
        self.assertAlmostEqual(alpha, 90.16, places=0)
        self.assertEqual(round(alpha), 90)

    def test_03_blank_length_calculation(self):
        """Kiểm tra công thức tính phôi cắt nguyên liệu bù đầu kẹp máy uốn 3 rulo"""
        finished_length = 1650.0 + 707.0  # 2357 mm
        clamp_allowance = 321.5           # (3000 - 2357) / 2
        model = ArchGeometryEngine.compute_arch_from_radius_and_angle(
            r_out=450.0,
            angle_deg=90.0,
            profile_width=55.0,
            leg_length=1650.0,
            clamp_allowance=clamp_allowance
        )
        self.assertEqual(model["blank_length_rounded"], 3000)
        self.assertAlmostEqual(model["blank_length"], 3000.0, places=0)

    def test_04_validate_real_drawing_1_3(self):
        """Kiểm toán chéo đối soát số đo trên bản vẽ 1.3 BV LỐC VÒM T12.A HÙNG.pdf (Zero Hallucination)"""
        res = ArchGeometryEngine.validate_arch_dimensions(
            r_out=450.0,
            profile_width=55.0,
            r_in=395.0,
            c_out=707.0,
            c_in=620.0,
            chord_in=559.0,
            sagitta_in=116.0,
            angle_deg=90.0,
            leg_length=1650.0,
            h_total=2100.0,
            tolerance_mm=1.5
        )
        self.assertTrue(res["is_valid"], "Bản vẽ vi phạm sai số hình học cho phép!")
        for key, check in res["checks"].items():
            self.assertTrue(check["passed"], f"Chỉ số {key} không đạt: error={check['error_mm']}mm")
            self.assertLessEqual(check["error_mm"], 1.0)

    def test_05_text_extractor_arch_integration(self):
        """Kiểm tra tích hợp TextExtractor bóc tách thực tế tệp 1.3 BV LỐC VÒM T12.A HÙNG.pdf"""
        pdf_path = BASE_DIR / "PDF_TEST" / "PDF_BANVE" / "1.3 BV LỐC VÒM T12.A HÙNG.pdf"
        self.assertTrue(pdf_path.exists(), f"Không tìm thấy file {pdf_path}")

        doc_data = TextExtractor.extract_document(pdf_path)
        self.assertEqual(doc_data["total_pages"], 1)
        
        page = doc_data["pages"][0]
        tb = page["title_block"]
        self.assertEqual(tb["fabricator"], "CÔNG TY CP NHÔM AN PHÚ")
        self.assertEqual(tb["customer"], "A. HÙNG")
        self.assertEqual(tb["designer"], "KS. NGUYỄN DUY TÂN")
        self.assertIn("CHG55", tb["aluminum_system"])
        self.assertIn("Hộp", tb["glass_bead"])

        # Phải bóc tách được đầy đủ các chỉ số hình học vòm
        dims = page["dimensions"]
        self.assertGreaterEqual(len(dims), 12)
        dim_texts = [d["raw_text"] for d in dims]
        self.assertIn("R450 mm", dim_texts)
        self.assertIn("R395 mm", dim_texts)
        self.assertIn("707 mm", dim_texts)
        self.assertIn("620 mm", dim_texts)
        self.assertIn("559 mm", dim_texts)
        self.assertIn("116 mm", dim_texts)
        self.assertIn("1650 mm", dim_texts)
        self.assertIn("2100 mm", dim_texts)
        self.assertIn("3000 mm", dim_texts)

if __name__ == "__main__":
    unittest.main()
