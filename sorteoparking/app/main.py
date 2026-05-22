from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.security import get_auth_context
from app.db.database import Base, SessionLocal, engine, configurar_sqlite_wal
from app.routers import admin, auth, catalogo as catalogo_router, debug, publico, sorteos
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Importa modelos para que SQLAlchemy registre todas las tablas.
from app.models import catalogo, log, sorteo, superadmin, tenant  # noqa: F401

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


@app.middleware("http")
async def tenant_auth_middleware(request: Request, call_next):
    try:
        # Excluir rutas de autenticación y administración global del middleware de tenant
        if request.url.path.startswith("/auth/") or request.url.path.startswith("/admin/") or request.url.path.startswith("/debug/"):
            request.state.tenant_id = None
            response = await call_next(request)
            # Inyectar header de diagnostico en respuestas de error de admin
            if response.status_code >= 400:
                response.headers["X-Auth-Path"] = "admin_router"
                response.headers["X-Auth-Status"] = str(response.status_code)
            return response
            
        auth_ctx = get_auth_context(request)
        request.state.tenant_id = auth_ctx.tenant_id
    except Exception as exc:  # HTTPException incluida
        status_code = getattr(exc, "status_code", 401)
        detail = getattr(exc, "detail", "No autorizado")
        exc_type = type(exc).__name__
        # Loggear para diagnostico en servidor
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
    # FASE 1: Creacion de tablas (Base + admin_sessions)
    tables_ok = True
    try:
        Base.metadata.create_all(bind=engine)
        logger.warning("STARTUP: Base.metadata.create_all OK")
    except Exception as e:
        logger.warning(
            "STARTUP: Error creando tablas Base: %s - "
            "continuando sin tablas principales", e
        )
        tables_ok = False
    
    # Intentar crear admin_sessions aunque Base.metadata.create_all haya fallado
    try:
        admin_session_table_ok = init_session_table(engine)
        logger.warning(
            "STARTUP: init_session_table result=%s (tables_ok=%s)",
            admin_session_table_ok, tables_ok
        )
    except Exception as e:
        logger.error("STARTUP: init_session_table exception: %s", e)
        admin_session_table_ok = False
    
    if not tables_ok:
        logger.warning(
            "STARTUP: tablas principales NO disponibles - "
            "sesiones pueden fallar. Health check respondera."
        )
    
    # FASE 2: Configurar SessionStore (SIEMPRE intentar, no depende de tablas)
    try:
        session_store.configure(engine)
        logger.warning("STARTUP: session_store.configure OK")
        
        # Verificar que SessionStore funcione creando una sesion de prueba
        try:
            test_db = session_store._get_db()
            test_db.close()
            logger.warning("STARTUP: session_store._get_db() OK")
        except Exception as test_e:
            logger.error("STARTUP: session_store._get_db() test FAILED: %s", test_e)
    except Exception as e:
        logger.error("STARTUP: Error configurando SessionStore: %s", e)
    
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
        logger.info("PostgreSQL detectado")
        try:
            _backfill_tenant_slugs()
        except Exception:
            pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(debug.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(catalogo_router.router)
app.include_router(sorteos.router)
app.include_router(publico.router)

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")
