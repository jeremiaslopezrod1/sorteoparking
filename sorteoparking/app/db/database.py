"""
Database engine — PostgreSQL en Render, SQLite local.
Hardened: pool_pre_ping, pool_recycle=180, sslmode=require,
connect_timeout, echo_pool para diagnostico.
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

if DATABASE_URL.startswith("postgresql"):
    logger.warning("DB CONNECT: PostgreSQL detectado — configurando SSL")

    engine = create_engine(
        DATABASE_URL,

        # CRÍTICO — evita conexiones zombie
        pool_pre_ping=True,

        # Reciclar conexiones antes que Render cierre SSL idle
        pool_recycle=180,

        # Pool razonable para produccion
        pool_size=5,
        max_overflow=2,

        # Evitar waits infinitos
        pool_timeout=30,

        # Logging temporal diagnostico
        echo_pool=True,

        connect_args={
            "sslmode": "require",
            "connect_timeout": 10,
            "application_name": "sorteoparking",
        },
    )

    logger.warning("DB CONNECT: engine PostgreSQL creado OK")

else:
    # SQLite solo local
    logger.warning("DB CONNECT: SQLite detectado")

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
