"""Almacenamiento de sesiones (SDD §13.11).

Usa SQLite propio en /data/ para sesiones de admin.
Independiente de la BD principal (PostgreSQL).
Ruta /data/ es writable y persistente en Render.

NO depende de database.py SessionLocal — evita problemas de SSL
con PostgreSQL en Render cuando la BD principal es inaccesible.
"""

import hashlib
import hmac
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# SQLite en /data/ — persistente en Render, writable en todos los entornos
_SESSION_DB_PATH = os.environ.get("SESSION_DB_PATH", "/data/admin_sessions.db")

_SessionBase = declarative_base()
_SessionEngine = None
_SessionLocal = None


def _get_session_engine():
    """Engine SQLite dedicado para admin_sessions (lazy init)."""
    global _SessionEngine, _SessionLocal
    if _SessionEngine is None:
        # Crear directorio si no existe
        _session_dir = os.path.dirname(_SESSION_DB_PATH)
        if _session_dir and not os.path.exists(_session_dir):
            try:
                os.makedirs(_session_dir, exist_ok=True)
            except Exception as e:
                logger.warning("No se pudo crear directorio para sesiones: %s", e)
        
        _SessionEngine = create_engine(
            f"sqlite:///{_SESSION_DB_PATH}",
            connect_args={"timeout": 30, "check_same_thread": False},
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_SessionEngine)
    return _SessionEngine


class AdminSession(_SessionBase):
    """Tabla admin_sessions (SDD §13.11).

    Almacenada en SQLite dedicado, independiente de la BD principal.
    """

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
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_sessions'")
            )
            exists = result.first() is not None
            if not exists:
                logger.error("VERIFY_TABLE: admin_sessions NO existe en SQLite de sesiones")
            else:
                logger.warning("VERIFY_TABLE: admin_sessions OK en SQLite de sesiones")
            return exists
    except Exception as e:
        logger.error("VERIFY_TABLE: error verificando admin_sessions: %s", e)
        return False


def init_session_table(engine=None) -> bool:
    """Crea la tabla admin_sessions en el SQLite de sesiones.

    Args:
        engine: ignorado (mantenido por compatibilidad con main.py).
                Siempre usa su propio engine SQLite en /data/.

    Returns:
        True si la tabla existe/fue creada, False en caso de error.
    """
    try:
        session_engine = _get_session_engine()
        _SessionBase.metadata.create_all(bind=session_engine)
        logger.warning("INIT_TABLE: _SessionBase.metadata.create_all en SQLite sesiones OK")

        # Configurar WAL para mejor concurrencia
        with session_engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))

        exists = _verify_admin_sessions_table(session_engine)
        if exists:
            logger.warning("INIT_TABLE: admin_sessions CONFIRMADA en %s", _SESSION_DB_PATH)
        else:
            logger.error("INIT_TABLE: admin_sessions NO encontrada post-create_all")
        return exists
    except Exception as e:
        logger.error("INIT_TABLE: No se pudo crear admin_sessions: %s", e)
        return False


class SessionStore:
    """Almacenamiento de sesiones en SQLite dedicado.

    Singleton. Usa su propio engine SQLite en /data/ — NO depende
    de la BD principal (PostgreSQL). Esto aisla las sesiones de
    problemas de conectividad con PostgreSQL en Render.
    
    /data/ es persistente en Render, a diferencia de /tmp/.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SessionStore, cls).__new__(cls)
        return cls._instance

    def configure(self, engine=None) -> None:
        """Inicializa el SessionStore.

        Args:
            engine: ignorado (compatibilidad con main.py).
                    SessionStore usa su propio engine SQLite.
        """
        logger.warning(
            "CONFIGURE: SessionStore usando SQLite propio en %s", _SESSION_DB_PATH
        )
        try:
            self._limpiar_expiradas()
        except Exception as e:
            logger.error("CONFIGURE: _limpiar_expiradas fallo en configure: %s", e)
        self.schedule_cleanup()

    def _get_db(self):
        """Crea una nueva sesion SQLAlchemy usando el engine SQLite propio."""
        global _SessionLocal
        _get_session_engine()  # asegura que _SessionLocal esté inicializado
        try:
            return _SessionLocal()
        except Exception as e:
            logger.error("SessionStore._get_db() error creando sesion: %s", e)
            raise

    def create_session(self, session_id: str, token: str, csrf_token: str = "") -> bool:
        """Asocia un ID de sesion con un SUPER_ADMIN_TOKEN.

        Returns:
            True si la sesion se creo y persistio correctamente.
            False si hubo algun error.
        """
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if not csrf_token:
            csrf_token = token_hash[:32]

        logger.warning(
            "AUTH CREATE session_id=%s | token_hash=%s... | len(session_id)=%d",
            session_id[:8], token_hash[:16], len(session_id)
        )

        db = None
        try:
            db = self._get_db()
            logger.warning("AUTH CREATE got_db_session (SQLite sesiones)")

            # Revocar sesiones previas del mismo token
            rev = db.query(AdminSession).filter(
                AdminSession.token_hash == token_hash,
                AdminSession.revoked_at.is_(None),
            ).update({"revoked_at": datetime.now(timezone.utc)})
            logger.warning("AUTH CREATE revoked_prev=%d", rev)

            ses = AdminSession(
                session_id=session_id,
                token_hash=token_hash,
                csrf_token=csrf_token,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
            )
            db.add(ses)
            logger.warning("AUTH CREATE added_to_session | repr(session_id)=%r", session_id)

            db.commit()
            logger.warning("AUTH CREATE commit_ok")

            # VALIDACION DIRECTA: verificar que el registro se persistio
            try:
                global _SessionLocal
                verify_db = _SessionLocal()
                raw = verify_db.execute(
                    text("SELECT session_id, expires_at, created_at "
                         "FROM admin_sessions WHERE session_id=:id"),
                    {"id": session_id}
                )
                row = raw.first()
                found = row is not None
                if found:
                    logger.warning(
                        "AUTH CREATE persisted=True | session_id=%r | "
                        "expires_at=%s | created_at=%s | ahora=%s | delta_exp=%ds",
                        session_id,
                        row[1] if row[1] else "?",
                        row[2] if row[2] else "?",
                        datetime.now(timezone.utc).isoformat(),
                        (row[1] - datetime.now(timezone.utc)).total_seconds() if row[1] else 0
                    )
                else:
                    logger.error(
                        "AUTH CREATE persisted=False | session_id=%r | "
                        "NO ENCONTRADO en SQLite sesiones",
                        session_id
                    )
                    return False
                verify_db.close()
            except Exception as inner_e:
                logger.error("AUTH CREATE post-commit verification error: %s", inner_e)

            logger.warning("AUTH CREATE session CREATED OK session_id=%s", session_id[:8])
            return True

        except Exception as e:
            logger.error(
                "AUTH CREATE ERROR session_id=%s | error=%s | db_initialized=%s",
                session_id[:8], e, db is not None
            )
            if db:
                try:
                    db.rollback()
                except Exception as rb_e:
                    logger.error("AUTH CREATE rollback_error=%s", rb_e)
            return False
        finally:
            if db:
                try:
                    db.close()
                except Exception as close_e:
                    logger.error("AUTH CREATE close_error=%s", close_e)

    def get_session(self, session_id: str) -> Optional[str]:
        """Recupera el token_hash asociado a una sesion."""
        db = None
        try:
            db = self._get_db()
            self._log_session_count(db, "prev")

            logger.warning(
                "AUTH GET entrada | session_id=%r | len=%d",
                session_id, len(session_id) if session_id else 0
            )

            ses = db.query(AdminSession).filter(
                AdminSession.session_id == session_id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > datetime.now(timezone.utc),
            ).first()
            found = ses is not None

            logger.warning(
                "AUTH GET session_id=%s | found=%s | hash=%s...",
                session_id[:8],
                found,
                ses.token_hash[:16] if found else "N/A"
            )

            if not found:
                total = db.query(AdminSession).count()
                expired = db.query(AdminSession).filter(
                    AdminSession.expires_at <= datetime.now(timezone.utc)
                ).count()
                revoked = db.query(AdminSession).filter(
                    AdminSession.revoked_at.isnot(None)
                ).count()
                any_row = db.query(AdminSession).filter(
                    AdminSession.session_id == session_id
                ).first()
                if any_row:
                    logger.warning(
                        "AUTH GET session_id=%s | EXISTS sin filtros | "
                        "expired=%s | revoked=%s",
                        session_id[:8],
                        any_row.expires_at <= datetime.now(timezone.utc),
                        any_row.revoked_at is not None,
                    )
                else:
                    logger.warning(
                        "AUTH GET session_id=%s | NO existe (0 filas) | "
                        "total_sesiones=%d | expired=%d | revoked=%d",
                        session_id[:8], total, expired, revoked,
                    )

            if ses:
                return ses.token_hash
            return None
        except Exception as e:
            logger.error(
                "AUTH GET ERROR session_id=%s | error=%s",
                session_id[:8] if session_id else "?", e
            )
            return None
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass

    def _log_session_count(self, db, context: str) -> None:
        try:
            total = db.query(AdminSession).count()
            active = db.query(AdminSession).filter(
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > datetime.now(timezone.utc),
            ).count()
            logger.warning(
                "AUTH SESSION_COUNT [%s] total=%d active=%d",
                context, total, active
            )
        except Exception as e:
            logger.debug("AUTH SESSION_COUNT [%s] error=%s", context, e)

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
                logger.warning(
                    "AUTH CSRF session=%s | match=%s",
                    session_id[:8], match
                )
                return match
            logger.warning(
                "AUTH CSRF session=%s | sesion_no_encontrada",
                session_id[:8]
            )
            return False
        except Exception as e:
            logger.error("AUTH CSRF ERROR session=%s | error=%s",
                         session_id[:8] if session_id else "?", e)
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
            logger.warning(
                "AUTH DELETE session=%s | revoked=%d",
                session_id[:8], result
            )
            return result > 0
        except Exception as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            logger.error("AUTH DELETE ERROR session=%s | error=%s",
                         session_id[:8] if session_id else "?", e)
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
