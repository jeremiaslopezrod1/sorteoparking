"""Tokens de recuperación de contraseña para SuperAdmin.

- password_reset_tokens: tokens de un solo uso, expiran en 15 min.
- superadmin_credentials: almacena el password_hash en BD (single row).
  login_superadmin lee de aquí primero; si no existe, usa env var.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Column, DateTime, Text
from sqlalchemy.orm import Session as OrmSession

from app.db.database import Base

# ── Password Reset Tokens ────────────────────────────────────────


class PasswordResetToken(Base):
    """Token de recuperación de contraseña (un solo uso, 15 min)."""

    __tablename__ = "password_reset_tokens"

    id = Column(Text, primary_key=True)
    email = Column(Text, nullable=False, index=True)
    token_hash = Column(Text, nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
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
            PasswordResetToken.used == False,  # noqa: E712
        ).update({"used": True})

        # Generar nuevo token
        token_plano = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(token_plano.encode("utf-8")).hexdigest()

        reset = PasswordResetToken(
            id=token_hash[:32],  # primeros 32 chars del hash como PK
            email=email,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db.add(reset)
        db.commit()

        return token_plano

    @staticmethod
    def validar(token_plano: str, db: OrmSession) -> str | None:
        """Valida un token de reset. Retorna el email si es válido, None si no.

        Marca el token como usado si es válido.
        """
        token_hash = hashlib.sha256(token_plano.encode("utf-8")).hexdigest()

        registro = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        ).first()

        if not registro:
            return None

        # Marcar como usado
        registro.used = True
        db.commit()

        return registro.email


# ── SuperAdmin Credentials ───────────────────────────────────────


class SuperAdminCredentials(Base):
    """Credenciales del SuperAdmin almacenadas en BD.

    Single-row table: siempre id="singleton".
    login_superadmin consulta aquí primero; si no existe, usa env var.
    """

    __tablename__ = "superadmin_credentials"

    id = Column(Text, primary_key=True, default="singleton")
    email = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @staticmethod
    def obtener(db: OrmSession) -> "SuperAdminCredentials | None":
        """Obtiene la fila singleton de credenciales."""
        return db.query(SuperAdminCredentials).filter(
            SuperAdminCredentials.id == "singleton"
        ).first()

    @staticmethod
    def guardar_o_actualizar(email: str, password_hash: str, db: OrmSession) -> None:
        """Crea o actualiza la fila singleton."""
        existente = SuperAdminCredentials.obtener(db)
        if existente:
            existente.email = email
            existente.password_hash = password_hash
            existente.updated_at = datetime.now(timezone.utc)
        else:
            nueva = SuperAdminCredentials(
                id="singleton",
                email=email,
                password_hash=password_hash,
            )
            db.add(nueva)
        db.commit()
