"""
Database engine — PostgreSQL en Render, SQLite local.
SSL obligatorio (sslmode=require), pool_pre_ping, pool_recycle=300.

ÚNICO engine. ÚNICO SessionLocal. Sin duplicados.
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
        connect_args={"sslmode": "require"},
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=2,
        pool_recycle=300,
    )
    logger.warning("DB CONNECT OK | engine=postgresql | pool_size=5 | sslmode=require")

else:
    logger.warning("DB CONNECT OK | engine=sqlite | local_only")

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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
        pass  # No crítico si falla
