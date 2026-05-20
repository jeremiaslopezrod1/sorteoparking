"""Debug: test _insertar_desde_df directly."""
import tempfile, os, sys
sys.path.insert(0, '.')
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from app.services.excel_parser import parsear_catalogo
from app.services.catalogo_service import _insertar_desde_df, _insertar_desde_df_legacy
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

with open(f.name, 'rb') as fh:
    data = fh.read()

# Step 1: parse
result = parsear_catalogo(data)
print(f'Parser OK: {result["filas_validas"]} filas')
col_map = result.get("_columnas_originales", {})
print(f'Col map: {col_map}')

# Step 2: read raw df
df = pd.read_excel(BytesIO(data), engine='openpyxl')
print(f'Columns in df: {list(df.columns)}')

# Step 3: test _get logic
def _get(row, campo):
    if campo in col_map:
        col_name = col_map[campo]
        if col_name in row.index:
            return row[col_name]
    return None

first_row = df.iloc[0]
num = _get(first_row, "numero_parqueadero")
print(f'First row numero_parqueadero: {num}')

vehiculo = _get(first_row, "tipo_vehiculo")
print(f'First row tipo_vehiculo: {vehiculo}')

zona = _get(first_row, "zona")
print(f'First row zona: {zona}')

# Step 4: test _insertar_desde_df
db = SessionLocal()
try:
    result2 = _insertar_desde_df(db, 'test-tenant-debug', df, col_map)
    print(f'_insertar_desde_df OK: {result2}')
except Exception as e:
    import traceback
    print(f'_insertar_desde_df ERROR: {type(e).__name__}: {e}')
    traceback.print_exc()
finally:
    db.close()
    os.unlink(f.name)
