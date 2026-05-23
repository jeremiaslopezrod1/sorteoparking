import asyncio
import hmac
import random
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, SecretStr
from slowapi import Limiter

def _get_client_ip(request) -> str:
    """Get real client IP behind proxy (Railway, Nginx, Cloudflare)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    forwarded_proto = request.headers.get("X-Real-IP", "")
    if forwarded_proto:
        return forwarded_proto.strip()
    return request.client.host if request.client else "127.0.0.1"

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import public_urls_config, super_admin_config
from app.core.session_store import session_store
from app.db.database import SessionLocal
from app.models.password_reset import PasswordResetToken, SuperAdminCredentials
from app.services.email_service import enviar_reset_password

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=_get_client_ip)
ph = PasswordHasher()

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=50)
    password: SecretStr

@router.post("/login/superadmin", status_code=status.HTTP_200_OK)
@limiter.limit("5/15minutes")
async def login_superadmin(request: Request, response: Response, payload: LoginRequest):
    """Endpoint de login seguro para SUPER_ADMIN (SDD §13).

    Devuelve 200 OK con JSON (NO 204) porque proxies como Render y algunos
    navegadores ignoran Set-Cookie en respuestas sin body, rompiendo la sesion.
    """
    
    # 1. Leer credenciales — BD primero, luego env var
    import logging
    logger = logging.getLogger(__name__)
    
    stored_user = super_admin_config.super_admin_user
    stored_token = super_admin_config.super_admin_token

    # Intentar obtener password_hash de BD
    db = SessionLocal()
    try:
        creds_db = SuperAdminCredentials.obtener(db)
        stored_hash = creds_db.password_hash if creds_db else None
        if stored_hash:
            logger.info("AUTH LOGIN: usando password_hash de BD")
        else:
            stored_hash = super_admin_config.super_admin_password_hash
            logger.info("AUTH LOGIN: usando password_hash de env var (BD vacia)")
    except Exception as e:
        logger.warning("AUTH LOGIN: error leyendo BD, usando env var: %s", e)
        stored_hash = super_admin_config.super_admin_password_hash
    finally:
        db.close()

    # 2. Verificar usuario con tiempo constante
    user_ok = hmac.compare_digest(payload.username, stored_user)
    
    # 3. Verificar contraseña con Argon2id
    password_ok = False
    if stored_hash:
        try:
            ph.verify(stored_hash, payload.password.get_secret_value())
            password_ok = True
        except VerifyMismatchError:
            password_ok = False
        except Exception:
            password_ok = False

    # 4. Manejo de falla: tiempo constante + error genérico
    if not user_ok or not password_ok or not stored_token:
        # Sleep aleatorio 200-400ms para tiempo constante + jitter
        await asyncio.sleep(random.uniform(0.2, 0.4))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    # Detectar si estamos en local para permitir cookies sin HTTPS
    # Detras de proxy (Render): usar X-Forwarded-Proto para deteccion correcta
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    is_secure = (request.url.scheme == "https") or (forwarded_proto == "https")
    
    # 5. Éxito: generar tokens de sesión y CSRF
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)

    # Guardar en almacen de sesiones (session_id -> TOKEN + CSRF)
    creado = session_store.create_session(session_id, stored_token, csrf_token)
    if not creado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo crear la sesion. Intente de nuevo."
        )

    # 6. Limpiar cookies viejas con paths antiguos (evita conflicto CSRF)
    # IMPORTANTE: delete_cookie debe coincidir secure/samesite con la cookie original
    for old_path in ("/admin", "/"):
        response.delete_cookie(
            key="admin_session", path=old_path,
            secure=is_secure, samesite="lax"
        )
        response.delete_cookie(
            key="csrf_token", path=old_path,
            secure=is_secure, samesite="lax"
        )

    # 7. Configurar cookies
    # admin_session: HttpOnly, SameSite=Lax (permite navegacion desde enlaces externos)
    response.set_cookie(
        key="admin_session",
        value=session_id,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=3600, # 60 minutos
        path="/"
    )
    
    # csrf_token: Visible al cliente para incluir en headers
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_secure,
        samesite="lax",
        max_age=3600,
        path="/"
    )

    # 8. Devolver 200 OK con JSON (NO 204 — Set-Cookie se pierde en 204 con proxies)
    # Incluir csrf_token en el body como fallback si la cookie no es accesible via JS
    return {
        "ok": True,
        "csrf_token": csrf_token,
        "expires_in": 3600
    }


@router.get("/session-check")
async def session_check(request: Request):
    """Endpoint de diagnostico: verifica si las cookies de sesion viajan correctamente.
    
    NO modifica estado. Retorna informacion segura sobre la sesion actual.
    Util para debugging de problemas de autenticacion en produccion.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    cookies_presentes = list(request.cookies.keys())
    session_id = request.cookies.get("admin_session")
    csrf_cookie = request.cookies.get("csrf_token")
    
    # Info de headers relevante
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    referer = request.headers.get("Referer", "")
    origin = request.headers.get("Origin", "")
    
    result = {
        "cookies_recibidas": cookies_presentes,
        "admin_session_presente": session_id is not None,
        "csrf_cookie_presente": csrf_cookie is not None,
        "es_https": (request.url.scheme == "https") or (forwarded_proto == "https"),
        "url_scheme": request.url.scheme,
        "forwarded_proto": forwarded_proto[:20] if forwarded_proto else "",
        "base_url": str(request.base_url),
    }
    
    if session_id:
        # Validar sesion contra BD
        token_hash = session_store.get_session(session_id)
        result["sesion_valida_en_bd"] = token_hash is not None
        result["session_id_fragmento"] = session_id[:8] + "..."
    else:
        result["sesion_valida_en_bd"] = False
    
    # Loggear para diagnostico en servidor
    logger.info(
        "SESSION-CHECK | cookies=%s | session=%s | bd=%s | https=%s",
        cookies_presentes,
        session_id[:8] + "..." if session_id else "ninguna",
        result["sesion_valida_en_bd"],
        result["es_https"]
    )
    
    return result


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request, response: Response):
    """Cierra la sesión del superadmin."""
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    is_secure = (request.url.scheme == "https") or (forwarded_proto == "https")
    for old_path in ("/admin", "/"):
        response.delete_cookie(
            key="admin_session", path=old_path,
            secure=is_secure, samesite="lax"
        )
        response.delete_cookie(
            key="csrf_token", path=old_path,
            secure=is_secure, samesite="lax"
        )
    return {"ok": True, "message": "Sesion cerrada"}


# ── RECUPERACIÓN DE CONTRASEÑA ──────────────────────────────────

class RequestResetRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
@limiter.limit("3/15minutes")
async def request_password_reset(request: Request, payload: RequestResetRequest):
    """Solicita recuperación de contraseña.

    Siempre retorna OK aunque el email no exista (anti-enumeración).
    """
    import logging
    logger = logging.getLogger(__name__)

    email = payload.email.strip().lower()
    logger.warning("PASSWORD_RESET_REQUEST | email=%s", email[:3] + "***")

    # Verificar si el email coincide con el configurado
    admin_email = super_admin_config.super_admin_email.strip().lower()

    if email != admin_email:
        # Email no coincide — mismo mensaje para evitar enumeración
        logger.warning("PASSWORD_RESET_REQUEST | email_no_coincide")
        await asyncio.sleep(random.uniform(0.2, 0.4))
        return {
            "ok": True,
            "message": "Si el correo existe, se enviaron instrucciones."
        }

    # Generar token y enviar correo
    db = SessionLocal()
    try:
        token_plano = PasswordResetToken.generar(email, db)

        base_url = public_urls_config.public_base_url.rstrip("/")
        reset_url = f"{base_url}/static/reset-password.html?token={token_plano}"

        enviado = enviar_reset_password(email, reset_url)
        if not enviado:
            logger.error("PASSWORD_RESET_REQUEST | email_fallo_envio")
    except Exception as e:
        logger.exception("PASSWORD_RESET_REQUEST | error=%s", e)
    finally:
        db.close()

    return {
        "ok": True,
        "message": "Si el correo existe, se enviaron instrucciones."
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/15minutes")
async def reset_password(request: Request, payload: ResetPasswordRequest):
    """Restablece la contraseña del SuperAdmin usando un token de reset.

    Invalida todas las sesiones activas tras el cambio.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.warning("PASSWORD_RESET_EXECUTE | token_prefix=%s", payload.token[:8] + "...")

    db = SessionLocal()
    try:
        # 1. Validar token
        email = PasswordResetToken.validar(payload.token, db)
        if not email:
            logger.warning("PASSWORD_RESET_EXECUTE | token_invalido")
            await asyncio.sleep(random.uniform(0.2, 0.4))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token invalido o expirado"
            )

        logger.warning("PASSWORD_RESET_EXECUTE | token_valido | email=%s", email[:3] + "***")

        # 2. Hashear nueva contraseña
        new_hash = ph.hash(payload.new_password)

        # 3. Guardar en BD
        SuperAdminCredentials.guardar_o_actualizar(email, new_hash, db)
        logger.warning("PASSWORD_RESET_EXECUTE | password_hash_actualizado")

        # 4. Invalidar TODOS los tokens de reset restantes
        db.query(PasswordResetToken).filter(
            PasswordResetToken.used == False  # noqa: E712
        ).update({"used": True})
        db.commit()
        logger.warning("PASSWORD_RESET_EXECUTE | todos_tokens_invalidados")

        # 5. Invalidar TODAS las sesiones admin activas
        try:
            from app.core.session_store import AdminSession
            from datetime import datetime as dt, timezone as tz
            db.query(AdminSession).filter(
                AdminSession.revoked_at.is_(None)
            ).update({"revoked_at": dt.now(tz.utc)})
            db.commit()
            logger.warning("PASSWORD_RESET_EXECUTE | todas_sesiones_invalidadas")
        except Exception as e:
            logger.error("PASSWORD_RESET_EXECUTE | error_invalidando_sesiones: %s", e)

        return {
            "ok": True,
            "message": "Contraseña actualizada correctamente. Todas las sesiones han sido cerradas."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("PASSWORD_RESET_EXECUTE | error=%s", e)
        if db:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al restablecer contraseña"
        )
    finally:
        db.close()
