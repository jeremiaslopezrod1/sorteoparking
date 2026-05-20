"""Cliente DeepSeek Flash para parser inteligente. SDD §14."""

import json
import logging
import os
import time
from typing import Any

import urllib.request
import urllib.error

from app.core.config import deepseek_config

logger = logging.getLogger(__name__)


def _analizar_con_ia(prompt_sistema: str, muestra: list[dict]) -> dict[str, Any] | None:
    """
    Envía muestra a DeepSeek Flash y recibe mapa de columnas.
    Retorna None si hay error (para fallback a sinónimos).
    """
    api_key = deepseek_config.api_key
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY no configurada — usando fallback a sinónimos")
        return None

    url = f"{deepseek_config.base_url}/chat/completions"
    payload = {
        "model": deepseek_config.model,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": json.dumps(muestra, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=deepseek_config.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"]

                # Extraer JSON de la respuesta (DeepSeek puede devolver markdown)
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                result = json.loads(content)
                logger.info("DeepSeek Flash respondió con confianza=%.2f", result.get("confianza", 0))
                return result

        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # exponential backoff: 1, 2, 4 seconds
                logger.warning("Intento %d/%d fallo: %s - reintentando en %ds", attempt + 1, max_retries, str(e), wait)
                time.sleep(wait)
            else:
                # Sanitize error messages to avoid leaking API key
                err_msg = str(e)
                if deepseek_config.api_key and deepseek_config.api_key in err_msg:
                    err_msg = err_msg.replace(deepseek_config.api_key, "***")
                logger.warning("Error llamando a DeepSeek Flash tras %d intentos: %s — usando fallback a sinónimos", max_retries, err_msg)
                return None


def analizar_catalogo(muestra: list[dict]) -> dict[str, Any] | None:
    """
    Analiza muestra de catálogo de parqueaderos con DeepSeek Flash.
    SDD §14.4 — Prompt para catálogo.
    """
    prompt = """Eres un analizador de estructuras de Excel para el sistema SorteoParking. Analiza los encabezados y la muestra de datos proporcionados y devuelve SOLO un JSON válido con el mapa de columnas para un catálogo de parqueaderos.

Campos obligatorios a identificar:
- numero_parqueadero: identificador único del parqueadero (P-001, C001, etc.)
- tipo_vehiculo: CARRO o MOTO (puede estar en variantes)
- zona: sector geográfico del conjunto (A, B, C, D o nombres completos)

Campos opcionales:
- torre: número o nombre de la torre
- tipo_espacio: SENCILLO, DOBLE, TANDEM, CUBIERTO, DESCUBIERTO
- disponible: true/false
- vecino: número del parqueadero adyacente (para dobles)

Responde ÚNICAMENTE con este JSON. Sin explicaciones.
{
  "mapa_columnas": { "columna_excel": "campo_sistema" },
  "reglas_limpieza": { "campo_sistema": "descripción de limpieza" },
  "patrones_ignorar": ["descripción"],
  "confianza": 0.95,
  "campos_obligatorios_encontrados": ["numero_parqueadero", "tipo_vehiculo", "zona"],
  "campos_obligatorios_faltantes": [],
  "advertencias": []
}"""
    return _analizar_con_ia(prompt, muestra)


def analizar_elegibles(muestra: list[dict]) -> dict[str, Any] | None:
    """
    Analiza muestra de elegibles con DeepSeek Flash.
    SDD §14.4 — Prompt para elegibles.
    """
    prompt = """Eres un analizador de estructuras de Excel para el sistema SorteoParking. Analiza los encabezados y la muestra de datos y devuelve SOLO un JSON válido con el mapa de columnas para una lista de participantes elegibles al sorteo.

Campos obligatorios a identificar:
- apartamento: identificador del apartamento (T01-101, 101, etc.)
- tipo_vehiculo: CARRO o MOTO

Campos opcionales:
- nombre: nombre del residente
- documento: número de identificación
- email: correo electrónico
- es_hatchback: true/false (para carros pequeños)

Responde ÚNICAMENTE con este JSON. Sin explicaciones.
{
  "mapa_columnas": { "columna_excel": "campo_sistema" },
  "reglas_limpieza": { "campo_sistema": "descripción de limpieza" },
  "patrones_ignorar": ["descripción"],
  "confianza": 0.95,
  "campos_obligatorios_encontrados": ["apartamento", "tipo_vehiculo"],
  "campos_obligatorios_faltantes": [],
  "advertencias": []
}"""
    return _analizar_con_ia(prompt, muestra)
