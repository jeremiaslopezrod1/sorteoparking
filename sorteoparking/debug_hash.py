"""Test snapshot hash methods"""
import hashlib, json

# Simulate test data
class P:
    def __init__(self, doc, name):
        self.documento = doc
        self.nombre = name

participantes = [P(f'CC{i}', f'R{i}') for i in range(1, 7)]

# Method 1: _calcular_snapshot_hash (used during iniciar)
lineas = sorted(f'{p.documento}|{p.nombre}' for p in participantes)
h1 = hashlib.sha256('\n'.join(lineas).encode('utf-8')).hexdigest()
print(f'Method 1 (_calcular): {h1}')

# Method 2: Old validation (json.dumps)
h2 = hashlib.sha256(
    json.dumps([{'documento': p.documento, 'nombre': p.nombre} for p in participantes],
               sort_keys=True).encode('utf-8')
).hexdigest()
print(f'Method 2 (old json): {h2}')

# Method 3: New validation (same as _calcular)
lineas3 = sorted(f'{p.documento}|{p.nombre}' for p in participantes)
h3 = hashlib.sha256('\n'.join(lineas3).encode('utf-8')).hexdigest()
print(f'Method 3 (new): {h3}')

stored = 'fea0cc2e08e641b7c100486e8133375d9d4e6e94ea4cf914539e9253c7a9392a'
print(f'\nMatch with stored:')
print(f'  Method 1: {h1 == stored}')
print(f'  Method 2: {h2 == stored}')
print(f'  Method 3: {h3 == stored}')
