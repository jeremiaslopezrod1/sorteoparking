from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text

from app.db.database import Base


class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    evento = Column(Text, nullable=False)
    payload = Column(Text, nullable=True)
    hash_anterior = Column(Text, nullable=True)
    hash_actual = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
