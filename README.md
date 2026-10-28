# BOSOL AI - Hệ Thống Tự Động Hóa Đọc Bản Vẽ Cơ Khí (CAD Engine & Copilot)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-Unified%20Hybrid%20v2.8-orange.svg)]()

> **BOSOL AI** là giải pháp phần mềm tự động hóa bóc tách dữ liệu bản vẽ cơ khí (Khung tên, Kích thước Ø/±/R, Bảng kê vật tư BOM) phục vụ nhà máy sản xuất cơ khí chính xác.

---

## 🌟 Điểm nổi bật (Core Features)

- **Local-First Hybrid:** 100% bản vẽ vector và scan rõ nét chạy ngoại tuyến (offline) trên máy tính văn phòng tại xưởng (chi phí máy chủ **0 VNĐ**).
- **Zero Hallucination:** Tách biệt độc lập giữa trạng thái máy xử lý (`processing_status`) và kỹ sư phê duyệt (`review_status`). Không bao giờ tự bịa đặt số đo.
- **Hard Gate ERP:** Khóa cứng xuất ERP / Máy cắt CNC cho đến khi kỹ sư trực tiếp kiểm tra và phê duyệt.
- **Cloud AI Rescue:** Tầng cứu viện Google Gemini API (`gemini-3.5-flash`) giải cứu các ô số mờ tịt với chi phí cực thấp, khống chế trần ngân sách an toàn `< 2.0 USD/ngày` và Circuit Breaker tự ngắt khi có sự cố.

---

## 📁 Cấu trúc thư mục

```text
BOSOL_AI/
├── .env.example                      # Mẫu biến môi trường
├── requirements.txt                  # Danh mục thư viện Python phụ thuộc
├── run.py                            # Bộ điều khiển CLI Runner (check, test, worker, doc)
├── app/                              # Mã nguồn chính của ứng dụng
│   ├── config.py                     # Quản lý cấu hình toàn cục & .env
│   ├── db/                           # Kết nối CSDL & Models (Dual-Driver: PostgreSQL / SQLite)
│   ├── schemas/                      # Schemas Pydantic v2.8
│   ├── pipeline/                     # Lõi xử lý (Affine Matrix, Router, Text, Gemini, Evidence, Multi-OCR)
│   ├── templates/                    # Giao diện Web HTML (Dashboard & Review Copilot)
│   ├── static/                       # File tĩnh CSS & JS
│   └── workers/                      # Worker Daemon nhận việc & xử lý nền
├── tests/                            # Bộ kiểm thử tự động (Unit & Integration tests)
└── HUONG_DAN_CHAY_DU_AN.md           # Hướng dẫn chi tiết cài đặt và vận hành
```

---

## 🚀 Cài đặt & Khởi chạy nhanh

### 1. Chuẩn bị môi trường
```bash
# Tạo môi trường ảo Python
python -m venv .venv

# Kích hoạt môi trường (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường
Tạo file `.env` từ file mẫu `.env.example`:
```bash
cp .env.example .env
```
Cập nhật `GEMINI_API_KEY` trong `.env` nếu muốn sử dụng tính năng AI Cloud Rescue.

### 3. Kiểm tra hệ thống & Chạy ứng dụng
```bash
# Kiểm tra môi trường & kết nối CSDL
python run.py check

# Chạy toàn bộ bài test
python run.py test

# Khởi chạy ứng dụng Web Server
python run.py web
```

Chi tiết vận hành đầy đủ xem tại [HUONG_DAN_CHAY_DU_AN.md](HUONG_DAN_CHAY_DU_AN.md).
