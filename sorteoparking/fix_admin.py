import sys; sys.path.insert(0, '.')
with open('app/routers/admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the router definition
needle = 'router = APIRouter('
idx = content.find(needle)
if idx < 0:
    print('Router definition not found')
    sys.exit(1)

# Find the end of the APIRouter call
end = content.find(')', idx)
if end < 0:
    print('End of APIRouter not found')
    sys.exit(1)

old_router = content[idx:end+1]

new_func = '''
import hmac
from fastapi import Request

def _super_admin_bearer(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Acceso denegado: se requiere token Bearer")
    token = auth.removeprefix("Bearer ").strip()
    from app.core.config import super_admin_config
    if not super_admin_config.super_admin_token:
        raise HTTPException(status_code=500, detail="SUPER_ADMIN_TOKEN no configurado")
    if not hmac.compare_digest(token, super_admin_config.super_admin_token):
        raise HTTPException(status_code=403, detail="Token de SUPER_ADMIN invalido")
    return token

'''

new_router = 'router = APIRouter(\n    prefix="/admin",\n    tags=["admin"],\n    dependencies=[Depends(_super_admin_bearer)],\n)'

content = content.replace(old_router, new_router)

# Add the import for HTTPException if not present
if 'from fastapi import APIRouter' in content:
    pass  # HTTPException already imported

# Add hmac import
if 'import hmac' not in content:
    content = content.replace('import os', 'import os\nimport hmac')

with open('app/routers/admin.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Admin router fixed with Bearer auth')
