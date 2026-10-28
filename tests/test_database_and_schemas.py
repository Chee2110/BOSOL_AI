import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc được nạp vào sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import unittest
from app.db.database import Base, engine, SessionLocal
from app.db.models import Document, Job, BOMItem, AIRequest, UserConsent
from app.schemas.extraction import (
    BOMCellSchema,
    ApprovalStatusEnum,
    CandidateItem,
    ProcessingStatusEnum,
    ReviewStatusEnum,
)

class TestDatabaseAndSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Khởi tạo toàn bộ bảng CSDL kiểm thử"""
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        """Dọn dẹp bảng CSDL sau kiểm thử"""
        Base.metadata.drop_all(bind=engine)

    def test_pydantic_bom_cell_validation(self):
        """Kiểm tra logic bảo vệ toàn vẹn dữ liệu của BOMCellSchema"""
        # 1. Trường hợp bình thường khi máy gợi ý
        cell = BOMCellSchema(
            column_name="part_number",
            suggested_value="BOSOL-001",
            confidence=0.92,
            source_method="pymupdf",
            bbox_pdf=[100.0, 200.0, 150.0, 220.0]
        )
        self.assertEqual(cell.approval_status, ApprovalStatusEnum.PENDING)
        self.assertEqual(cell.suggested_value, "BOSOL-001")
        self.assertIsNone(cell.verified_value)

        # 2. Trường hợp chấp nhận và đã có verified_value
        cell_accepted = BOMCellSchema(
            column_name="part_number",
            suggested_value="BOSOL-001",
            verified_value="BOSOL-001-FIXED",
            confidence=0.92,
            source_method="pymupdf",
            bbox_pdf=[100.0, 200.0, 150.0, 220.0],
            approval_status=ApprovalStatusEnum.ACCEPTED
        )
        self.assertEqual(cell_accepted.verified_value, "BOSOL-001-FIXED")

        # 3. Trường hợp accepted nhưng verified_value để trống -> Tự động điền từ suggested_value
        cell_autofill = BOMCellSchema(
            column_name="qty",
            suggested_value="10",
            confidence=0.95,
            source_method="paddleocr",
            bbox_pdf=[50.0, 50.0, 80.0, 70.0],
            approval_status=ApprovalStatusEnum.ACCEPTED
        )
        self.assertEqual(cell_autofill.verified_value, "10")

        # 4. Trường hợp accepted nhưng CẢ HAI đều rỗng -> Bắt buộc ném ngoại lệ ValueError!
        with self.assertRaises(ValueError):
            BOMCellSchema(
                column_name="material",
                suggested_value="",
                verified_value="",
                confidence=0.5,
                source_method="tesseract",
                bbox_pdf=[10.0, 10.0, 40.0, 40.0],
                approval_status=ApprovalStatusEnum.ACCEPTED
            )

    def test_database_dual_state_lifecycle(self):
        """Kiểm tra vòng đời dữ liệu và mô hình Dual-State trong CSDL"""
        db = SessionLocal()
        try:
            # 1. Tạo tài liệu Document
            doc = Document(
                filename="test_drawing_sample.pdf",
                file_path="uploads/test_drawing_sample.pdf",
                file_hash_sha256="abc123def456_test_hash",
                file_size_bytes=1048576,
                total_pages=1,
                detected_category="CAD_VECTOR"
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            self.assertIsNotNone(doc.id)

            # 2. Tạo Job với trạng thái khởi tạo: processing_status='queued', review_status='pending'
            job = Job(
                document_id=doc.id,
                priority=2,
                processing_status="queued",
                review_status="pending"
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            self.assertEqual(job.processing_status, "queued")
            self.assertEqual(job.review_status, "pending")

            # 3. Tiến trình Worker nhận việc: chuyển processing_status sang 'processing'
            job.processing_status = "processing"
            job.worker_id = "worker-laptop-01"
            job.lease_token = "lease-token-test-123"
            db.commit()
            db.refresh(job)
            self.assertEqual(job.processing_status, "processing")

            # 4. Worker hoàn thành bóc tách: chuyển processing_status sang 'completed'
            job.processing_status = "completed"
            
            # Thêm 1 dòng BOMItem chi tiết
            bom_item = BOMItem(
                job_id=job.id,
                page_number=1,
                row_index=1,
                column_name="part_name",
                suggested_value="TRUC KHUYEU",
                confidence=0.96,
                source_method="pymupdf",
                bbox_pdf=[120.5, 340.2, 280.0, 360.0],
                approval_status="pending",
                candidates=[
                    {"source": "pymupdf", "value": "TRUC KHUYEU", "confidence": 0.96}
                ]
            )
            db.add(bom_item)
            db.commit()

            # 5. Kỹ sư kiểm duyệt: Cập nhật verified_value và chuyển review_status sang 'approved'
            bom_item.verified_value = "TRUC KHUYEU GIA CONG"
            bom_item.approval_status = "accepted"
            job.review_status = "approved"
            job.reviewed_by = "engineer_thanh"
            db.commit()
            db.refresh(job)

            self.assertEqual(job.review_status, "approved")
            self.assertEqual(job.reviewed_by, "engineer_thanh")
            self.assertEqual(bom_item.verified_value, "TRUC KHUYEU GIA CONG")

            # 6. Kiểm tra bảng AIRequest & UserConsent
            consent = UserConsent(
                user_id="engineer_thanh",
                consent_given=True,
                scope="gemini_rescue_crop"
            )
            db.add(consent)

            ai_req = AIRequest(
                job_id=job.id,
                model_id="gemini-2.5-flash",
                prompt_tokens=150,
                candidates_tokens=30,
                total_tokens=180,
                cost_usd=0.000135,
                latency_ms=1250,
                circuit_state="CLOSED"
            )
            db.add(ai_req)
            db.commit()

            self.assertEqual(ai_req.cost_usd, 0.000135)
            self.assertTrue(consent.consent_given)

        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
