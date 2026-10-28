import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import unittest
from app.pipeline.document_router import DocumentRouter

class TestRouterRealFiles(unittest.TestCase):
    def test_classify_all_sample_pdfs(self):
        pdf_test_dir = BASE_DIR / "PDF_TEST"
        if not pdf_test_dir.exists():
            self.skipTest("Thư mục PDF_TEST không tồn tại!")

        pdf_files = list(pdf_test_dir.rglob("*.pdf"))
        self.assertGreater(len(pdf_files), 0, "Không tìm thấy file PDF nào trong PDF_TEST!")

        print(f"\n{'='*70}")
        print(f"KẾT QUẢ ĐO KIỂM BỘ ĐỊNH TUYẾN ROUTER TRÊN {len(pdf_files)} FILE THỰC TẾ:")
        print(f"{'='*70}")

        results_by_folder = {}
        for pdf_path in pdf_files:
            folder_name = pdf_path.parent.name
            start_time = time.time()
            res = DocumentRouter.route_document(pdf_path)
            duration_ms = (time.time() - start_time) * 1000

            results_by_folder.setdefault(folder_name, []).append((pdf_path.name, res["category"], duration_ms, res["reason"]))
            print(f"• [{folder_name:<16}] {pdf_path.name[:35]:<35} -> {res['category']:<12} ({duration_ms:.1f}ms)")

        print(f"{'='*70}\n")

        # Xác thực độ chính xác phân loại theo folder
        # PDF_BANVE -> CAD_VECTOR
        for name, cat, _, _ in results_by_folder.get("PDF_BANVE", []):
            self.assertEqual(cat, "CAD_VECTOR", f"File {name} trong PDF_BANVE phải là CAD_VECTOR nhưng nhận là {cat}")

        # PDF_SCAN_BAN_VE -> CAD_SCAN
        for name, cat, _, _ in results_by_folder.get("PDF_SCAN_BAN_VE", []):
            self.assertEqual(cat, "CAD_SCAN", f"File {name} trong PDF_SCAN_BAN_VE phải là CAD_SCAN nhưng nhận là {cat}")

        # PDF_SCAN_TEXT -> SCAN_TEXT
        for name, cat, _, _ in results_by_folder.get("PDF_SCAN_TEXT", []):
            self.assertEqual(cat, "SCAN_TEXT", f"File {name} trong PDF_SCAN_TEXT phải là SCAN_TEXT nhưng nhận là {cat}")

        # PDF_TEXT -> TEXT_PDF
        for name, cat, _, _ in results_by_folder.get("PDF_TEXT", []):
            self.assertEqual(cat, "TEXT_PDF", f"File {name} trong PDF_TEXT phải là TEXT_PDF nhưng nhận là {cat}")

if __name__ == "__main__":
    unittest.main()
