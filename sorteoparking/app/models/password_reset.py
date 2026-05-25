"""Credenciales de SuperAdmin almacenadas en BD.

- superadmin_credentials: almacena el password_hash en BD (single row).
  login_superadmin lee de aquí primero; si no existe, usa env var.
- PasswordResetToken: movido a app.models.superadmin (SSD v2.1 T-315).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Text
from sqlalchemy.orm import Session as OrmSession

from app.db.database import Base


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
