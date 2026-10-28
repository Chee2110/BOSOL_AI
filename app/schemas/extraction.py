from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class ProcessingStatusEnum(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatusEnum(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalStatusEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class SourceMethodEnum(str, Enum):
    PYMUPDF = "pymupdf"
    PADDLEOCR = "paddleocr"
    TESSERACT = "tesseract"
    GEMINI = "gemini"
    MANUAL = "manual"


class CandidateItem(BaseModel):
    """Một kết quả bóc tách ứng viên từ OCR hoặc Gemini để đối chiếu song song"""
    source: str = Field(..., description="'paddleocr' | 'tesseract' | 'gemini' | 'manual'")
    value: str = Field(..., description="Giá trị trích xuất được")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Mức tin cậy (0.0 - 1.0)")


class BOMCellSchema(BaseModel):
    """
    Schema kiểm soát dữ liệu cấp từng ô trong Bảng kê BOM hoặc Khung tên.
    Mỗi ô lưu vết nguồn gốc, tọa độ BBox và bằng chứng hình ảnh (Evidence Crop).
    """
    column_name: str = Field(..., description="Tên cột: item_no, part_number, part_name, qty, material...")
    suggested_value: Optional[str] = Field(None, description="Giá trị do máy gợi ý ban đầu")
    verified_value: Optional[str] = Field(None, description="Giá trị sau khi kỹ sư xác nhận hoặc chỉnh sửa")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Độ tin cậy của thuật toán bóc tách")
    source_method: str = Field(default="pymupdf", description="Nguồn trích xuất: pymupdf, paddleocr, tesseract, gemini")
    bbox_pdf: List[float] = Field(..., min_length=4, max_length=4, description="Tọa độ [x0, y0, x1, y1] theo hệ tọa độ PDF")
    evidence_crop_id: Optional[str] = Field(None, description="Khóa ảnh crop lưu trong evidence_store")
    approval_status: ApprovalStatusEnum = Field(default=ApprovalStatusEnum.PENDING, description="Trạng thái duyệt của ô")
    candidates: List[CandidateItem] = Field(default_factory=list, description="Danh sách các kết quả đối chiếu song song")

    @model_validator(mode="after")
    def validate_approval_consistency(self):
        """
        NGUYÊN TẮC BẢO TOÀN DỮ LIỆU:
        Khắc phục triệt để lỗi logic: Nếu ô đã được đánh dấu 'accepted' hoặc 'edited'
        thì bắt buộc phải có giá trị kiểm chứng verified_value (không được rỗng hoặc None).
        """
        if self.approval_status in (ApprovalStatusEnum.ACCEPTED, ApprovalStatusEnum.EDITED):
            if self.verified_value is None or str(self.verified_value).strip() == "":
                # Nếu chấp nhận mà chưa gõ verified_value, tự động gán từ suggested_value nếu có
                if self.suggested_value is not None and str(self.suggested_value).strip() != "":
                    self.verified_value = str(self.suggested_value).strip()
                else:
                    raise ValueError(
                        f"Ô '{self.column_name}' được đánh dấu '{self.approval_status.value}' "
                        f"nhưng cả verified_value và suggested_value đều bị rỗng!"
                    )
        return self


class TitleBlockSchema(BaseModel):
    """Dữ liệu khung tên bản vẽ kỹ thuật"""
    drawing_number: BOMCellSchema
    part_name: BOMCellSchema
    material: BOMCellSchema
    scale: Optional[BOMCellSchema] = None
    designer: Optional[BOMCellSchema] = None
    approver: Optional[BOMCellSchema] = None


class DimensionItemSchema(BaseModel):
    """Kích thước và dung sai hình học cơ khí bóc tách từ bản vẽ"""
    dimension_type: str = Field(..., description="'linear' | 'diameter' | 'radius' | 'tolerance' | 'chamfer'")
    nominal_value: Optional[float] = Field(None, description="Giá trị danh nghĩa số (vd: 35.0)")
    tolerance: Optional[str] = Field(None, description="Dung sai kèm theo (vd: ±0.05, +0.02/-0.01, h7)")
    raw_text: str = Field(..., description="Chuỗi ký tự gốc (vd: Ø35±0.05, 4xM8, R15)")
    bbox_pdf: List[float] = Field(..., min_length=4, max_length=4)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_method: str = Field(default="pymupdf")
    evidence_crop_id: Optional[str] = None
    verified_value: Optional[str] = None
    approval_status: ApprovalStatusEnum = Field(default=ApprovalStatusEnum.PENDING)


class ExtractionResultSchema(BaseModel):
    """Toàn bộ kết quả bóc tách bản vẽ kỹ thuật theo chuẩn v2.8"""
    document_id: str
    job_id: str
    processing_status: ProcessingStatusEnum
    review_status: ReviewStatusEnum
    title_block: Optional[TitleBlockSchema] = None
    bom_rows: List[Dict[str, BOMCellSchema]] = Field(default_factory=list)
    dimensions: List[DimensionItemSchema] = Field(default_factory=list)
    total_cost_usd: float = Field(default=0.0, description="Tổng chi phí API Cloud phát sinh")
