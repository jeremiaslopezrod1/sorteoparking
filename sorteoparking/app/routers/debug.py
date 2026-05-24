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
import smtplib
import traceback
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import email_config, super_admin_config
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
def session_test():
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


# ──────────────────────────────────────────────
#  /debug/send-report — informe por correo
# ──────────────────────────────────────────────
@router.post("/send-report")
def send_report():
    """Envía informe completo de diagnóstico por correo."""
    reporte = """Asunto: SorteoParking — Informe de diagnostico PostgreSQL + Sesiones

Hola Michael,

INFORME COMPLETO DE DIAGNOSTICO
===============================

CAMBIOS APLICADOS (2026-05-23):
- session_store.py: usa el MISMO engine que la app (sin duplicar pools)
- main.py: FAIL-FAST real (si DB falla, la app NO arranca)
- database.py: logs DB CONNECT START/OK/FAIL
- debug.py: nuevos endpoints /debug/db-url, /debug/db-connect, /debug/admin-check, /debug/engines

PROBLEMA RAIZ:
El PostgreSQL de Render NO es accesible desde la app.
SSL connection has been closed unexpectedly.

Esto NO es un problema de código.
Es un problema de infraestructura PostgreSQL en Render.

ACCIONES PENDIENTES:
1. Revisar estado de la instancia PostgreSQL en dashboard.render.com
2. Si fue suspendida (free tier 90 días), reactivar o crear nueva
3. Unificar región de app y DB (ambas en Ohio o ambas en Oregon)
4. Si PostgreSQL se reactiva, probar GET /debug/db-connect y /debug/db-ping

--
Jarvis"""

    host = email_config.smtp_host
    port = email_config.smtp_port
    user = email_config.smtp_user
    password = email_config.smtp_password
    from_addr = email_config.smtp_from or user

    if not host or not from_addr:
        return {"ok": False, "error": "SMTP no configurado (faltan host o from)"}

    destino = "pruebaalisocajica@gmail.com"
    asunto = "SorteoParking — Informe diagnostico PostgreSQL + Sesiones"

    msg = MIMEText(reporte, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = from_addr
    msg["To"] = destino

    try:
        with smtplib.SMTP_SSL(host, 465, timeout=30) as smtp:
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [destino], msg.as_string())
        logger.warning("REPORT enviado a %s", destino)
        return {"ok": True, "sent_to": destino}
    except Exception as e:
        logger.error("REPORT send failed: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "smtp_host": host,
            "smtp_port": port,
            "from": from_addr,
        }


# ──────────────────────────────────────────────
#  /debug/reset-admin-password — TEMPORAL
#  Restablece la contraseña del SuperAdmin.
#  ELIMINAR después de usar.
# ──────────────────────────────────────────────
@router.post("/reset-admin-password")
def reset_admin_password():
    """[TEMPORAL] Restablece contraseña del admin Michael a Admin2026!"""
    from argon2 import PasswordHasher

    logger.warning("ADMIN RESET START")

    username = "Michael"
    new_password = "Admin2026!"
    email = "pruebaalisocajica@gmail.com"

    db = None
    try:
        # Mismo PasswordHasher que auth.py (defaults: time_cost=3, memory_cost=65536, parallelism=4)
        ph = PasswordHasher()
        new_hash = ph.hash(new_password)
        logger.warning("ADMIN RESET hash_generado | username=%s", username)

        db = SessionLocal()

        # Guardar en BD (superadmin_credentials — login lo lee de aquí primero)
        SuperAdminCredentials.guardar_o_actualizar(email, new_hash, db)
        logger.warning("ADMIN RESET credenciales_guardadas_en_bd")

        # Invalidar TODAS las sesiones activas
        revoked = db.query(AdminSession).filter(
            AdminSession.revoked_at.is_(None)
        ).update({"revoked_at": datetime.now(timezone.utc)})
        db.commit()
        logger.warning("ADMIN RESET sesiones_invalidadas=%d", revoked)

        logger.warning("ADMIN RESET OK | username=%s | email=%s", username, email)

        return {
            "ok": True,
            "username": username,
            "message": "Contraseña restablecida. Usa Admin2026! para ingresar."
        }

    except Exception as e:
        logger.error("ADMIN RESET FAILED | error=%s", e)
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        if db:
            db.close()
