import sys; sys.path.insert(0, '.')
with open('app/services/sorteos_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the json.dumps block in the snapshot validation
idx = content.find('json.dumps(')
if idx >= 0:
    assign_start = content.rfind('hash_actual', idx - 200, idx)
    if assign_start >= 0:
        hex_end = content.find('.hexdigest()', idx) + len('.hexdigest()')
        block = content[assign_start:hex_end]
        
        replacement = '''        lineas = sorted(f"{p.documento}|{p.nombre}" for p in participantes)
        hash_actual = hashlib.sha256("\\n".join(lineas).encode("utf-8")).hexdigest()'''
        
        content = content.replace(block, replacement)
        print('Fixed snapshot validation')
        
with open('app/services/sorteos_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
