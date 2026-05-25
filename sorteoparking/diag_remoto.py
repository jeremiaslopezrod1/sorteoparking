"""Diagnostico remoto de auth en produccion Render."""
import requests
import sys

BASE = 'https://sorteoparking.onrender.com'

session = requests.Session()

print('=== DIAGNOSTICO PRODUCCION ===\n')

# 0. Health
r = session.get(f'{BASE}/health')
print(f'Health: {r.status_code}')

# 1. Session check (sin login)
r = session.get(f'{BASE}/auth/session-check')
diag = r.json()
print(f'\nSession-check SIN login:')
print(f'  cookies_recibidas: {diag.get("cookies_recibidas")}')
print(f'  admin_session_presente: {diag.get("admin_session_presente")}')
print(f'  es_https: {diag.get("es_https")}')
print(f'  base_url: {diag.get("base_url")}')

# 2. Intentar acceder a admin sin auth (debe fallar)
r = session.get(f'{BASE}/admin/metricas')
print(f'\nGET /admin/metricas sin auth: {r.status_code}')
try:
    print(f'  body: {r.json()}')
except:
    print(f'  body: {r.text[:200]}')

# 3. Headers de la respuesta 401/403
print(f'\nResponse headers:')
for k, v in r.headers.items():
    if 'cookie' in k.lower() or 'auth' in k.lower() or 'csrf' in k.lower():
        print(f'  {k}: {v}')
