"""Backup de base de datos (SDD §3.6).

En PostgreSQL (Render): no-op — Render gestiona backups automáticos.
En SQLite (local): backup via SQLite backup API.

El directorio /data NO existe en Render sin un Disk configurado.
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sorteoparking.db")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "./backups"))
RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))


def _es_sqlite() -> bool:
    return "sqlite" in DATABASE_URL.lower()


def _get_db_path() -> Path | None:
    """Devuelve la ruta al archivo SQLite, o None si es PostgreSQL."""
    if not _es_sqlite():
        return None
    return Path(DATABASE_URL.replace("sqlite:///", ""))


def hacer_backup() -> Path | None:
    """Crea backup de la DB SQLite usando SQLite backup API.

    Returns:
        Path del backup creado, o None si es PostgreSQL (no aplica).
    """
    if not _es_sqlite():
        logger.info("PostgreSQL detectado — Render gestiona backups, nada que hacer.")
        return None

    db_path = _get_db_path()
    if db_path is None:
        logger.warning("No se pudo determinar la ruta de la DB SQLite.")
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"sorteoparking_{timestamp}.db"

    # SQLite backup API — consistente con WAL
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    dst.close()
    src.close()

    logger.info(
        "Backup creado: %s (%.2f MB)",
        backup_path.name,
        backup_path.stat().st_size / 1024 / 1024,
    )
    return backup_path


def verificar_backup(path: Path) -> bool:
    """Verifica que el backup es una DB SQLite válida y legible."""
    try:
        conn = sqlite3.connect(str(path))
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.execute("SELECT COUNT(*) FROM tenants").fetchone()
        conn.close()
        ok = result[0] == "ok"
        if ok:
            logger.info("Backup verificado: %s", path.name)
        else:
            logger.error("Backup corrupto: %s — %s", path.name, result[0])
        return ok
    except Exception as e:
        logger.error("Error verificando backup %s: %s", path.name, e)
        return False


def limpiar_backups_antiguos():
    """Retiene solo los últimos RETENTION_DAYS días de backups."""
    if not BACKUP_DIR.exists():
        return

    ahora = datetime.now(timezone.utc).timestamp()
    backups = sorted(
        BACKUP_DIR.glob("sorteoparking_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for backup_antiguo in backups:
        edad_dias = (ahora - backup_antiguo.stat().st_mtime) / 86400
        if edad_dias > RETENTION_DAYS:
            backup_antiguo.unlink()
            logger.info(
                "Backup eliminado: %s (edad: %.1f días)",
                backup_antiguo.name,
                edad_dias,
            )


def ejecutar_ciclo_backup() -> bool:
    """Ciclo completo: backup + verificación + limpieza.

    En PostgreSQL: no hace nada, retorna True (Render gestiona backups).

    Returns:
        True si todo fue exitoso (o si no aplica en PostgreSQL).
    """
    if not _es_sqlite():
        logger.info("PostgreSQL detectado — Render gestiona backups, ciclo omitido.")
        return True

    try:
        path = hacer_backup()
        if path is None:
            return True

        ok = verificar_backup(path)
        if not ok:
            logger.error(
                "Backup falló verificación — conservando archivo para diagnóstico"
            )
            return False
        limpiar_backups_antiguos()
        return True
    except Exception as e:
        logger.error("Ciclo de backup falló: %s", e)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exito = ejecutar_ciclo_backup()
    exit(0 if exito else 1)
