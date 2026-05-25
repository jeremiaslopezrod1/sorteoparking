"""Envio de informe por correo a Michael."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.email_service import enviar_correo_texto

reporte = """Asunto: SorteoParking | FIX: Login loop al crear conjunto

Hola Michael,

PROBLEMA
========
Cuando intentabas crear un conjunto desde el panel Super Admin, la app te
devolvia al login sin crear nada. Loop infinito: login -> crear conjunto ->
login -> crear conjunto...

CAUSA RAIZ
==========
El endpoint de login (/auth/login/superadmin) devolvia HTTP 204 No Content.

El proxy de Render (y algunos navegadores) IGNORAN las cabeceras Set-Cookie
en respuestas 204 (sin body). Resultado: las cookies admin_session y
csrf_token NUNCA se guardaban en el navegador.

Las peticiones GET cargaban el dashboard vacio (con skeletons) porque
showDashboard() se ejecuta al recibir 2xx, pero las llamadas a /admin/metricas
fallaban en silencio (403, sin cookies).

Al hacer POST /admin/tenants (crear conjunto), el backend pedia CSRF.
Sin cookies, el frontend no tenia CSRF que enviar -> 403 -> redirigia al login.

CAMBIOS REALIZADOS
==================

1. auth.py:
   - Login ahora devuelve 200 OK con JSON {ok, csrf_token, expires_in}
   - delete_cookie ahora incluye secure= y samesite= (antes no coincidian
     con las cookies originales y el navegador no las borraba)
   - Deteccion HTTPS via X-Forwarded-Proto (proxy de Render)
   - Logout tambien devuelve 200 OK

2. superadmin.html:
   - Nueva funcion getCsrfToken() con triple fallback:
     a) Cookie csrf_token (funcionamiento normal)
     b) Cache en memoria del CSRF devuelto en el body del login
     c) sessionStorage (sobrevive recargas de pagina)
   - Si el proxy/navegador ignora la cookie, el CSRF del JSON body
     se usa como respaldo

3. admin.py y session_store.py:
   - Codigos de error detallados [A0]-[A7] para diagnostico futuro
   - Sesiones extendidas a 60 minutos
   - validate_csrf() validacion contra BD

VERIFICACION
============
Test E2E especifico del flujo login-cookie-POST:
  12/12 tests OK

Incluye:
  - Login 200 OK
  - CSRF en body + cookies
  - GET metricas funciona
  - GET tenants funciona
  - POST crear tenant CON CSRF -> 201 Created
  - POST crear tenant SIN CSRF -> 403 (seguridad intacta)

DEPLOY
======
Commit: 65540a9
Push a GitHub main -> Render deberia hacer deploy automatico.
Si no es automatico, haz deploy manual desde el dashboard de Render.

Revisa en: https://dashboard.render.com

--
Jarvis"""

ok = enviar_correo_texto(
    destino="pruebaalisocajica@gmail.com",
    asunto="SorteoParking v1.7 - FIX: Login loop al crear conjunto",
    cuerpo=reporte
)
print(f"Envio por email: {'EXITOSO' if ok else 'FALLIDO (sin SMTP configurado localmente)'}")
