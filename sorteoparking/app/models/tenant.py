from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, Integer, Text

from app.db.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    slug = Column(Text, unique=True, nullable=True, index=True)
    nombre = Column(Text, nullable=False)
    nit = Column(Text, unique=True, nullable=True)
    municipio = Column(Text, nullable=False)
    email_admin = Column(Text, nullable=False)
    estado = Column(Enum("ACTIVO", "SUSPENDIDO", "DEMO", name="tenant_estado"), default="ACTIVO")
    plan = Column(Enum("POR_EVENTO", name="tenant_plan"), default="POR_EVENTO")
    total_unidades = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
