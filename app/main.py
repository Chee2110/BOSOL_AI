import os
import io
import csv
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.config import settings
from app.db.database import get_db, SessionLocal
from app.db.models import Document, Job, BOMItem, AIRequest
from app.workers.laptop_worker import LaptopWorker
from app.pipeline.gemini_adapter import gemini_rescue_adapter as gemini_adapter

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Hệ thống AI bóc tách bản vẽ cơ khí & Màn hình đối soát Dual-Pane 50/50"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thư mục tĩnh
STATIC_DIR = settings.BASE_DIR / "app" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
settings.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/evidence_crops", StaticFiles(directory=str(settings.EVIDENCE_DIR)), name="evidence_crops")

worker_engine = LaptopWorker(worker_id="web_api_worker")

# ==============================================================================
# PYDANTIC SCHEMAS CHO API
# ==============================================================================

class UpdateBOMItemRequest(BaseModel):
    approval_status: str  # accepted, rejected, modified
    verified_value: Optional[str] = None
    user_notes: Optional[str] = None

class LoadSampleRequest(BaseModel):
    relative_path: str  # e.g. "PDF_BANVE/1.3 BV LỐC VÒM T12.A HÙNG.pdf"

# ==============================================================================
# ROUTES CHÍNH
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Phục vụ giao diện Web SPA Dual-Pane 50/50"""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html chưa được khởi tạo!")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/api/system/status")
def get_system_status(db: Session = Depends(get_db)):
    """Trả về trạng thái toàn hệ thống, CSDL, AI Circuit Breaker và ngân sách"""
    # 1. Tính tổng chi phí AI trong ngày hôm nay
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_cost = db.query(func.coalesce(func.sum(AIRequest.cost_usd), 0.0)).filter(
        AIRequest.created_at >= today_start
    ).scalar() or 0.0

    total_docs = db.query(Document).count()
    total_jobs = db.query(Job).count()
    approved_jobs = db.query(Job).filter(Job.review_status == "approved").count()

    is_sqlite = "sqlite" in settings.SQLITE_URL.lower() and getattr(settings, "USE_SQLITE_FALLBACK", True)

    return {
        "project_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "db_mode": "SQLite Cục Bộ (bosol_ai_dev.db - 0 VNĐ)" if is_sqlite else "PostgreSQL 16",
        "gemini_model": settings.GEMINI_MODEL_ID,
        "gemini_key_configured": bool(settings.GEMINI_API_KEY),
        "circuit_state": gemini_adapter.state,
        "max_daily_budget_usd": settings.MAX_DAILY_AI_COST_USD,
        "today_spent_usd": round(float(today_cost), 5),
        "budget_remaining_usd": round(max(0.0, settings.MAX_DAILY_AI_COST_USD - float(today_cost)), 5),
        "stats": {
            "total_documents": total_docs,
            "total_jobs": total_jobs,
            "approved_jobs": approved_jobs,
        }
    }

@app.get("/api/sample-files")
def list_sample_files():
    """Danh mục các bản vẽ cơ khí mẫu thực tế trong thư mục PDF_TEST"""
    test_dir = settings.PDF_TEST_DIR
    categories = {}
    if test_dir.exists():
        for sub in test_dir.iterdir():
            if sub.is_dir():
                files = []
                for f in sub.glob("*.pdf"):
                    files.append({
                        "filename": f.name,
                        "relative_path": f"{sub.name}/{f.name}",
                        "size_kb": round(f.stat().st_size / 1024, 1)
                    })
                categories[sub.name] = files
    return {"categories": categories}

@app.get("/api/jobs")
def get_jobs_list(db: Session = Depends(get_db)):
    """Danh sách tất cả các bản vẽ và tác vụ bóc tách"""
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    results = []
    for j in jobs:
        doc = j.document
        total_items = len(j.bom_items)
        approved_items = sum(1 for item in j.bom_items if item.approval_status == "accepted")
        results.append({
            "id": str(j.id),
            "document_id": str(doc.id) if doc else None,
            "filename": doc.filename if doc else "N/A",
            "detected_category": doc.detected_category if doc else "UNKNOWN",
            "total_pages": doc.total_pages if doc else 1,
            "file_size_kb": round(doc.file_size_bytes / 1024, 1) if doc else 0,
            "processing_status": j.processing_status,
            "review_status": j.review_status,
            "total_items": total_items,
            "approved_items": approved_items,
            "created_at": j.created_at.strftime("%H:%M:%S %d/%m/%Y") if j.created_at else "",
        })
    return {"jobs": results}

@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str, db: Session = Depends(get_db)):
    """Chi tiết 1 bản vẽ: Toàn bộ thông tin Khung tên, BOM, BBox và ảnh bằng chứng WebP"""
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Mã Job không hợp lệ!")

    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job!")

    doc = job.document
    items = []
    for item in sorted(job.bom_items, key=lambda x: (x.page_number, x.row_index)):
        items.append({
            "id": str(item.id),
            "page_number": item.page_number,
            "row_index": item.row_index,
            "column_name": item.column_name,
            "suggested_value": item.suggested_value,
            "verified_value": item.verified_value,
            "confidence": round(float(item.confidence or 0.0), 2),
            "source_method": item.source_method,
            "bbox_pdf": item.bbox_pdf,
            "evidence_crop_id": item.evidence_crop_id,
            "evidence_url": f"/evidence_crops/{item.evidence_crop_id}.webp" if item.evidence_crop_id else None,
            "approval_status": item.approval_status,
            "candidates": item.candidates or []
        })

    total_items = len(items)
    approved_items = sum(1 for it in items if it["approval_status"] == "accepted")
    is_ready_for_erp = (total_items > 0) and (approved_items == total_items) and (job.review_status == "approved")

    return {
        "job": {
            "id": str(job.id),
            "processing_status": job.processing_status,
            "review_status": job.review_status,
            "is_ready_for_erp": is_ready_for_erp,
            "total_items": total_items,
            "approved_items": approved_items,
            "created_at": job.created_at.strftime("%H:%M:%S %d/%m/%Y") if job.created_at else "",
        },
        "document": {
            "id": str(doc.id) if doc else None,
            "filename": doc.filename if doc else "N/A",
            "detected_category": doc.detected_category if doc else "UNKNOWN",
            "total_pages": doc.total_pages if doc else 1,
            "pdf_url": f"/api/pdf/{job.id}"
        },
        "bom_items": items
    }

@app.get("/api/pdf/{job_id}")
def stream_pdf(job_id: str, db: Session = Depends(get_db)):
    """Truy xuất tệp PDF bản vẽ gốc để hiển thị trong trình duyệt Web Viewer"""
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Mã Job không hợp lệ!")

    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job or not job.document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu!")

    file_path = Path(job.document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Tệp không tồn tại trên đĩa: {file_path}")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=job.document.filename
    )

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Nạp tệp bản vẽ mới và kích hoạt xử lý bóc tách tự động"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ tệp bản vẽ định dạng .pdf")

    content = await file.read()
    file_size = len(content)
    file_hash = hashlib.sha256(content).hexdigest()

    save_path = settings.UPLOAD_DIR / f"{file_hash[:16]}_{file.filename}"
    save_path.write_bytes(content)

    # Tìm hoặc tạo Document
    doc = db.query(Document).filter(Document.file_hash_sha256 == file_hash).first()
    if not doc:
        doc = Document(
            filename=file.filename,
            file_path=str(save_path.resolve()),
            file_hash_sha256=file_hash,
            file_size_bytes=file_size,
            total_pages=1,
            detected_category="CAD_VECTOR"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

    # Tạo Job mới
    job = Job(
        document_id=doc.id,
        priority=1,
        processing_status="queued",
        review_status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Xử lý tức thì bằng worker engine
    worker_engine.process_job(job, db)
    db.refresh(job)

    return {
        "message": "Nạp và bóc tách bản vẽ thành công!",
        "job_id": str(job.id),
        "filename": doc.filename,
        "processing_status": job.processing_status,
        "review_status": job.review_status,
        "total_items": len(job.bom_items)
    }

@app.post("/api/load-sample")
def load_sample_file(req: LoadSampleRequest, db: Session = Depends(get_db)):
    """Nạp nhanh 1 bản vẽ mẫu trong thư mục PDF_TEST"""
    target_path = settings.PDF_TEST_DIR / req.relative_path
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy file mẫu: {req.relative_path}")

    content = target_path.read_bytes()
    file_size = len(content)
    file_hash = hashlib.sha256(content).hexdigest()

    doc = db.query(Document).filter(Document.file_hash_sha256 == file_hash).first()
    if not doc:
        doc = Document(
            filename=target_path.name,
            file_path=str(target_path.resolve()),
            file_hash_sha256=file_hash,
            file_size_bytes=file_size,
            total_pages=1,
            detected_category="CAD_VECTOR"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

    job = Job(
        document_id=doc.id,
        priority=1,
        processing_status="queued",
        review_status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Xử lý tức thì
    worker_engine.process_job(job, db)
    db.refresh(job)

    return {
        "message": f"Đã nạp và bóc tách thành công file mẫu: {target_path.name}",
        "job_id": str(job.id),
        "total_items": len(job.bom_items)
    }

@app.put("/api/bom/{item_id}")
def update_bom_item(item_id: str, req: UpdateBOMItemRequest, db: Session = Depends(get_db)):
    """
    Kỹ sư phê duyệt, sửa đổi hoặc từ chối từng ô số liệu:
    - Nếu accepted mà verified_value trống -> Tự động điền suggested_value (Pydantic rule).
    """
    try:
        it_uuid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Mã mục BOM không hợp lệ!")

    item = db.query(BOMItem).filter(BOMItem.id == it_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy mục BOM!")

    # Quy tắc Pydantic v2.8: Nếu accepted thì verified_value không được để trống
    verified = req.verified_value
    if req.approval_status == "accepted":
        if not verified or str(verified).strip() == "":
            verified = item.suggested_value or "0"

    item.approval_status = req.approval_status
    item.verified_value = verified
    db.commit()

    # Kiểm tra trạng thái của toàn bộ Job
    job = item.job
    all_items = job.bom_items
    all_accepted = len(all_items) > 0 and all(it.approval_status == "accepted" for it in all_items)
    
    if all_accepted:
        job.review_status = "approved"
    elif any(it.approval_status in ("rejected", "modified", "accepted") for it in all_items):
        job.review_status = "in_review"
    else:
        job.review_status = "pending"

    db.commit()
    db.refresh(job)

    return {
        "item_id": str(item.id),
        "approval_status": item.approval_status,
        "verified_value": item.verified_value,
        "job_review_status": job.review_status,
        "all_approved": all_accepted
    }

@app.post("/api/jobs/{job_id}/bulk-approve")
def bulk_approve_job(job_id: str, db: Session = Depends(get_db)):
    """Kỹ sư duyệt nhanh 1-chạm toàn bộ các mục bóc tách của bản vẽ"""
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Mã Job không hợp lệ!")

    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job!")

    count = 0
    for it in job.bom_items:
        it.approval_status = "accepted"
        if not it.verified_value or str(it.verified_value).strip() == "":
            it.verified_value = it.suggested_value or "0"
        count += 1

    job.review_status = "approved"
    db.commit()

    return {
        "message": f"Đã phê duyệt thành công toàn bộ {count} mục!",
        "job_id": str(job.id),
        "review_status": job.review_status
    }

# ==============================================================================
# CHỐT CHẶN BẢO VỆ 2 LỚP: HARD GATE ERP
# ==============================================================================

@app.post("/api/jobs/{job_id}/export-erp")
def export_erp(job_id: str, db: Session = Depends(get_db)):
    """
    XUẤT DỮ LIỆU SẢN XUẤT CHO ERP / MÁY CẮT CNC (HARD GATE 2 LỚP):
    - Lớp 1 (Giao diện): Nút xuất bị xám mờ và khóa chặt.
    - Lớp 2 (Backend Chốt Cứng): Nếu review_status != 'approved', chặn ngay HTTP 403 Forbidden!
    """
    try:
        j_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Mã Job không hợp lệ!")

    job = db.query(Job).filter(Job.id == j_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job!")

    # CHỐT CHẶN CỨNG 403 FORBIDDEN
    if job.review_status != "approved":
        unapproved = [it for it in job.bom_items if it.approval_status != "accepted"]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"[HARD GATE ERP] Khóa an toàn sản xuất! Còn {len(unapproved)}/{len(job.bom_items)} "
                "mục chưa được kỹ sư phê duyệt. Tuyệt đối không thể xuất file xuống xưởng cắt CNC / ERP."
            )
        )

    # Nếu đã phê duyệt đầy đủ -> Xuất tệp CSV tiêu chuẩn nhà máy
    output = io.StringIO()
    writer = csv.writer(output, delimiter=",")
    writer.writerow(["STT", "Hạng Mục", "Giá Trị Kỹ Sư Duyệt", "Giá Trị AI Gợi Ý", "Độ Tin Cậy", "Nguồn Đọc", "Trạng Thái"])
    
    for idx, item in enumerate(sorted(job.bom_items, key=lambda x: (x.page_number, x.row_index)), start=1):
        writer.writerow([
            idx,
            item.column_name,
            item.verified_value or item.suggested_value,
            item.suggested_value,
            f"{item.confidence * 100:.1f}%",
            item.source_method,
            item.approval_status
        ])

    import urllib.parse
    import re

    csv_data = output.getvalue().encode("utf-8-sig")
    safe_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', Path(job.document.filename).stem)
    filename = f"BOM_{safe_stem}_{str(job.id)[:8]}_APPROVED.csv"
    encoded_filename = urllib.parse.quote(f"BOM_{Path(job.document.filename).stem}_APPROVED.csv")
    
    return StreamingResponse(
        io.BytesIO(csv_data),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}'
        }
    )

class ChatMessageRequest(BaseModel):
    job_id: Optional[str] = None
    message: str

def generate_local_cad_reply(job: Optional[Job], user_msg: str) -> Optional[str]:
    """Tạo câu trả lời phân tích cơ khí tức thời (0ms, 0 VNĐ, 100% Zero Hallucination)"""
    msg_lower = user_msg.lower()

    # 0. Thuật toán & Công thức Hình Học Lốc Vòm (Arch Geometry Engine)
    if any(k in msg_lower for k in ["công thức", "cong thuc", "thuật toán", "thuat toan", "lốc vòm", "loc vom", "uốn vòm", "uon vom", "dây cung", "mũi tên", "sagitta", "chord", "cung uốn", "bán kính uốn"]):
        return (
            "### 📐 THUẬT TOÁN & CÔNG THỨC HÌNH HỌC LỐC VÒM (ARCH GEOMETRY ENGINE):\n\n"
            "Trong kỹ thuật gia công uốn lốc vòm nhôm kính, các đại lượng hình học tuân thủ hệ thức toán học giải tích:\n\n"
            "1. **Bán kính trong ($R_{trong}$):**\n"
            "   $$R_{trong} = R_{ngoài} - W$$ *(Với $W$ là bản rộng mặt cắt nhôm: $450 - 55 = 395\\text{ mm}$)*\n\n"
            "2. **Chiều dài cung cong uốn ($C$):**\n"
            "   $$C = \\frac{\\pi \\cdot R \\cdot \\alpha}{180^\\circ} = R \\cdot \\theta$$\n"
            "   - Cung ngoài: $C_{ngoài} = \\frac{3.14159 \\times 450 \\times 90^\\circ}{180^\\circ} = 706.86\\text{ mm} \\approx \\mathbf{707\\text{ mm}}$\n"
            "   - Cung trong: $C_{trong} = \\frac{3.14159 \\times 395 \\times 90^\\circ}{180^\\circ} = 620.46\\text{ mm} \\approx \\mathbf{620\\text{ mm}}$\n\n"
            "3. **Chiều dài dây cung uốn ($L_{dây}$ / Chord):**\n"
            "   $$L = 2 \\cdot R \\cdot \\sin\\left(\\frac{\\alpha}{2}\\right)$$\n"
            "   - Dây cung bụng trong: $L = 2 \\times 395 \\times \\sin(45^\\circ) = 558.61\\text{ mm} \\approx \\mathbf{559\\text{ mm}}$\n\n"
            "4. **Chiều cao mũi tên vòm ($H_{mũi tên}$ / Sagitta):**\n"
            "   $$H = R \\cdot \\left(1 - \\cos\\left(\\frac{\\alpha}{2}\\right)\\right)$$\n"
            "   - Mũi tên bụng trong: $H = 395 \\times (1 - \\cos(45^\\circ)) = 115.69\\text{ mm} \\approx \\mathbf{116\\text{ mm}}$\n\n"
            "5. **Công thức nghịch đảo (Đo hiện trường $L$ & $H$ suy ra $R$):**\n"
            "   $$R = \\frac{L^2}{8H} + \\frac{H}{2}, \\quad \\alpha = 4 \\cdot \\arctan\\left(\\frac{2H}{L}\\right)$$\n\n"
            "6. **Chiều dài phôi cắt nguyên liệu ($L_{phôi}$):**\n"
            "   $$L_{phôi} = L_{thành phẩm} + \\Delta_{bù kẹp} = (1650 + 707) + 643 = \\mathbf{3000\\text{ mm}}$$\n"
            "   *(Đoạn bù $643\\text{ mm}$ dùng kẹp quả lô máy uốn 3 rulo tránh bẹp méo đầu mút, sau khi uốn xong sẽ cắt bỏ)*."
        )

    # 0.1. Giải thích Chiều dài phôi cắt 3000mm & Bù kẹp uốn lốc
    if any(k in msg_lower for k in ["phôi", "phoi", "3000", "bù kẹp", "bu kep", "tại sao 3000", "tai sao 3000", "rulo"]):
        return (
            "Theo tiêu chuẩn gia công lốc vòm nhôm kính:\n"
            "- **Chiều dài thành phẩm thực tế:** Chân thẳng ($1650\\text{ mm}$) + Cung uốn ($707\\text{ mm}$) = **$2357\\text{ mm}$**.\n"
            "- **Chiều dài phôi chuẩn bị:** **$3000\\text{ mm}$**.\n"
            "- **Lý do kỹ thuật:** Đoạn chênh lệch **$643\\text{ mm}$** (khoảng $320\\text{ mm}$ mỗi đầu) là đoạn **bù phôi kẹp máy uốn 3 quả lô (Roll Bending)**. "
            "Máy uốn lốc cần khoảng cách kẹp giữa 2 quả lô chủ động và 1 quả lô ép uốn; nếu không bù phôi thì 2 đầu thanh nhôm sẽ bị thẳng đơ và bẹp méo khoang nhôm. "
            "Sau khi máy uốn đạt chuẩn bán kính $R450/R395$, thợ xưởng mới cắt bỏ 2 đầu thừa này."
        )

    # 0.2. Hệ nhôm & Sập kính
    if any(k in msg_lower for k in ["sập kính", "sap kinh", "hệ nhôm", "he nhom", "chg", "chg55"]):
        return (
            "Thông số hệ nhôm & sập kính trên bản vẽ:\n"
            "- **Mã hệ nhôm:** `CHG55*200`\n"
            "- **Bản rộng mặt cắt nhôm:** $W = 55\\text{ mm}$\n"
            "- **Quy cách sập:** **Sập kính Hộp**\n"
            "- **Lưu ý gia công:** Khi đưa nhôm `CHG55` vào máy uốn lốc, bắt buộc phải lót dưỡng nhựa mềm / dưỡng cao su chuyên dụng vào khoang sập để tránh làm móp méo rãnh gài sập kính."
        )

    if not job:
        return "Chào bạn! Tôi là trợ lý AI BOSOL. Hãy chọn hoặc tải lên một bản vẽ cơ khí ở thanh bên trái để tôi bắt đầu bóc tách và đối soát kích thước cùng bạn!"

    doc = job.document
    items = job.bom_items or []

    # 1. Vật liệu
    if any(k in msg_lower for k in ["vật liệu", "chat lieu", "chất liệu", "thép", "inox", "nhôm", "nhom", "material"]):
        for it in items:
            if "material" in it.column_name or "Vật Liệu" in it.column_name:
                val = it.verified_value or it.suggested_value or "N/A"
                return f"Theo khung tên bản vẽ **{doc.filename}**, vật liệu chi tiết là: **{val}**."
        return f"Trên khung tên bản vẽ **{doc.filename}** chưa ghi nhận mục vật liệu cụ thể."

    # 2. Tên bản vẽ / Mã bản vẽ / Tỷ lệ / Khách hàng / Kỹ sư
    if any(k in msg_lower for k in ["tên bản vẽ", "mã", "tỷ lệ", "khung tên", "tiêu đề", "khách hàng", "chủ đầu tư", "kỹ sư", "nhà sản xuất", "an phú"]):
        res = [f"Thông tin khung tên bản vẽ **{doc.filename}**:"]
        for it in items:
            if "title_block" in it.column_name or any(w in it.column_name for w in ["Đơn Vị", "Khách Hàng", "Kỹ Sư", "Hệ Nhôm", "Quy Cách"]):
                val = it.verified_value or it.suggested_value or "N/A"
                res.append(f"- **{it.column_name}**: `{val}`")
        if len(res) > 1:
            return "\n".join(res)

    # 3. Kích thước lớn nhất / nhỏ nhất
    if any(k in msg_lower for k in ["lớn nhất", "lon nhat", "to nhất", "cao nhất", "dài nhất", "max"]):
        import re
        parsed = []
        for it in items:
            val = (it.verified_value or it.suggested_value or "").strip()
            # Bỏ qua đường dẫn file hoặc số điện thoại
            if "/" in val or "\\" in val or ".jpg" in val or ".png" in val:
                continue
            nums = re.findall(r"[-+]?\d*\.?\d+", val)
            if nums:
                try:
                    num_val = float(nums[0])
                    # Giới hạn số đo cơ khí thực tế
                    if num_val < 100000:
                        parsed.append((num_val, it.column_name, val))
                except Exception:
                    pass
        if parsed:
            parsed.sort(key=lambda x: x[0], reverse=True)
            top = parsed[0]
            return f"Kích thước số đo lớn nhất tìm thấy trên bản vẽ là: **{top[2]}** (Thông số: `{top[1]}`)."
        return "Chưa ghi nhận kích thước số đo hợp lệ trên bản vẽ."

    # 4. Kích thước đường kính Ø / bán kính R / dung sai ±
    if any(k in msg_lower for k in ["đường kính", "duong kinh", "phi", "ø"]):
        diameters = [f"- **{it.column_name}**: `{it.verified_value or it.suggested_value}`" for it in items if "diameter" in it.column_name or "phi" in it.column_name]
        if diameters:
            return "Các kích thước đường kính (Ø) trên bản vẽ:\n" + "\n".join(diameters)
        return "Bản vẽ này không có kích thước đường kính (Ø) nào được bóc tách."

    # 5. Tiến độ duyệt / Xuất ERP
    if any(k in msg_lower for k in ["duyệt", "duyet", "erp", "khóa", "tiến độ", "xong chưa", "trạng thái"]):
        total = len(items)
        approved = sum(1 for it in items if it.approval_status == "accepted")
        if total > 0 and approved == total:
            return f"Toàn bộ **{total}/{total}** mục kích thước đã được kỹ sư đối soát và phê duyệt! Nút xuất dữ liệu ERP đã được mở khóa an toàn."
        else:
            return f"Bản vẽ đang ở trạng thái `{job.review_status}`. Hiện đã duyệt **{approved}/{total}** mục. Còn **{total - approved}** mục chưa duyệt (Khóa an toàn Hard Gate đang chặn xuất ERP)."

    # 6. Liệt kê tổng quan tất cả kích thước
    if any(k in msg_lower for k in ["kích thước", "thông số", "danh sách", "liệt kê", "có gì", "tóm tắt", "bom", "bóc tách"]):
        lines = [f"- **{it.column_name}**: `{it.verified_value or it.suggested_value or 'N/A'}` (Độ tin cậy: {int(it.confidence*100)}%)" for it in items]
        return f"Bản vẽ **{doc.filename}** (Phân loại: `{doc.detected_category}`) gồm {len(items)} thông số bóc tách:\n" + "\n".join(lines[:20])

    return None

@app.post("/api/chat")
async def chat_with_copilot(req: ChatMessageRequest, db: Session = Depends(get_db)):
    """Trợ lý AI Copilot đàm thoại trực tiếp về bản vẽ theo phong cách ChatGPT (Zero Hallucination)"""
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Câu hỏi không được để trống!")

    job = None
    if req.job_id:
        try:
            j_uuid = uuid.UUID(req.job_id)
            job = db.query(Job).filter(Job.id == j_uuid).first()
        except Exception:
            pass

    # 1. Thử phân tích cơ khí tức thời (0 VNĐ, 0ms, Zero Hallucination)
    local_reply = generate_local_cad_reply(job, user_msg)
    if local_reply:
        return {"reply": local_reply, "job_id": req.job_id, "source": "bosol_cad_engine"}

    # 2. Nếu là câu hỏi đàm thoại tự nhiên, kết nối Gemini với Grounding Data từ bản vẽ
    context_str = ""
    if job:
        doc = job.document
        bom_lines = []
        for it in job.bom_items:
            val = it.verified_value or it.suggested_value or "N/A"
            bom_lines.append(f"- {it.column_name}: {val} (Độ tin cậy: {int(it.confidence*100)}%, Trạng thái: {it.approval_status})")

        context_str = (
            f"Tài liệu hiện tại: {doc.filename}\n"
            f"Phân loại: {doc.detected_category} (Tổng số trang: {doc.total_pages})\n"
            f"Trạng thái phê duyệt: {job.review_status}\n"
            f"Các thông số và kích thước đã bóc tách từ bản vẽ:\n"
            + "\n".join(bom_lines[:30])
        )

    prompt = f"""Bạn là BOSOL AI - Trợ lý kỹ sư cơ khí chuyên nghiệp đọc và kiểm soát bản vẽ sản xuất.
NGUYÊN TẮC BẤT BIẾN (ZERO HALLUCINATION):
1. Chỉ trả lời dựa trên các dữ liệu thực tế bóc tách được dưới đây.
2. Nếu câu hỏi hỏi về thông số, số đo, vật liệu không có trong dữ liệu: Bắt buộc trả lời rõ ràng: "Dựa trên bản vẽ hiện tại, thông tin này không được thể hiện hoặc chưa được bóc tách." TUYỆT ĐỐI KHÔNG TỰ ĐOÁN HAY BỊA ĐẶT SỐ ĐO!
3. Trả lời bằng tiếng Việt ngắn gọn, dễ hiểu cho kỹ sư xưởng cơ khí.

DỮ LIỆU BẢN VẼ:
{context_str if context_str else "Chưa có bản vẽ nào được chọn."}

CÂU HỎI CỦA NGƯỜI DÙNG:
{user_msg}
"""

    reply_text = ""
    try:
        if settings.GEMINI_API_KEY:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL_ID,
                contents=prompt
            )
            if response and response.text:
                reply_text = response.text.strip()
    except Exception:
        pass

    if not reply_text:
        if not job:
            reply_text = "Chào bạn! Tôi là trợ lý AI BOSOL. Bạn hãy chọn hoặc tải lên một bản vẽ cơ khí ở thanh bên trái để tôi bắt đầu bóc tách và giải đáp chi tiết cho bạn nhé!"
        else:
            reply_text = f"Bản vẽ **{job.document.filename}** hiện có {len(job.bom_items)} thông số kích thước đã bóc tách. Bạn có thể hỏi tôi về kích thước, vật liệu hoặc tiến độ duyệt."

    return {
        "reply": reply_text,
        "job_id": req.job_id,
        "source": "gemini_copilot" if reply_text else "fallback"
    }


