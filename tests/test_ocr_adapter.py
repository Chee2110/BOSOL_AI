import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.db.database import get_db, init_db
from app.pipeline.ocr_adapter import ocr_adapter

class TestOCRAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = next(get_db())
        pdf_banve_dir = settings.PDF_TEST_DIR / "PDF_BANVE"
        pdf_files = list(pdf_banve_dir.glob("*.pdf"))
        self.assertTrue(len(pdf_files) > 0, "Không tìm thấy file trong PDF_BANVE")
        self.test_pdf = pdf_files[0]

    def tearDown(self):
        self.db.close()

    def test_01_local_text_cell(self):
        """Kiểm tra trích xuất ô bình thường: 100% cục bộ 0 VNĐ"""
        # BBox bao phủ dòng text có thật ở góc dưới trang bản vẽ: (200.0, 750.0, 300.0, 900.0)
        bbox = (200.0, 750.0, 300.0, 900.0)
        res = ocr_adapter.extract_cell_value(
            pdf_path=str(self.test_pdf),
            page_number=1,
            bbox_pdf=bbox,
            file_hash="test_ocr_hash_001",
            db=self.db,
            force_cloud_rescue=False
        )
        print("\n--- TEST LOCAL TEXT CELL (0 VNĐ) ---")
        print(f"Source Method: {res['source_method']}")
        print(f"Cost: ${res['cost_usd']}")
        print(f"Extracted Text: {res['text']}")
        self.assertEqual(res["source_method"], "pymupdf_local")
        self.assertEqual(res["cost_usd"], 0.0)
        self.assertFalse(res["needs_review"])
        self.assertIn("0983.773.255", res["text"])

    def test_02_cloud_rescue_flow(self):
        """Kiểm tra chu trình cứu viện: Crop WebP -> Gemini Rescue hoặc Fallback"""
        # BBox vùng ô bản vẽ
        bbox = (250.0, 800.0, 265.0, 870.0)
        res = ocr_adapter.extract_cell_value(
            pdf_path=str(self.test_pdf),
            page_number=1,
            bbox_pdf=bbox,
            file_hash="test_ocr_hash_002",
            db=self.db,
            force_cloud_rescue=True
        )
        print("\n--- TEST CLOUD RESCUE FLOW ---")
        print(f"Source Method: {res['source_method']}")
        print(f"Evidence Crop ID: {res['evidence_crop_id']}")
        print(f"Result Text: {res['text']}")
        print(f"Cost: ${res['cost_usd']:.6f}")
        # Luôn phải sinh ra Evidence Crop ID để người dùng kiểm chứng
        self.assertIsNotNone(res["evidence_crop_id"])
        # Source method phải là gemini_rescue (khi Cloud thông suốt) hoặc fallback_local (khi Cloud từ chối/503)
        self.assertIn(res["source_method"], ("gemini_rescue", "fallback_local"))

if __name__ == "__main__":
    unittest.main()
