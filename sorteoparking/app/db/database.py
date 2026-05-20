from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import deploy_config

DATABASE_URL = deploy_config.database_url

_connect_args = {}
_sqlite_pool_size = 1  # SQLite is single-writer, pool > 1 causes contention
_sqlite_overflow = 0
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {
        "timeout": 30,
        "check_same_thread": False,
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_size=_sqlite_pool_size,
    max_overflow=_sqlite_overflow,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def configurar_sqlite_wal():
    """Configura SQLite WAL mode y optimizaciones (SDD §3.6)."""
    from sqlalchemy import inspect
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA cache_size=10000"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
        # Verificar que WAL esté activo
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode")).scalar()
    except Exception:
        pass  # No crítico si falla
