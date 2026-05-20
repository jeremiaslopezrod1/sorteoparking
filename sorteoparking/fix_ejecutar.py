import sys; sys.path.insert(0, '.')
with open('app/services/sorteos_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find ejecutar function boundaries
start = content.find('def ejecutar_sorteo_asignacion')
end = content.find('def notificar_resultados')
print(f'Function from {start} to {end}')

# Check if already wrapped
if 'except HTTPException' in content[start:end]:
    print('Already wrapped')
    sys.exit(0)

# Find the actual logic start (after the docstring and definition)
logic_marker = '    sorteo = _obtener_sorteo_tenant'
logic_pos = content.find(logic_marker, start)
print(f'Logic starts at {logic_pos}')

if logic_pos < 0:
    print('Could not find logic start')
    sys.exit(1)

# Split the function
prefix = content[:logic_pos]
suffix = content[logic_pos:]

# Add try
modified = prefix + '    try:\n' + suffix

# Find the next function and add except before it
next_func = modified.find('def ', len(prefix))
if next_func < 0:
    print('Could not find next function')
    sys.exit(1)

# The return statement is right before the next function
# Add except before the next function
before_next = modified[:next_func]
after_next = modified[next_func:]

# Find the last non-empty line before the next function
lines = before_next.split('\n')
while lines and lines[-1].strip() == '':
    lines.pop()

# Add except block
except_block = '''
    except HTTPException:
        raise
    except Exception as _ej_exc:
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en ejecucion: {str(_ej_exc)}")
'''

new_content = '\n'.join(lines) + except_block + '\n\n' + after_next

with open('app/services/sorteos_service.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('DONE - Added try/except to ejecutar')
