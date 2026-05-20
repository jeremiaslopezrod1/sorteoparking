from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text

from app.db.database import Base


class Zona(Base):
    __tablename__ = "zonas"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(Text, nullable=False)


class Torre(Base):
    __tablename__ = "torres"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    zona_id = Column(Integer, ForeignKey("zonas.id"), nullable=False)
    nombre = Column(Text, nullable=False)


class Parqueadero(Base):
    __tablename__ = "parqueaderos"

    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False, index=True)
    id = Column(Integer, primary_key=True, autoincrement=True)
    numero = Column(Text, nullable=False)
    tipo = Column(Text, nullable=False)  # SENCILLO / DOBLE
    vehiculo = Column(Text, nullable=False, default="CARRO") # CARRO / MOTO
    zona_id = Column(Integer, ForeignKey("zonas.id"), nullable=False)
    torre_id = Column(Integer, ForeignKey("torres.id"), nullable=True)
    disponible = Column(Boolean, default=True)
    vecino = Column(Text, nullable=True) # Numero del parqueadero vecino para tandem
