# SorteoParking

Implementacion base del servicio definida por `SDD_SorteoParking_Servicio_v1.7.md`.

## Fuente de verdad

Todo el desarrollo de este repositorio se alinea estrictamente al SDD:

- `SDD_SorteoParking_Servicio_v1.7.md`

## Estructura del proyecto (SDD §3.4)

```
sorteoparking/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── security_headers.py
│   │   ├── session_store.py
│   │   ├── scheduler.py
│   │   └── slug.py
│   ├── models/
│   │   ├── tenant.py
│   │   ├── catalogo.py
│   │   ├── sorteo.py
│   │   ├── log.py
│   │   └── superadmin.py
│   ├── routers/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── catalogo.py
│   │   ├── sorteos.py
│   │   └── publico.py
│   ├── services/
│   │   ├── sorteo_engine.py
│   │   ├── sorteos_service.py
│   │   ├── catalogo_service.py
│   │   ├── otp_service.py
│   │   ├── whatsapp.py
│   │   ├── email_service.py
│   │   ├── log_service.py
│   │   ├── excel_parser.py
│   │   ├── deepseek_service.py
│   │   └── exportadores.py
│   ├── scripts/
│   │   ├── backup_db.py
│   │   └── create_superadmin.py
│   └── db/
│       └── database.py
├── frontend/
│   ├── dashboard.html
│   ├── otp_panel.html
│   ├── publico.html
│   └── superadmin.html
├── agents.md
├── SDD_SorteoParking_Servicio_v1.7.md
├── requirements.txt
└── README.md
```

## Avance por tareas

### T-101 (SDD §4.1 y §4.2) - Completada

- Entidad `Tenant` creada.
- `tenant_id` agregado como primera columna en tablas heredadas:
  - `Zona`, `Torre`, `Parqueadero`
  - `Participante`, `Consejero`, `Sorteo`, `SesionOTP`, `ResultadoSorteo`
  - `LogAuditoria`

### T-102 (SDD §3.3 y §5) - Completada

- Middleware `Authorization: Bearer {token}` para rutas privadas.
- Extraccion de `tenant_id` desde token.
- Exclusion de rutas publicas `/p/...` y ruta de salud `/health`.
- Validacion de aislamiento por tenant con respuesta `403` en cruce de tenant.

### T-103 (SDD §5.1) - Completada (Asegurada)

- `POST /admin/tenants`:
  - crea tenant (onboarding)
  - responde `201`
  - valida NIT duplicado y responde `409`
- `GET /admin/tenants`:
  - lista tenants activos (`estado=ACTIVO`)
  - responde `200`
- **Seguridad**: Rutas protegidas con `verify_super_admin`. Requieren token UUID en el header `Authorization: Bearer {token}`.
- **Mecanismo dual**: Valida contra variable de entorno `SUPER_ADMIN_TOKEN` (dev/CI) o tabla `superadmins` (prod).

### T-104 (SDD §3.1) - Completada

- Formulario de onboarding para registro de nuevo conjunto en:
  - `frontend/dashboard.html`
- El formulario envia `POST /admin/tenants` con `Authorization: Bearer {token}`.
- Campos alineados con entidad `Tenant` del SDD.

### T-105 (SDD §3.2) - Completada

- Configuracion de despliegue por variables de entorno en `app/core/config.py`:
  - `APP_ENV` (default `development`)
  - `APP_HOST` (default `0.0.0.0`)
  - `PORT` o `APP_PORT` (default `8000`)
  - `DATABASE_URL` (default `sqlite:///./sorteoparking.db`)
- Conexion de base de datos adaptada para Cloud en `app/db/database.py` usando `DATABASE_URL`.
- Arranque compatible con Railway/Render:
  - `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- HTTPS en produccion delegado al proveedor Cloud (Railway/Render), segun SDD §3.2.

### T-106 (SDD §3.5) - Completada

- Migracion funcional de catalogo/sorteo/log con `tenant_id`:
  - Servicios nuevos en `app/services/` para separar logica de negocio de routers.
  - `app/services/catalogo_service.py` filtra por tenant en zonas y parqueaderos.
  - `app/services/sorteos_service.py` lista historial por tenant.
  - `app/services/log_service.py` registra `LogAuditoria` encadenado por tenant (`hash_anterior` -> `hash_actual`).
- Routers conectados a servicios:
  - `GET /catalogo/zonas`
  - `GET /catalogo/parqueaderos`
  - `GET /sorteos/historial`
- Todas las consultas de estos flujos aplican filtro estricto por `tenant_id`.

### Mes 2 — T-201 a T-206 (SDD §5.3, §5.4, §6, §3.2) - Actualizada a v1.7

- **T-201** — `app/services/email_service.py`: envío por SMTP. Variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
- **T-202** — Panel consejero `frontend/otp_panel.html` (estatico `/static/otp_panel.html`) + confirmacion `POST /sorteos/{id}/otp/confirmar` con header `X-Sorteo-Otp-Token` (sin Bearer de tenant).
- **T-203** — `frontend/dashboard.html`: polling cada 2s a `GET /sorteos/{id}/otp/estado` y `GET /sorteos/{id}/estado`.
- **T-204** — `POST /sorteos/{id}/notificar`: notificación por correo electrónico a participantes. Variables SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
- **T-205** — `GET /p/{tenant_slug}/sorteos/{id}` y `.../seed` + `frontend/publico.html`.
- Otros endpoints Mes 2: `POST /sorteos/carga-excel`, `POST /sorteos/iniciar`, `POST /sorteos/{id}/ejecutar` (asignacion determinista por seed SDD §6.3, distinta del motor hibrido v1.4.3 hasta integrar `sorteo_engine.py`).
- **Slug** en `tenants.slug` (URLs publicas SDD §5.4); onboarding asigna slug; arranque rellena slugs faltantes.
- Variables adicionales: `PUBLIC_BASE_URL` (enlaces en mensajes OTP), `OTP_PEPPER` (hash OTP en produccion).

Si la base SQLite ya existia antes de Mes 2, puede hacer falta borrar `sorteoparking.db` para recrear tablas con las nuevas columnas, o aplicar migraciones manuales.

## Despliegue Cloud (Railway) - SDD §3.2

Configura estas variables en el servicio de Railway:

- `APP_ENV=production`
- `APP_HOST=0.0.0.0`
- `PORT` (Railway la inyecta automaticamente)
- `DATABASE_URL=sqlite:///./sorteoparking.db`

Comando de inicio:

- `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

Validacion minima post-despliegue:

- `GET /health` responde `{"status":"ok"}`
- El servicio queda publicado por URL `https://...` administrada por Railway

### Mes 3 — T-301 (SDD §3.5, §9) - Completada

- **T-301** — `app/services/sorteo_engine.py`: Integración del motor híbrido determinista v1.4.3.
  - Implementación de `ejecutar_sorteo_hibrido` (Modelo 2: por zona + pool global).
  - Derivación de seed reproducible `SHA-256(timestamp_utc + snapshot_hash)`.
  - Optimización de parqueaderos dobles (Tandem) para vehículos hatchback.
  - Aislamiento multi-tenant estricto en todas las consultas del motor.
- **Modelos**: Actualizados para trazabilidad completa:
  - `Sorteo`: `modelo_aplicado`.
  - `Participante`: `apartamento`, `es_hatchback`, `tipo_vehiculo`.
  - `ResultadoSorteo`: `apartamento`, `tipo_resultado`, `parqueadero_asignado`, `zona_asignada`, `fue_reasignado`.
- **Frontend**: Sincronización de estados (`LISTO` -> `COMPLETADO`) en dashboard y paneles públicos.

### Hardening y Backups — T-121 y T-122 (SDD §18, §19) - Completada

- **T-121** — `app/scripts/backup_db.py` y `app/core/scheduler.py`: Backup automático diario de SQLite.
  - Implementación de SQLite backup API para consistencia con WAL.
  - Verificación automática de integridad (`PRAGMA integrity_check` y lectura de tenants).
  - Rotación y purga automática de backups conservando los últimos 30 días.
  - Scheduler liviano integrado en el arranque asíncrono y endpoint de backup manual `/admin/backup` para `SUPER_ADMIN`.
- **T-122** — `app/core/security_headers.py`: HTTP Security Headers (HSTS, CSP, X-Frame-Options).
  - Configuración global de cabeceras de seguridad (`Strict-Transport-Security`, `X-Frame-Options: DENY`, `Content-Security-Policy` restrictiva, `X-Content-Type-Options`, `Referrer-Policy`, y `Permissions-Policy`).
  - Cache Control diferenciado: las vistas públicas (`/p/...`) son cacheables por 5 minutos, mientras que el panel de administración y las APIs tienen cabeceras estrictas de `no-store` para evitar fugas de información.
  - Registrado como middleware prioritario para cubrir todos los flujos de respuesta incluyendo errores.

## Despliegue Cloud (Railway) - SDD §3.2

Configura estas variables en el servicio de Railway:

- `APP_ENV=production`
- `APP_HOST=0.0.0.0`
- `PORT` (Railway la inyecta automaticamente)
- `DATABASE_URL=sqlite:///./sorteoparking.db`

Comando de inicio:

- `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`

Validacion minima post-despliegue:

- `GET /health` responde `{"status":"ok"}`
- El servicio queda publicado por URL `https://...` administrada por Railway

## Gestión de SUPER_ADMIN (SDD §2, §5.1)

Para acceder a los endpoints de `/admin/`, es necesario generar un token de acceso global.

### Inicialización de Token

Ejecutar el script desde la raíz del proyecto (`sorteoparking/`):

```bash
# Generar y guardar en base de datos (Producción)
python -m app.scripts.create_superadmin --descripcion "token admin inicial"

# Solo generar para .env (Desarrollo / CI sin base de datos)
python -m app.scripts.create_superadmin --env-only
```

### Variables de Entorno Adicionales

- `SUPER_ADMIN_TOKEN`: Token UUID para bypass de base de datos en entornos de desarrollo.
- `OTP_PEPPER`: Pepper para el hash SHA-256 de los OTPs.
- `PUBLIC_BASE_URL`: URL base para los enlaces enviados por correo a los consejeros.

## ADVERTENCIA — OTPs en entornos de desarrollo

- En entornos de desarrollo la API puede incluir información de depuración sobre los OTPs generados al ejecutar `POST /sorteos/iniciar` bajo la clave `_dev_otps` en la respuesta. Esto ocurre únicamente cuando se cumplen ambas condiciones: `APP_ENV=development` y `DEBUG=true`.
- **Riesgo:** Si se activa `DEBUG=true` en entornos de staging o compartidos, los OTPs podrían exponerse a usuarios no autorizados y comprometer la seguridad del sorteo.
- **Recomendación:** Nunca establecer `DEBUG=true` fuera de su máquina de desarrollo local. Para entornos de prueba compartidos (staging) use `APP_ENV=production` o deje `DEBUG` vacío/`false`.


## Backup de base de datos (SDD §18, T-121)

El sistema ejecuta backup automático diario
a las 3 AM UTC usando SQLite backup API.

**Backup manual desde el panel admin:**
POST /admin/backup (requiere sesión SUPER_ADMIN)

**Backup manual desde terminal:**
python -m app.scripts.backup_db

**Verificar backups existentes:**
ls -lh /data/backups/

**Antes de cada sorteo ejecutar:**
python -m app.scripts.backup_db

**Variables de entorno:**
- BACKUP_DIR: directorio de backups 
  (default: /data/backups)
- BACKUP_RETENTION_DAYS: días a retener 
  (default: 30)

## Cabeceras de Seguridad HTTP (SDD §19, T-122)

El sistema integra `SecurityHeadersMiddleware` para mitigar vectores de ataque como XSS y clickjacking durante la realización de sorteos en vivo.

**Cabeceras inyectadas:**
- `Strict-Transport-Security` (HSTS): Fuerza HTTPS por 1 año incluyendo subdominios.
- `X-Frame-Options: DENY`: Previene ataques de Clickjacking impidiendo que la aplicación se cargue en `<frame>`, `<iframe>` u `<object>`.
- `Content-Security-Policy`: Define orígenes permitidos restringiendo la carga de código no autorizado (`frame-ancestors 'none'`).
- `X-Content-Type-Options: nosniff`: Evita la suplantación MIME.
- `Referrer-Policy`: Protege la privacidad en redirecciones salientes.
- `Permissions-Policy`: Deshabilita accesos no deseados a sensores físicos (cámara, micrófono, geolocalización).

**Comportamiento de Caché:**
- **Rutas Públicas (`/p/...`)**: Aplica caché público de 5 minutos (`Cache-Control: public, max-age=300, stale-while-revalidate=60`).
- **Otras Rutas (Admin, APIs)**: Fuerza la no persistencia en caché (`Cache-Control: no-store, no-cache, must-revalidate`).

## Estado Actual

- **Base de datos**: SQLite local (`sorteoparking.db`).
- **Stack**: FastAPI + SQLAlchemy + openpyxl + **Motor Híbrido v1.4.3**.
- **Hito**: Sistema listo para piloto en Aliso Vivienda con cumplimiento total de SDD v1.7 (incluyendo backups y seguridad reforzada T-121 y T-122).

## Sistema de Diseño Apple

El frontend usa el **Apple Design System** generado con 
px getdesign@latest add apple.

- apple/DESIGN.md: diseño original generado por getdesign
- DESIGN.md: copia activa en la raíz (fuente de verdad para el agente)
- Todos los HTML en frontend/ siguen las guías de DESIGN.md

**Características:** Action Blue #0066cc · Botones pill · SF Pro Text (system-ui) · Sin sombras decorativas · Tarjetas 18px border-radius · Nav oscuro 44px.

*Última actualización: Mayo 2026 — sincronizado con SDD v1.7*
