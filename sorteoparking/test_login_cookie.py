"""Test especifico: login con cookie -> crear tenant (POST con CSRF)."""
import requests
import sys
import json

BASE = 'http://127.0.0.1:8769'
ok = 0
fail = 0

def check(desc, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print(f'  [OK] {desc}')
    else:
        fail += 1
        print(f'  [FAIL] {desc}{": " + detail if detail else ""}')

print('\n=== TEST: Login por cookie -> POST crear tenant ===\n')

# 1. Health check
r = requests.get(f'{BASE}/health')
check('GET /health', r.json().get('status') == 'ok', r.text)

# 2. Login como superadmin
print('\n--- Login ---')
session = requests.Session()
r = session.post(f'{BASE}/auth/login/superadmin', json={
    'username': 'admin',
    'password': 'test1234'
})
check('POST /auth/login/superadmin -> 200', r.status_code == 200, f'status={r.status_code}')
if r.status_code == 200:
    data = r.json()
    check('  response.ok == True', data.get('ok') == True)
    check('  csrf_token en body', bool(data.get('csrf_token')), str(data.get('csrf_token',''))[:20]+'...')
    check('  expires_in == 3600', data.get('expires_in') == 3600)
    
    # Verificar cookies
    cookies = session.cookies.get_dict()
    print(f'  Cookies recibidas: {list(cookies.keys())}')
    check('  cookie admin_session', 'admin_session' in cookies, str(cookies.keys()))
    check('  cookie csrf_token', 'csrf_token' in cookies, str(cookies.keys()))
    
    if 'csrf_token' in cookies:
        csrf = cookies['csrf_token']
        print(f'  CSRF cookie: {csrf[:20]}...')
        
        # 3. GET /admin/metricas (debe funcionar)
        print('\n--- GET metricas ---')
        r = session.get(f'{BASE}/admin/metricas')
        check('GET /admin/metricas -> 200', r.status_code == 200, f'status={r.status_code} {r.text[:100]}')
        
        # 4. GET /admin/tenants (debe funcionar)
        print('\n--- GET tenants ---')
        r = session.get(f'{BASE}/admin/tenants')
        check('GET /admin/tenants -> 200', r.status_code == 200, f'status={r.status_code}')
        
        # 5. POST /admin/tenants con CSRF header
        print('\n--- POST crear tenant ---')
        r = session.post(f'{BASE}/admin/tenants', 
            json={
                'nombre': 'TEST COOKIE',
                'municipio': 'Bogota',
                'email_admin': 'test@test.com',
                'total_unidades': 30
            },
            headers={'X-CSRF-Token': csrf}
        )
        check('POST /admin/tenants -> 201', r.status_code == 201, f'status={r.status_code} body={r.text[:200]}')
        if r.status_code == 201:
            data = r.json()
            check('  slug presente', bool(data.get('slug')), str(data.get('slug','')))
            print(f'  Tenant creado: {data.get("id","")[:16]}... slug={data.get("slug")}')
        
        # 6. POST /admin/tenants SIN CSRF (debe fallar)
        print('\n--- POST sin CSRF (debe fallar) ---')
        r2 = session.post(f'{BASE}/admin/tenants',
            json={'nombre': 'SIN CSRF', 'municipio': 'Cali', 'email_admin': 'x@x.com'}
        )
        check('POST sin CSRF -> 403', r2.status_code == 403, f'status={r2.status_code}')

print(f'\n=== RESULTADO: {ok} OK, {fail} FAIL ===')
sys.exit(0 if fail == 0 else 1)
