"""Servicio de catálogo de parqueaderos. SDD §15."""

from sqlalchemy.orm import Session
import pandas as pd
from io import BytesIO
import logging

from app.models.catalogo import Parqueadero, Zona, Torre
from app.services.excel_parser import parsear_catalogo

logger = logging.getLogger(__name__)


def listar_zonas_por_tenant(db: Session, tenant_id: str) -> list[Zona]:
    """Obtiene las zonas del tenant actual."""
    return db.query(Zona).filter(Zona.tenant_id == tenant_id).order_by(Zona.id.asc()).all()


def listar_parqueaderos_por_tenant(db: Session, tenant_id: str) -> list[Parqueadero]:
    """Obtiene el catalogo de parqueaderos del tenant actual."""
    return (
        db.query(Parqueadero)
        .filter(Parqueadero.tenant_id == tenant_id)
        .order_by(Parqueadero.id.asc())
        .all()
    )


def cargar_catalogo_desde_excel(db: Session, tenant_id: str, archivo_bytes: bytes) -> dict:
    """Carga el catálogo de parqueaderos usando el parser inteligente (SDD §14).

    Primero intenta el parser con IA, si falla o no encuentra estructura,
    usa el método legacy con pandas.
    """
    # Intentar parser inteligente primero
    try:
        resultado_parser = parsear_catalogo(archivo_bytes)
        if resultado_parser["filas_validas"] > 0:
            # Parse exitoso -> leer completa con pandas
            df = pd.read_excel(BytesIO(archivo_bytes), engine="openpyxl")
            # Construir mapa inverso de columnas
            col_map = resultado_parser.get("_columnas_originales", {})
            return _insertar_desde_df(db, tenant_id, df, col_map)
    except Exception as e:
        logger.warning("Parser IA fallo, usando metodo legacy: %s", str(e))

    # Fallback: método legacy (catalogo con hoja "CATALOGO" header=3)
    # Fallback: método legacy (catalogo con hoja "CATALOGO" header=3)
    try:
        df = pd.read_excel(BytesIO(archivo_bytes), sheet_name="CATALOGO", header=3)
    except Exception:
        try:
            df = pd.read_excel(BytesIO(archivo_bytes), engine="openpyxl")
        except Exception:
            df = pd.read_csv(BytesIO(archivo_bytes))

    df = df[~df["numero"].astype(str).str.startswith("TOTAL")]
    df = df.dropna(subset=["numero"])

    return _insertar_desde_df_legacy(db, tenant_id, df)


def _insertar_desde_df(db: Session, tenant_id: str, df: pd.DataFrame, col_map: dict) -> dict:
    """Inserta datos desde DataFrame usando el mapa del parser IA."""
    zonas_creadas = {}
    torres_creadas = {}
    parqueaderos_cargados = 0

    # Mapear columna excel -> nombre esperado
    # col_map es {campo_sistema: nombre_columna_excel}
    def _get(row, campo):
        if campo in col_map:
            col_name = col_map[campo]
            if col_name in row.index:
                return row[col_name]
        return None

    for _, row in df.iterrows():
        raw_numero = _get(row, "numero_parqueadero")
        if raw_numero is None:
            continue
        numero = str(raw_numero).strip()
        if not numero or numero.upper().startswith("TOTAL"):
            continue

        vehiculo = str(_get(row, "tipo_vehiculo") or "CARRO").strip().upper()
        if vehiculo not in ("CARRO", "MOTO"):
            vehiculo = "CARRO"
        zona_nombre = str(_get(row, "zona") or "").strip()
        if not zona_nombre:
            continue
        tipo_espacio = str(_get(row, "tipo_espacio") or "SENCILLO").strip().upper()
        torre_nombre = str(_get(row, "torre") or "").strip() or None
        disponible = _get(row, "disponible")
        if disponible is not None:
            if isinstance(disponible, str):
                disponible = disponible.strip().upper() in ("TRUE", "1", "SI", "SÍ")
            else:
                disponible = bool(disponible)
        else:
            disponible = True
        vecino = str(_get(row, "vecino") or "").strip() or None

        if zona_nombre not in zonas_creadas:
            zona = db.query(Zona).filter(Zona.tenant_id == tenant_id, Zona.nombre == zona_nombre).first()
            if not zona:
                zona = Zona(tenant_id=tenant_id, nombre=zona_nombre)
                db.add(zona)
                db.flush()
            zonas_creadas[zona_nombre] = zona

        zona = zonas_creadas[zona_nombre]
        torre = None
        if torre_nombre:
            key = (zona.id, torre_nombre)
            if key not in torres_creadas:
                torre_obj = db.query(Torre).filter(Torre.tenant_id == tenant_id, Torre.zona_id == zona.id, Torre.nombre == torre_nombre).first()
                if not torre_obj:
                    torre_obj = Torre(tenant_id=tenant_id, zona_id=zona.id, nombre=torre_nombre)
                    db.add(torre_obj)
                    db.flush()
                torres_creadas[key] = torre_obj
            torre = torres_creadas[key]

        pq = Parqueadero(
            tenant_id=tenant_id,
            numero=numero,
            tipo=tipo_espacio,
            vehiculo=vehiculo,
            zona_id=zona.id,
            torre_id=torre.id if torre else None,
            disponible=disponible,
            vecino=vecino,
        )
        db.add(pq)
        parqueaderos_cargados += 1

    db.commit()
    return {
        "zonas_creadas": len(zonas_creadas),
        "torres_creadas": len(torres_creadas),
        "parqueaderos_cargados": parqueaderos_cargados,
    }


def _insertar_desde_df_legacy(db: Session, tenant_id: str, df: pd.DataFrame) -> dict:
    """Método legacy de carga de catálogo."""
    zonas_creadas = {}
    torres_creadas = {}
    parqueaderos_cargados = 0

    for _, row in df.iterrows():
        numero = str(row["numero"]).strip()
        tipo = str(row.get("tipo", "SENCILLO")).strip().upper()
        vehiculo = str(row.get("vehiculo", "CARRO")).strip().upper()
        zona_nombre = str(row["zona"]).strip()
        torre_nombre = str(row.get("torre", "")).strip() or None

        if zona_nombre not in zonas_creadas:
            zona = db.query(Zona).filter(Zona.tenant_id == tenant_id, Zona.nombre == zona_nombre).first()
            if not zona:
                zona = Zona(tenant_id=tenant_id, nombre=zona_nombre)
                db.add(zona)
                db.flush()
            zonas_creadas[zona_nombre] = zona

        zona = zonas_creadas[zona_nombre]
        torre = None
        if torre_nombre:
            key = (zona.id, torre_nombre)
            if key not in torres_creadas:
                torre_obj = db.query(Torre).filter(Torre.tenant_id == tenant_id, Torre.zona_id == zona.id, Torre.nombre == torre_nombre).first()
                if not torre_obj:
                    torre_obj = Torre(tenant_id=tenant_id, zona_id=zona.id, nombre=torre_nombre)
                    db.add(torre_obj)
                    db.flush()
                torres_creadas[key] = torre_obj
            torre = torres_creadas[key]

        # FIX #27: Import disponible and vecino from legacy method
        disponible = str(row.get("disponible", "true")).strip().lower() in ("true", "1", "si", "sí", "verdadero")
        vecino = str(row.get("vecino", "")).strip() or None

        pq = Parqueadero(
            tenant_id=tenant_id,
            numero=numero,
            tipo=tipo,
            vehiculo=vehiculo,
            zona_id=zona.id,
            disponible=disponible,
            vecino=vecino,
            torre_id=torre.id if torre else None,
        )
        db.add(pq)
        parqueaderos_cargados += 1

    db.commit()
    return {
        "zonas_creadas": len(zonas_creadas),
        "torres_creadas": len(torres_creadas),
        "parqueaderos_cargados": parqueaderos_cargados,
    }
