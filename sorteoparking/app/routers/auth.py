import asyncio
import hmac
import random
import secrets
from datetime import datetime, timezone

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

from app.core.config import deploy_config, public_urls_config, super_admin_config
from app.core.session_store import session_store
from app.db.database import SessionLocal
from app.models.superadmin import PasswordResetToken
from app.models.password_reset import SuperAdminCredentials
from app.services.email_service import enviar_reset_password
from app.services.log_service import registrar_log_auditoria

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=_get_client_ip)
ph = PasswordHasher()

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=50)
    password: SecretStr
    totp_code: str | None = None


class TenantLoginRequest(BaseModel):
    """T-321: Login de TENANT_ADMIN vía UUID."""
    tenant_id: str = Field(..., min_length=36, max_length=36)


class RecuperarPasswordIn(BaseModel):
    """T-315: Solicitud de recuperación de contraseña."""
    email: str = Field(..., min_length=5, max_length=120)


class ResetPasswordIn(BaseModel):
    """T-315: Restablecimiento de contraseña con token."""
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

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
        # T-317: Audit trail de login fallido
        client_ip = _get_client_ip(request)
        db_audit = SessionLocal()
        try:
            registrar_log_auditoria(
                db_audit, "SUPER_ADMIN", "SUPERADMIN_LOGIN_FALLO",
                f"ip={client_ip},intento=1"
            )
            db_audit.commit()
        except Exception:
            logger.exception("AUDIT LOGIN FALLO")
        finally:
            db_audit.close()

        # Sleep aleatorio 200-400ms para tiempo constante + jitter
        await asyncio.sleep(random.uniform(0.2, 0.4))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    # 4b. T-316: Validar TOTP si está configurado y en producción
    totp_secret = super_admin_config.super_admin_totp_secret
    if totp_secret and deploy_config.app_env == "production":
        if not payload.totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código TOTP requerido"
            )
        try:
            import pyotp
            totp = pyotp.TOTP(totp_secret)
            if not totp.verify(payload.totp_code):
                logger.warning("AUTH LOGIN: TOTP inválido")
                db_audit = SessionLocal()
                try:
                    registrar_log_auditoria(
                        db_audit, "SUPER_ADMIN", "SUPERADMIN_LOGIN_FALLO",
                        f"ip={_get_client_ip(request)},intento=1,motivo=TOTP_invalido"
                    )
                    db_audit.commit()
                except Exception:
                    logger.exception("AUDIT TOTP FALLO")
                finally:
                    db_audit.close()

                await asyncio.sleep(random.uniform(0.2, 0.4))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Código TOTP inválido"
                )
        except ImportError:
            logger.error("AUTH LOGIN: pyotp no instalado, TOTP no disponible")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de configuración TOTP"
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

    # 8. T-317: Audit trail de login exitoso
    db_audit = SessionLocal()
    try:
        registrar_log_auditoria(
            db_audit, "SUPER_ADMIN", "SUPERADMIN_LOGIN_OK",
            f"ip={_get_client_ip(request)}"
        )
        db_audit.commit()
    except Exception:
        logger.exception("AUDIT LOGIN OK")
    finally:
        db_audit.close()

    # 9. Redirect 303 (See Other) para que el navegador procese las cookies antes de navegar
    # Las cookies ya están en la response, el 303 hace que el navegador las persista
    # y luego siga el redirect a superadmin.html con las cookies en el siguiente GET
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url="/static/superadmin.html", status_code=status.HTTP_303_SEE_OTHER)
    
    # Re-aplicar las cookies a la response de redirect (importante para que persistan)
    response.set_cookie(
        key="admin_session",
        value=session_id,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=3600,
        path="/"
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_secure,
        samesite="lax",
        max_age=3600,
        path="/"
    )
    
    return response


# ── T-321: LOGIN TENANT_ADMIN (UUID) ────────────────────────────────

@router.post("/login/tenant", status_code=status.HTTP_200_OK)
@limiter.limit("10/15minutes")
async def login_tenant(request: Request, payload: TenantLoginRequest):
    """Valida UUID de conjunto y retorna datos del tenant.

    Público (sin Bearer). Verifica que el UUID exista en la tabla
    `tenants` y que su estado sea ACTIVO. Retorna nombre y municipio
    para que el frontend los guarde en sessionStorage.

    Contrato (SDD §10.2.1):
        → 200: {"valid": true, "nombre": "...", "municipio": "..."}
        → 401: {"valid": false, "error": "UUID no válido o conjunto suspendido"}
    """
    import logging
    import re
    logger = logging.getLogger(__name__)

    tenant_id = payload.tenant_id.strip().lower()

    # Validar formato UUID v4
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', tenant_id):
        logger.warning("TENANT_LOGIN | formato_invalido | input=%s", tenant_id[:20])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="UUID no válido o conjunto suspendido"
        )

    from app.db.database import SessionLocal
    from app.models.tenant import Tenant

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

        if not tenant:
            logger.warning("TENANT_LOGIN | no_encontrado | id=%s", tenant_id[:8] + "...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="UUID no válido o conjunto suspendido"
            )

        if tenant.estado != "ACTIVO":
            logger.warning(
                "TENANT_LOGIN | suspendido | id=%s | estado=%s",
                tenant_id[:8] + "...", tenant.estado
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="UUID no válido o conjunto suspendido"
            )

        logger.info("TENANT_LOGIN | ok | id=%s | nombre=%s", tenant_id[:8] + "...", tenant.nombre)

        return {
            "valid": True,
            "nombre": tenant.nombre,
            "municipio": tenant.municipio
        }

    finally:
        db.close()


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
    import logging
    logger = logging.getLogger(__name__)

    forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
    is_secure = (request.url.scheme == "https") or (forwarded_proto == "https")

    session_id = request.cookies.get("admin_session", "")

    for old_path in ("/admin", "/"):
        response.delete_cookie(
            key="admin_session", path=old_path,
            secure=is_secure, samesite="lax"
        )
        response.delete_cookie(
            key="csrf_token", path=old_path,
            secure=is_secure, samesite="lax"
        )

    # T-317: Audit trail de logout
    db_audit = SessionLocal()
    try:
        registrar_log_auditoria(
            db_audit, "SUPER_ADMIN", "SUPERADMIN_LOGOUT",
            f"session_id={session_id[:16] if session_id else 'none'}"
        )
        db_audit.commit()
    except Exception:
        logger.exception("AUDIT LOGOUT")
    finally:
        db_audit.close()

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

        # T-315: Audit trail
        db_audit = SessionLocal()
        try:
            registrar_log_auditoria(
                db_audit, "SUPER_ADMIN", "PASSWORD_RESET_SOLICITADO",
                f"email={email[:3]}***"
            )
            db_audit.commit()
        except Exception:
            logger.exception("AUDIT PASSWORD_RESET_SOLICITADO")
        finally:
            db_audit.close()
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
            PasswordResetToken.used_at.is_(None)
        ).update({"used_at": datetime.now(timezone.utc)})
        db.commit()
        logger.warning("PASSWORD_RESET_EXECUTE | todos_tokens_invalidados")

        # 5. Invalidar TODAS las sesiones admin activas
        try:
            from app.core.session_store import AdminSession
            db.query(AdminSession).filter(
                AdminSession.revoked_at.is_(None)
            ).update({"revoked_at": datetime.now(timezone.utc)})
            db.commit()
            logger.warning("PASSWORD_RESET_EXECUTE | todas_sesiones_invalidadas")
        except Exception as e:
            logger.error("PASSWORD_RESET_EXECUTE | error_invalidando_sesiones: %s", e)

        # T-315: Audit trail PASSWORD_RESET_APLICADO
        db_audit = SessionLocal()
        try:
            registrar_log_auditoria(
                db_audit, "SUPER_ADMIN", "PASSWORD_RESET_APLICADO",
                f"email={email[:3]}***"
            )
            db_audit.commit()
        except Exception:
            logger.exception("AUDIT PASSWORD_RESET_APLICADO")
        finally:
            db_audit.close()

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


# ── T-315: SUPERADMIN PASSWORD RESET (paths exactos del SDD) ──

superadmin_reset_router = APIRouter(prefix="", tags=["superadmin-reset"])


@superadmin_reset_router.post("/superadmin/recuperar-password", status_code=statu