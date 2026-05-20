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
    if not host or not from_addr:
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
        return True
    except (OSError, smtplib.SMTPException) as e:
        logger.warning("Error enviando correo a %s: %s", destino, str(e))
        return False

