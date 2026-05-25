from datetime import datetime
import hashlib
import os
import hmac
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import super_admin_config, public_urls_config
from app.core.slug import generar_slug_unico
from app.db.database import SessionLocal
from app.models.tenant import Tenant
from app.models.sorteo import Sorteo, Participante, Garante, Consejero, SesionOTP, ResultadoSorteo
from app.models.catalogo import Zona, Torre, Parqueadero
from app.models.log import LogAuditoria
from app.services.email_service import enviar_correo_texto
from app.services.log_service import registrar_log_auditoria


def _super_admin_bearer(request: Request):
    """Valida token Bearer de SUPER_ADMIN (SDD §5.1) o sesion por cookie.
    
    En cada fallo, incluye cabecera X-Auth-Fail con el codigo de error.
    En exito, no modifica headers (el endpoint los maneja).
    """
    import logging
    _log = logging.getLogger(__name__)
    
    # 0. Log de entrada para diagnostico
    cookies_list = list(request.cookies.keys())
    _log.info(
        "AUTH_ENTRY | path=%s | method=%s | cookies=%s",
        request.url.path, request.method, cookies_list
    )
    
    # 1. Intentar Authorization: Bearer (para API/curl/cli)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ").strip()
        if not super_admin_config.super_admin_token:
            raise HTTPException(status_code=500, detail="SUPER_ADMIN_TOKEN no configurado")
        if hmac.compare_digest(token, super_admin_config.super_admin_token):
            return token
        raise HTTPException(status_code=403, detail="[A0] Token Bearer invalido")

    # 2. Intentar sesion por cookie admin_session (para frontend)
    session_id = request.cookies.get("admin_session")
    if not session_id:
        _log.warning(
            "AUTH_FAIL | code=A1 | path=%s | cookies_enviadas=%s",
            request.url.path, cookies_list
        )
        raise HTTPException(status_code=403, detail="[A1] Sin cookie admin_session")

    from app.core.session_store import session_store
    token_hash = session_store.get_session(session_id)
    if not token_hash:
        _log.warning(
            "AUTH_FAIL | code=A2 | path=%s | session_id=%s... | sesion_no_encontrada_en_bd",
            request.url.path, session_id[:8]
        )
        raise HTTPException(
            status_code=403,
            detail="[A2] Sesion no encontrada en BD (expiro o no se creo). Vuelva a iniciar sesion."
        )

    if not super_admin_config.super_admin_token:
        _log.error("AUTH_FAIL | code=A3 | SUPER_ADMIN_TOKEN no configurado en servidor")
        raise HTTPException(status_code=500, detail="[A3] SUPER_ADMIN_TOKEN no configurado en servidor")

    expected_hash = hashlib.sha256(
        super_admin_config.super_admin_token.encode("utf-8")
    ).hexdigest()
    if not hmac.compare_digest(token_hash, expected_hash):
        _log.warning(
            "AUTH_FAIL | code=A4 | path=%s | session_id=%s... | hash_mismatch | "
            "db_hash=%s... | expected_hash=%s...",
            request.url.path, session_id[:8],
            token_hash[:16] if token_hash else "None",
            expected_hash[:16]
        )
        raise HTTPException(
            status_code=403,
            detail="[A4] Token hash no coincide (cambio SUPER_ADMIN_TOKEN?). Vuelva a iniciar sesion."
        )

    # CSRF validation for mutating requests — validado contra BD, no contra cookie
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_header:
            # Fallback temporal: si la sesion es valida y el Referer/Origin es same-origin,
            # permitir CON ADVERTENCIA. Esto NO debe ser permanente.
            referer = request.headers.get("Referer", "")
            origin = request.headers.get("Origin", "")
            base_url = str(request.base_url).rstrip("/")
            is_same_origin = (
                (origin and origin == base_url) or
                (referer and referer.startswith(base_url))
            )
            if is_same_origin:
                _log.warning(
                    "CSRF_BYPASS_SAME_ORIGIN | session=%s... | method=%s | path=%s | "
                    "origin=%s | referer=%s — El frontend NO envio X-CSRF-Token. "
                    "Verificar getCsrfToken() en superadmin.html.",
                    session_id[:8] if session_id else "?",
                    request.method,
                    request.url.path,
                    origin[:50] if origin else "-",
                    referer[:50] if referer else "-"
                )
                return super_admin_config.super_admin_token
            _log.warning(
                "AUTH_FAIL | code=A6 | path=%s | session_id=%s... | sin_csrf_header | "
                "origin=%s | referer=%s | base_url=%s",
                request.url.path, session_id[:8],
                origin[:50] if origin else "-",
                referer[:50] if referer else "-",
                base_url[:50]
            )
            raise HTTPException(
                status_code=403,
                detail="[A6] Falta header X-CSRF-Token y no es same-origin."
            )
        if not session_store.validate_csrf(session_id, csrf_header):
            _log.warning(
                "AUTH_FAIL | code=A7 | path=%s | session_id=%s... | "
                "csrf_header=%s... | csrf_no_valido_en_bd",
                request.url.path, session_id[:8], csrf_header[:8]
            )
            raise HTTPException(
                status_code=403,
                detail=f"[A7] CSRF invalido (validado contra BD). header={csrf_header[:8]}... Vuelva a iniciar sesion."
            )

    _log.info(
        "AUTH_OK | path=%s | method=%s | session_id=%s...",
        request.url.path, request.method, session_id[:8]
    )
    return super_admin_config.super_admin_token


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


class TenantPatch(BaseModel):
    """Campos editables para PATCH /tenants/{id} — todos opcionales."""
    nombre: str | None = None
    nit: str | None = None
    email_admin: str | None = None
    municipio: str | None = None
    total_unidades: int | None = None
    estado: str | None = None


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

    # T-311: Auditoria de creacion
    registrar_log_auditoria(db, tenant.id, "TENANT_CREADO", f"nombre={tenant.nombre} email={tenant.email_admin}")
    db.commit()

    # T-311: Correo de bienvenida al admin del conjunto
    dashboard_url = f"{public_urls_config.public_base_url}/static/dashboard.html"
    cuerpo = (
        f"¡Bienvenido a SorteoParking!\n\n"
        f"Conjunto: {tenant.nombre}\n"
        f"UUID del conjunto: {tenant.id}\n\n"
        f"Accede a tu panel de administracion aqui:\n"
        f"{dashboard_url}\n\n"
        f"Usa el UUID de tu conjunto como token de acceso (Authorization: Bearer {tenant.id}).\n\n"
        f"— SorteoParking"
    )
    enviar_correo_texto(tenant.email_admin, "Bienvenido a SorteoParking", cuerpo)

    return _tenant_to_dict(tenant)


@router.get("/tenants", response_model=list[TenantOut])
def listar_tenants(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    tenants = db.query(Tenant).filter(Tenant.estado == "ACTIVO").all()
    return [_tenant_to_dict(tenant) for tenant in tenants]


@router.get("/tenants/{tenant_id}")
def detalle_tenant(tenant_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return _tenant_to_dict(tenant)


@router.patch("/tenants/{tenant_id}")
def editar_tenant(tenant_id: str, payload: TenantPatch, db: Session = Depends(get_db)) -> dict[str, object]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    # Validar unicidad de NIT si se esta cambiando
    if payload.nit:
        existing_nit = db.query(Tenant).filter(Tenant.nit == payload.nit, Tenant.id != tenant_id).first()
        if existing_nit:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NIT ya registrado por otro conjunto")
    if payload.estado and payload.estado not in ("ACTIVO", "SUSPENDIDO", "DEMO"):
        raise HTTPException(status_code=400, detail="Estado invalido")
    campos_aplicados = list(payload.model_dump(exclude_unset=True).keys())
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, key, val)
    db.commit()
    db.refresh(tenant)
    registrar_log_auditoria(db, tenant_id, "TENANT_EDITADO", f"campos={campos_aplicados}")
    db.commit()
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


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_200_OK)
def eliminar_tenant(tenant_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    # Verificar si hay sorteos COMPLETADOS — no se permite eliminar
    sorteos_completados = db.query(Sorteo).filter(
        Sorteo.tenant_id == tenant_id,
        Sorteo.estado == "COMPLETADO"
    ).first()
    if sorteos_completados:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el tenant tiene sorteos COMPLETADOS"
        )

    # Auditar ANTES de eliminar en cascada (LogAuditoria se borra junto con lo demas)
    registrar_log_auditoria(db, tenant_id, "TENANT_ELIMINADO",
                            f"nombre={tenant.nombre} email={tenant.email_admin}")
    db.flush()

    # Eliminar en cascada todos los datos del tenant
    for model in [ResultadoSorteo, SesionOTP, Consejero, Garante, Participante,
                   Parqueadero, Torre, Zona, Sorteo, LogAuditoria]:
        db.query(model).filter(model.tenant_id == tenant_id).delete()
    db.delete(tenant)
    db.commit()

    return {"mensaje": f"Tenant {tenant_id} eliminado exitosamente"}


@router.post("/tenants/{tenant_id}/rotar-token")
def rotar_token(tenant_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    nuevo_id = str(uuid4())
    # Migrar tenant_id en todas las tablas hijas al nuevo UUID
    for tabla in [Zona, Torre, Parqueadero, Participante, Garante, Consejero,
                   Sorteo, SesionOTP, ResultadoSorteo, LogAuditoria]:
        db.query(tabla).filter(tabla.tenant_id == tenant_id).update(
            {"tenant_id": nuevo_id}, synchronize_session=False
        )
    # Actualizar la PK del tenant
    tenant.id = nuevo_id
    db.commit()
    registrar_log_auditoria(db, nuevo_id, "TOKEN_ROTADO", f"tenant_id_anterior={tenant_id}")
    db.commit()
    return {"nuevo_token": nuevo_id}


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
