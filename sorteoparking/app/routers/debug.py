"""Endpoints de diagnóstico.

/debug/db-url      — muestra DATABASE_URL sanitizada (sin password)
/debug/db-connect  — test de conexión directa psycopg2 (sin SQLAlchemy)
/debug/db-ping     — SELECT 1 vía SQLAlchemy
/debug/admin-check — verifica estado del super admin (sin exponer hash completo)
/debug/session-test— INSERT + COMMIT + SELECT en admin_sessions
"""

import logging
import os
import secrets
import traceback
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.config import super_admin_config
from app.core.security import verify_super_admin
from app.core.session_store import AdminSession
from app.db.database import DATABASE_URL, SessionLocal
from app.models.password_reset import SuperAdminCredentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


# ──────────────────────────────────────────────
#  /debug/db-url — DATABASE_URL sanitizada
# ──────────────────────────────────────────────
@router.get("/db-url")
def debug_db_url():
    """Devuelve la DATABASE_URL sin password."""
    try:
        parsed = urlparse(DATABASE_URL)
        sanitized = urlunparse((
            parsed.scheme,
            f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname or "",
            parsed.path or "",
            "",  # params
            "",  # query
            "",  # fragment
        ))

        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "host_full": parsed.hostname,
            "port": parsed.port,
            "database": parsed.path.lstrip("/") if parsed.path else "",
            "has_password": bool(parsed.password),
            "sanitized_url": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{parsed.path}",
        }
    except Exception as e:
        return {
            "error": str(e),
            "raw_url_prefix": DATABASE_URL[:30] + "..." if len(DATABASE_URL) > 30 else DATABASE_URL,
        }


# ──────────────────────────────────────────────
#  /debug/db-connect — psycopg2 directo, sin SQLAlchemy
# ──────────────────────────────────────────────
@router.get("/db-connect")
def debug_db_connect():
    """Test de conexión directa con psycopg2 (sin SQLAlchemy).

    timeout=10s, sslmode=require.
    Separa problema psycopg2 vs SQLAlchemy.
    """
    result = {
        "ok": False,
        "method": "psycopg2_direct",
        "engine": "none",
    }

    if not DATABASE_URL.startswith("postgresql"):
        result["note"] = "No PostgreSQL — saltando test psycopg2"
        result["ok"] = True
        return result

    try:
        import psycopg2

        logger.warning("DB CONNECT TEST — psycopg2 directo START")
        conn = psycopg2.connect(
            DATABASE_URL,
            connect_timeout=10,
            sslmode="require",
        )
        logger.warning("DB CONNECT TEST — psycopg2 directo OK")

        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()

        result["ok"] = True
        result["details"] = "psycopg2 conectó y ejecutó SELECT 1 correctamente"
    except Exception as e:
        logger.error("DB CONNECT FAIL — psycopg2: %s", e)
        result["ok"] = False
        result["error_type"] = type(e).__name__
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()

    return result


# ──────────────────────────────────────────────
#  /debug/db-ping — SELECT 1 vía SQLAlchemy
# ──────────────────────────────────────────────
@router.get("/db-ping")
def db_ping():
    """SELECT 1 — ¿responde la BD vía SQLAlchemy?"""
    db = None
    try:
        logger.warning("DB PING attempt")
        db = SessionLocal()
        logger.warning("DB PING session created")
        result = db.execute(text("SELECT 1")).fetchone()
        logger.warning("DB PING success | result=%s", result[0] if result else "None")
        return {
            "ok": True,
            "result": result[0] if result else None,
        }
    except Exception as e:
        logger.warning("DB PING FAIL: %s", e)
        return {
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        if db:
            db.close()


# ──────────────────────────────────────────────
#  /debug/admin-check — estado del super admin
# ──────────────────────────────────────────────
@router.get("/admin-check")
def debug_admin_check():
    """Verifica el estado del super admin configurado.

    NO retorna hashes completos ni tokens.
    """
    user = super_admin_config.super_admin_user
    pwd_hash = super_admin_config.super_admin_password_hash
    token = super_admin_config.super_admin_token

    return {
        "admin_exists": bool(user),
        "username": user,
        "password_hash_configured": bool(pwd_hash),
        "password_hash_length": len(pwd_hash) if pwd_hash else 0,
        "password_hash_prefix": (pwd_hash[:20] + "...") if pwd_hash else None,
        "password_hash_algo": pwd_hash.split("$")[1] if pwd_hash and "$" in pwd_hash else "unknown",
        "token_configured": bool(token),
        "token_length": len(token) if token else 0,
        "token_format": "uuid4" if (token and len(token) == 36 and token.count("-") == 4) else "unknown",
    }


# ──────────────────────────────────────────────
#  /debug/engines — detectar engines duplicados
# ──────────────────────────────────────────────
@router.get("/engines")
def debug_engines():
    """Verifica que haya un solo engine activo."""
    from app.db.database import engine as main_engine
    import gc

    engines_found = []
    for obj in gc.get_objects():
        try:
            if hasattr(obj, "url") and hasattr(obj, "connect") and hasattr(obj, "dispose"):
                engines_found.append({
                    "type": type(obj).__name__,
                    "url_scheme": str(obj.url).split("://")[0] if "://" in str(obj.url) else "unknown",
                    "pool_size": getattr(obj.pool, "size", "?") if hasattr(obj, "pool") else "?",
                    "is_main": obj is main_engine,
                })
        except Exception:
            pass

    return {
        "total_engines": len(engines_found),
        "engines": engines_found,
        "single_engine": len(engines_found) <= 1,
    }


# ──────────────────────────────────────────────
#  /debug/session-test — INSERT + COMMIT + SELECT
# ──────────────────────────────────────────────
@router.post("/session-test")
def session_test(_sa=Depends(verify_super_admin)):
    """INSERT + COMMIT + SELECT — ¿persiste el row en la BD?"""
    db = None
    try:
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        token_hash = secrets.token_hex(32)

        db = SessionLocal()

        db.execute(
            text(
                """
                INSERT INTO admin_sessions (
                    session_id, token_hash, csrf_token,
                    created_at, expires_at
                )
                VALUES (
                    :session_id, :token_hash, :csrf_token,
                    :created_at, :expires_at
                )
                """
            ),
            {
                "session_id": session_id,
                "token_hash": token_hash,
                "csrf_token": csrf_token,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            },
        )
        db.commit()

        same_conn = db.execute(
            text("SELECT session_id FROM admin_sessions WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()

        db2 = SessionLocal()
        new_conn = db2.execute(
            text("SELECT session_id FROM admin_sessions WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()
        db2.close()

        return {
            "ok": True,
            "session_id": session_id,
            "persisted_same_connection": same_conn is not None,
            "persisted_new_connection": new_conn is not None,
        }
    except Exception as e:
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return {
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        if db:
            db.close()


