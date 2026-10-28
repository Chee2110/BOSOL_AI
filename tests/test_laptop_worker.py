import os
import sys
import unittest
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.db.database import get_db, init_db, SessionLocal
from app.db.models import Document, Job, BOMItem
from app.workers.laptop_worker import LaptopWorker

class TestLaptopWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        self.worker = LaptopWorker(worker_id="test_worker_001")
        
        pdf_banve_dir = settings.PDF_TEST_DIR / "PDF_BANVE"
        pdf_files = list(pdf_banve_dir.glob("*.pdf"))
        self.assertTrue(len(pdf_files) > 0, "Không tìm thấy file CAD trong PDF_TEST/PDF_BANVE")
        self.test_pdf = pdf_files[0]

    def tearDown(self):
        self.db.close()

    def test_01_claim_and_process_job(self):
        """Kiểm tra toàn bộ chu trình Worker: Claim job -> Extract PyMuPDF -> Save BOM -> Dual-State Update"""
        file_bytes = self.test_pdf.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # 1. Tạo hoặc lấy Document
        doc = self.db.query(Document).filter(Document.file_hash_sha256 == file_hash).first()
        if not doc:
            doc = Document(
                filename=self.test_pdf.name,
                file_path=str(self.test_pdf),
                file_hash_sha256=file_hash,
                file_size_bytes=len(file_bytes),
                detected_category="CAD_VECTOR"
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)

        # 2. Tạo Job ở hàng đợi 'queued'
        job = Job(
            document_id=doc.id,
            priority=10,
            processing_status="queued",
            review_status="pending"
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        print(f"\n[TestWorker] Đã tạo Job {job.id} cho tệp {doc.filename}")

        # 3. Worker chạy 1 chu kỳ xử lý
        processed = self.worker.run_once()
        self.assertTrue(processed, "Worker không xử lý được Job nào!")

        # 4. Kiểm tra trạng thái Job sau khi xử lý
        self.db.refresh(job)
        print(f"[TestWorker] Trạng thái sau xử lý: processing_status={job.processing_status}, review_status={job.review_status}")
        self.assertEqual(job.processing_status, "completed")
        self.assertEqual(job.review_status, "pending")  # Bắt buộc Hard Gate ERP
        self.assertEqual(job.attempts, 1)

        # 5. Kiểm tra các BOM Item được lưu trong CSDL
        bom_items = self.db.query(BOMItem).filter(BOMItem.job_id == job.id).all()
        print(f"[TestWorker] Số lượng BOM Item bóc tách được: {len(bom_items)}")
        self.assertGreater(len(bom_items), 0, "Không trích xuất được mục BOM nào!")
        
        sample_item = bom_items[0]
        print(f"  Mẫu BOM #1: Cột={sample_item.column_name}, Giá trị={sample_item.suggested_value}, Nguồn={sample_item.source_method}")

    def test_02_zombie_reaper(self):
        """Kiểm tra cơ chế tự động dọn và hồi sinh Zombie Job bị treo quá hạn lease"""
        # Tạo 1 job bị treo trong quá khứ
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        # Lấy 1 document có sẵn
        doc = self.db.query(Document).first()
        self.assertIsNotNone(doc)

        zombie_job = Job(
            document_id=doc.id,
            priority=5,
            processing_status="processing",
            lease_token="old_expired_token",
            lease_expires_at=expired_time,
            attempts=1
        )
        self.db.add(zombie_job)
        self.db.commit()
        self.db.refresh(zombie_job)

        # Chạy dọn dẹp Zombie
        reaped = self.worker.reap_zombie_jobs(self.db)
        self.assertGreaterEqual(reaped, 1)

        # Kiểm tra: Job phải được hồi sinh về 'queued'
        self.db.refresh(zombie_job)
        self.assertEqual(zombie_job.processing_status, "queued")
        self.assertIsNone(zombie_job.lease_token)
        print(f"\n[TestWorker] Đã hồi sinh thành công Zombie Job {zombie_job.id} về trạng thái 'queued'.")

        # Dọn dẹp bản ghi test
        self.db.delete(zombie_job)
        self.db.commit()

if __name__ == "__main__":
    unittest.main()
