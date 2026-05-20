import sys; sys.path.insert(0, '.')
with open('app/services/sorteos_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '''    resultado_mutex = db.execute(

        update(Sorteo)

        .where(

            Sorteo.id == sorteo_id,

            Sorteo.tenant_id == tenant_id,

            Sorteo.estado == "LISTO"

        )

        .values(estado="EJECUTANDO")

        .returning(Sorteo.id)

    )

    db.commit()

    if not resultado_mutex.fetchone():

        sorteo_refrescado = db.query(Sorteo).filter(

            Sorteo.id == sorteo_id, Sorteo.tenant_id == tenant_id

        ).first()

        estado_actual = sorteo_refrescado.estado if sorteo_refrescado else "DESCONOCIDO"

        raise HTTPException(

            status_code=status.HTTP_409_CONFLICT,

            detail=f"El sorteo ya est\u00e1 siendo ejecutado o no est\u00e1 en estado LISTO (actual: {estado_actual})",

        )'''

NEW = '''    sorteo_antes = db.query(Sorteo).filter(
        Sorteo.id == sorteo_id,
        Sorteo.tenant_id == tenant_id,
        Sorteo.estado == "LISTO"
    ).first()

    if not sorteo_antes:
        sorteo_refrescado = db.query(Sorteo).filter(
            Sorteo.id == sorteo_id, Sorteo.tenant_id == tenant_id
        ).first()
        estado_actual = sorteo_refrescado.estado if sorteo_refrescado else "DESCONOCIDO"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El sorteo ya est\u00e1 siendo ejecutado o no est\u00e1 en estado LISTO (actual: {estado_actual})",
        )

    sorteo_antes.estado = "EJECUTANDO"
    db.commit()
    sorteo_refrescado = sorteo_antes'''

count = content.count(OLD)
if count > 0:
    content = content.replace(OLD, NEW)
    print(f'Replaced {count} occurrence(s)')
else:
    # Try without special chars
    print('Exact match not found. Searching for .returning...')
    idx = content.find('.returning(Sorteo.id)')
    if idx >= 0:
        print(f'Found .returning at position {idx}')
        # Show context
        print(repr(content[idx-100:idx+100]))
    else:
        print('.returning NOT found')

with open('app/services/sorteos_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
