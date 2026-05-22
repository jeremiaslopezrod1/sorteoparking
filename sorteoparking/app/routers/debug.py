"""
ENDPOINT TEMPORAL DE DIAGNÓSTICO.
Aislar: INSERT + COMMIT + SELECT directo.
No auth, no cookies, no SessionStore, no middleware.
"""

import logging
import secrets
import smtplib
import traceback
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import email_config
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


@router.post("/send-report")
def send_report():
    """Envia informe completo de diagnostico por correo."""
    reporte = """Asunto: SorteoParking — Informe de diagnostico PostgreSQL + Sesiones

Hola Michael,

INFORME COMPLETO DE DIAGNOSTICO
===============================

FECHA: 2026-05-22
APP: sorteoparking.onrender.com
PLAN: Render Free (Ohio)
POSTGRESQL: dpg-d86ksduk1jcs739cpaqg-a.oregon-postgres.render.com (Oregon)

==================================================
1. PROBLEMA ORIGINAL
==================================================

Error reportado:
  [A2] Sesion no encontrada en BD (expiro o no se creo).
  Vuelva a iniciar sesion.

El flujo de auth fallaba al intentar recuperar sesiones
del admin desde PostgreSQL.

==================================================
2. HIPOTESIS PROBADAS
==================================================

H1: La tabla admin_sessions NO persiste rows
  -> FALSO. El problema es anterior: la conexion misma falla.

H2: Configuracion SSL (sslmode)
  -> require/disable/prefer — todos fallan igual.

H3: Pool de conexiones zombie (pool_recycle, pool_pre_ping)
  -> No resuelve. El error es pre-pool, en handshake TCP/SSL.

H4: engine.dispose() al inicio
  -> No ayuda. Conexiones fresh tambien fallan.

H5: Version de Python (3.14 causa incompatibilidad TLS)
  -> Bajamos de 3.14 a 3.11.11 (via PYTHON_VERSION + .python-version).
  -> python3.11 confirmado en tracebacks.
  -> Mismo error: SSL connection has been closed unexpectedly.

==================================================
3. EVIDENCIA EXPERIMENTAL
==================================================

Endpoints creados:

GET /debug/db-ping
  SELECT 1 directo contra PostgreSQL.
  Resultado: OperationalError — SSL connection closed unexpectedly.
  Python 3.14: FAIL
  Python 3.11: FAIL (mismo error)

POST /debug/session-test
  INSERT + COMMIT + SELECT en admin_sessions via PostgreSQL.
  Resultado: OperationalError — la app nunca llega al INSERT.
  La conexion muere en el handshake SSL antes de ejecutar queries.

GET /auth/session-check
  Usa session_store (SQLite en /tmp/) para verificar sesiones.
  Resultado: OK — responde correctamente sin errores.

==================================================
4. CAUSA RAIZ
==================================================

El PostgreSQL de Render NO es accesible desde la app.

Host: dpg-d86ksduk1jcs739cpaqg-a.oregon-postgres.render.com
Puerto: 5432
Region: Oregon (app en Ohio)

Posible causa: la instancia PostgreSQL fue suspendida
(limite de 90 dias en free tier de Render) o presenta
un problema de red/TLS entre regiones.

NO es un problema de codigo.
NO es un problema de configuracion.
ES un problema de infraestructura PostgreSQL en Render.

==================================================
5. SOLUCION IMPLEMENTADA
==================================================

SessionStore AHORA USA SQLite propio en /tmp/admin_sessions.db

Cambios:
  - session_store.py: engine SQLite independiente
  - main.py: session_store.configure() sin depender de PostgreSQL
  - Las sesiones de admin persisten en SQLite local (writable en Render)

Estado: FUNCIONANDO.
  - Login crea sesion en SQLite -> OK
  - Auth recupera sesion de SQLite -> OK
  - CSRF validado contra SQLite -> OK

NO se toco: frontend, cookies, CSRF, middleware auth, rutas.

==================================================
6. ACCIONES PENDIENTES
==================================================

URGENTE:
  1. Revisar estado de la instancia PostgreSQL en Render dashboard.
     Si fue suspendida, reactivarla o crear una nueva.
  2. Si PostgreSQL se reactiva, probar GET /debug/db-ping.
  3. Si db-ping da OK, considerar migrar sesiones de vuelta
     a PostgreSQL para persistencia entre deploys.

OPCIONAL:
  4. Agregar Render Disk para persistencia del SQLite de sesiones.
  5. Unificar region de app y DB (ambas en Ohio o ambas en Oregon).

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
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.sendmail(from_addr, [destino], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                if port == 587:
                    smtp.starttls()
                    smtp.ehlo()
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
