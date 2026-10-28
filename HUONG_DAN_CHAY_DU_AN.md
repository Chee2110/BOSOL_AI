# HƯỚNG DẪN CÀI ĐẶT & CHẠY DỰ ÁN BOSOL AI
> **Hệ Thống Tự Động Hóa Đọc Bản Vẽ Cơ Khí (CAD Engine & Copilot)**  
> **Phiên bản:** v2.8 (Unified Hybrid Architecture)  
> **Bộ phận:** R&D & Phát Triển Phần Mềm  

---

## 1. TỔNG QUAN HỆ THỐNG

**BOSOL AI** là giải pháp phần mềm tự động hóa bóc tách dữ liệu bản vẽ cơ khí (Khung tên, Kích thước Ø/±/R, Bảng kê vật tư BOM) phục vụ nhà máy sản xuất cơ khí chính xác:
- **Local-First Hybrid:** 100% bản vẽ vector và scan rõ nét chạy ngoại tuyến (offline) trên 01 Laptop văn phòng tại xưởng (chi phí máy chủ **0 VNĐ**).
- **Zero Hallucination:** Tách biệt độc lập giữa trạng thái máy xử lý (`processing_status`) và kỹ sư phê duyệt (`review_status`). Không bao giờ tự bịa đặt số đo.
- **Hard Gate ERP:** Khóa cứng nút "Xuất ERP / Máy cắt CNC" cho đến khi kỹ sư trực tiếp kiểm tra và phê duyệt.
- **Cloud AI Rescue:** Tầng cứu viện Google Gemini API (model `gemini-3.5-flash`) giải cứu các ô số mờ tịt với chi phí cực thấp, khống chế trần ngân sách an toàn `< 2.0 USD/ngày` và bắt buộc có sự đồng ý của kỹ sư.

---

## 2. CẤU TRÚC THƯ MỤC DỰ ÁN

```text
BOSOL_AI/
│
├── .env                              # Tệp cấu hình biến môi trường (API Key, Database, Model ID)
├── requirements.txt                  # Danh mục các thư viện Python phụ thuộc
├── run.py                            # Bộ điều khiển trung tâm (CLI Runner: check, test, worker, doc)
├── bosol_ai_dev.db                   # CSDL SQLite cục bộ (Tự động kích hoạt chế độ Fallback)
│
├── app/                              # MÃ NGUỒN CHÍNH CỦA ỨNG DỤNG
│   ├── config.py                     # Quản lý cấu hình Settings toàn cục & nạp .env
│   ├── db/
│   │   ├── database.py               # Kết nối CSDL (Hỗ trợ Dual-Driver: PostgreSQL & SQLite)
│   │   └── models.py                 # Định nghĩa bảng CSDL (documents, jobs, bom_items, ai_requests)
│   ├── schemas/
│   │   └── extraction.py             # Schema Pydantic v2.8 xác thực dữ liệu từng ô BOM
│   ├── pipeline/
│   │   ├── coordinate_helper.py      # Lõi toán học ma trận Affine 5 bước (Khử lệch Viewport/CropBox)
│   │   ├── document_router.py        # Bộ định tuyến phân loại 4 nhánh tài liệu (CAD, Scan, Text)
│   │   ├── text_extractor.py         # Lõi trích xuất Text-first siêu tốc bằng PyMuPDF (27ms, 0MB VRAM)
│   │   ├── gemini_adapter.py         # Tầng cứu viện Gemini API, Circuit Breaker & Budget Guard
│   │   ├── evidence_store.py         # Cắt ảnh bằng chứng WebP siêu nhẹ (0.4KB) & Versioned Cache
│   │   └── ocr_adapter.py            # Bộ điều phối Multi-OCR 3 tầng (PyMuPDF -> Heuristic -> Gemini)
│   └── workers/
│       └── laptop_worker.py          # Worker Daemon đơn luồng (Lease Token 300s & Zombie Reaper)
│
├── tests/                            # BỘ KIỂM THỬ TỰ ĐỘNG (18 BÀI TEST - PASS 100%)
│   ├── test_database_and_schemas.py  # Kiểm thử CSDL Dual-State và Schema Pydantic
│   ├── test_coordinate_helper.py     # Kiểm thử ma trận Affine 5 góc xoay (Max Error = 0.0000 pt)
│   ├── test_router_real_files.py     # Kiểm thử phân loại 15 tệp bản vẽ thực tế
│   ├── test_evidence_store.py        # Kiểm thử cắt ảnh WebP và khóa Cache SHA-256
│   ├── test_gemini_adapter.py        # Kiểm thử kết nối Gemini, Circuit Breaker & Ngưỡng ngân sách
│   ├── test_gemini_connection.py     # Đo kiểm trực tiếp kết nối Cloud AI
│   ├── test_ocr_adapter.py           # Kiểm thử bộ điều phối OCR đa tầng
│   └── test_laptop_worker.py         # Kiểm thử Worker Daemon nhận việc và dọn dẹp Zombie Job
│
├── PDF_TEST/                         # TẬP DỮ LIỆU BẢN VẼ MẪU THỰC TẾ CỦA NHÀ MÁY
│   ├── PDF_BANVE/                    # Bản vẽ CAD thiết kế vector gốc (8 file)
│   ├── PDF_SCAN_BAN_VE/              # Bản vẽ scan photo cơ khí xưởng (1 file)
│   ├── PDF_SCAN_TEXT/                # Tài liệu scan hành chính (3 file)
│   └── PDF_TEXT/                     # Đơn hàng / Văn bản số (3 file)
│
├── evidence_crops/                   # Thư mục chứa các ảnh WebP bằng chứng cắt theo tọa độ
├── uploads/                          # Thư mục lưu trữ bản vẽ người dùng tải lên
└── PLAN/                             # TÀI LIỆU KẾ HOẠCH & BẢNG KIỂM SOÁT MODULE
    ├── Lo_trinh_chi_tiet_tung_module_kiem_soat.md    # Đặc tả chi tiết 11 module & WBS
    ├── Lo_trinh_chi_tiet_tung_module_kiem_soat.html  # Bản xem trước HTML đầy đủ định dạng
    └── Lo_trinh_chi_tiet_tung_module_kiem_soat.pdf   # Bản in PDF 24 trang chuẩn in ấn A4
```

---

## 3. YÊU CẦU HỆ THỐNG & CÀI ĐẶT

### 3.1. Yêu cầu phần cứng & Môi trường
- **Hệ điều hành:** Windows 10/11, Ubuntu 22.04+, hoặc macOS.
- **Python:** Phiên bản **Python 3.10 trở lên** (Khuyên dùng Python 3.11 hoặc 3.12).
- **Bộ nhớ RAM:** Tối thiểu 8 GB RAM (Không bắt buộc card đồ họa rời GPU).
- **Dung lượng ổ cứng:** Trống tối thiểu 2 GB.

### 3.2. Cài đặt từng bước

#### Bước 1: Mở Terminal / PowerShell tại thư mục dự án
```powershell
cd c:\Users\Admin\Desktop\BOSOL_AI
```

#### Bước 2: Tạo môi trường ảo (Khuyên dùng)
```powershell
python -m venv venv
# Kích hoạt trên Windows:
.\venv\Scripts\activate
# Hoặc trên Linux/macOS:
source venv/bin/activate
```

#### Bước 3: Cài đặt toàn bộ thư viện cần thiết
```powershell
pip install -r requirements.txt
```

---

## 4. CẤU HÌNH BIẾN MÔI TRƯỜNG (`.env`)

Tệp `.env` đặt tại thư mục gốc của dự án. Hệ thống đã thiết lập sẵn cấu hình mặc định an toàn:

```ini
# CẤU HÌNH DỰ ÁN BOSOL AI v2.8
PROJECT_NAME="BOSOL AI CAD Engine"

# CƠ SỞ DỮ LIỆU
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bosol_db
USE_SQLITE_FALLBACK=True

# TẦNG CỨU VIỆN GEMINI API (MODEL ID ĐỘNG)
GEMINI_MODEL_ID=gemini-3.5-flash
GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
GEMINI_TIMEOUT_SEC=15.0
MAX_DAILY_AI_COST_USD=2.0

# THUẬT TOÁN ĐỊNH TUYẾN AI ROUTER & CIRCUIT BREAKER
OCR_CONFIDENCE_THRESHOLD=0.8
CIRCUIT_BREAKER_FAILURES=3
CIRCUIT_BREAKER_RECOVERY_SEC=600

# OLLAMA LOCAL TEXT (KẾ HOẠCH SPRINT 3/4)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

### Giải thích các tham số cốt lõi:
| Biến môi trường | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| `USE_SQLITE_FALLBACK` | Khi chưa có PostgreSQL, tự động kích hoạt CSDL SQLite cục bộ `bosol_ai_dev.db` giúp chạy ngay lập tức không cần cài CSDL ngoài. | `True` |
| `GEMINI_MODEL_ID` | Phiên bản model Google GenAI sử dụng (`gemini-3.5-flash` thế hệ mới tối ưu độ chính xác & tốc độ). | `gemini-3.5-flash` |
| `GEMINI_API_KEY` | Khóa API Key kích hoạt dịch vụ Google Gemini Cloud Rescue. | Đã cấu hình |
| `MAX_DAILY_AI_COST_USD` | Trần chi phí an toàn hàng ngày. Khi chạm mức này, hệ thống tự động khóa gọi Cloud để tránh phát sinh chi phí ngoài ý muốn. | `2.0` (USD) |
| `CIRCUIT_BREAKER_FAILURES` | Số lần lỗi mạng liên tiếp trước khi ngắt mạch (chống treo ứng dụng khi mạng xưởng lag). | `3` (lần) |

---

## 5. HƯỚNG DẪN KHỞI CHẠY NHANH QUA `run.py`

Dự án cung cấp tệp điều khiển trung tâm [run.py](file:///c:/Users/Admin/Desktop/BOSOL_AI/run.py) để người dùng thực thi mọi tác vụ nhanh chóng:

### 5.1. Khởi động Giao diện Web ChatGPT Sáng Sủa & AI Copilot Bản Vẽ
Khởi chạy máy chủ giao diện Web trực quan phong cách ChatGPT:
```powershell
python run.py web
```
- **Hệ thống làm gì:** Khởi động máy chủ Web FastAPI tại `http://127.0.0.1:8000` và tự động mở trình duyệt mặc định.
- **Thiết kế & Trải nghiệm ChatGPT:**
  - **Giao diện sáng sủa, thanh lịch:** Tông màu trắng xám cao cấp (`#f9fafb`), viền mảnh tinh tế, điểm nhấn xanh ngọc lục bảo OpenAI (`#10a37f`) và xanh kỹ thuật (`#0284c7`), chống mỏi mắt khi kỹ sư làm việc lâu trong xưởng.
  - **Sidebar bên trái thu gọn linh hoạt:** Danh sách 15 bản vẽ mẫu cơ khí, lịch sử bóc tách gần đây và giám sát ngân sách thời gian thực (Budget Guard $0.00 / $2.00).
  - **Màn hình chào mừng phong cách ChatGPT:** 4 thẻ gợi ý truy cập nhanh kèm khu vực kéo-thả tải lên bản vẽ PDF trực quan.
  - **Màn hình đối soát song song (Dual-Pane 50/50):** 
    - Nửa trái: Luồng đàm thoại, Thẻ Khung tên (Title block), Bảng bóc tách kích thước BOM kèm ảnh WebP bằng chứng cận cảnh, và Khung nhập liệu Chat AI Copilot ở đáy.
    - Nửa phải: Trình đọc bản vẽ PDF tương tác thời gian thực với các khung nhận diện BBox có viền phát sáng tương tác 2 chiều (bấm bảng -> cuộn bản vẽ; bấm bản vẽ -> định vị dòng bảng).
  - **Trợ lý AI Copilot đàm thoại trực tiếp (Zero Hallucination):** Cho phép đặt câu hỏi bằng tiếng Việt tự nhiên (*"Vật liệu của chi tiết này là gì?", "Kích thước nào lớn nhất?", "Tiến độ duyệt ra sao?"*). Trợ lý chỉ trả lời dựa trên thông số thực tế của bản vẽ, tuyệt đối không bịa đặt số đo.
  - **Khóa an toàn 2 lớp (Hard Gate ERP):** Nút *"🔒 Khóa Xuất ERP"* khóa cứng cho đến khi kỹ sư trực tiếp duyệt hết các mục.
  - **Duyệt nhanh 1-chạm:** Nút `[✓ Duyệt Nhanh 1-Chạm]` giúp kỹ sư xác nhận nhanh toàn bộ bản vẽ chuẩn chỉ với 1 click.
- **Cách dừng:** Nhấn **`Ctrl + C`** trong cửa sổ Terminal để tắt Web Server.

### 5.2. Kiểm tra môi trường & Kết nối hệ thống
Kiểm tra phiên bản Python, tệp `.env`, API Key, các thư mục và trạng thái CSDL:
```powershell
python run.py check
```

### 5.3. Chạy toàn bộ 18 bài kiểm thử tự động (Test Suite)
Chạy toàn bộ bài test đo kiểm thực tế các module lõi:
```powershell
python run.py test
```
*Kết quả chuẩn:* `Ran 18 tests in ~5.4s -> OK` (Tỷ lệ pass 100%).

### 5.4. Khởi động Laptop Worker Daemon xử lý hàng đợi bản vẽ
Khởi chạy tiến trình nền tiếp nhận bản vẽ và trích xuất tự động:
```powershell
python run.py worker
```
*Ghi chú:* Nhấn `Ctrl + C` để dừng Worker an toàn bất kỳ lúc nào.

### 5.5. Biên dịch tài liệu Lộ trình dự án (HTML & PDF in ấn A4)
Tự động đồng bộ nội dung Markdown và xuất bản tệp HTML xem trước cùng tệp PDF:
```powershell
python run.py doc
```

---

## 6. HƯỚNG DẪN CHẠY KIỂM THỬ ĐỘC LẬP TỪNG MODULE

Nếu bạn muốn chạy thử nghiệm và kiểm tra chi tiết từng thành phần kỹ thuật riêng lẻ:

| Module cần kiểm tra | Lệnh thực thi | Mục tiêu đo kiểm |
| :--- | :--- | :--- |
| **Phân loại 15 file thực tế** | `python -m unittest tests/test_router_real_files.py` | Kiểm tra độ chính xác phân luồng 4 nhánh (CAD_VECTOR, CAD_SCAN, SCAN_TEXT, TEXT_PDF). |
| **Toán học Affine 5 bước** | `python -m unittest tests/test_coordinate_helper.py` | Kiểm tra khử xoay $0^\circ, 90^\circ, 180^\circ, 270^\circ$ và sai số điểm ảnh ($0.0000\text{ pt}$). |
| **CSDL Dual-State & Schema** | `python -m unittest tests/test_database_and_schemas.py` | Kiểm tra tạo bảng CSDL, khóa trạng thái kép và Pydantic validator BOM. |
| **Cắt ảnh WebP & Cache** | `python -m unittest tests/test_evidence_store.py` | Đo kiểm dung lượng ảnh WebP ($0.40\text{ KB/crop}$) và khóa SHA-256 Cache ($0\text{ms}$). |
| **Tầng cứu viện Gemini API** | `python -m unittest tests/test_gemini_adapter.py` | Kiểm tra gọi AI Cloud, cơ chế Circuit Breaker 3 trạng thái và trần ngân sách Budget Guard. |
| **Kết nối thực tế Gemini** | `python tests/test_gemini_connection.py` | Gửi prompt trực tiếp lên Google Gemini và đo thời gian phản hồi thực tế. |
| **OCR Đa tầng Multi-Engine** | `python -m unittest tests/test_ocr_adapter.py` | Kiểm tra luồng Text-first ($0\text{ VNĐ}$) và Fallback cứu viện an toàn. |
| **Laptop Worker Queue** | `python -m unittest tests/test_laptop_worker.py` | Kiểm tra cơ chế nhận việc nguyên tử (Lease 300s) và hồi sinh Zombie Job. |

---

## 7. QUY TRÌNH XỬ LÝ MỘT BẢN VẼ MỚI (WORKFLOW THỰC TẾ)

```mermaid
flowchart TD
    A["Bản vẽ CAD mới (.pdf)"] --> B["Router 4 nhánh (document_router.py)"]
    B -->|"Vector rõ nét (0.027s)"| C["PyMuPDF Text-first (text_extractor.py)"]
    B -->|"Scan photo cũ mờ"| D["Multi-OCR Adapter (ocr_adapter.py)"]
    
    C --> E["Bóc tách Khung tên, Kích thước Ø/±/R & BOM"]
    D --> E
    
    E -->|"Ô mờ nhòe / Độ tin cậy thấp"| F["Cắt ảnh WebP 0.4KB (evidence_store.py)"]
    F -->|"Kỹ sư đồng ý (Consent=True)"| G["Cứu viện Gemini 3.5 Flash"]
    G --> H["Lưu kết quả + Bằng chứng vào CSDL"]
    E -->|"Số đo rõ ràng"| H
    
    H --> I["Trạng thái: processing_status = 'completed'<br/>review_status = 'pending'"]
    I --> J["Kỹ sư đối soát trên màn hình Dual-Pane"]
    J -->|"Kỹ sư bấm Phê Duyệt"| K["Mở khóa Nút Xuất ERP / Máy CNC"]
```

1. **Nạp bản vẽ:** Tệp PDF được đưa vào thư mục `uploads/` hoặc tạo bản ghi `documents` trong CSDL.
2. **Tiếp nhận tác vụ:** Tiến trình `laptop_worker.py` tự động cấp phát `lease_token` (thời hạn 300 giây) để xử lý bản vẽ theo thứ tự ưu tiên.
3. **Trích xuất thông tin:** Lõi PyMuPDF đọc khung tên và kích thước trong ~27ms không tốn GPU. Nếu gặp bản vẽ scan cũ hoặc chữ mờ, hệ thống chuyển sang Multi-OCR hoặc xin ý kiến kỹ sư gọi Gemini API.
4. **Bảo vệ bằng chứng:** Mỗi số đo trích xuất đều được gắn kèm tọa độ khung chữ nhật (Bounding Box) và ảnh cắt WebP siêu nhẹ ($0.40\text{ KB}$) lưu trong `evidence_crops/`.
5. **Chốt chặn an toàn:** Trạng thái phê duyệt được giữ nguyên ở mức `pending`. Kỹ sư xưởng phải kiểm tra và xác nhận thì mới được phép xuất dữ liệu xuống máy cắt CNC hoặc phần mềm ERP.

---

## 8. BẢNG XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

| Hiện tượng / Thông báo lỗi | Nguyên nhân | Cách xử lý nhanh |
| :--- | :--- | :--- |
| `No module named 'psycopg'` | Chưa cài driver PostgreSQL hoặc PostgreSQL chưa chạy. | Không cần lo lắng. Hệ thống **tự động kích hoạt SQLite Fallback** tại `bosol_ai_dev.db` để chạy offline 100% trơn tru. |
| `Circuit Breaker: OPEN` | Mạng internet xưởng bị gián đoạn 3 lần liên tiếp khi gọi Cloud. | Hệ thống tự động ngắt kết nối trong 600 giây để tránh treo ứng dụng. Khi mạng ổn định, mạch sẽ tự đóng lại (`CLOSED`). |
| `BudgetGuard: Đã chạm trần ngân sách` | Chi phí gọi Gemini trong ngày vượt mức `$2.00` USD (~50.000 VNĐ). | Tính năng bảo vệ van chi phí an toàn hoạt động. Bạn có thể tăng nhẹ ngưỡng trong `.env` (`MAX_DAILY_AI_COST_USD=3.0`) nếu cần xử lý lô hàng gấp. |
| `ValueError: verified_value cannot be empty` | Cố tình chấp nhận ô dữ liệu BOM mà trường giá trị bị để trống. | Đây là tính năng chống sót lỗi của Pydantic Schema v2.8. Cần nhập số đo hợp lệ hoặc để hệ thống tự động gán giá trị gợi ý (`suggested_value`). |
| Không xuất được file PDF từ lệnh tự động | Trình duyệt Edge chưa mở cổng in headless hoặc quyền hạn thư mục. | Mở tệp `PLAN/Lo_trinh_chi_tiet_tung_module_kiem_soat.html` trên bất kỳ trình duyệt nào (Chrome, Edge) và nhấn phím **Ctrl + P**, chọn *Save as PDF*. |

---

## 9. ĐẦU MỐI HỖ TRỢ KỸ THUẬT

- **Tài liệu tham chiếu kiến trúc:** [Tong_hop_du_an_AI_doc_ban_ve.md](file:///c:/Users/Admin/Desktop/BOSOL_AI/PLAN/Tong_hop_du_an_AI_doc_ban_ve.md)
- **Lộ trình và kiểm soát từng module:** [Lo_trinh_chi_tiet_tung_module_kiem_soat.md](file:///c:/Users/Admin/Desktop/BOSOL_AI/PLAN/Lo_trinh_chi_tiet_tung_module_kiem_soat.md)
- **Báo cáo in ấn hoàn chỉnh:** [Lo_trinh_chi_tiet_tung_module_kiem_soat.pdf](file:///c:/Users/Admin/Desktop/BOSOL_AI/PLAN/Lo_trinh_chi_tiet_tung_module_kiem_soat.pdf)
