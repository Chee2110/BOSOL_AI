import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.pipeline.evidence_store import EvidenceStore

class TestEvidenceStore(unittest.TestCase):
    def setUp(self):
        self.evidence_dir = settings.EVIDENCE_DIR
        self.store = EvidenceStore(storage_dir=self.evidence_dir)
        pdf_banve_dir = settings.PDF_TEST_DIR / "PDF_BANVE"
        pdf_files = list(pdf_banve_dir.glob("*.pdf"))
        self.assertTrue(len(pdf_files) > 0, "Không tìm thấy file CAD trong PDF_TEST/PDF_BANVE")
        self.test_pdf = pdf_files[0]
        print(f"\n[TestEvidenceStore] Sử dụng tệp thực tế: {self.test_pdf.name}")

    def test_crop_and_cache(self):
        """Cắt ảnh crop WebP từ file CAD thật và kiểm tra nén + caching"""
        import uuid
        file_hash = f"mock_hash_{uuid.uuid4().hex[:8]}"
        bbox = (100.0, 100.0, 300.0, 200.0)  # Vùng 200x100 pt
        
        # 1. Cắt lần đầu (chưa có trong cache)
        result1 = self.store.crop_and_save(
            pdf_path=str(self.test_pdf),
            page_number=1,
            bbox_pdf=bbox,
            file_hash=file_hash,
            dpi=200,
            quality=85
        )

        self.assertFalse(result1["cached"])
        crop_path = Path(result1["file_path"])
        self.assertTrue(crop_path.exists())
        self.assertTrue(crop_path.name.endswith(".webp"))
        
        # Kiểm tra kích thước tệp nén: phải rất nhẹ (< 40 KB)
        file_size = result1["file_size_bytes"]
        print(f"\n[EvidenceStore] Kích thước file WebP: {file_size / 1024:.2f} KB (Ảnh width={result1['width']}, height={result1['height']})")
        self.assertLess(file_size, 40 * 1024, "File crop WebP vượt quá ngưỡng 40 KB!")

        # 2. Cắt lần hai (phải lấy từ Cache)
        result2 = self.store.crop_and_save(
            pdf_path=str(self.test_pdf),
            page_number=1,
            bbox_pdf=bbox,
            file_hash=file_hash,
            dpi=200
        )
        self.assertTrue(result2["cached"])
        self.assertEqual(result1["evidence_crop_id"], result2["evidence_crop_id"])

        # 3. Đọc lại raw bytes
        crop_bytes = self.store.get_crop_bytes(result1["evidence_crop_id"])
        self.assertIsNotNone(crop_bytes)
        self.assertEqual(len(crop_bytes), file_size)

if __name__ == "__main__":
    unittest.main()
