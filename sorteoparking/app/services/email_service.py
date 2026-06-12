"""Envio de correos via Brevo API. Solución gratuita y sin restricciones de destinatario."""
import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

def enviar_correo_texto(destino: str, asunto: str, cuerpo: str) -> bool:
    """Envía un correo en texto plano via Brevo API (HTTPS, puerto 443)."""
    
    api_key = os.getenv("BREVO_API_KEY")
    remitente_email = os.getenv("BREVO_SENDER_EMAIL", "tu_correo@gmail.com")
    remitente_nombre = os.getenv("BREVO_SENDER_NAME", "SorteoParking")

    if not api_key:
        logger.error("BREVO_ERROR: Falta la variable de entorno BREVO_API_KEY")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    
    payload = {
        "sender": {"name": remitente_nombre, "email": remitente_email},
        "to": [{"email": destino}],
        "subject": asunto,
        "htmlContent": f"<pre style='font-family: system-ui, sans-serif; white-space: pre-wrap;'>{cuerpo}</pre>"
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    )

    try:
        logger.info("BREVO_SEND_START | destino=%s", destino)
        with urllib.request.urlopen(req, timeout=10) as response:
            logger.info("BREVO_SEND_OK | destino=%s | status=%d", destino, response.status)
            return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error("BREVO_SEND_HTTP_ERROR | destino=%s | status=%d | body=%s", destino, e.code, error_body)
        return False
    except Exception as e:
        logger.exception("BREVO_SEND_ERROR | destino=%s | error=%s", destino, str(e))
        return False

def enviar_reset_password(destino: str, reset_url: str) -> bool:
    """Wrapper para mantener compatibilidad con el flujo de recuperación de contraseña."""
    asunto = "SorteoParking — Recuperación de contraseña"
    cuerpo = f"""Hola,

Se solicitó restablecer la contraseña del panel SuperAdmin de SorteoParking.

Para continuar, abre este enlace (válido por 15 minutos):
{reset_url}

Si no solicitaste este cambio, ignora este mensaje.

— SorteoParking"""
    return enviar_correo_texto(destino, asunto, cuerpo)