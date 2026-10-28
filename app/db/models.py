import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.database import Base


class GUID(TypeDecorator):
    """
    Kiểu dữ liệu GUID độc lập nền tảng:
    - Trên PostgreSQL: Sử dụng kiểu bản địa UUID
    - Trên SQLite: Lưu trữ dưới dạng CHAR(36)
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class Document(Base):
    """Bảng quản lý tài liệu tệp PDF bản vẽ đầu vào"""
    __tablename__ = "documents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False, unique=True, index=True)
    file_size_bytes = Column(BigInteger, nullable=False)
    total_pages = Column(Integer, nullable=False, default=1)
    detected_category = Column(String(32), nullable=False, default="CAD_VECTOR")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")


class Job(Base):
    """
    Bảng quản lý Hàng đợi Worker và Mô hình Trạng thái Kép Dual-State:
    - processing_status: Tiến trình máy tự động (queued -> processing -> completed / failed)
    - review_status: Quyết định của kỹ sư (pending -> in_review -> approved / rejected)
    """
    __tablename__ = "jobs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    priority = Column(Integer, nullable=False, default=1)
    attempts = Column(Integer, nullable=False, default=0)
    worker_id = Column(String(64), nullable=True)
    lease_token = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)

    # TRẠNG THÁI KÉP BẮT BUỘC (DUAL-STATE)
    processing_status = Column(String(20), nullable=False, default="queued")
    review_status = Column(String(20), nullable=False, default="pending")

    rejection_reason = Column(Text, nullable=True)
    reviewed_by = Column(String(64), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Ràng buộc toàn vẹn logic ở cấp CSDL
    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('queued', 'processing', 'completed', 'failed')",
            name="chk_processing_status"
        ),
        CheckConstraint(
            "review_status IN ('pending', 'in_review', 'approved', 'rejected')",
            name="chk_review_status"
        ),
        Index("idx_jobs_processing_priority", "processing_status", "priority", "created_at"),
    )

    document = relationship("Document", back_populates="jobs")
    bom_items = relationship("BOMItem", back_populates="job", cascade="all, delete-orphan")
    ai_requests = relationship("AIRequest", back_populates="job")


class BOMItem(Base):
    """Bảng bóc tách bảng kê BOM chi tiết từng ô kèm tọa độ BBox và bằng chứng ảnh"""
    __tablename__ = "bom_items"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id = Column(GUID(), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False, default=1)
    row_index = Column(Integer, nullable=False)
    column_name = Column(String(64), nullable=False)
    suggested_value = Column(String(255), nullable=True)
    verified_value = Column(String(255), nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    source_method = Column(String(20), nullable=False, default="pymupdf")
    bbox_pdf = Column(JSON, nullable=False)  # [x0, y0, x1, y1]
    evidence_crop_id = Column(String(128), nullable=True)
    approval_status = Column(String(20), nullable=False, default="pending")
    candidates = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="bom_items")


class AIRequest(Base):
    """Bảng nhật ký kiểm soát chi phí token và trạng thái Circuit Breaker khi gọi Cloud"""
    __tablename__ = "ai_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id = Column(GUID(), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    model_id = Column(String(64), nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    candidates_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=False, default=0)
    circuit_state = Column(String(16), nullable=False, default="CLOSED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="ai_requests")


class UserConsent(Base):
    """Bảng lưu vết kỹ sư kích hoạt sự đồng ý gửi ảnh crop lên Cloud"""
    __tablename__ = "user_consents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False)
    consent_given = Column(Boolean, nullable=False, default=False)
    scope = Column(String(64), nullable=False, default="gemini_rescue_crop")
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
