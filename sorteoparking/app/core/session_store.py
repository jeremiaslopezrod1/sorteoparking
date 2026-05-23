"""Almacenamiento de sesiones (SDD §13.11).

Usa EXACTAMENTE el mismo engine y pool que la app principal.
NO crea engine propio. NO SQLite paralelo. NO fallback.

Si PostgreSQL no está disponible → la app NO arranca (fail-fast en main.py).
"""

import hashlib
import hmac
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Text, text
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

_SessionBase = declarative_base()


class AdminSession(_SessionBase):
    """Tabla admin_sessions (SDD §13.11)."""

    __tablename__ = "admin_sessions"

    session_id = Column(Text, primary_key=True)
    token_hash = Column(Text, nullable=False)
    csrf_token = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


def _verify_admin_sessions_table(engine) -> bool:
    """Verifica que la tabla admin_sessions exista y sea accesible."""
    try:
        with engine.connect() as conn:
            # Detectar tipo de BD
            is_postgresql = "postgresql" in str(engine.url)
            if is_postgresql:
                result = conn.execute(
                    text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables "
                        "WHERE table_name = 'admin_sessions')"
                    )
                )
                exists = result.scalar()
            else:
                result = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_sessions'")
                )
                exists = result.first() is not None

            if not exists:
                logger.error("VERIFY_TABLE: admin_sessions NO existe")
            else:
                logger.warning("VERIFY_TABLE: admin_sessions OK")
            return exists
    except Exception as e:
        logger.error("VERIFY_TABLE: error verificando admin_sessions: %s", e)
        return False


def init_session_table(engine) -> bool:
    """Crea la tabla admin_sessions usando el engine principal.

    Args:
        engine: engine SQLAlchemy de app.db.database (único, compartido).

    Returns:
        True si la tabla existe/fue creada, False en caso de error.
    """
    try:
        _SessionBase.metadata.create_all(bind=engine)
        logger.warning("INIT_TABLE: admin_sessions create_all OK")

        exists = _verify_admin_sessions_table(engine)
        if exists:
            logger.warning("INIT_TABLE: admin_sessions CONFIRMADA")
        else:
            logger.error("INIT_TABLE: admin_sessions NO encontrada post-create_all")
        return exists
    except Exception as e:
        logger.error("INIT_TABLE: No se pudo crear admin_sessions: %s", e)
        return False


class SessionStore:
    """Almacenamiento de sesiones.

    Singleton. Usa el SessionLocal de app.db.database (mismo engine, mismo pool).
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SessionStore, cls).__new__(cls)
        return cls._instance

    def configure(self) -> None:
        """Inicializa el SessionStore usando el SessionLocal principal."""
        logger.warning("CONFIGURE: SessionStore inicializando con engine compartido")
        try:
            self._limpiar_expiradas()
        except Exception as e:
            logger.error("CONFIGURE: _limpiar_expiradas fallo en configure: %s", e)
        self.schedule_cleanup()

    def _get_db(self):
        """Crea una nueva sesion usando el SessionLocal principal."""
        from app.db.database import SessionLocal  # import local para evitar circular

        try:
            return SessionLocal()
        except Exception as e:
            logger.error("SessionStore._get_db() error creando sesion: %s", e)
            raise

    def create_session(self, session_id: str, token: str, csrf_token: str = "") -> bool:
        """Asocia un ID de sesion con un SUPER_ADMIN_TOKEN.

        Returns:
            True si la sesion se creo y persistio correctamente.
        """
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not csrf_token:
            csrf_token = token_hash[:32]

        logger.warning(
            "AUTH SESSION CREATE session_id=%s | token_hash=%s...",
            session_id[:8], token_hash[:16]
        )

        db = None
        try:
            db = self._get_db()

            # Revocar sesiones previas del mismo token
            rev = db.query(AdminSession).filter(
                AdminSession.token_hash == token_hash,
                AdminSession.revoked_at.is_(None),
            ).update({"revoked_at": datetime.now(timezone.utc)})
            logger.warning("AUTH SESSION CREATE revoked_prev=%d", rev)

            ses = AdminSession(
                session_id=session_id,
                token_hash=token_hash,
                csrf_token=csrf_token,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
            )
            db.add(ses)
            db.commit()
            logger.warning("AUTH SESSION CREATED session_id=%s", session_id[:8])

            # VALIDACION DIRECTA
            verify_db = None
            try:
                from app.db.database import SessionLocal
                verify_db = SessionLocal()
                raw = verify_db.execute(
                    text("SELECT session_id, expires_at, created_at "
                         "FROM admin_sessions WHERE session_id=:id"),
                    {"id": session_id}
                )
                row = raw.first()
                found = row is not None
                if found:
                    logger.warning(
                        "AUTH SESSION CREATED persisted=True | session_id=%s",
                        session_id[:8]
                    )
                else:
                    logger.error(
                        "AUTH SESSION CREATED persisted=False | session_id=%s",
                        session_id[:8]
                    )
                    return False
            except Exception as inner_e:
                logger.error("AUTH SESSION CREATED verify error: %s", inner_e)
            finally:
                if verify_db:
                    verify_db.close()

            return True

        except Exception as e:
            logger.error("AUTH SESSION CREATE ERROR session_id=%s | error=%s", session_id[:8], e)
            if db:
                try:
                    db.rollback()
                except Exception as rb_e:
                    logger.error("AUTH SESSION CREATE rollback_error=%s", rb_e)
            return False
        finally:
            if db:
                try:
                    db.close()
                except Exception as close_e:
                    logger.error("AUTH SESSION CREATE close_error=%s", close_e)

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
            found = ses is not None

            if found:
                logger.warning("AUTH SESSION FOUND session_id=%s", session_id[:8])
                return ses.token_hash
            else:
                # Diagnóstico: ¿por qué no se encontró?
                total = db.query(AdminSession).count()
                any_row = db.query(AdminSession).filter(
                    AdminSession.session_id == session_id
                ).first()
                if any_row:
                    logger.warning(
                        "AUTH SESSION NOT FOUND session_id=%s | expired=%s | revoked=%s | total=%d",
                        session_id[:8],
                        any_row.expires_at <= datetime.now(timezone.utc),
                        any_row.revoked_at is not None,
                        total,
                    )
                else:
                    logger.warning(
                        "AUTH SESSION NOT FOUND session_id=%s | no_rows | total=%d",
                        session_id[:8], total,
                    )
                return None
        except Exception as e:
            logger.error("AUTH SESSION GET ERROR session_id=%s | error=%s", session_id[:8] if session_id else "?", e)
            return None
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def validate_csrf(self, session_id: str, csrf_header: str) -> bool:
        if not csrf_header:
            logger.warning("AUTH CSRF reject: header_vacio")
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
                match = hmac.compare_digest(ses.csrf_token, csrf_header)
                return match
            logger.warning("AUTH CSRF session=%s | sesion_no_encontrada", session_id[:8])
            return False
        except Exception as e:
            logger.error("AUTH CSRF ERROR session=%s | error=%s", session_id[:8] if session_id else "?", e)
            return False
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def delete_session(self, session_id: str) -> bool:
        db = None
        try:
            db = self._get_db()
            result = db.query(AdminSession).filter(
                AdminSession.session_id == session_id
            ).update({"revoked_at": datetime.now(timezone.utc)})
            db.commit()
            logger.warning("AUTH SESSION DELETED session=%s | revoked=%d", session_id[:8], result)
            return result > 0
        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error("AUTH SESSION DELETE ERROR session=%s | error=%s", session_id[:8] if session_id else "?", e)
            return False
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def _limpiar_expiradas(self):
        db = None
        try:
            db = self._get_db()
            deleted = db.query(AdminSession).filter(
                (AdminSession.expires_at < datetime.now(timezone.utc))
                | (AdminSession.revoked_at.isnot(None))
            ).delete()
            db.commit()
            if deleted:
                logger.info("SESSION CLEAN: %d sesiones eliminadas", deleted)
        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error("SESSION CLEAN ERROR: %s", e)
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def schedule_cleanup(self):
        import time
        import threading

        def _cleanup_loop():
            while True:
                time.sleep(3600)
                try:
                    self._limpiar_expiradas()
                except Exception:
                    pass

        t = threading.Thread(target=_cleanup_loop, daemon=True)
        t.start()


session_store = SessionStore()
