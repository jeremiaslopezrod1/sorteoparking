"""Modelos de SuperAdmin (SDD v2.1).

- SuperAdmin: tokens de acceso SUPER_ADMIN.
- PasswordResetToken: tokens de recuperación de contraseña (T-315).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Integer, Text
from sqlalchemy.orm import Session as OrmSession

from app.db.database import Base


# ── SuperAdmin ───────────────────────────────────────────────────


class SuperAdmin(Base):
    """Tabla que almacena tokens de acceso SUPER_ADMIN.

    Cada fila representa un token activo.
    """

    __tablename__ = "superadmins"

    id = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    token = Column(Text, unique=True, nullable=False, index=True)
    descripcion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    revocado_at = Column(DateTime, nullable=True)


# ── Password Reset Tokens ────────────────────────────────────────


class PasswordResetToken(Base):
    """Token de recuperación de contraseña para SUPER_ADMIN (SSD v2.1 T-315).

    Un solo uso, expira en 30 minutos.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False)
    token_hash = Column(Text, nullable=False)  # SHA-256 del token
    expires_at = Column(DateTime, nullable=False)  # now() + 30 min
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @staticmethod
    def generar(email: str, db: OrmSession) -> str:
        """Genera un token de reset, invalida anteriores y retorna el token plano.

        Args:
            email: correo del SuperAdmin
            db: sesión SQLAlchemy

        Returns:
            token plano (para incluir en la URL del correo)
        """
        # Invalidar tokens anteriores del mismo email
        db.query(PasswordResetToken).filter(
            PasswordResetToken.email == email,
            PasswordResetToken.used_at.is_(None),
        ).update({"used_at": datetime.now(timezone.utc)})

        # Generar nuevo token
        token_plano = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token_plano.encode("utf-8")).hexdigest()

        reset = PasswordResetToken(
            email=email,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(reset)
        db.commit()

        return token_plano

    @staticmethod
    def validar(token_plano: str, db: OrmSession) -> str | None:
        """Valida un token de reset. Retorna el email si es válido, None si no.

        Marca el token como usado si es válido.
        """
        import hmac as hmac_mod

        token_hash = hashlib.sha256(token_plano.encode("utf-8")).hexdigest()

        now = datetime.now(timezone.utc)
        registros = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        ).all()

        if not registros:
            return None

        # Usar hmac.compare_digest para comparación segura
        for registro in registros:
            if hmac_mod.compare_digest(registro.token_hash, token_hash):
                # Marcar como usado
                registro.used_at = datetime.now(timezone.utc)
                db.commit()
                return registro.email

        return None
