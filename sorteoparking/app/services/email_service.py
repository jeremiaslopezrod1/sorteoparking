"""Envio de correo SMTP para fallback SDD §3.2 / T-206."""

import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import email_config

logger = logging.getLogger(__name__)


def enviar_correo_texto(destino: str, asunto: str, cuerpo: str) -> bool:
    """
    Envía un correo en texto plano usando SMTP si la configuración está completa.

    Returns:
        True si se envió, False si faltan variables o falló el envío.
    """
    host = email_config.smtp_host
    user = email_config.smtp_user
    password = email_config.smtp_password
    from_addr = email_config.smtp_from or user
    logger.warning("SMTP_DIAG | host=%s user=%s from=%s port=%s destino=%s",
                   bool(host), bool(user), bool(from_addr), email_config.smtp_port, destino)
    if not host or not from_addr:
        logger.warning("SMTP_FALTA_CONFIG | host=%s from=%s user=%s pass=%s",
                       bool(host), bool(from_addr), bool(user), bool(password))
        return False

    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = from_addr
    msg["To"] = destino

    try:
        if email_config.smtp_port == 465:
            with smtplib.SMTP_SSL(host, email_config.smtp_port, timeout=30) as smtp:
                if user and password:
                    smtp.login(user, password)
                smtp.sendmail(from_addr, [destino], msg.as_string())
        else:
            with smtplib.SMTP(host, email_config.smtp_port, timeout=30) as smtp:
                smtp.ehlo()
                if email_config.smtp_port == 587:
                    smtp.starttls()
                    smtp.ehlo()
                if user and password:
                    smtp.login(user, password)
                smtp.sendmail(from_addr, [destino], msg.as_string())
        logger.warning("SMTP_ENVIO_OK | destino=%s", destino)
        return True
    except Exception as e:
        smtp_code = getattr(e, 'smtp_code', None)
        smtp_error = getattr(e, 'smtp_error', None)
        logger.exception("SMTP_SEND_ERROR | destino=%s host=%s port=%s smtp_code=%s smtp_error=%s",
                         destino, host, email_config.smtp_port, smtp_code, smtp_error)
        return False


def enviar_reset_password(destino: str, reset_url: str) -> bool:
    """Envía correo de recuperación de contraseña.

    Args:
        destino: email del SuperAdmin
        reset_url: URL completa con token para reset

    Returns:
        True si se envió correctamente.
    """
    asunto = "SorteoParking — Recuperación de contraseña"
    cuerpo = f"""Hola,

Se solicitó restablecer la contraseña del panel SuperAdmin de SorteoParking.

Para continuar, abre este enlace (válido por 15 minutos):

{reset_url}

Si no solicitaste este cambio, ignora este mensaje. El enlace expirará automáticamente.

— SorteoParking"""

    resultado = enviar_correo_texto(destino, asunto, cuerpo)
    if resultado:
        logger.warning("PASSWORD_RESET_EMAIL_SENT | destino=%s", destino)
    else:
        logger.error("PASSWORD_RESET_EMAIL_FAILED | destino=%s", destino)
    return resultado

