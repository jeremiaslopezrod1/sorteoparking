"""Rutas publicas residente (SDD §5.4)."""



from typing import Any



from fastapi import APIRouter, Depends

from slowapi import Limiter

from sqlalchemy.orm import Session



from app.db.database import SessionLocal

from app.services.sorteos_service import publico_seed, publico_sorteo



def _public_client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_public_client_ip)


router = APIRouter(prefix="/p", tags=["publico"])





def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()





@router.get("/{tenant_slug}/sorteos/{sorteo_id}")

def resultado_publico(

    tenant_slug: str,

    sorteo_id: int,

    db: Session = Depends(get_db),

) -> dict[str, Any]:

    return publico_sorteo(db=db, tenant_slug=tenant_slug, sorteo_id=sorteo_id)





@router.get("/{tenant_slug}/sorteos/{sorteo_id}/seed")

def seed_publico(

    tenant_slug: str,

    sorteo_id: int,

    db: Session = Depends(get_db),

) -> dict[str, str]:

    return publico_seed(db=db, tenant_slug=tenant_slug, sorteo_id=sorteo_id)


