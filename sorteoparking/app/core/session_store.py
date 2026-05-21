"""Almacenamiento de sesiones (SDD §13.11).

Usa la MISMA base de datos que la app principal (PostgreSQL o SQLite).
NO crea archivo SQLite separado — eso rompia en Render por filesystem read-only.
"""

import hashlib
import hmac
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

_SessionBase = declarative_base()


class AdminSession(_SessionBase):
    """Tabla admin_sessions (SDD §13.11).
    
    Se crea en la misma DB que las demas tablas (PostgreSQL o SQLite).
    """

    __tablename__ = "admin_sessions"

    session_id = Column(Text, primary_key=True)
    token_hash = Column(Text, nullable=False)  # SHA-256 del SUPER_ADMIN_TOKEN
    csrf_token = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


def init_session_table(engine) -> None:
    """Crea la tabla admin_sessions en la BD principal.
    
    Debe llamarse durante startup, despues de crear el engine.
    """
    try:
        _SessionBase.metadata.create_all(bind=engine)
        logger.info("Tabla admin_sessions verificada/creada")
    except Exception as e:
        logger.warning("No se pudo crear admin_sessions: %s", e)


class SessionStore:
    """Almacenamiento de sesiones en la BD principal.

    Singleton. Usa la misma conexion que el resto de la app.
    El engine se inyecta via configure() antes del primer uso.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SessionStore, cls).__new__(cls)
                    cls._instance._engine = None
                    cls._instance._Session = None
        return cls._instance

    def configure(self, engine) -> None:
        """Inyecta el engine de la BD principal (PostgreSQL o SQLite).
        
        Debe llamarse durante startup, despues de crear el engine.
        """
        self._engine = engine
        self._Session = sessionmaker(bind=engine)
        try:
            self._limpiar_expiradas()
        except Exception:
            pass
        self.schedule_cleanup()

    def _get_db(self):
        """Crea una nueva sesion SQLAlchemy."""
        if self._Session is None:
            logger.error("SessionStore._get_db() llamado sin configure(engine) previo")
            raise RuntimeError("SessionStore no configurado. Llamar configure(engine) en startup.")
        try:
            return self._Session()
        except Exception as e:
            logger.error("SessionStore._get_db() error creando sesion: %s", e)
            raise

    def create_session(self, session_id: str, token: str, csrf_token: str = "") -> None:
        """Asocia un ID de sesion con un SUPER_ADMIN_TOKEN."""
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not csrf_token:
            csrf_token = token_hash[:32]

        db = None
        try:
            db = self._get_db()
            db.query(AdminSession).filter(
                AdminSession.token_hash == token_hash,
                AdminSession.revoked_at.is_(None),
            ).update({"revoked_at": datetime.now(timezone.utc)})

            ses = AdminSession(
                session_id=session_id,
                token_hash=token_hash,
                csrf_token=csrf_token,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
            )
            db.add(ses)
            db.commit()
            logger.info("Sesion creada: %s (expira en 60 min)", session_id[:8])
        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error("Error creando sesion: %s", e)
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def get_session(self, session_id: str) -> Optional[str]:
        """Recupera el token_hash asociado a una sesion."""
        db = None
        try:
            db = self._get_db()
            ses = db.query(AdminSession).filter(
                AdminSession.session_id == session_id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > datetime.now(timezone.utc),
            ).first()
            if ses:
                return ses.token_hash
            return None
        except Exception as e:
            logger.error("Error leyendo sesion: %s", e)
            return None
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def validate_csrf(self, session_id: str, csrf_header: str) -> bool:
        """Valida el token CSRF contra el almacenado en BD."""
        if not csrf_header:
            return False
        db = None
        try:
            db = self._get_db()
            ses = db.query(AdminSession).filter(
                AdminSession.session_id == session_id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > datetime.now(timezone.utc),
            ).first()
            if ses:
                return hmac.compare_digest(ses.csrf_token, csrf_header)
            return False
        except Exception as e:
            logger.error("Error validando CSRF: %s", e)
            return False
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def delete_session(self, session_id: str) -> None:
        """Revoca una sesion."""
        db = None
        try:
            db = self._get_db()
            db.query(AdminSession).filter(
                AdminSession.session_id == session_id
            ).update({"revoked_at": datetime.now(timezone.utc)})
            db.commit()
        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error("Error revocando sesion: %s", e)
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def _limpiar_expiradas(self):
        """Elimina sesiones expiradas o revocadas."""
        db = None
        try:
            db = self._get_db()
            deleted = db.query(AdminSession).filter(
                (AdminSession.expires_at < datetime.now(timezone.utc))
                | (AdminSession.revoked_at.isnot(None))
            ).delete()
            db.commit()
            if deleted:
                logger.info("Limpieza: %d sesiones eliminadas", deleted)
        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error("Error limpiando sesiones: %s", e)
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass


    def schedule_cleanup(self):
        """Run periodic cleanup of expired sessions."""
        import threading
        import time
        def _cleanup_loop():
            while True:
                time.sleep(3600)  # every hour
                try:
                    self._limpiar_expiradas()
                except Exception:
                    pass
        t = threading.Thread(target=_cleanup_loop, daemon=True)
        t.start()


session_store = SessionStore()
