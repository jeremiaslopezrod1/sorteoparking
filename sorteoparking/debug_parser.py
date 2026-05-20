"""Quick debug: test parser directly."""
import tempfile, os, sys
sys.path.insert(0, '.')
from openpyxl import Workbook
from app.services.excel_parser import parsear_catalogo

f = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
wb = Workbook()
ws = wb.active
ws.title = 'CATALOGO'
ws.append(['numero','tipo_vehiculo','zona','tipo_espacio','torre','disponible','vecino'])
for i in range(1, 11):
    zona = 'Zona A' if i <= 4 else 'Zona B' if i <= 8 else 'Zona C'
    ws.append([f'P-{i:03d}', 'CARRO', zona, 'SENCILLO', 'Torre 1', 'TRUE', ''])
wb.save(f.name)
f.close()

with open(f.name, 'rb') as fh:
    data = fh.read()
    try:
        result = parsear_catalogo(data)
        print(f'OK: {result["filas_validas"]} filas validas')
        print(f'Columnas_originales: {result.get("_columnas_originales", {})}')
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}')
os.unlink(f.name)
