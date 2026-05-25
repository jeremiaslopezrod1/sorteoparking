"""
DIAGNÓSTICO COMPLETO DE AUTENTICACIÓN - SorteoParking

Ejecutar contra produccion Render:
    python diag_auth_completo.py

Prueba todo el flujo de session y cookies.
"""

import requests
import sys
import time

BASE = 'https://sorteoparking.onrender.com'
# Para desarrollo local:
# BASE = 'http://127.0.0.1:8772'  # o el puerto que uses

session = requests.Session()
ok = 0
fail = 0

def check(desc, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print(f'  ✅ {desc}')
    else:
        fail += 1
        print(f'  ❌ {desc}: {detail}')

def print_response(r, label='Response'):
    print(f'    {label}: status={r.status_code}')
    print(f'    Headers (auth/cookie related):')
    for k, v in r.headers.items():
        lower_k = k.lower()
        if any(x in lower_k for x in ('auth', 'cookie', 'csrf', 'set-cookie', 'x-auth')):
            print(f'      {k}: {v}')
    try:
        body = r.json()
        print(f'    Body: keys={list(body.keys())}')
        for k, v in body.items():
            if isinstance(v, (str, int, bool, float)):
                print(f'      {k}: {v}')
    except Exception:
        print(f'    Body (text): {r.text[:200]}')


print('=' * 60)
print('DIAGNÓSTICO DE AUTENTICACIÓN')
print('=' * 60)
print(f'Base URL: {BASE}')
print()

# 0. Health check
print('--- 0. Health Check ---')
r = session.get(f'{BASE}/health')
check('Health endpoint', r.json().get('status') == 'ok', str(r.status_code))

# 1. Session check BEFORE login
print('\n--- 1. Session Check SIN Login ---')
r = session.get(f'{BASE}/auth/session-check')
check('Session-check endpoint reachable', r.status_code == 200, str(r.status_code))
if r.status_code == 200:
    diag = r.json()
    check('  no admin_session presente', not diag.get('admin_session_presente'))
    check('  sesion_valida_en_bd = False', not diag.get('sesion_valida_en_bd'))
    print(f'  Cookies recibidas: {diag.get("cookies_recibidas")}')
    print(f'  Scheme: {diag.get("url_scheme")}')
    print(f'  es_https: {diag.get("es_https")}')

# 2. Admin access WITHOUT auth
print('\n--- 2. Admin Access SIN Auth (debe fallar) ---')
r = session.get(f'{BASE}/admin/metricas')
check('Admin/metricas sin auth -> 403', r.status_code == 403, str(r.status_code))
detail = ''
try: detail = r.json().get('detail', r.text[:200])
except: detail = r.text[:200]
print(f'  Detail: {detail}')
# Check for custom headers
for k, v in r.headers.items():
    if 'x-auth' in k.lower() or 'x-csrf' in k.lower():
        print(f'  {k}: {v}')

# 3. LOGIN
print('\n--- 3. LOGIN ---')
print('⚠️  Enter SUPER_ADMIN_USER and SUPER_ADMIN_PASSWORD:')
username = input('  Username: ').strip()
password = input('  Password: ').strip()

if username and password:
    r = session.post(f'{BASE}/auth/login/superadmin', json={
        'username': username,
        'password': password
    })
    check('Login -> 200', r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        data = r.json()
        check('  response.ok == True', data.get('ok') == True)
        check('  csrf_token en body', bool(data.get('csrf_token')))
        check('  expires_in == 3600', data.get('expires_in') == 3600)
        print(f'  CSRF token (first 20): {str(data.get("csrf_token",""))[:20]}...')

        # 3b. Check cookies in session
        cookies = session.cookies.get_dict()
        print(f'  Cookies en session: {list(cookies.keys())}')
        check('  admin_session cookie', 'admin_session' in cookies)
        check('  csrf_token cookie', 'csrf_token' in cookies)
        
        csrf = cookies.get('csrf_token', '')
        print(f'  CSRF cookie value (first 20): {csrf[:20]}...')
        
        # 4. Session check AFTER login
        print('\n--- 4. Session Check POST Login ---')
        r = session.get(f'{BASE}/auth/session-check')
        check('Session-check -> 200', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            diag = r.json()
            check('  admin_session_presente', diag.get('admin_session_presente') == True)
            check('  sesion_valida_en_bd', diag.get('sesion_valida_en_bd') == True)
            check('  csrf_cookie_presente', diag.get('csrf_cookie_presente') == True)
            print(f'  Cookies recibidas: {diag.get("cookies_recibidas")}')
            print(f'  Session fragment: {diag.get("session_id_fragmento","N/A")}')
        
        # 5. GET /admin/metricas
        print('\n--- 5. GET /admin/metricas ---')
        r = session.get(f'{BASE}/admin/metricas')
        check('Metricas -> 200', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            data = r.json()
            print(f'  tenants: {data.get("tenants", {})}')
            print(f'  sorteos: {data.get("sorteos", {})}')
        else:
            print_response(r)
        
        # 6. GET /admin/tenants
        print('\n--- 6. GET /admin/tenants ---')
        r = session.get(f'{BASE}/admin/tenants')
        check('Tenants list -> 200', r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print_response(r)
        
        # 7. POST /admin/tenants WITH CSRF
        print('\n--- 7. POST /admin/tenants (with CSRF) ---')
        test_suffix = int(time.time())
        r = session.post(f'{BASE}/admin/tenants',
            json={
                'nombre': f'DIAG TEST {test_suffix}',
                'municipio': 'Bogota',
                'email_admin': f'diag{test_suffix}@test.com',
                'total_unidades': 10
            },
            headers={'X-CSRF-Token': csrf}
        )
        check('POST tenant -> 201', r.status_code == 201, str(r.status_code))
        if r.status_code == 201:
            data = r.json()
            check('  slug presente', bool(data.get('slug')))
            print(f'  Tenant creado: id={str(data.get("id",""))[:16]}... slug={data.get("slug")}')
        else:
            print_response(r)

        # 8. POST /admin/tenants SIN CSRF (debe fallar)
        print('\n--- 8. POST /admin/tenants SIN CSRF (debe fallar) ---')
        r = session.post(f'{BASE}/admin/tenants',
            json={
                'nombre': 'SIN CSRF TEST',
                'municipio': 'Cali',
                'email_admin': 'sincsrf@test.com'
            }
        )
        check('POST sin CSRF -> 403', r.status_code == 403, str(r.status_code))
        try:
            detail = r.json().get('detail', '')
            print(f'  Detail: {detail}')
        except:
            pass

        # 9. LOGOUT
        print('\n--- 9. Logout ---')
        r = session.post(f'{BASE}/auth/logout')
        check('Logout -> 200', r.status_code == 200, str(r.status_code))
        
        # 10. Session check AFTER logout
        print('\n--- 10. Session Check POST Logout ---')
        r = session.get(f'{BASE}/auth/session-check')
        check('Session-check -> 200', r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            diag = r.json()
            check('  admin_session NOT presente', not diag.get('admin_session_presente'))
            check('  sesion_valida_en_bd = False', not diag.get('sesion_valida_en_bd'))

else:
    print('⚠️  No credentials provided, skipping login tests')

print()
print('=' * 60)
print(f'RESULTADOS: {ok} OK, {fail} FAIL')
print('=' * 60)
sys.exit(0 if fail == 0 else 1)
