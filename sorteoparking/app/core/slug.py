"""Generacion de slug unico para URLs publicas (SDD §5.4)."""

import re
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tenant import Tenant


def generar_slug_unico(nombre: str, db: Session) -> str:
    """Produce un slug URL-safe unico por conjunto."""
    base = re.sub(r"[^a-z0-9]+", "-", nombre.lower().strip())
    base = (base.strip("-")[:60] or "conjunto").strip("-") or "conjunto"
    slug = base
    intento = 0
    while True:
        existing = db.query(Tenant).filter(Tenant.slug == slug).first()
        if not existing:
            return slug
        intento += 1
        if intento > 500:
            slug = f"{base}-{uuid4().hex[:10]}"
            return slug
        slug = f"{base}-{intento}"

