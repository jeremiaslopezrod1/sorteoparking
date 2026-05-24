from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import io
import logging

logger = logging.getLogger(__name__)

from app.db.database import SessionLocal
from app.services.catalogo_service import listar_parqueaderos_por_tenant, listar_zonas_por_tenant, cargar_catalogo_desde_excel
from app.models.catalogo import Parqueadero
from app.services.excel_parser import validar_archivo

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


class ZonaOut(BaseModel):
    id: int
    nombre: str


class ParqueaderoOut(BaseModel):
    id: int
    numero: str
    tipo: str
    zona_id: int
    torre_id: int | None


class ResumenCarga(BaseModel):
    zonas_creadas: int
    torres_creadas: int
    parqueaderos_cargados: int

class ParqueaderoPatch(BaseModel):
    tipo: str | None = None
    zona_nombre: str | None = None
    torre_nombre: str | None = None
    disponible: bool | None = None
    vecino: str | None = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/zonas")
def listar_zonas(request: Request, db: Session = Depends(get_db)) -> list[ZonaOut]:
    tenant_id = request.state.tenant_id
    zonas = listar_zonas_por_tenant(db=db, tenant_id=tenant_id)
    return [ZonaOut(id=zona.id, nombre=zona.nombre) for zona in zonas]


@router.get("/parqueaderos")
def listar_parqueaderos(request: Request, db: Session = Depends(get_db)) -> list[ParqueaderoOut]:
    tenant_id = request.state.tenant_id
    parqueaderos = listar_parqueaderos_por_tenant(db=db, tenant_id=tenant_id)
    return [
        ParqueaderoOut(
            id=parqueadero.id,
            numero=parqueadero.numero,
            tipo=parqueadero.tipo,
            zona_id=parqueadero.zona_id,
            torre_id=parqueadero.torre_id,
        )
        for parqueadero in parqueaderos
    ]


@router.post("/carga-csv", response_model=ResumenCarga, status_code=201)
async def cargar_catalogo(request: Request, archivo: UploadFile = File(...), db: Session = Depends(get_db)) -> ResumenCarga:
    """Importa CSV o Excel de parqueaderos usando parser inteligente (SDD §14, §15)."""
    tenant_id = request.state.tenant_id
    logger.warning("UPLOAD RECIBIDO: tenant=%s filename=%s content_type=%s", tenant_id, archivo.filename, archivo.content_type)
    
    # Verificar que no haya parqueaderos ya cargados
    existentes = db.query(Parqueadero).filter(Parqueadero.tenant_id == tenant_id).count()
    if existentes > 0:
        raise HTTPException(status_code=409, detail="El catálogo ya está cargado para este conjunto.")
    
    # SDD §14.10 — Validar archivo
    contenido = await validar_archivo(archivo)
    
    # Usar el catalogo_service existente para cargar
    try:
        resumen = cargar_catalogo_desde_excel(db=db, tenant_id=tenant_id, archivo_bytes=contenido)
        return ResumenCarga(**resumen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando el archivo: {str(e)}")


@router.patch("/parqueaderos/{numero}")
def editar_parqueadero(
    request: Request,
    numero: str,
    payload: ParqueaderoPatch,
    db: Session = Depends(get_db),
) -> dict:
    """Edición puntual de parqueadero (SDD §5.2)."""
    tenant_id = request.state.tenant_id
    pq = db.query(Parqueadero).filter(
        Parqueadero.tenant_id == tenant_id,
        Parqueadero.numero == numero,
    ).first()
    if not pq:
        raise HTTPException(status_code=404, detail="Parqueadero no encontrado")
    
    if payload.tipo is not None:
        pq.tipo = payload.tipo.upper()
    if payload.disponible is not None:
        pq.disponible = payload.disponible
    if payload.vecino is not None:
        pq.vecino = payload.vecino
    if payload.zona_nombre is not None:
        from app.models.catalogo import Zona
        zona = db.query(Zona).filter(Zona.tenant_id == tenant_id, Zona.nombre == payload.zona_nombre).first()
        if not zona:
            raise HTTPException(status_code=404, detail="Zona no encontrada")
        pq.zona_id = zona.id
    if payload.torre_nombre is not None:
        from app.models.catalogo import Torre
        torre = db.query(Torre).filter(Torre.tenant_id == tenant_id, Torre.nombre == payload.torre_nombre).first()
        if not torre:
            raise HTTPException(status_code=404, detail="Torre no encontrada")
        pq.torre_id = torre.id
    
    db.commit()
    return {"mensaje": f"Parqueadero {numero} actualizado"}


@router.get("/plantilla")
def descargar_plantilla():
    """Descarga la plantilla oficial de SorteoParking (SDD §15.4)."""
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    
    wb = Workbook()
    ws = wb.active
    ws.title = "CATALOGO"
    
    # Encabezados según SDD §15.3
    headers = ["numero", "tipo_vehiculo", "zona", "tipo_espacio", "torre", "disponible", "vecino"]
    ws.append(headers)
    
    # Ejemplo (1 fila de datos)
    ws.append(["P-001", "CARRO", "Zona A", "SENCILLO", "Torre 1", "TRUE", ""])
    ws.append(["P-002", "CARRO", "Zona A", "DOBLE", "Torre 1", "TRUE", "P-003"])
    ws.append(["P-003", "CARRO", "Zona B", "DOBLE", "Torre 2", "TRUE", "P-002"])
    ws.append(["M-001", "MOTO", "Zona C", "SENCILLO", "Torre 3", "TRUE", ""])
    
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    
    return StreamingResponse(
        iter([buf.read()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="SorteoParking_CATALOGO_MAESTRO_plantilla.xlsx"'},
    )
