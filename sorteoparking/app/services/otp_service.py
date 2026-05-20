"""Generación y verificación de OTP (SHA-256). SDD §6.2, agents.md."""

import hashlib
import secrets

from app.core.config import otp_config


def generar_otp_numerico_seis_digitos() -> str:
    """OTP de 6 digitos para ingreso desde celular (coherente con panel OTP)."""
    return f"{secrets.randbelow(900000) + 100000:d}"


def hashear_otp(otp_plano: str) -> str:
    """Hash SHA-256 del OTP con pepper; nunca almacenar el OTP en claro."""
    base = f"{otp_config.pepper}|{otp_plano}".encode("utf-8")
    return hashlib.sha256(base).hexdigest()


def verificar_otp(otp_plano: str, otp_hash: str) -> bool:
    """Compara el OTP ingresado con el hash almacenado."""
    return secrets.compare_digest(hashear_otp(otp_plano), otp_hash)

