from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text

from app.db.database import Base


class Sorteo(Base):
    __tablename__ = "sorteos"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    estado = Column(Text, nullable=False)
    seed = Column(Text, nullable=True)
    tipo = Column(Text, nullable=True) # CARRO / MOTO
    modelo_aplicado = Column(Text, nullable=True) # HIBRIDO / MANUAL
    snapshot_hash = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Participante(Base):
    __tablename__ = "participantes"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    sorteo_id = Column(Integer, ForeignKey("sorteos.id"), nullable=True, index=True)
    nombre = Column(Text, nullable=False)
    documento = Column(Text, nullable=False)
    apartamento = Column(Text, nullable=True)
    es_hatchback = Column(Boolean, default=False)
    tipo_vehiculo = Column(Text, nullable=False, default="CARRO") # CARRO / MOTO
    email = Column(Text, nullable=True)


class Consejero(Base):
    __tablename__ = "consejeros"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    sorteo_id = Column(Integer, ForeignKey("sorteos.id"), nullable=True, index=True)
    nombre = Column(Text, nullable=False)
    email = Column(Text, nullable=True)


class SesionOTP(Base):
    __tablename__ = "sesiones_otp"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    sorteo_id = Column(Integer, ForeignKey("sorteos.id"), nullable=False)
    consejero_id = Column(Integer, ForeignKey("consejeros.id"), nullable=False)
    otp_hash = Column(Text, nullable=False)
    token_enlace = Column(Text, unique=True, nullable=False, index=True)
    estado = Column(Text, nullable=False)
    expira_en = Column(DateTime, nullable=False)
    confirmado_en = Column(DateTime, nullable=True)
    intentos = Column(Integer, default=0, nullable=False)
    invalidado = Column(Boolean, default=False)


class ResultadoSorteo(Base):
    __tablename__ = "resultados_sorteo"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    sorteo_id = Column(Integer, ForeignKey("sorteos.id"), nullable=False)
    participante_id = Column(Integer, ForeignKey("participantes.id"), nullable=False)
    apartamento = Column(Text, nullable=True)
    tipo_resultado = Column(Text, nullable=False) # GANADOR / PERDEDOR
    parqueadero_asignado = Column(Text, nullable=True) # Numero
    zona_asignada = Column(Text, nullable=True)
    fue_reasignado = Column(Boolean, default=False)

