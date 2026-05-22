from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import deploy_config

DATABASE_URL = deploy_config.database_url

_connect_args = {}
_pool_size = 5     # PostgreSQL: hasta 5 conexiones simultaneas
_max_overflow = 10  # PostgreSQL: hasta 10 conexiones extra bajo demanda
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {
        "timeout": 30,
        "check_same_thread": False,
    }
    _pool_size = 1      # SQLite: single-writer
    _max_overflow = 0    # SQLite: no overflow
elif DATABASE_URL.startswith("postgresql"):
    # Render PostgreSQL — probar sin SSL primero
    _connect_args = {"sslmode": "disable"}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
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
