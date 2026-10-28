import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

def create_db_engine():
    """
    Khởi tạo engine CSDL:
    1. Thử kết nối PostgreSQL 16 theo cấu hình.
    2. Nếu không kết nối được (ví dụ chưa bật service Postgres), tự động fallback sang SQLite cục bộ
       để bảo đảm môi trường lập trình và kiểm thử offline 100% không bị gián đoạn.
    """
    if not settings.USE_SQLITE_FALLBACK:
        logger.info(f"Đang kết nối PostgreSQL: {settings.POSTGRES_URL}")
        return create_engine(settings.POSTGRES_URL, pool_pre_ping=True)
    
    try:
        # Thử kết nối PostgreSQL với timeout ngắn 2 giây
        pg_engine = create_engine(
            settings.POSTGRES_URL, 
            pool_pre_ping=True, 
            connect_args={"connect_timeout": 2}
        )
        with pg_engine.connect():
            logger.info("Kết nối PostgreSQL 16 thành công!")
            return pg_engine
    except Exception as e:
        logger.warning(
            f"Không thể kết nối PostgreSQL ({e}). "
            f"Tự động kích hoạt SQLite Fallback tại: {settings.SQLITE_URL}"
        )
        return create_engine(
            settings.SQLITE_URL,
            connect_args={"check_same_thread": False}
        )

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI Dependency cung cấp session CSDL"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Khởi tạo toàn bộ bảng CSDL theo schema"""
    import app.db.models  # Import để models đăng ký vào Base
    Base.metadata.create_all(bind=engine)

