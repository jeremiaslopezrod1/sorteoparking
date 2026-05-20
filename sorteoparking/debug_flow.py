"""Debug full flow step by step."""
import requests, hashlib, secrets, sqlite3, tempfile, os
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook

BASE = 'http://127.0.0.1:8767'
TOKEN = 'e15247d4c4a94f36a1d3b0c8f5e6d7a8'

th = hashlib.sha256(TOKEN.encode()).hexdigest()
sid = secrets.token_urlsafe(32)
csrf = secrets.token_urlsafe(32)
conn = sqlite3.connect('admin_sessions.db')
conn.execute('DELETE FROM admin_sessions')
conn.execute('INSERT INTO admin_sessions VALUES (?,?,?,?,?,NULL)',
    (sid, th, csrf, datetime.now(timezone.utc).isoformat(),
     (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
conn.commit()
conn.close()

COOKIES = {'admin_session': sid, 'csrf_token': csrf}
AH = {'X-CSRF-Token': csrf, 'Content-Type': 'application/json'}

# 1. Create tenant
r = requests.post(f'{BASE}/admin/tenants', json={'nombre':'DEBUG FLOW','municipio':'Bogota','email_admin':'t@t.com','total_unidades':50}, headers=AH, cookies=COOKIES)
TID = r.json()['id']
print(f'1. Tenant created: {TID[:16]}...')
HT = {'Authorization': f'Bearer {TID}'}

# 2. Upload catalog
f = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
wb = Workbook(); ws = wb.active; ws.title = 'CATALOGO'
ws.append(['numero','tipo_vehiculo','zona','tipo_espacio','torre','disponible','vecino'])
for i in range(1, 11):
    ws.append([f'P-{i:03d}', 'CARRO', f'Zona {chr(65+i%3)}', 'SENCILLO', 'T1', 'TRUE', ''])
wb.save(f.name); f.close()
with open(f.name, 'rb') as fh:
    r = requests.post(f'{BASE}/catalogo/carga-csv',
        files={'archivo': ('c.xlsx', fh, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers=HT)
    print(f'2. Catalog: status={r.status_code} data={r.json()}')
os.unlink(f.name)

# 3. Verify catalog
r = requests.get(f'{BASE}/catalogo/zonas', headers=HT)
print(f'3. Zonas: {len(r.json())}')
r = requests.get(f'{BASE}/catalogo/parqueaderos', headers=HT)
print(f'4. Parqueaderos: {len(r.json())}')

# 4. Upload elegibles
f = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
wb = Workbook(); ws = wb.active
ws.append(['nombre','documento','apartamento','torre','correo','tipoVehiculo','marcaModelo','esHatchback'])
for i in range(1, 7):
    ws.append([f'R{i}',f'CC{i}',f'{100+i}','T1',f'a{i}@t.com','CARRO','Mazda','NO'])
wb.save(f.name); f.close()
with open(f.name, 'rb') as fh:
    r = requests.post(f'{BASE}/sorteos/carga-excel',
        files={'archivo': ('e.xlsx', fh, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
        headers=HT)
    jd = r.json()
    SID = jd.get('sorteo_id')
    print(f'5. Elegibles: status={r.status_code} jd={jd}')
os.unlink(f.name)

# 5. Iniciar
consejeros = [{'nombre':f'C{i}','whatsapp':f'+5730010000{i}','email':f'c{i}@t.com'} for i in range(1,6)]
r = requests.post(f'{BASE}/sorteos/iniciar', json={'sorteo_id': SID, 'consejeros': consejeros}, headers=HT)
print(f'6. Iniciar: status={r.status_code} body={r.text[:300]}')

# 6. Estado
r = requests.get(f'{BASE}/sorteos/{SID}/estado', headers=HT)
print(f'7. Estado: {r.json()}')
