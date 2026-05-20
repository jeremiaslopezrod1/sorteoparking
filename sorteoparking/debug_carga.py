"""Debug: test full catalog load function."""
import tempfile, os, sys
sys.path.insert(0, '.')
from openpyxl import Workbook
from app.services.catalogo_service import cargar_catalogo_desde_excel
from app.db.database import SessionLocal

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

db = SessionLocal()
try:
    with open(f.name, 'rb') as fh:
        data = fh.read()
        result = cargar_catalogo_desde_excel(db, 'test-tenant-id', data)
        print(f'OK: {result}')
except Exception as e:
    import traceback
    print(f'ERROR: {type(e).__name__}: {e}')
    traceback.print_exc()
finally:
    db.close()
    os.unlink(f.name)
