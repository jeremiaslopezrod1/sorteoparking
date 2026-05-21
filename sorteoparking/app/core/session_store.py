"""Almacenamiento de sesiones en SQLite (SDD §13.11).

En v1.5 las sesiones se persisten en SQLite en lugar de diccionario en memoria.
Esto permite que los reinicios de Railway no invaliden sesiones activas.
"""

import hashlib
import hmac
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

_SessionBase = declarative_base()


class AdminSession(_SessionBase):
    """Tabla admin_sessions (SDD §13.11)."""

    __tablename__ = "admin_sessions"

    session_id = Column(Text, primary_key=True)
    token_hash = Column(Text, nullable=False)  # SHA-256 del SUPER_ADMIN_TOKEN
    csrf_token = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class SessionStore:
    """Almacenamiento de sesiones en SQLite.

    Singleton. Crea su propia base de datos SQLite para no depender
    de la base de datos principal del sistema.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SessionStore, cls).__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        """Inicializa la base de datos de sesiones."""
        # Render: /data/ persiste entre deploys (si existe disco).
        # Fallback a directorio de la app + env var ADMIN_SESSIONS_PATH.
        _db_dir = os.environ.get("ADMIN_SESSIONS_DIR", "")
        if _db_dir and os.path.isdir(_db_dir):
            pass
        elif os.path.isdir("/data"):
            _db_dir = "/data"
        else:
            _db_dir = os.path.dirname(os.path.abspath(__file__))
        _admin_db_path = os.path.join(_db_dir, "admin_sessions.db")
        self._engine = create_engine(
            f"sqlite:///{_admin_db_path}",
            connect_args={"check_same_thread": False, "timeout": 3},
        )
        _SessionBase.metadata.create_all(bind=self._engine)
        self._Session = sessionmaker(bind=self._engine)
        try:
            self._limpiar_expiradas()
        except Exception:
            pass  # Primera ejecución, tabla recién creada
        self.schedule_cleanup()

    def _get_db(self):
        """Crea una nueva sesion SQLAlchemy.
        
        Antes usaba generador con yield, pero el finally del generador
        provocaba double-close y OperationalError en Render.
        Ahora es un factory simple: el caller es responsable de close().
        """
        return self._Session()

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
