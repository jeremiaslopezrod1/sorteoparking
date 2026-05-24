"""Envio de correos via Resend HTTP API. SDD §3.2 / T-206."""

import logging
import os

import resend

from app.core.config import email_config

logger = logging.getLogger(__name__)

resend.api_key = email_config.resend_api_key or os.getenv("RESEND_API_KEY", "")


def enviar_correo_texto(destino: str, asunto: str, cuerpo: str) -> bool:
    """Envía un correo en texto plano via Resend HTTP API.

    Args:
        destino: email del destinatario
        asunto: asunto del correo
        cuerpo: cuerpo en texto plano (se envuelve en HTML minimal)

    Returns:
        True si Resend respondió OK, False en caso contrario.
    """
    if not resend.api_key:
        logger.error("RESEND_MISSING_API_KEY")
        return False

    from_addr = email_config.resend_from

    # Envolver texto plano en HTML minimal para Resend (requiere html)
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; white-space: pre-wrap;">
{cuerpo}
</body>
</html>"""

    logger.warning("RESEND_SEND_START | destino=%s asunto=%s", destino, asunto)

    try:
        response = resend.Emails.send({
            "from": from_addr,
            "to": destino,
            "subject": asunto,
            "html": html,
        })
        logger.warning("RESEND_SEND_OK | destino=%s response_id=%s", destino, response.get("id", "?"))
        return True
    except Exception:
        logger.exception("RESEND_SEND_ERROR | destino=%s", destino)
        return False


def enviar_reset_password(destino: str, reset_url: str) -> bool:
    """Envía correo de recuperación de contraseña via Resend.

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
