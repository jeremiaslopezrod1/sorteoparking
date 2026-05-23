import hmac
import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import security_config, super_admin_config


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str


def _is_public_path(path: str) -> bool:
    return path.startswith(security_config.public_path_prefixes) or path.startswith("/static/") or path in (
        "/health",
    )


def _acceso_confirmar_otp_consejero(request: Request) -> bool:
    """POST /sorteos/{id}/otp/confirmar con header de enlace unico (SDD §6.2, T-202)."""
    if request.method != "POST":
        return False
    if not security_config.es_post_confirmar_otp_sin_bearer(request.url.path):
        return False
    token_header = request.headers.get(security_config.otp_confirm_header_name, "").strip()
    return bool(token_header)


def parse_tenant_id_from_token(token: str) -> str:
    # SDD §3.3 y §5: el token identifica al tenant.
    try:
        return str(UUID(token.strip()))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido: tenant_id no es UUID",
        ) from exc


def get_auth_context(request: Request) -> AuthContext:
    if _is_public_path(request.url.path):
        return AuthContext(tenant_id="")

    if _acceso_confirmar_otp_consejero(request):
        # Explicitly set tenant_id="" for OTP confirm path (no tenant context)
        return AuthContext(tenant_id="")

    auth_header = request.headers.get(security_config.auth_header_name, "")
    if not auth_header.startswith(security_config.bearer_prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta Authorization Bearer",
        )

    raw_token = auth_header.removeprefix(security_config.bearer_prefix).strip()
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token vacio",
        )

    return AuthContext(tenant_id=parse_tenant_id_from_token(raw_token))


def enforce_tenant_scope(request_tenant_id: str, resource_tenant_id: str) -> None:
    if request_tenant_id != resource_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: recurso de otro tenant",
        )


def _get_db_for_superadmin():
    """Generador de sesion exclusivo para verify_super_admin.

    Necesario porque verify_super_admin se usa como router-level dependency
    y no hereda la sesion de los endpoints individuales.
    """
    from app.db.database import SessionLocal  # import local para evitar importacion circular en arranque

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_super_admin_from_cookie(request: Request) -> str:
    """Valida la sesión del SUPER_ADMIN desde cookies (SDD §13).
    
    Retorna el SUPER_ADMIN_TOKEN si es válido.
    """
    from app.core.session_store import session_store
    logger = logging.getLogger(__name__)
    # Loguear solo nombres de cookies (nunca valores)
    logger.debug("Cookie recibida: %s", list(request.cookies.keys()))

    # DEBUG T-107: información adicional para localizar fallo de sesión
    logger.debug("=== DEBUG T-107 ===")
    logger.debug("Cookies presentes: %s", list(request.cookies.keys()))
    logger.debug("admin_session presente: %s", "admin_session" in request.cookies)

    session_id = request.cookies.get("admin_session")
    logger.debug("session_id obtenido: %s", bool(session_id))

    token = None
    if session_id:
        token = session_store.get_session(session_id)
        logger.debug("token en store: %s", bool(token))

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: sin sesión activa"
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: sesión expirada o inválida"
        )
        
    # Validación CSRF para mutaciones
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")
        
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: validación CSRF fallida"
            )

    return token


def verify_super_admin(request: Request, db: Session = Depends(_get_db_for_superadmin)) -> None:
    """Valida que el request venga de un SUPER_ADMIN (SDD §2, §5.1).

    [DEPRECATED] Usar get_super_admin_from_cookie para nuevos endpoints.
    Mantenido por compatibilidad legacy si fuera necesario.
    """
    auth_header = request.headers.get(security_config.auth_header_name, "")
    if not auth_header.startswith(security_config.bearer_prefix):
        # Fallback a cookie si no hay bearer (transición T-107)
        try:
            get_super_admin_from_cookie(request)
            return
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado",
            )

    raw_token = auth_header.removeprefix(security_config.bearer_prefix).strip()
    
    # Comparación segura
    if super_admin_config.super_admin_token and hmac.compare_digest(raw_token, super_admin_config.super_admin_token):
        return

    from app.models.superadmin import SuperAdmin
    registro = db.query(SuperAdmin).filter(
        SuperAdmin.token == raw_token,
        SuperAdmin.revocado_at.is_(None),
    ).first()
    
    if registro:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso denegado",
    )
