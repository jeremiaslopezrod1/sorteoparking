import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.log import LogAuditoria


def registrar_log_auditoria(
    db: Session,
    tenant_id: str,
    evento: str,
    payload: str | None = None,
) -> LogAuditoria:
    """Registra evento en log encadenado por tenant."""
    anterior = (
        db.query(LogAuditoria)
        .filter(LogAuditoria.tenant_id == tenant_id)
        .order_by(LogAuditoria.id.desc())
        .first()
    )
    hash_anterior = anterior.hash_actual if anterior else None
    base = f"{tenant_id}|{evento}|{payload or ''}|{hash_anterior or ''}|{datetime.now(timezone.utc).isoformat()}"
    hash_actual = hashlib.sha256(base.encode("utf-8")).hexdigest()

    nuevo_log = LogAuditoria(
        tenant_id=tenant_id,
        evento=evento,
        payload=payload,
        hash_anterior=hash_anterior,
        hash_actual=hash_actual,
    )
    db.add(nuevo_log)
    db.flush()
    db.refresh(nuevo_log)
    return nuevo_log
