"""E2E Test + Monkey Test -- SorteoParking v1.6"""
import requests, hashlib, secrets, os, sqlite3, tempfile
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook
from app.services.otp_service import generar_otp_numerico_seis_digitos, hashear_otp

BASE = 'http://127.0.0.1:8769'
TOKEN = 'e152473d-072f-44bd-b4b0-d0513f1f4f36'
ok = 0; fail = 0; errors = []

def check(desc, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print(f'  [OK] {desc}')
    else:
        fail += 1
        errors.append(desc)
        print(f'  [FAIL] {desc}{": " + detail if detail else ""}')

HEADERS = {'Content-Type': 'application/json', 'Authorization': f'Bearer {TOKEN}'}

print('\n=== E2E TEST - SorteoParking v1.6 ===\n')

# 1. Health
r = requests.get(f'{BASE}/health')
check('GET /health', r.json().get('status') == 'ok')

# 2. Monkey tests
for m, p in [('GET','/sorteos/historial'),('GET','/catalogo/zonas'),('POST','/sorteos/iniciar'),
             ('GET','/admin/tenants'),('POST','/admin/backup'),('DELETE','/sorteos/1'),
             ('PATCH','/admin/tenants/fake'),('POST','/catalogo/carga-csv')]:
    r = requests.request(m, f'{BASE}{p}', timeout=5)
    check(f'Monkey {m} {p} -> {r.status_code}', r.status_code in (401,403,405))

# 3. Create tenant
r = requests.post(f'{BASE}/admin/tenants', json={'nombre':'E2E TEST','municipio':'Bogota','email_admin':'t@t.com','total_unidades':50}, headers=HEADERS)
check('Crear tenant', r.status_code == 201, r.text)
TENANT_ID = r.json()['id']
SLUG = r.json()['slug']
print(f'  Tenant: {TENANT_ID[:16]}... | Slug: {SLUG}')
HT = {'Authorization': f'Bearer {TENANT_ID}'}

# 4. Isolation
r = requests.get(f'{BASE}/catalogo/zonas', headers=HT)
check('Aislamiento: 0 zonas', len(r.json()) == 0)

# 5. Upload catalog
f = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
wb = Workbook(); ws = wb.active; ws.title = 'CATALOGO'
ws.append(['numero','tipo_vehiculo','zona','tipo_espacio','torre','disponible','vecino'])
for i in range(1,11): ws.append([f'P-{i:03d}','CARRO',f'Zona {chr(65+i%3)}','SENCILLO','T1','TRUE',''])
wb.save(f.name); f.close()
with open(f.name, 'rb') as fh:
    r = requests.post(f'{BASE}/catalogo/carga-csv', files={'archivo':('c.xlsx',fh,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, headers=HT)
    check('Cargar 10 pq', r.status_code in (200,201) and r.json()['parqueaderos_cargados']==10, r.text)
os.unlink(f.name)

# 6. Verify
r = requests.get(f'{BASE}/catalogo/zonas', headers=HT)
check('3 zonas', len(r.json()) == 3)
r = requests.get(f'{BASE}/catalogo/parqueaderos', headers=HT)
check('10 pq', len(r.json()) == 10)
r = requests.get(f'{BASE}/catalogo/plantilla', headers=HT)
check('Plantilla', r.status_code == 200)

# 7. Upload elegibles
f = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
wb = Workbook(); ws = wb.active
ws.append(['nombre','documento','apartamento','torre','correo','tipoVehiculo','marcaModelo','esHatchback'])
for i in range(1,7): ws.append([f'R{i}',f'CC{i}',f'{100+i}','T1',f'a{i}@t.com','CARRO','Mazda','NO'])
wb.save(f.name); f.close()
with open(f.name, 'rb') as fh:
    r = requests.post(f'{BASE}/sorteos/carga-excel', files={'archivo':('e.xlsx',fh,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, headers=HT)
    check('Cargar elegibles', r.status_code in (200,201) and r.json().get('sorteo_id'), r.text)
    SORTEO_ID = r.json()['sorteo_id']
os.unlink(f.name)
print(f'  Sorteo ID: {SORTEO_ID}')

# 8. Start raffle
consejeros = [{'nombre':f'C{i}','whatsapp':f'+5730010000{i}','email':f'c{i}@t.com'} for i in range(1,6)]
r = requests.post(f'{BASE}/sorteos/iniciar', json={'sorteo_id':SORTEO_ID,'consejeros':consejeros}, headers=HT)
check('Iniciar sorteo', r.status_code == 201, r.text)
r = requests.get(f'{BASE}/sorteos/{SORTEO_ID}/estado', headers=HT)
check('Estado EN_CURSO', r.json()['estado'] == 'EN_CURSO', r.text)

# 9. Confirm OTPs
sesiones = []
conn = sqlite3.connect('sorteoparking.db')
sesiones = conn.execute('SELECT id, token_enlace FROM sesiones_otp WHERE sorteo_id=?', (SORTEO_ID,)).fetchall()
conn.close()
print(f'  OTPs: {len(sesiones)}')

for i, (ses_id, token_enlace) in enumerate(sesiones):
    otp = generar_otp_numerico_seis_digitos()
    conn = sqlite3.connect('sorteoparking.db')
    conn.execute('UPDATE sesiones_otp SET otp_hash=? WHERE id=?', (hashear_otp(otp), ses_id))
    conn.commit(); conn.close()
    r = requests.post(f'{BASE}/sorteos/{SORTEO_ID}/otp/confirmar', json={'otp':otp}, headers={'X-Sorteo-Otp-Token':token_enlace})
    check(f'OTP {i+1}', r.status_code == 200, r.text)

# 10. LISTO
r = requests.get(f'{BASE}/sorteos/{SORTEO_ID}/estado', headers=HT)
check('Estado LISTO', r.json()['estado'] == 'LISTO', r.text)
r = requests.get(f'{BASE}/sorteos/{SORTEO_ID}/otp/estado', headers=HT)
check('5/5 OTPs', r.json()['confirmados'] == 5)

# 11. Diagnostico
r = requests.get(f'{BASE}/sorteos/{SORTEO_ID}/diagnostico', headers=HT)
check('Diagnostico', r.status_code == 200)

# 12. Execute
r = requests.post(f'{BASE}/sorteos/{SORTEO_ID}/ejecutar', headers=HT)
check('Ejecutar', r.status_code == 200 and len(r.json()) > 0, r.text)
r2 = requests.post(f'{BASE}/sorteos/{SORTEO_ID}/ejecutar', headers=HT)
check('Doble clic -> 409', r2.status_code == 409, r2.text)

# 13. Results
r = requests.get(f'{BASE}/sorteos/{SORTEO_ID}/estado', headers=HT)
check('COMPLETADO', r.json()['estado'] == 'COMPLETADO', r.text)
check('Seed presente', r.json().get('seed') is not None)
r = requests.get(f'{BASE}/sorteos/{SORTEO_ID}/resultados', headers=HT)
check('Resultados paginados', len(r.json()['items']) > 0)

# 14. Export
r = requests.post(f'{BASE}/sorteos/{SORTEO_ID}/exportar', params={'formato':'excel'}, headers=HT)
check('Export Excel', r.status_code == 200)
r = requests.post(f'{BASE}/sorteos/{SORTEO_ID}/exportar', params={'formato':'word'}, headers=HT)
check('Export Word', r.status_code == 200)

# 15. Public
r = requests.get(f'{BASE}/p/{SLUG}/sorteos/{SORTEO_ID}')
check('Vista publica', r.status_code == 200)
r = requests.get(f'{BASE}/p/{SLUG}/sorteos/{SORTEO_ID}/seed')
check('Seed publico', r.json().get('seed') is not None)

# 16. Anti-replay
conn = sqlite3.connect('sorteoparking.db')
tk = conn.execute('SELECT token_enlace FROM sesiones_otp WHERE sorteo_id=? LIMIT 1', (SORTEO_ID,)).fetchone()[0]
conn.close()
r = requests.post(f'{BASE}/sorteos/{SORTEO_ID}/otp/confirmar', json={'otp':'000000'}, headers={'X-Sorteo-Otp-Token':tk})
check('Replay OTP -> 400', r.status_code == 400, r.text)

# 17. Notify
r = requests.post(f'{BASE}/sorteos/{SORTEO_ID}/notificar', headers=HT)
check('Notificar', r.status_code == 200, r.text)

# 18. Multi-tenant
r3x = requests.post(f'{BASE}/admin/tenants', json={'nombre':'INTRUSO','municipio':'Cali','email_admin':'i@t.com'}, headers=HEADERS)
T2 = r3x.json()['id']
HT2 = {'Authorization': f'Bearer {T2}'}
r = requests.get(f'{BASE}/catalogo/zonas', headers=HT2)
check('Tenant B sin zonas', len(r.json()) == 0)
r = requests.get(f'{BASE}/sorteos/{SORTEO_ID}/estado', headers=HT2)
check('Tenant B sin acceso', r.status_code == 404, r.text)

print(f'\n=== RESULTADOS: {ok} OK, {fail} FAIL ===')
if fail > 0: print(f'Errores: {", ".join(errors)}')
exit(0 if fail == 0 else 1)
