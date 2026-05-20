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

from app.core.config import super_admin_config
from app.core.session_store import session_store

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=_get_client_ip)
ph = PasswordHasher()

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=50)
    password: SecretStr

@router.post("/login/superadmin", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/15minutes")
async def login_superadmin(request: Request, response: Response, payload: LoginRequest):
    """Endpoint de login seguro para SUPER_ADMIN (SDD §13)."""
    
    # 1. Leer credenciales desde variables de entorno
    stored_user = super_admin_config.super_admin_user
    stored_hash = super_admin_config.super_admin_password_hash
    stored_token = super_admin_config.super_admin_token

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
    is_secure = request.url.scheme == "https"
    
    # 5. Éxito: generar tokens de sesión y CSRF
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)

    # Guardar en almacen de sesiones (session_id -> TOKEN)
    session_store.create_session(session_id, stored_token)

    # 6. Configurar cookies
    # admin_session: HttpOnly, SameSite=strict
    response.set_cookie(
        key="admin_session",
        value=session_id,
        httponly=True,
        secure=is_secure,
        samesite="strict",
        max_age=1800, # 30 minutos
        path="/" # Ampliado a raíz para mayor compatibilidad
    )
    
    # csrf_token: Visible al cliente para incluir en headers
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_secure,
        samesite="strict",
        max_age=1800,
        path="/"
    )

    # Asegurar que el objeto Response tiene un código HTTP válido
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
