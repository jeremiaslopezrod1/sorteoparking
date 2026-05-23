from datetime import datetime, timezone
import sqlite3
import shutil
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/data/backups"))
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./sorteoparking.db")
RETENTION_DAYS = int(os.getenv(
    "BACKUP_RETENTION_DAYS", "30"))


def _es_sqlite() -> bool:
    """Detecta si la BD es SQLite."""
    return "sqlite" in DB_URL.lower()


def _es_postgresql() -> bool:
    """Detecta si la BD es PostgreSQL."""
    return "postgresql" in DB_URL.lower() or DB_URL.startswith("postgres://")


def _get_db_path() -> Path | None:
    """Extrae ruta de SQLite desde DATABASE_URL."""
    if not _es_sqlite():
        return None
    return Path(DB_URL.replace("sqlite:///", ""))


def hacer_backup() -> bool:
    """
    Crea backup según el motor de BD.
    
    - SQLite: Usa SQLite backup API (consistente con WAL)
    - PostgreSQL: Render gestiona backups automáticos
    
    Returns:
        True si el backup fue exitoso o gestionado por plataforma.
        False si hubo error.
    """
    # PostgreSQL en Render — backups automáticos
    if _es_postgresql():
        logger.info(
            "PostgreSQL detectado — backups gestionados automáticamente por Render. "
            "SDD §3.6 migración PostgreSQL."
        )
        return True
    
    # SQLite — backup local con SQLite backup API
    if not _es_sqlite():
        logger.error("Motor de BD no identificado: %s", DB_URL)
        return False
    
    return _backup_sqlite()


def _backup_sqlite() -> bool:
    """
    Crea backup de sorteoparking.db usando SQLite backup API.
    Seguro incluso con WAL activo y conexiones abiertas.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Obtener ruta de la BD
    db_path = _get_db_path()
    if not db_path:
        logger.error("No se pudo extraer ruta de SQLite desde DATABASE_URL: %s", DB_URL)
        return False
    
    if not db_path.exists():
        logger.error("Archivo SQLite no existe: %s", db_path)
        return False
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"sorteoparking_{timestamp}.db"
    
    try:
        # SQLite backup API — consistente con WAL
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(backup_path))
        src.backup(dst)
        dst.close()
        src.close()
        
        logger.info(
            "Backup SQLite creado: %s (%.2f MB)",
            backup_path.name,
            backup_path.stat().st_size / 1024 / 1024
        )
        return True
    except Exception as e:
        logger.error("Error creando backup SQLite: %s", e)
        return False


def verificar_backup(path: Path) -> bool:
    """
    Verifica que el backup SQLite es válido y legible.
    (Solo aplica para SQLite — PostgreSQL se verifica en la plataforma)
    """
    if not _es_sqlite():
        logger.info("PostgreSQL — verificación de backup omitida")
        return True
    
    try:
        conn = sqlite3.connect(str(path))
        result = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()
        conn.execute(
            "SELECT COUNT(*) FROM tenants"
        ).fetchone()
        conn.close()
        ok = result[0] == "ok"
        if ok:
            logger.info(
                "Backup SQLite verificado: %s", 
                path.name
            )
        else:
            logger.error(
                "Backup SQLite corrupto: %s — %s",
                path.name, result[0]
            )
        return ok
    except Exception as e:
        logger.error(
            "Error verificando backup SQLite %s: %s",
            path.name, e
        )
        return False


def limpiar_backups_antiguos():
    """
    Retiene solo los últimos RETENTION_DAYS días de backups SQLite.
    (Solo aplica para SQLite — PostgreSQL lo gestiona Render)
    """
    if not _es_sqlite():
        logger.info("PostgreSQL — limpieza de backups omitida")
        return
    
    if not BACKUP_DIR.exists():
        return
    
    ahora = datetime.now(timezone.utc).timestamp()
    backups = sorted(
        BACKUP_DIR.glob("sorteoparking_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    for backup_antiguo in backups:
        edad_dias = (ahora - backup_antiguo.stat().st_mtime) / 86400
        if edad_dias > RETENTION_DAYS:
            backup_antiguo.unlink()
            logger.info("Backup SQLite eliminado: %s (edad: %.1f días)", 
                       backup_antiguo.name, edad_dias)


def ejecutar_ciclo_backup() -> bool:
    """
    Ciclo completo de backup según motor de BD.
    
    - PostgreSQL: Solo logging (Render gestiona)
    - SQLite: backup + verificación + limpieza
    
    Retorna True si todo fue exitoso.
    """
    try:
        # Hacer backup (SQLite o PostgreSQL)
        backup_ok = hacer_backup()
        if not backup_ok:
            logger.error("Ciclo de backup falló: hacer_backup() retornó False")
            return False
        
        # Si es PostgreSQL, ya terminamos
        if _es_postgresql():
            return True
        
        # Para SQLite: verificar y limpiar
        db_path = _get_db_path()
        if not db_path:
            logger.error("No se pudo obtener ruta de BD SQLite")
            return False
        
        # Buscar el backup más reciente
        backups = sorted(
            BACKUP_DIR.glob("sorteoparking_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not backups:
            logger.error("No se encontró backup reciente para verificar")
            return False
        
        latest_backup = backups[0]
        
        # Verificar backup
        ok = verificar_backup(latest_backup)
        if not ok:
            logger.error(
                "Backup falló verificación — "
                "conservando archivo para diagnóstico"
            )
            return False
        
        # Limpiar backups antiguos
        limpiar_backups_antiguos()
        
        logger.info("Ciclo de backup SQLite completado exitosamente")
        return True
        
    except Exception as e:
        logger.error("Ciclo de backup falló: %s", e)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exito = ejecutar_ciclo_backup()
    exit(0 if exito else 1)
