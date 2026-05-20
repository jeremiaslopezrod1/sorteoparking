"""
Motor de Sorteo Híbrido Determinista v1.4.3 (Restaurado).
Basado en el núcleo original de Aliso Vivienda.
Cumple con SDD §3.5, §6.3 y Regla de Oro (Multi-tenant).

NOTE(FIX #29): optimizar_emparejamiento_dobles es O(n^2) en el peor caso.
Para conjuntos > 2000 participantes, revisar si se requiere optimizacion.
"""

import hashlib
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session

from app.models.catalogo import Parqueadero, Torre, Zona
from app.models.sorteo import Participante, ResultadoSorteo, Sorteo
from app.services.log_service import registrar_log_auditoria


def _chunked_filter(model_class, column, ids, batch_size=500):
    """Creates filter conditions in batches to avoid SQLite parameter limit."""
    filters = []
    for i in range(0, len(ids), batch_size):
        chunk = ids[i:i + batch_size]
        filters.append(column.in_(chunk))
    return or_(*filters) if len(filters) > 1 else filters[0] if filters else None


def ejecutar_sorteo_hibrido(
    db: Session, tenant_id: str, sorteo_id: int, modo_simulacion: bool = False, seed_override: str = None
) -> List[Dict]:
    """
    Ejecuta el sorteo híbrido determinista por zona y pool global.
    """
    # PASO 1 — Verificaciones previas y aislamiento multi-tenant
    sorteo = db.query(Sorteo).filter(Sorteo.id == sorteo_id, Sorteo.tenant_id == tenant_id).first()
    if not sorteo:
        raise ValueError("Sorteo no encontrado")

    if not modo_simulacion and sorteo.estado not in ["LISTO", "EN_CURSO", "EJECUTANDO"]:
        raise ValueError(f"Sorteo no está en estado LISTO (actual: {sorteo.estado})")

    # PASO 2 — Determinar seed (reproducibilidad §6.3)
    if seed_override:
        seed_hex = seed_override
    else:
        # Usamos snapshot_hash del sorteo según SDD
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        seed_input = f"{timestamp_utc}{sorteo.snapshot_hash}"
        seed_hex = hashlib.sha256(seed_input.encode()).hexdigest()

    seed_int = int(seed_hex, 16) % (2**32)
    rng = random.Random(seed_int)

    # PASO 3 — Cargar datos (filtrados por tenant_id)
    tipo_vehiculo = sorteo.tipo or "CARRO"
    # SDD §4.2 — "GENERAL" significa incluir todos los tipos de vehículo
    if tipo_vehiculo == "GENERAL":
        tipo_vehiculo = None
    zonas = db.query(Zona).filter(Zona.tenant_id == tenant_id).order_by(Zona.nombre).all()
    resultados = []
    pool_global_pq = []
    pool_global_par = []

    def _filter_tipo(base_filter):
        """Agrega filtro por tipo_vehiculo solo si no es GENERAL."""
        if tipo_vehiculo is not None:
            return base_filter
        return []

    # PASO 4 — Fase 1: Evaluar cada zona (Modelo 2 por zona)
    for zona in zonas:
        # Participantes cuya torre pertenece a esta zona
        filtros_elegibles = [
            Participante.tenant_id == tenant_id,
            Participante.sorteo_id == sorteo_id,
            Torre.zona_id == zona.id
        ]
        if tipo_vehiculo is not None:
            filtros_elegibles.append(Participante.tipo_vehiculo == tipo_vehiculo)

        elegibles = (
            db.query(Participante)
            .join(Torre, (Participante.apartamento.like(Torre.nombre + "%")) & (Torre.tenant_id == tenant_id))
            .filter(*filtros_elegibles)
            .all()
        )

        # Parqueaderos disponibles en esta zona
        filtros_puestos = [
            Parqueadero.tenant_id == tenant_id,
            Parqueadero.zona_id == zona.id,
            Parqueadero.disponible == True
        ]
        if tipo_vehiculo is not None:
            filtros_puestos.append(Parqueadero.vehiculo == tipo_vehiculo)

        puestos = (
            db.query(Parqueadero)
            .filter(*filtros_puestos)
            .all()
        )

        if len(elegibles) <= len(puestos):
            rng.shuffle(puestos)
            for p, pq in zip(elegibles, puestos):
                resultados.append({
                    "apartamento": p.apartamento,
                    "participante_id": p.id,
                    "tipo_resultado": "GANADOR",
                    "parqueadero_asignado": pq.numero,
                    "zona_asignada": zona.nombre,
                    "fue_reasignado": False,
                    "es_hatchback": p.es_hatchback
                })
            pool_global_pq += puestos[len(elegibles):]
        else:
            pool_global_par += elegibles
            pool_global_pq += puestos

    # Rescate de Participantes Huérfanos
    procesados_ids = [r["participante_id"] for r in resultados] + [p.id for p in pool_global_par]
    filtros_huerfanos = [
        Participante.tenant_id == tenant_id,
        Participante.sorteo_id == sorteo_id,
    ]
    if tipo_vehiculo is not None:
        filtros_huerfanos.append(Participante.tipo_vehiculo == tipo_vehiculo)
    if procesados_ids:
        chunk_filter = _chunked_filter(Participante, Participante.id, procesados_ids)
        if chunk_filter is not None:
            filtros_huerfanos.append(not_(chunk_filter))

    huerfanos = db.query(Participante).filter(*filtros_huerfanos).all()
    pool_global_par += huerfanos

    # PASO 5 — Fase 2: Resolver pool global
    if pool_global_par:
        rng.shuffle(pool_global_pq)
        # Shuffle del pool global de participantes para justicia
        rng.shuffle(pool_global_par)
        
        for p in pool_global_par:
            if pool_global_pq:
                pq = pool_global_pq.pop()
                zona_pq = db.query(Zona).filter(Zona.id == pq.zona_id, Zona.tenant_id == tenant_id).first()
                resultados.append({
                    "apartamento": p.apartamento,
                    "participante_id": p.id,
                    "tipo_resultado": "GANADOR",
                    "parqueadero_asignado": pq.numero,
                    "zona_asignada": zona_pq.nombre if zona_pq else "GLOBAL",
                    "fue_reasignado": True,
                    "es_hatchback": p.es_hatchback
                })
            else:
                resultados.append({
                    "apartamento": p.apartamento,
                    "participante_id": p.id,
                    "tipo_resultado": "PERDEDOR",
                    "parqueadero_asignado": None,
                    "zona_asignada": None,
                    "fue_reasignado": False,
                    "es_hatchback": p.es_hatchback
                })

    # PASO 6 — Fase 3: Optimización hatchback-doble
    optimizar_emparejamiento_dobles(db, tenant_id, resultados, rng, sorteo_id, modo_simulacion)

    # PASO 7 — Persistir o retornar
    if not modo_simulacion:
        sorteo.estado = "COMPLETADO"
        sorteo.seed = seed_hex
        sorteo.modelo_aplicado = "HIBRIDO"
        
        # Limpiar resultados previos si los hubiera (re-ejecución)
        db.query(ResultadoSorteo).filter(ResultadoSorteo.sorteo_id == sorteo_id, ResultadoSorteo.tenant_id == tenant_id).delete()

        for r in resultados:
            res_db = ResultadoSorteo(
                tenant_id=tenant_id,
                sorteo_id=sorteo_id,
                participante_id=r["participante_id"],
                apartamento=r["apartamento"],
                tipo_resultado=r["tipo_resultado"],
                parqueadero_asignado=r["parqueadero_asignado"],
                zona_asignada=r["zona_asignada"],
                fue_reasignado=r.get("fue_reasignado", False),
            )
            db.add(res_db)
        
        db.commit()
        
        ganadores = sum(1 for r in resultados if r["tipo_resultado"] == "GANADOR")
        registrar_log_auditoria(
            db=db,
            tenant_id=tenant_id,
            evento="SORTEO_EJECUTADO",
            payload=f"seed={seed_hex}, ganadores={ganadores}, modelo=HIBRIDO"
        )

    return resultados


def optimizar_emparejamiento_dobles(
    db: Session, tenant_id: str, resultados: List[Dict], rng: random.Random, sorteo_id: int, modo_simulacion: bool
):
    """
    Optimiza la asignación de parqueaderos dobles para hatchbacks.
    """
    ganadores = [r for r in resultados if r["tipo_resultado"] == "GANADOR"]
    mapa_pq = {}
    for r in ganadores:
        pq = r.get("parqueadero_asignado")
        if pq:
            if pq in mapa_pq:
                import logging
                logging.getLogger(__name__).warning("Duplicado de parqueadero %s en ganadores", pq)
            mapa_pq[pq] = r

    pares_procesados = set()
    swaps = 0

    for r in ganadores:
        pq_num = r["parqueadero_asignado"]
        if not pq_num or pq_num in pares_procesados:
            continue

        pq = db.query(Parqueadero).filter(
            Parqueadero.numero == pq_num, 
            Parqueadero.tenant_id == tenant_id
        ).first()
        
        if not pq or pq.tipo != "DOBLE" or not pq.vecino:
            continue

        vecino_num = pq.vecino
        resultado_vecino = mapa_pq.get(vecino_num)

        if vecino_num in pares_procesados:
            pares_procesados.add(pq_num)
            continue

        # Si ambos son hatchback, ya está optimizado
        if r.get("es_hatchback") and resultado_vecino and resultado_vecino.get("es_hatchback"):
            pares_procesados.update([pq_num, vecino_num])
            continue

        # Si r es hatchback pero el vecino no, buscamos otro hatchback para intercambiar
        if r.get("es_hatchback") and resultado_vecino and not resultado_vecino.get("es_hatchback"):
            candidato = next(
                (g for g in ganadores 
                 if g.get("es_hatchback") 
                 and g["parqueadero_asignado"] not in pares_procesados
                 and g["apartamento"] != r["apartamento"]
                 and g["parqueadero_asignado"] != pq_num),
                None
            )
            if candidato:
                # Intercambio
                temp_pq = resultado_vecino["parqueadero_asignado"]
                temp_zona = resultado_vecino["zona_asignada"]
                
                resultado_vecino["parqueadero_asignado"] = candidato["parqueadero_asignado"]
                resultado_vecino["zona_asignada"] = candidato["zona_asignada"]
                resultado_vecino["fue_reasignado"] = True
                
                candidato["parqueadero_asignado"] = temp_pq
                candidato["zona_asignada"] = temp_zona
                candidato["fue_reasignado"] = True
                
                swaps += 1
                if not modo_simulacion:
                    registrar_log_auditoria(
                        db=db,
                        tenant_id=tenant_id,
                        evento="OPTIMIZACION_DOBLES",
                        payload=f"Swap {resultado_vecino['apartamento']} <-> {candidato['apartamento']}"
                    )

        pares_procesados.update([pq_num, vecino_num])
