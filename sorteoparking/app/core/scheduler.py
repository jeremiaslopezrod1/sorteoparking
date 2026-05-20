import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def scheduler_diario(
    hora_utc: int, 
    tarea,
    nombre: str
):
    """
    Ejecuta una tarea diariamente a la 
    hora_utc especificada.
    Liviano — sin Redis ni Celery.
    """
    while True:
        ahora = datetime.now(timezone.utc)
        # Calcular segundos hasta próxima 
        # ejecución
        proxima = ahora.replace(
            hour=hora_utc,
            minute=0,
            second=0,
            microsecond=0
        )
        if proxima <= ahora:
            proxima = proxima.replace(
                day=proxima.day + 1
            )
        
        espera = (proxima - ahora).total_seconds()
        logger.info(
            "Próximo %s en %.1f horas",
            nombre, espera / 3600
        )
        await asyncio.sleep(espera)
        
        try:
            logger.info("Ejecutando %s...", nombre)
            tarea()
            logger.info("%s completado", nombre)
        except Exception as e:
            logger.error(
                "%s falló: %s", nombre, e
            )
