"""Fix the ejecutar mutex for SQLite (no .returning())."""
import sys; sys.path.insert(0, '.')
with open('app/services/sorteos_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = """    # SDD \u00a73.8 T-120 — Mutex de ejecuci\u00f3n: LISTO \u2192 EJECUTANDO (solo si est\u00e1 LISTO)
    resultado_mutex = db.execute(
        update(Sorteo)
        .where(
            Sorteo.id == sorteo_id,
            Sorteo.tenant_id == tenant_id,
            Sorteo.estado == \"LISTO\"
        )
        .values(estado=\"EJECUTANDO\")
        .returning(Sorteo.id)
    )
    db.commit()

    if not resultado_mutex.fetchone():
        sorteo_refrescado = db.query(Sorteo).filter(
            Sorteo.id == sorteo_id, Sorteo.tenant_id == tenant_id
        ).first()
        estado_actual = sorteo_refrescado.estado if sorteo_refrescado else \"DESCONOCIDO\"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f\"El sorteo ya est\u00e1 siendo ejecutado o no est\u00e1 en estado LISTO (actual: {estado_actual})\",
        )"""

# Also try without unicode
old2 = """    # SDD \xa73.8 T-120 - Mutex de ejecuci\xf3n: LISTO \xbb EJECUTANDO (solo si est\xe1 LISTO)
    resultado_mutex = db.execute(
        update(Sorteo)
        .where(
            Sorteo.id == sorteo_id,
            Sorteo.tenant_id == tenant_id,
            Sorteo.estado == \"LISTO\"
        )
        .values(estado=\"EJECUTANDO\")
        .returning(Sorteo.id)
    )
    db.commit()

    if not resultado_mutex.fetchone():
        sorteo_refrescado = db.query(Sorteo).filter(
            Sorteo.id == sorteo_id, Sorteo.tenant_id == tenant_id
        ).first()
        estado_actual = sorteo_refrescado.estado if sorteo_refrescado else \"DESCONOCIDO\"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f\"El sorteo ya est\xe1 siendo ejecutado o no est\xe1 en estado LISTO (actual: {estado_actual})\",
        )"""

new = """    # SDD \xa73.8 T-120 — Mutex de ejecuci\xf3n compatible con SQLite
    sorteo_antes = db.query(Sorteo).filter(
        Sorteo.id == sorteo_id,
        Sorteo.tenant_id == tenant_id,
        Sorteo.estado == "LISTO"
    ).first()

    if not sorteo_antes:
        estado_actual = db.query(Sorteo.estado).filter(
            Sorteo.id == sorteo_id, Sorteo.tenant_id == tenant_id
        ).scalar() or "DESCONOCIDO"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El sorteo ya est\xe1 siendo ejecutado o no est\xe1 en estado LISTO (actual: {estado_actual})",
        )

    sorteo_antes.estado = "EJECUTANDO"
    db.commit()
    sorteo_refrescado = sorteo_antes"""

if old in content:
    content = content.replace(old, new)
    print(f'Replace SUCCESS (unicode version)')
elif old2 in content:
    content = content.replace(old2, new)
    print(f'Replace SUCCESS (raw version)')
else:
    # Find .returning in context
    idx = content.find('.returning(Sorteo.id)')
    if idx >= 0:
        start = content.rfind('# SDD', 0, idx)
        end = content.find('    # SDD', idx)
        if end < 0: end = len(content)
        print(f'Found .returning at {idx}. Start={start} End={end}')
        print(f'Context: ...{content[start-20:end+20]}...')
    else:
        print('.returning NOT found')

with open('app/services/sorteos_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
