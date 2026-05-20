"""Rutas de sorteos (SDD §5.3). Logica en services."""



from datetime import datetime



from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile, status

from pydantic import BaseModel, Field

from slowapi import Limiter

from slowapi.util import get_remote_address

from sqlalchemy.orm import Session



from app.core.config import security_config

from app.db.database import SessionLocal

from app.services.sorteos_service import (

    cargar_excel_elegibles,

    confirmar_otp,

    estado_otp,

    estado_sorteo,

    ejecutar_sorteo_asignacion,

    iniciar_sorteo,

    listar_historial_sorteos,

    notificar_resultados,

    obtener_resultados_paginados,

    obtener_diagnostico,

    exportar_resultados,

)





router = APIRouter(prefix="/sorteos", tags=["sorteos"])

limiter = Limiter(key_func=get_remote_address)


class SorteoResumenOut(BaseModel):

    id: int

    estado: str

    seed: str | None

    tipo: str | None

    created_at: datetime





class ConsejeroIn(BaseModel):

    nombre: str

    email: str | None = None





class IniciarSorteoIn(BaseModel):

    sorteo_id: int

    consejeros: list[ConsejeroIn] = Field(..., min_length=5, max_length=5)





class ConfirmarOtpIn(BaseModel):

    otp: str





class ResultadoLineaOut(BaseModel):

    participante_id: int

    apartamento: str | None

    parqueadero_asignado: str | None

    zona_asignada: str | None

    tipo_resultado: str





def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()





@router.get("/historial")

def historial(request: Request, db: Session = Depends(get_db)) -> list[SorteoResumenOut]:

    tenant_id = request.state.tenant_id

    sorteos = listar_historial_sorteos(db=db, tenant_id=tenant_id)

    return [

        SorteoResumenOut(

            id=sorteo.id,

            estado=sorteo.estado,

            seed=sorteo.seed,

            tipo=sorteo.tipo,

            created_at=sorteo.created_at,

        )

        for sorteo in sorteos

    ]





@router.post("/carga-excel", status_code=status.HTTP_201_CREATED)

async def carga_excel(

    request: Request,

    db: Session = Depends(get_db),

    archivo: UploadFile = File(..., description="Excel con columnas nombre, documento, email"),

) -> dict[str, int]:

    tenant_id = request.state.tenant_id

    contenido = await archivo.read()

    return cargar_excel_elegibles(db=db, tenant_id=tenant_id, contenido=contenido)





@router.post("/iniciar", status_code=status.HTTP_201_CREATED)

def iniciar(

    request: Request,

    payload: IniciarSorteoIn,

    db: Session = Depends(get_db),

) -> dict[str, object]:

    """Sorteo PENDIENTE con participantes: OTPs por email (SDD §5.3)."""

    tenant_id = request.state.tenant_id

    consejeros = [c.model_dump() for c in payload.consejeros]

    return iniciar_sorteo(

        db=db,

        tenant_id=tenant_id,

        sorteo_id=payload.sorteo_id,

        consejeros=consejeros,

    )





@router.post("/{sorteo_id}/otp/confirmar")
@limiter.limit("10/minute")
def otp_confirmar(

    sorteo_id: int,

    request: Request,

    body: ConfirmarOtpIn,

    db: Session = Depends(get_db),

    x_sorteo_otp_token: str | None = Header(default=None, alias=security_config.otp_confirm_header_name),

) -> dict[str, str]:

    token = (x_sorteo_otp_token or "").strip()

    tenant_desde_bearer = request.state.tenant_id or ""

    if not token:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail=f"Falta header {security_config.otp_confirm_header_name}",

        )

    return confirmar_otp(

        db=db,

        sorteo_id=sorteo_id,

        tenant_id_desde_token=tenant_desde_bearer,

        token_enlace=token,

        otp_ingresado=body.otp.strip(),

    )





@router.get("/{sorteo_id}/otp/estado")

def otp_estado(request: Request, sorteo_id: int, db: Session = Depends(get_db)) -> dict[str, object]:

    tenant_id = request.state.tenant_id

    return estado_otp(db=db, tenant_id=tenant_id, sorteo_id=sorteo_id)





@router.get("/{sorteo_id}/estado")

def sorteo_estado(request: Request, sorteo_id: int, db: Session = Depends(get_db)) -> dict[str, object]:

    tenant_id = request.state.tenant_id

    return estado_sorteo(db=db, tenant_id=tenant_id, sorteo_id=sorteo_id)





@router.post("/{sorteo_id}/ejecutar")

def ejecutar(request: Request, sorteo_id: int, db: Session = Depends(get_db)) -> list[ResultadoLineaOut]:

    tenant_id = request.state.tenant_id

    resultados = ejecutar_sorteo_asignacion(db=db, tenant_id=tenant_id, sorteo_id=sorteo_id)

    return [

        ResultadoLineaOut(

            participante_id=r.participante_id,

            apartamento=r.apartamento,

            parqueadero_asignado=r.parqueadero_asignado,

            zona_asignada=r.zona_asignada,

            tipo_resultado=r.tipo_resultado

        ) for r in resultados

    ]





@router.post("/{sorteo_id}/notificar")

def notificar(request: Request, sorteo_id: int, db: Session = Depends(get_db)) -> dict[str, int]:

    tenant_id = request.state.tenant_id

    return notificar_resultados(db=db, tenant_id=tenant_id, sorteo_id=sorteo_id)





# ====== NUEVOS ENDPOINTS ======



@router.get("/{sorteo_id}/diagnostico")

def diagnostico(request: Request, sorteo_id: int, db: Session = Depends(get_db)) -> dict[str, object]:

    """Previsualiza modelo por zona antes de ejecutar (SDD §5.3)."""

    tenant_id = request.state.tenant_id

    return obtener_diagnostico(db=db, tenant_id=tenant_id, sorteo_id=sorteo_id)



@router.get("/{sorteo_id}/resultados")

def resultados_paginados(

    request: Request,

    sorteo_id: int,

    pagina: int = Query(default=1, ge=1),

    por_pagina: int = Query(default=20, ge=1, le=100),

    db: Session = Depends(get_db),

) -> dict[str, object]:

    """Resultados paginados (SDD §5.3)."""

    tenant_id = request.state.tenant_id

    return obtener_resultados_paginados(db=db, tenant_id=tenant_id, sorteo_id=sorteo_id, pagina=pagina, por_pagina=por_pagina)



@router.post("/{sorteo_id}/exportar")

def exportar(

    request: Request,

    sorteo_id: int,

    formato: str = Query(default="excel", pattern="^(excel|word)$"),

    db: Session = Depends(get_db),

):

    """Exporta acta del sorteo en Excel o Word (SDD §16)."""

    from fastapi.responses import StreamingResponse

    tenant_id = request.state.tenant_id

    content = exportar_resultados(db=db, tenant_id=tenant_id, sorteo_id=sorteo_id, formato=formato)

    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if formato == "excel" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    ext = "xlsx" if formato == "excel" else "docx"

    return StreamingResponse(

        iter([content]),

        media_type=media_type,

        headers={"Content-Disposition": f'attachment; filename="acta_sorteo_{sorteo_id}.{ext}"'},

    )
