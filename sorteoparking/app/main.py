from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.security import get_auth_context
from app.db.database import Base, SessionLocal, engine, configurar_sqlite_wal
from app.routers import admin, auth, catalogo as catalogo_router, publico, sorteos
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Importa modelos para que SQLAlchemy registre todas las tablas.
from app.models import catalogo, log, sorteo, superadmin, tenant  # noqa: F401

import asyncio
import logging
from app.scripts.backup_db import ejecutar_ciclo_backup
from app.core.scheduler import scheduler_diario
from app.core.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(title="SorteoParking")
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ProxyHeadersMiddleware: confía en X-Forwarded-* de Render (necesario para HTTPS y IP real)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Agregar después de crear la app FastAPI
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def tenant_auth_middleware(request: Request, call_next):
    try:
        # Excluir rutas de autenticación y administración global del middleware de tenant
        if request.url.path.startswith("/auth/") or request.url.path.startswith("/admin/"):
            request.state.tenant_id = None
            return await call_next(request)
            
        auth_ctx = get_auth_context(request)
        request.state.tenant_id = auth_ctx.tenant_id
    except Exception as exc:  # HTTPException incluida
        status_code = getattr(exc, "status_code", 401)
        detail = getattr(exc, "detail", "No autorizado")
        return JSONResponse(status_code=status_code, content={"detail": detail})

    return await call_next(request)


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
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.warning("Error creando tablas: %s - continuando con short circuit", e)
        return  # Short circuit - health check responderá pero sin DB
    
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


app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(catalogo_router.router)
app.include_router(sorteos.router)
app.include_router(publico.router)

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")
