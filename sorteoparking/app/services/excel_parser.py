"""Parser inteligente de Excel. SDD §14 — T-108."""

import io
import logging
import os
import threading
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.services.deepseek_service import analizar_catalogo, analizar_elegibles

logger = logging.getLogger(__name__)

# SDD §14.10 — Limites de seguridad
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 50_000
PARSE_TIMEOUT = 15  # segundos

# Mapa de sinonimos para fallback sin DeepSeek (SDD §14.5)
SINONIMOS_CATALOGO: dict[str, list[str]] = {
    "numero_parqueadero": ["numero", "numero", "parqueadero", "puesto", "cupo", "id", "codigo", "codigo"],
    "tipo_vehiculo": ["tipo", "vehiculo", "vehiculo", "tipo_vehiculo", "tipo de vehiculo", "auto", "moto"],
    "zona": ["zona", "bloque", "sector", "area", "area"],
    "torre": ["torre", "edificio", "bloque", "torre_numero"],
    "tipo_espacio": ["tipo_espacio", "espacio", "tipo espacio", "clase"],
    "disponible": ["disponible", "activo", "habilitado"],
    "vecino": ["vecino", "adyacente", "doble", "tandem", "pareja"],
}

SINONIMOS_ELEGIBLES: dict[str, list[str]] = {
    "apartamento": ["apartamento", "apto", "unidad", "vivienda", "piso", "apt"],
    "tipo_vehiculo": ["tipo_vehiculo", "tipo", "vehiculo", "vehiculo", "tipo de vehiculo", "auto", "moto"],
    "nombre": ["nombre", "propietario", "residente", "titular", "conductor"],
    "documento": ["documento", "cedula", "cedula", "identificacion", "id", "cc"],
    "email": ["email", "correo", "e-mail", "mail"],

    "es_hatchback": ["hatchback", "es_hatchback", "hatch", "es hatchback", "carro pequeno"],
}


def _sanitizar_muestra_estructural(df_muestra: pd.DataFrame) -> list[dict]:
    """SDD §14.3b — Sanitizacion estructural obligatoria (Ley 1581/2012).

    TODO(FIX #29): Extender tipo-handling para datetime.time, decimal.Decimal,
    numpy dtypes (int64, float64), y objetos complejos que puedan aparecer en Excel.
    """
    resultado = []
    for _, fila in df_muestra.iterrows():
        fila_sanitizada = {}
        for col, valor in fila.items():
            if pd.isna(valor):
                fila_sanitizada[col] = "[VACIO]"
            elif isinstance(valor, bool):
                fila_sanitizada[col] = "[BOOL]"
            elif isinstance(valor, (int, float)):
                fila_sanitizada[col] = "[NUMERO]"
            elif isinstance(valor, pd.Timestamp):
                fila_sanitizada[col] = "[FECHA]"
            else:
                fila_sanitizada[col] = "[TEXTO]"
        resultado.append(fila_sanitizada)
    return resultado


def _resolver_sinonimos(columnas: list[str], sinonimos: dict[str, list[str]]) -> dict[str, str]:
    """Fallback a sinonimos basicos (SDD §14.5)."""
    mapa: dict[str, str] = {}
    col_lower = {c: c.lower().strip().replace(" ", "").replace("_", "").replace("-", "") for c in columnas}

    for campo_sistema, variaciones in sinonimos.items():
        for var in variaciones:
            var_key = var.lower().strip().replace(" ", "").replace("_", "").replace("-", "")
            for col_orig, col_key in col_lower.items():
                if var_key == col_key:
                    mapa[col_orig] = campo_sistema
                    break
    return mapa


def _leer_excel_seguro(contenido: bytes, tipo: str) -> pd.DataFrame:
    """Lee Excel con limites de seguridad. Compatible Windows/Linux.

    NOTE(FIX #29): Solo analiza la primera hoja del archivo Excel/CSV.
    Si se necesitan múltiples hojas, extender este parser.
    """
    resultado = []
    exception = [None]

    def _leer():
        try:
            if tipo == "csv":
                df = pd.read_csv(io.BytesIO(contenido), nrows=MAX_ROWS)
            else:
                df = pd.read_excel(
                    io.BytesIO(contenido),
                    nrows=MAX_ROWS,
                    engine="openpyxl",
                )
            if len(df) >= MAX_ROWS:
                exception[0] = HTTPException(status_code=413, detail=f"El archivo excede {MAX_ROWS} filas.")
                return
            resultado.append(df)
        except MemoryError:
            exception[0] = HTTPException(status_code=503, detail="Archivo demasiado complejo para procesar.")
        except Exception as e:
            exception[0] = e

    hilo = threading.Thread(target=_leer, daemon=True)
    hilo.start()
    hilo.join(timeout=PARSE_TIMEOUT)

    if hilo.is_alive():
        logger.warning("Excel parser timeout after %ds", PARSE_TIMEOUT)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="El archivo Excel tardó demasiado en procesarse",
        )

    if exception[0]:
        if isinstance(exception[0], HTTPException):
            raise exception[0]
        raise HTTPException(status_code=400, detail=f"Error procesando archivo: {str(exception[0])}")

    return resultado[0]


def _aplicar_mapa(df: pd.DataFrame, mapa_columnas: dict[str, str]) -> tuple[pd.DataFrame, list[dict]]:
    """Renombra columnas segun el mapa y registra ignoradas."""
    ignoradas = []
    rename_map = {}
    for col_excel, campo_sistema in mapa_columnas.items():
        if col_excel in df.columns:
            rename_map[col_excel] = campo_sistema

    for col in df.columns:
        if col not in rename_map:
            ignoradas.append({"columna": col, "razon": "no identificada por el parser"})

    df = df.rename(columns=rename_map)
    return df, ignoradas


async def validar_archivo(archivo: UploadFile) -> bytes:
    """SDD §14.10 — Valida tamano y lee archivo."""
    contenido = await archivo.read(MAX_FILE_SIZE + 1)
    if len(contenido) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande. Maximo 5 MB.")
    return contenido


def parsear_catalogo(contenido: bytes) -> dict[str, Any]:
    """Parser de catalogo de parqueaderos. SDD §15."""
    df = _leer_excel_seguro(contenido, "excel")

    muestra = _sanitizar_muestra_estructural(df.head(5))
    resultado_ia = analizar_catalogo(muestra)

    mapa_columnas: dict[str, str] = {}
    confianza = 0.0
    advertencias: list[str] = []
    patrones_ignorar: list[str] = []

    if resultado_ia and resultado_ia.get("confianza", 0) >= deepseek_min_confidence():
        mapa_columnas = resultado_ia["mapa_columnas"]
        confianza = resultado_ia.get("confianza", 0.95)
        advertencias = resultado_ia.get("advertencias", [])
        patrones_ignorar = resultado_ia.get("patrones_ignorar", [])
        logger.info("Parser IA: confianza=%.2f, mapa=%s", confianza, mapa_columnas)
    else:
        logger.info("Parser IA no disponible o baja confianza — usando fallback a sinonimos")
        mapa_columnas = _resolver_sinonimos(list(df.columns), SINONIMOS_CATALOGO)
        confianza = 0.5
        advertencias.append("Parser automatico usado (sin IA) — verifique las columnas manualmente")

    campos_obligatorios = ["numero_parqueadero", "tipo_vehiculo", "zona"]
    encontrados = [c for c in campos_obligatorios if c in mapa_columnas.values()]
    faltantes = [c for c in campos_obligatorios if c not in mapa_columnas.values()]

    if faltantes:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "No se pudo identificar la estructura del archivo",
                "campos_faltantes": faltantes,
                "confianza": confianza,
                "sugerencia": "Use la plantilla descargable en GET /catalogo/plantilla",
            },
        )

    mapa_filtrado = {
        k: v for k, v in mapa_columnas.items()
        if v in campos_obligatorios + ["torre", "tipo_espacio", "disponible", "vecino"]
    }
    columnas_originales = {v: k for k, v in mapa_filtrado.items()}
    df_mapped, cols_ignoradas = _aplicar_mapa(df, mapa_filtrado)
    advertencias.extend([f"Columna ignorada: {c['columna']}" for c in cols_ignoradas])

    before = len(df_mapped)
    if "numero_parqueadero" in df_mapped.columns:
        df_mapped = df_mapped[~df_mapped["numero_parqueadero"].astype(str).str.upper().str.startswith("TOTAL")]
        df_mapped = df_mapped.dropna(subset=["numero_parqueadero"])
    after = len(df_mapped)
    ignoradas_count = before - after

    return {
        "columnas": list(df_mapped.columns),
        "filas_validas": after,
        "filas_ignoradas": ignoradas_count,
        "confianza": confianza,
        "_columnas_originales": columnas_originales,
        "campos_obligatorios_encontrados": encontrados,
        "campos_obligatorios_faltantes": faltantes,
        "advertencias": advertencias,
        "resumen": {
            "carros": int(df_mapped[df_mapped.get("tipo_vehiculo", "").astype(str).str.upper() == "CARRO"].shape[0]) if "tipo_vehiculo" in df_mapped.columns else 0,
            "motos": int(df_mapped[df_mapped.get("tipo_vehiculo", "").astype(str).str.upper() == "MOTO"].shape[0]) if "tipo_vehiculo" in df_mapped.columns else 0,
            "zonas": list(df_mapped["zona"].unique()) if "zona" in df_mapped.columns else [],
        },
    }


def deepseek_min_confidence() -> float:
    """Confianza minima para aceptar resultado de IA (SDD §14.4)."""
    try:
        return float(os.getenv("DEEPSEEK_MIN_CONFIDENCE", "0.80"))
    except ValueError:
        return 0.80


def parsear_elegibles(contenido: bytes) -> dict[str, Any]:
    """Parser de elegibles (participantes). SDD §14."""
    df = _leer_excel_seguro(contenido, "excel")

    muestra = _sanitizar_muestra_estructural(df.head(5))
    resultado_ia = analizar_elegibles(muestra)

    mapa_columnas: dict[str, str] = {}
    confianza = 0.0
    advertencias: list[str] = []
    patrones_ignorar: list[str] = []

    if resultado_ia and resultado_ia.get("confianza", 0) >= deepseek_min_confidence():
        mapa_columnas = resultado_ia["mapa_columnas"]
        confianza = resultado_ia.get("confianza", 0.95)
        advertencias = resultado_ia.get("advertencias", [])
        patrones_ignorar = resultado_ia.get("patrones_ignorar", [])
    else:
        mapa_columnas = _resolver_sinonimos(list(df.columns), SINONIMOS_ELEGIBLES)
        confianza = 0.5
        advertencias.append("Parser automatico usado (sin IA) — verifique las columnas manualmente")

    campos_obligatorios = ["apartamento", "tipo_vehiculo"]
    encontrados = [c for c in campos_obligatorios if c in mapa_columnas.values()]
    faltantes = [c for c in campos_obligatorios if c not in mapa_columnas.values()]

    if faltantes:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "No se pudo identificar la estructura del archivo",
                "campos_faltantes": faltantes,
                "confianza": confianza,
                "sugerencia": "Verifique que el Excel tenga columnas de apartamento y tipo de vehiculo",
            },
        )

    return {
        "mapa_columnas": mapa_columnas,
        "confianza": confianza,
        "advertencias": advertencias,
        "patrones_ignorar": patrones_ignorar,
    }
