"""
Database engine — PostgreSQL en Render, SQLite local.
SSL obligatorio (sslmode=require), pool_pre_ping, pool_recycle=300.

ÚNICO engine. ÚNICO SessionLocal. Sin duplicados.

IMPORTANTE: NO hace conexiones a nivel de módulo.
La validación de conectividad ocurre en main.py startup.
"""

import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sorteoparking.db")

# Render entrega postgres:// en vez de postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

logger.warning("DB CONNECT START | scheme=%s", DATABASE_URL.split("://")[0] if "://" in DATABASE_URL else "unknown")

if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "sslmode": "require",
            "connect_timeout": 10,
        },
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
        pool_timeout=10,
    )
    logger.warning("DB ENGINE CREATED | engine=postgresql | pool_size=3 | sslmode=require")

else:
    logger.warning("DB ENGINE CREATED | engine=sqlite | local_only")

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def verificar_conexion_postgresql() -> bool:
    """TEST de conexión directa — llamado desde startup en main.py.
    
    SÓLO para PostgreSQL. Retorna True si SELECT 1 funciona.
    No se llama a nivel de módulo para evitar crashes en import-time.
    """
    if not DATABASE_URL.startswith("postgresql"):
        return True  # SQLite no necesita test

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.warning("DB CONNECT OK — SELECT 1 exitoso")
        return True
    except Exception:
        logger.exception("DB CONNECT FAILED — PostgreSQL unreachable")
        return False


def configurar_sqlite_wal():
    """Configura SQLite WAL mode y optimizaciones (SDD §3.6)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA cache_size=10000"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode")).scalar()
    except Exception:
        pass
