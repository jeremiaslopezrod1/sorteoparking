import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Cargar variables de entorno desde .env (SDD §13)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class SecurityConfig(BaseModel):
    auth_header_name: str = "Authorization"
    bearer_prefix: str = "Bearer "
    otp_confirm_header_name: str = "X-Sorteo-Otp-Token"
    public_path_prefixes: tuple[str, ...] = ("/p/",)
    internal_open_paths: tuple[str, ...] = ("/health", "/static")

    @staticmethod
    def es_post_confirmar_otp_sin_bearer(path: str) -> bool:
        """SDD §5.3 + §6.2: consejero confirma desde panel sin token de tenant."""
        return bool(re.match(r"^/sorteos/\d+/otp/confirmar/?$", path))

    @staticmethod
    def es_get_estado_otp_sin_bearer(path: str) -> bool:
        """SDD §5.3: consejero consulta estado OTP desde panel sin token de tenant."""
        return bool(re.match(r"^/sorteos/\d+/otp/estado/?$", path))


security_config = SecurityConfig()


class DeployConfig(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./sorteoparking.db")


deploy_config = DeployConfig()


class OtpConfig(BaseModel):
    """Parametros OTP alineados a agents.md y SDD §6."""

    pepper: str = os.getenv("OTP_PEPPER", "sorteoparking-dev-pepper-cambiar-en-produccion")





class EmailConfig(BaseModel):
    """Resend HTTP API para envio de correos SDD §3.2 / T-206."""

    resend_api_key: str | None = os.getenv("RESEND_API_KEY")
    resend_from: str = os.getenv("RESEND_FROM", "onboarding@resend.dev")


class PublicUrlsConfig(BaseModel):
    """Base publica para enlaces en mensajes (SDD §6.2)."""

    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")


class SuperAdminConfig(BaseModel):
    """Token global de SUPER_ADMIN (SDD §2 y §5.1).

    En desarrollo: poner SUPER_ADMIN_TOKEN en .env o variable de entorno
    para autenticar sin base de datos (util en local/CI).
    En produccion: dejar vacio y validar contra la tabla superadmins.
    """

    super_admin_token: str | None = os.getenv("SUPER_ADMIN_TOKEN") or None
    super_admin_user: str = os.getenv("SUPER_ADMIN_USER", "admin")
    super_admin_password_hash: str | None = os.getenv("SUPER_ADMIN_PASSWORD_HASH")
    super_admin_email: str = os.getenv("SUPER_ADMIN_EMAIL", "pruebaalisocajica@gmail.com")


otp_config = OtpConfig()
if deploy_config.app_env == "production" and otp_config.pepper == "sorteoparking-dev-pepper-cambiar-en-produccion":
    raise RuntimeError("OTP_PEPPER must be configured in production environment")
email_config = EmailConfig()
public_urls_config = PublicUrlsConfig()
class DeepSeekConfig(BaseModel):
    """Config DeepSeek Flash para parser inteligente. SDD §14."""

    api_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    timeout: int = int(os.getenv("DEEPSEEK_TIMEOUT", "10"))
    min_confidence: float = float(os.getenv("DEEPSEEK_MIN_CONFIDENCE", "0.80"))


super_admin_config = SuperAdminConfig()
deepseek_config = DeepSeekConfig()
