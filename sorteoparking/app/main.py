from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.security import get_auth_context, get_super_admin_from_cookie
from app.db.database import Base, SessionLocal, engine, configurar_sqlite_wal, verificar_conexion_postgresql
from app.routers import admin, auth, catalogo as catalogo_router, debug, publico, sorteos
from app.routers.auth import superadmin_reset_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Importa modelos para que SQLAlchemy registre todas las tablas.
from app.models import catalogo, log, password_reset, sorteo, superadmin, tenant  # noqa: F401

import asyncio
import logging
from app.scripts.backup_db import ejecutar_ciclo_backup
from app.core.scheduler import scheduler_diario
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.session_store import init_session_table, session_store

logger = logging.getLogger(__name__)

app = FastAPI(title="SorteoParking")
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sorteoparking.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def tenant_auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.url.path == "/favicon.ico":
        return Response(status_code=204)

    try:
        if request.url.path.startswith("/auth/") or request.url.path.startswith("/admin/") or request.url.path.startswith("/debug/"):
            request.state.tenant_id = None
            response = await call_next(request)
            if response.status_code >= 400:
                response.headers["X-Auth-Path"] = "admin_router"
                response.headers["X-Auth-Status"] = str(response.status_code)
            return response
            
        auth_ctx = get_auth_context(request)
        request.state.tenant_id = auth_ctx.tenant_id
    except Exception as exc:
        status_code = getattr(exc, "status_code", 401)
        detail = getattr(exc, "detail", "No autorizado")
        exc_type = type(exc).__name__
        logger.warning(
            "AUTH_MIDDLEWARE_ERROR | path=%s | exc_type=%s | status=%s | detail=%s",
            request.url.path, exc_type, status_code, str(detail)[:100]
        )
        response = JSONResponse(status_code=status_code, content={"detail": detail})
        response.headers["X-Auth-Path"] = "middleware_catch"
        response.headers["X-Auth-Exc"] = exc_type
        response.headers["X-Auth-Status"] = str(status_code)
        return response

    response = await call_next(request)
    return response


def _backfill_tenant_slugs() -> None:
    """Asigna slug a tenants existentes (SDD §5.4)."""
    from app.core.slug import generar_slug_unico
    from app.models.tenant import Tenant

    db = SessionLocal()
    try:
        for tenant in db.query(Tenant).filter(Tenant.slug.is_(None)).all():
            tenant.slug = generar_slug_unico(tenant.nombre, db)
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
async def startup() -> None:
    # ── FASE 0: Dispose de pool viejo ──────────────────────────────────
    logger.warning("DB CONNECT START — disposing stale pool...")
    engine.dispose()
    logger.warning("DB CONNECT START — pool disposed")

    # ── FASE 0.5: Verificar conectividad PostgreSQL ────────────────────
    if not verificar_conexion_postgresql():
        logger.critical("CRITICAL: PostgreSQL unreachable — abortando startup")
        raise RuntimeError("Database startup failed: PostgreSQL unreachable")

    # ── FASE 1: Creación de tablas principales — FAIL-FAST ─────────────
    try:
        Base.metadata.create_all(bind=engine)
        logger.warning("DB CONNECT OK — Base.metadata.create_all OK")
    except Exception:
        logger.exception("CRITICAL: DB unavailable — Base.metadata.create_all FAILED")
        raise RuntimeError("Database startup failed: PostgreSQL unreachable") from None

    # ── FASE 2: admin_sessions (mismo engine) ─────────────────────────
    admin_sessions_ok = init_session_table(engine)
    if not admin_sessions_ok:
        logger.error("CRITICAL: admin_sessions table creation FAILED")
        raise RuntimeError("Database startup failed: admin_sessions unavailable")

    # ── FASE 3: SessionStore ──────────────────────────────────────────
    try:
        session_store.configure()
        logger.warning("CONFIGURE OK — SessionStore inicializado")
    except Exception:
        logger.exception("CRITICAL: SessionStore configure FAILED")
        raise RuntimeError("Database startup failed: SessionStore unavailable") from None

    # ── FASE 4: Post-inicialización (SQLite WAL, slugs, backups) ──────
    is_sqlite = "sqlite" in str(engine.url)

    if is_sqlite:
        try:
            configurar_sqlite_wal()
        except Exception:
            pass
        try:
            _backfill_tenant_slugs()
        except Exception:
            pass
        try:
            logger.info("Ejecutando backup inicial...")
            ejecutar_ciclo_backup()
        except Exception:
            pass
        try:
            asyncio.create_task(
                scheduler_diario(
                    hora_utc=3,
                    tarea=ejecutar_ciclo_backup,
                    nombre="backup_diario"
                )
            )
        except Exception:
            pass
    else:
        logger.info("PostgreSQL detectado — pool unificado, startup completo")
        try:
            _backfill_tenant_slugs()
        except Exception:
            pass


@app.get("/health")
def health():
    """Health check con verificación real de BD (SDD §3.9).

    Retorna 200 si la BD responde, 503 si no.
    """
    from app.db.database import SessionLocal
    from datetime import datetime, timezone
    from sqlalchemy import text
    from fastapi import Response

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "ok"
    except Exception:
        return Response(
            status_code=503,
            content={"status": "error", "version": "2.1", "db": "unreachable", "timestamp": datetime.now(timezone.utc).isoformat()},
            media_type="application/json",
        )

    return {
        "status": "ok",
        "version": "2.1",
        "db": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


app.include_router(debug.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(catalogo_router.router)
app.include_router(sorteos.router)
app.include_router(publico.router)
app.include_router(superadmin_reset_router)

# ── T-314: Endpoints protegidos para paneles HTML ────────────────────────
# Estos endpoints capturan las rutas /static/*.html antes del StaticFiles mount.
# El StaticFiles sigue sirviendo CSS, JS, imagenes e index.html/publico.html.

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/static/dashboard.html")
async def serve_dashboard(request: Request):
    """Sirve dashboard.html solo si el request tiene Bearer token valido."""
    auth_ctx = get_auth_context(request)
    if not auth_ctx.tenant_id:
        return Response(status_code=401, content="No autorizado")
    return FileResponse(path=_frontend_dir / "dashboard.html")


@app.get("/static/superadmin.html")
async def serve_superadmin(request: Request):
    """Sirve superadmin.html solo si hay cookie admin_session valida."""
    try:
        get_super_admin_from_cookie(request)
        return FileResponse(path=_frontend_dir / "superadmin.html")
    except HTTPException:
        return Response(status_code=401, content="No autorizado")


if _frontend_dir.is_dir():
    # StaticFiles sirve el resto: CSS, JS, imagenes, index.html, publico.html, otp_panel.html
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")
