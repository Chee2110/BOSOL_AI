import os
from pathlib import Path
from dotenv import load_dotenv

# Tìm và nạp file .env từ thư mục gốc
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "BOSOL AI CAD Engine"
    VERSION: str = "2.8.0"
    
    # Thư mục gốc & Dữ liệu
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    EVIDENCE_DIR: Path = BASE_DIR / "evidence_crops"
    PDF_TEST_DIR: Path = BASE_DIR / "PDF_TEST"
    FIXTURES_DIR: Path = BASE_DIR / "fixtures" / "pdf_coords"

    # CSDL: Mặc định PostgreSQL 16; nếu không có kết nối sẽ fallback SQLite cục bộ
    POSTGRES_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/bosol_db"
    )
    SQLITE_URL: str = f"sqlite:///{BASE_DIR / 'bosol_ai_dev.db'}"
    USE_SQLITE_FALLBACK: bool = os.getenv("USE_SQLITE_FALLBACK", "True").lower() in ("true", "1", "yes")

    # Cloud AI Rescue (Google Gemini API)
    # Model ID động: Mặc định model Flash đang active (không fix cứng model cũ)
    GEMINI_MODEL_ID: str = os.getenv("GEMINI_MODEL_ID", "gemini-3.5-flash")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_TIMEOUT_SEC: float = float(os.getenv("GEMINI_TIMEOUT_SEC", "15.0"))
    MAX_DAILY_AI_COST_USD: float = float(os.getenv("MAX_DAILY_AI_COST_USD", "2.0"))

    # Ngưỡng OCR & Circuit Breaker
    OCR_CONFIDENCE_THRESHOLD: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.8"))
    CIRCUIT_BREAKER_FAILURES: int = int(os.getenv("CIRCUIT_BREAKER_FAILURES", "3"))
    CIRCUIT_BREAKER_RECOVERY_SEC: int = int(os.getenv("CIRCUIT_BREAKER_RECOVERY_SEC", "600"))

    # Local LLM (Ollama Text Copilot)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    def ensure_directories(self):
        """Đảm bảo các thư mục vận hành đều tồn tại"""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        self.FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
