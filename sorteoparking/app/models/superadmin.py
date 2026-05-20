from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Text

from app.db.database import Base


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
