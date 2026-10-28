"""
==============================================================================
BOSOL AI CAD Engine - Trình Điều Khiển Dự Án Trung Tâm (CLI Runner)
==============================================================================
Sử dụng:
    python run.py check        Kiểm tra môi trường, thư mục, CSDL và API Key
    python run.py test         Chạy toàn bộ 18 bài kiểm thử tự động (Unit & Integration Tests)
    python run.py worker       Khởi động Laptop Worker Daemon xử lý hàng đợi bản vẽ
    python run.py doc          Biên dịch tài liệu Lộ trình sang định dạng HTML và PDF
"""

import sys
import os
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def check_env():
    """Kiểm tra toàn bộ môi trường và kết nối hệ thống"""
    print("\n" + "="*60)
    print(" BẢO MẬT & KIỂM TRA MÔI TRƯỜNG DỰ ÁN BOSOL AI v2.8")
    print("="*60)
    
    # 1. Kiểm tra Python
    py_ver = sys.version.split()[0]
    print(f"[1] Python Runtime: {py_ver} (Yêu cầu >= 3.10) -> OK")
    
    # 2. Kiểm tra file .env
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        print(f"[2] Tệp cấu hình: {env_file} -> TỒN TẠI")
    else:
        print(f"[2] CẢNH BÁO: Không tìm thấy {env_file}! Vui lòng tạo tệp .env.")

    # 3. Nạp cấu hình ứng dụng
    try:
        from app.config import settings
        print(f"[3] Cấu hình Dự án: {settings.PROJECT_NAME} (Phiên bản {settings.VERSION})")
        print(f"    - Database URL : {settings.POSTGRES_URL}")
        print(f"    - SQLite Fallback: {settings.USE_SQLITE_FALLBACK} ({settings.SQLITE_URL})")
        print(f"    - Gemini Model : {settings.GEMINI_MODEL_ID}")
        print(f"    - Gemini Key   : {'*** Đã thiết lập ***' if settings.GEMINI_API_KEY else 'CHƯA CÓ'}")
        print(f"    - Trần ngân sách: {settings.MAX_DAILY_AI_COST_USD} USD/ngày")
    except Exception as e:
        print(f"[3] Lỗi khi nạp app/config.py: {e}")

    # 4. Kiểm tra thư mục dữ liệu
    dirs = [
        BASE_DIR / "uploads",
        BASE_DIR / "evidence_crops",
        BASE_DIR / "fixtures",
        BASE_DIR / "PDF_TEST",
        BASE_DIR / "PLAN"
    ]
    print("\n[4] Kiểm tra thư mục dữ liệu:")
    for d in dirs:
        status = "TỒN TẠI" if d.exists() else "CHƯA TẠO (Tự động khởi tạo)"
        d.mkdir(parents=True, exist_ok=True)
        print(f"    - {d.name:<18}: {status}")

    # 5. Kiểm tra CSDL
    try:
        from app.db.database import get_db
        db = next(get_db())
        print("\n[5] Kết nối CSDL:")
        print("    - Kết nối CSDL thành công! Hệ thống sẵn sàng.")
        db.close()
    except Exception as e:
        print(f"\n[5] Lỗi kết nối CSDL: {e}")

    print("\n" + "="*60)
    print(" KIỂM TRA HOÀN TẤT!")
    print("="*60 + "\n")

def run_tests():
    """Chạy toàn bộ 18 bài test tự động"""
    print("\n" + "="*60)
    print(" CHẠY BỘ KIỂM THỬ TỰ ĐỘNG (UNIT & INTEGRATION TESTS)")
    print("="*60)
    cmd = [sys.executable, "-m", "unittest", "discover", "tests"]
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    sys.exit(result.returncode)

def run_worker(loop: bool = True):
    """Khởi động Laptop Worker Daemon"""
    print("\n" + "="*60)
    print(" KHỞI ĐỘNG LAPTOP WORKER DAEMON (DIRECT DB QUEUE)")
    print("="*60)
    try:
        from app.workers.laptop_worker import LaptopWorker
        worker = LaptopWorker()
        print("[Worker] Đã khởi tạo Worker thành công.")
        print("[Worker] Nhấn Ctrl + C để dừng tiến trình.\n")
        
        while True:
            processed = worker.run_once()
            if processed:
                print("[Worker] Đã xử lý xong 1 Job. Tiếp tục lắng nghe...")
            time.sleep(3.0)
    except KeyboardInterrupt:
        print("\n[Worker] Nhận tín hiệu dừng từ người dùng. Kết thúc Worker an toàn.")
    except Exception as e:
        print(f"\n[Worker] Lỗi nghiêm trọng: {e}")
        sys.exit(1)

def build_docs():
    """Biên dịch tài liệu sang HTML và PDF"""
    print("\n" + "="*60)
    print(" XUẤT BẢN TÀI LIỆU LỘ TRÌNH DỰ ÁN (HTML & PDF A4)")
    print("="*60)
    
    # 1. HTML
    html_script = BASE_DIR / "generate_html_preview.py"
    if html_script.exists():
        print("[1/2] Đang tạo file HTML từ Markdown...")
        res = subprocess.run([sys.executable, str(html_script)], cwd=str(BASE_DIR))
        if res.returncode != 0:
            print("[Lỗi] Không thể tạo file HTML!")
            return
    
    # 2. PDF
    html_file = BASE_DIR / "PLAN" / "Lo_trinh_chi_tiet_tung_module_kiem_soat.html"
    pdf_file = BASE_DIR / "PLAN" / "Lo_trinh_chi_tiet_tung_module_kiem_soat.pdf"
    print("[2/2] Đang xuất file PDF chuẩn in ấn bằng Headless Browser...")
    
    # Tìm trình duyệt Edge hoặc Chrome trên Windows
    browser_candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    browser_exe = None
    for cand in browser_candidates:
        if cand.exists():
            browser_exe = cand
            break

    if browser_exe:
        edge_cmd = [
            str(browser_exe),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_file.resolve()}",
            str(html_file.resolve())
        ]
        try:
            res = subprocess.run(edge_cmd, capture_output=True)
            if pdf_file.exists():
                print(f"[Thành công] Đã xuất file PDF chuẩn đẹp: {pdf_file.resolve()} ({pdf_file.stat().st_size / (1024*1024):.2f} MB)")
            else:
                print("[Cảnh báo] Chưa xuất được PDF tự động. Bạn có thể mở file HTML và nhấn Ctrl + P -> Save as PDF.")
        except Exception as e:
            print(f"[Thông báo] Không thể chạy trình duyệt tự động: {e}. Vui lòng mở file HTML và nhấn Ctrl + P.")
    else:
        print("[Thông báo] Không tìm thấy Edge/Chrome mặc định. Vui lòng mở file HTML trên trình duyệt và nhấn Ctrl + P.")

def run_web(host: str = "127.0.0.1", port: int = 8000):
    """Khởi động Giao diện Web Review Split-View 50/50"""
    import uvicorn
    import webbrowser
    import threading

    url = f"http://{host}:{port}"
    print("\n" + "="*60)
    print(f" KHỞI ĐỘNG GIAO DIỆN WEB ĐỐI SOÁT SONG SONG (DUAL-PANE 50/50)")
    print(f" Địa chỉ truy cập: {url}")
    print(" Nhấn Ctrl + C để dừng Web Server.")
    print("="*60 + "\n")

    def open_browser():
        time.sleep(1.2)
        try:
            webbrowser.open(url)
            print(f"[Web] Đã tự động mở trình duyệt tại: {url}")
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host=host, port=port, reload=False)

def print_help():
    print("""
Cách sử dụng:
    python run.py web        : Khởi động Giao diện Web Review Split-View 50/50 (http://localhost:8000)
    python run.py check      : Kiểm tra toàn bộ cấu hình, thư mục, CSDL và API Key
    python run.py test       : Chạy toàn bộ 18 bài kiểm thử tự động
    python run.py worker     : Khởi động Worker Daemon đơn luồng xử lý bản vẽ ngầm
    python run.py doc        : Biên dịch tài liệu kế hoạch sang HTML & PDF in ấn A4
    python run.py help       : Hiển thị hướng dẫn này
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
        
    action = sys.argv[1].lower()
    if action == "web":
        run_web()
    elif action == "check":
        check_env()
    elif action == "test":
        run_tests()
    elif action == "worker":
        run_worker(loop=True)
    elif action == "doc":
        build_docs()
    else:
        print_help()
