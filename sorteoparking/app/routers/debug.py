"""
ENDPOINT TEMPORAL DE DIAGNÓSTICO.
Aislar: INSERT + COMMIT + SELECT directo.
No auth, no cookies, no SessionStore, no middleware.
"""

import logging
import secrets
import traceback
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.db.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/db-ping")
def db_ping():
    """SELECT 1 — ¿responde PostgreSQL? Ultra simple, sin auth."""
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
        logger.warning("DB PING failed: %s", e)

        return {
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

    finally:
        if db:
            db.close()


@router.post("/session-test")
def session_test():
    """INSERT + COMMIT + SELECT — ¿persiste el row en PostgreSQL?"""
    db = None

    try:
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        # token_hash es NOT NULL en la tabla real
        token_hash = secrets.token_hex(32)

        db = SessionLocal()

        # STEP 1 — INSERT
        db.execute(
            text(
                """
                INSERT INTO admin_sessions (
                    session_id,
                    token_hash,
                    csrf_token,
                    created_at,
                    expires_at
                )
                VALUES (
                    :session_id,
                    :token_hash,
                    :csrf_token,
                    :created_at,
                    :expires_at
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

        # STEP 2 — COMMIT
        db.commit()

        # STEP 3 — VERIFY SAME CONNECTION
        same_conn = db.execute(
            text(
                """
                SELECT session_id
                FROM admin_sessions
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        ).fetchone()

        # STEP 4 — VERIFY NEW CONNECTION
        db2 = SessionLocal()
        new_conn = db2.execute(
            text(
                """
                SELECT session_id
                FROM admin_sessions
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
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
