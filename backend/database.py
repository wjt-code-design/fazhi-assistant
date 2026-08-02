import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 路径锚定到本文件所在目录，避免依赖启动目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")

# check_same_thread=False：允许 FastAPI 线程池跨线程使用连接
# timeout=30：并发写时等待锁释放，缓解 "database is locked"
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建表 + 幂等补列（见 migrations.run_migrations）。"""
    from migrations import run_migrations

    run_migrations()
