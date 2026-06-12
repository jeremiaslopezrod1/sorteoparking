"""Envio de correos via SMTP nativo de Python. Solución pragmática MVP."""
import os
import smtplib
from email.message import EmailMessage
import logging

logger = logging.getLogger(__name__)

def enviar_correo_texto(destino: str, asunto: str, cuerpo: str) -> bool:
    """Envía un correo en texto plano usando SMTP nativo (ej. Gmail)."""
    
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not smtp_user or not smtp_pass:
        logger.error("SMTP_ERROR: Faltan credenciales SMTP_USER o SMTP_PASS en variables de entorno")
        return False

    # CORRECCIÓN: Se agregaron los paréntesis () aquí
    msg = EmailMessage()
    msg.set_content(cuerpo)
    msg["Subject"] = asunto
    msg["From"] = smtp_user
    msg["To"] = destino

    try:
        logger.info("SMTP_SEND_START | destino=%s", destino)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Cifra la conexión
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("SMTP_SEND_OK | destino=%s", destino)
        return True
    except Exception as e:
        logger.exception("SMTP_SEND_ERROR | destino=%s | error=%s", destino, str(e))
        return False

def enviar_reset_password(destino: str, reset_url: str) -> bool:
    """Wrapper para mantener compatibilidad con el resto del código."""
    asunto = "SorteoParking — Recuperación de contraseña"
    cuerpo = f"""Hola,

Se solicitó restablecer la contraseña del panel SuperAdmin de SorteoParking.

Para continuar, abre este enlace (válido por 15 minutos):
{reset_url}

Si no solicitaste este cambio, ignora este mensaje.

— SorteoParking"""
    return enviar_correo_texto(destino, asunto, cuerpo)