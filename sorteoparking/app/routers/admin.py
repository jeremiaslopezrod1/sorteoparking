from datetime import datetime
import hashlib
import os
import hmac
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import super_admin_config
from app.core.slug import generar_slug_unico
from app.db.database import SessionLocal
from app.models.tenant import Tenant
from app.models.sorteo import Sorteo
from app.models.log import LogAuditoria


def _super_admin_bearer(request: Request):
    """Valida token Bearer de SUPER_ADMIN (SDD §5.1) o sesion por cookie."""
    # 1. Intentar Authorization: Bearer (para API/curl/cli)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ").strip()
        if not super_admin_config.super_admin_token:
            raise HTTPException(status_code=500, detail="SUPER_ADMIN_TOKEN no configurado")
        if hmac.compare_digest(token, super_admin_config.super_admin_token):
            return token
        raise HTTPException(status_code=403, detail="Token de SUPER_ADMIN invalido")

    # 2. Intentar sesion por cookie admin_session (para frontend)
    session_id = request.cookies.get("admin_session")
    if session_id:
        from app.core.session_store import session_store
        token_hash = session_store.get_session(session_id)
        if token_hash and super_admin_config.super_admin_token:
            expected_hash = hashlib.sha256(
                super_admin_config.super_admin_token.encode("utf-8")
            ).hexdigest()
            if hmac.compare_digest(token_hash, expected_hash):
                # CSRF validation for mutating requests
                if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                    csrf_cookie = request.cookies.get("csrf_token")
                    csrf_header = request.headers.get("X-CSRF-Token")
                    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                        raise HTTPException(
                            status_code=403,
                            detail="Validacion CSRF fallida",
                        )
                return super_admin_config.super_admin_token
        raise HTTPException(
            status_code=403,
            detail="Sesion expirada o invalida. Inicie sesion nuevamente."
        )

    # 3. Sin credencial
    raise HTTPException(status_code=403, detail="Acceso denegado: se requiere token Bearer o sesion activa")


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(_super_admin_bearer)],
)


class TenantCreate(BaseModel):
    nombre: str
    municipio: str
    email_admin: str

    # TODO(FIX #25): Add email format validation (Pydantic v2 @field_validator)
    nit: str | None = None
    total_unidades: int | None = None


class TenantOut(BaseModel):
    id: str
    slug: str | None
    nombre: str
    nit: str | None
    municipio: str
    email_admin: str
    estado: str
    plan: str
    total_unidades: int | None
    created_at: datetime


class TenantEstado(BaseModel):
    estado: str  # ACTIVO, SUSPENDIDO, DEMO


def _tenant_to_dict(tenant: Tenant) -> dict[str, object]:
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "nombre": tenant.nombre,
        "nit": tenant.nit,
        "municipio": tenant.municipio,
        "email_admin": tenant.email_admin,
        "estado": tenant.estado,
        "plan": tenant.plan,
        "total_unidades": tenant.total_unidades,
        "created_at": tenant.created_at,
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def crear_tenant(payload: TenantCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    if payload.nit:
        existing = db.query(Tenant).filter(Tenant.nit == payload.nit).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NIT duplicado")
    slug = generar_slug_unico(payload.nombre, db)
    tenant = Tenant(slug=slug, nombre=payload.nombre, nit=payload.nit, municipio=payload.municipio,
                    email_admin=payload.email_admin,
                    total_unidades=payload.total_unidades, estado="ACTIVO", plan="POR_EVENTO")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return _tenant_to_dict(tenant)


@router.get("/tenants", response_model=list[TenantOut])
def listar_tenants(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    tenants = db.query(Tenant).filter(Tenant.estado == "ACTIVO").all()
    return [_tenant_to_dict(tenant) for tenant in tenants]


@router.patch("/tenants/{tenant_id}")
def actualizar_tenant(tenant_id: str, payload: TenantCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    if payload.nombre: tenant.nombre = payload.nombre
    if payload.municipio: tenant.municipio = payload.municipio
    if payload.email_admin: tenant.email_admin = payload.email_admin
    if payload.nit:
        existing_nit = db.query(Tenant).filter(Tenant.nit == payload.nit, Tenant.id != tenant_id).first()
        if existing_nit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NIT ya registrado por otro conjunto")
    if payload.nit is not None: tenant.nit = payload.nit
    if payload.total_unidades is not None: tenant.total_unidades = payload.total_unidades
    db.commit()
    db.refresh(tenant)
    return _tenant_to_dict(tenant)


@router.patch("/tenants/{tenant_id}/estado")
def suspender_reactivar_tenant(tenant_id: str, payload: TenantEstado, db: Session = Depends(get_db)) -> dict[str, object]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    if payload.estado not in ("ACTIVO", "SUSPENDIDO", "DEMO"):
        raise HTTPException(status_code=400, detail="Estado invalido")
    tenant.estado = payload.estado
    db.commit()
    db.refresh(tenant)
    return _tenant_to_dict(tenant)


@router.get("/metricas")
def metricas_globales(db: Session = Depends(get_db)) -> dict[str, object]:
    total_tenants = db.query(Tenant).limit(10000).count()
    activos = db.query(Tenant).filter(Tenant.estado == "ACTIVO").limit(10000).count()
    sorteos_totales = db.query(Sorteo).limit(100000).count()
    sorteos_completados = db.query(Sorteo).filter(Sorteo.estado == "COMPLETADO").count()
    sorteos_en_curso = db.query(Sorteo).filter(Sorteo.estado.in_(("EN_CURSO", "LISTO", "EJECUTANDO"))).count()
    logs_totales = db.query(LogAuditoria).limit(100000).count()
    return {
        "tenants": {"total": total_tenants, "activos": activos},
        "sorteos": {"total": sorteos_totales, "completados": sorteos_completados, "en_curso": sorteos_en_curso},
        "logs_auditoria": logs_totales,
    }


@router.post("/backup", status_code=status.HTTP_200_OK)
def backup_manual() -> dict:
    from app.scripts.backup_db import ejecutar_ciclo_backup
    exito = ejecutar_ciclo_backup()
    if not exito:
        raise HTTPException(500, "Backup fallo — revisar logs")
    return {"mensaje": "Backup ejecutado exitosamente", "backup_dir": str(os.getenv("BACKUP_DIR", "/data/backups"))}
