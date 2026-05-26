# SorteoParking

Sistema multi-tenant de asignación de parqueaderos residenciales con validación distribuida vía OTP, seed reproducible y exportación verificable.

**URL producción:** `https://sorteoparking.onrender.com`  
**Documento de diseño:** [`SDD_v2.1_SorteoParking.md`](SDD_v2.1_SorteoParking.md)  
**Reglas del agente:** [`agents.md`](agents.md)  
**Diseño frontend:** [`DESIGN.md`](DESIGN.md)

---

## Fuente de verdad

| Documento | Descripción |
|---|---|
| [`SDD_v2.1_SorteoParking.md`](SDD_v2.1_SorteoParking.md) | Especificación completa del sistema — arquitectura, API, seguridad, plan de implementación |
| [`agents.md`](agents.md) | Reglas del agente de desarrollo (Cursor) |
| [`DESIGN.md`](DESIGN.md) | Apple Design System para frontend |

El `SDD_v2.1_SorteoParking.md` es el documento maestro. Contiene arquitectura, contratos API, flujo OTP, modelo de datos, auditoría encadenada, seguridad (2FA, políticas de acceso, recuperación de contraseña), despliegue y plan de implementación completo.

---

## Stack

| Componente | Tecnología |
|---|---|
| Backend | Python · FastAPI |
| Base de datos | PostgreSQL (Render) / SQLite (desarrollo) |
| Correos | Resend HTTP API |
| Parser IA | DeepSeek Flash (`deepseek-chat`) |
| Exportación | openpyxl · python-docx |
| Frontend | HTML · CSS · JS vanilla (Apple Design System) |
| 2FA | pyotp (TOTP) |
| Hosting | Render |

---

## Flujo del sistema

```
index.html (landing público)
  └─ "Acceder" → login.html
                   └─ UUID válido → dashboard.html (panel TENANT_ADMIN)
                                            ├─ Cargar catálogo
                                            ├─ Cargar elegibles
                                            ├─ Configurar garantes (3-10)
                                            └─ Iniciar sorteo
                                                   └─ Enviar OTP por email a garantes
                                                          └─ otp_panel.html (garante confirma)
                                                                 └─ Sorteo ejecutado
                                                                        ├─ Resultados públicos
                                                                        └─ Acta descargable

superadmin.html (solo dashboard — login separado en login_superadmin.html)
  ├─ CRUD de conjuntos (crear, editar, eliminar, rotar token)
  ├─ Dashboard con métricas globales
  ├─ Visor de logs de auditoría (filtrables, paginados)
  └─ Backup manual

login_superadmin.html (público, formulario de login SUPER_ADMIN)
  └─ Ingresa credenciales → redirect a superadmin.html
  └─ Enlace a reset-password.html
```

---

## Estructura del proyecto

```
sorteoparking/
├── app/
│   ├── main.py                         # FastAPI app + middleware + rutas protegidas
│   ├── core/
│   │   ├── config.py                   # Configuración multi-entorno
│   │   ├── security.py                 # Auth context, UUID parsing, session validation
│   │   ├── security_headers.py         # CSP, HSTS, X-Frame-Options, etc.
│   │   ├── session_store.py            # Sesiones SUPER_ADMIN (DB-backed)
│   │   ├── scheduler.py               # Tareas programadas (backups)
│   │   └── slug.py                     # Generación de slugs únicos
│   ├── models/
│   │   ├── tenant.py                   # Tenant (conjunto residencial)
│   │   ├── catalogo.py                 # Zona, Torre, Parqueadero
│   │   ├── sorteo.py                   # Sorteo, Participante, Garante, SesionOTP, ResultadoSorteo
│   │   ├── log.py                      # LogAuditoria (cadena de hash SHA-256)
│   │   ├── password_reset.py           # SuperAdminCredentials
│   │   └── superadmin.py               # PasswordResetToken
│   ├── routers/
│   │   ├── admin.py                    # CRUD tenants + métricas + backup + logs de auditoría
│   │   ├── auth.py                     # Login SUPER_ADMIN (con TOTP), login TENANT, logout, password reset
│   │   ├── catalogo.py                 # Catálogo maestro de parqueaderos
│   │   ├── sorteos.py                  # Iniciar, ejecutar, OTP, exportar, estado
│   │   ├── publico.py                  # Resultados públicos por slug
│   │   └── debug.py                    # Endpoints de depuración
│   ├── services/
│   │   ├── sorteo_engine.py            # Algoritmo híbrido de asignación
│   │   ├── sorteos_service.py          # Lógica de negocio de sorteos
│   │   ├── catalogo_service.py         # Lógica de catálogo
│   │   ├── otp_service.py              # Generación y validación OTP (SHA-256 + pepper)
│   │   ├── email_service.py            # Envío de correos vía Resend
│   │   ├── log_service.py              # Log encadenado con hash
│   │   ├── excel_parser.py             # Parseo de Excel/CSV
│   │   ├── deepseek_service.py         # Parser IA con DeepSeek Flash
│   │   └── exportadores.py             # Exportación de actas (Excel/Word)
│   ├── scripts/
│   │   ├── backup_db.py               # Backup automático de BD
│   │   └── create_superadmin.py        # Creación inicial de SUPER_ADMIN
│   └── db/
│       └── database.py                 # Conexión PostgreSQL/SQLite
├── frontend/
│   ├── index.html                      # Landing page (Apple Design System)
│   ├── login.html                      # Login de TENANT_ADMIN con UUID
│   ├── login_superadmin.html           # Login de SUPER_ADMIN (público)
│   ├── reset-password.html             # Recuperación de contraseña SUPER_ADMIN
│   ├── dashboard.html                  # Panel TENANT_ADMIN (catálogo + sorteo)
│   ├── otp_panel.html                  # Panel OTP para garantes (dark theme)
│   ├── publico.html                    # Resultados públicos del sorteo
│   └── superadmin.html                 # Panel SUPER_ADMIN (CRUD + logs + métricas)
├── DESIGN.md                           # Apple Design System
├── apple/DESIGN.md                     # Referencia visual Apple Design System
├── SDD_v2.1_SorteoParking.md           # Especificación de diseño (master)
├── agents.md                           # Reglas del agente
├── README.md
└── requirements.txt
```

---

## Endpoints principales

### Autenticación

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| POST | `/auth/login/superadmin` | — ⭐ | Login SUPER_ADMIN (TOTP solo si configurado en producción) |
| POST | `/auth/logout` | Cookie | Cerrar sesión SUPER_ADMIN |
| POST | `/auth/login/tenant` | — ⭐ | Login TENANT_ADMIN con UUID del conjunto |
| POST | `/auth/superadmin/recuperar-password` | — ⭐ | Solicitar reset de contraseña |
| POST | `/auth/superadmin/reset-password` | — ⭐ | Aplicar reset con token |

### Gestión de conjuntos (SUPER_ADMIN)

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| POST | `/admin/tenants` | Bearer SA | Crear conjunto + correo de bienvenida |
| GET | `/admin/tenants` | Bearer SA | Listar conjuntos |
| GET | `/admin/tenants/{id}` | Bearer SA | Detalle de conjunto |
| PATCH | `/admin/tenants/{id}` | Bearer SA | Editar conjunto |
| PATCH | `/admin/tenants/{id}/estado` | Bearer SA | Cambiar estado (ACTIVO/SUSPENDIDO/DEMO) |
| DELETE | `/admin/tenants/{id}` | Bearer SA | Eliminar conjunto (solo sin sorteos completados) |
| POST | `/admin/tenants/{id}/rotar-token` | Bearer SA | Rotar UUID del conjunto |

### Catálogo (TENANT_ADMIN)

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| POST | `/catalogo/carga-csv` | Bearer UUID | Cargar catálogo (Excel/CSV) |
| GET | `/catalogo/zonas` | Bearer UUID | Listar zonas |
| GET | `/catalogo/parqueaderos` | Bearer UUID | Listar parqueaderos |
| PATCH | `/catalogo/parqueaderos/{num}` | Bearer UUID | Editar parqueadero |

### Sorteo (TENANT_ADMIN)

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| POST | `/sorteos/iniciar` | Bearer UUID | Iniciar sorteo + enviar OTPs a garantes |
| GET | `/sorteos/{id}/otp/estado` | token_enlace ⭐ | Estado OTP por garante |
| POST | `/sorteos/{id}/otp/confirmar` | X-Sorteo-Otp-Token ⭐ | Confirmar OTP |
| GET | `/sorteos/{id}/estado` | Bearer UUID | Estado del sorteo |
| POST | `/sorteos/{id}/ejecutar` | Bearer UUID | Ejecutar sorteo |
| POST | `/sorteos/{id}/exportar` | Bearer UUID | Exportar acta (Excel/Word) |
| POST | `/sorteos/{id}/notificar` | Bearer UUID | Notificar resultados |

### Público

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| GET | `/p/{slug}/sorteos/{id}` | — ⭐ | Resultados públicos del sorteo |
| GET | `/p/{slug}/sorteos/{id}/seed` | — ⭐ | Seed criptográfico público |

### Operaciones (SUPER_ADMIN)

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| GET | `/admin/metricas` | Bearer SA | Métricas globales |
| POST | `/admin/backup` | Bearer SA | Backup manual de BD |
| GET | `/admin/logs` | Bearer SA | Logs de auditoría (paginados + filtrables) |
| GET | `/health` | — ⭐ | Health check |

⭐ Endpoints públicos (sin autenticación)

Ver el [`SDD_v2.1_SorteoParking.md`](SDD_v2.1_SorteoParking.md) para la especificación completa de todos los endpoints.

---

## Características de seguridad

- **Política de acceso a paneles HTML:**
  - `dashboard.html` → requiere Bearer UUID válido (server-side)
  - `superadmin.html` → público (HTML sin datos; APIs protegidas con cookie de sesión)
  - `otp_panel.html` → público sin datos sensibles sin token_enlace
  - `login.html`, `login_superadmin.html` → público
- **2FA TOTP** para SUPER_ADMIN en producción (via pyotp, campo oculto por defecto — se activa configurando `SUPER_ADMIN_TOTP_SECRET`)
- **Rate limiting** por IP en todos los endpoints de autenticación
- **Auditoría encadenada** con hash SHA-256 (todos los eventos de SUPER_ADMIN)
- **Recuperación de contraseña** por correo con token de un solo uso
- **CSP, HSTS, X-Frame-Options, Referrer-Policy** vía middleware
- **UUID v4 como token de tenant**, revocable y rotable

---

## Variables de Entorno en Render

| Variable | Requerida | Descripción |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL URL (Render la inyecta) |
| `RESEND_API_KEY` | ✅ | API key de Resend para correos |
| `OTP_PEPPER` | ✅ | Pepper para hash SHA-256 de OTPs |
| `PUBLIC_BASE_URL` | ✅ | `https://sorteoparking.onrender.com` |
| `DEEPSEEK_API_KEY` | ❓ | API key de DeepSeek (opcional, fallback a sinónimos) |
| `SUPER_ADMIN_USER` | ✅ | Usuario del SUPER_ADMIN |
| `SUPER_ADMIN_PASSWORD_HASH` | ✅ | Hash Argon2id de la contraseña admin |
| `SUPER_ADMIN_TOKEN` | ✅ | Token Bearer del SUPER_ADMIN |
| `SUPER_ADMIN_EMAIL` | ✅* | Email para recuperación de contraseña y alertas |
| `SUPER_ADMIN_TOTP_SECRET` | ❓ | Secreto TOTP para 2FA (solo producción). El campo TOTP en login_superadmin.html está oculto por defecto; al configurarlo, cambiar `display:none` → `display:block` en el HTML |
| `BACKUP_DIR` | ❓ | Directorio de backups (`/data/backups`) |
| `BACKUP_RETENTION_DAYS` | ❓ | Días de retención de backups (30) |

*Requerida en producción.

---

## Estado del proyecto

**v2.1 completada — 100% de las tareas implementadas.**

| Bloque | Tareas | Estado |
|---|---|---|
| A — Bugs críticos | T-301 a T-303 | ✅ |
| B — Responsividad | T-304 a T-307 | ✅ |
| C — Features | T-308 a T-313 | ✅ |
| D — Seguridad | T-314 a T-317, T-321 | ✅ |
| E — Infraestructura | T-318 a T-320 | ✅ |

Ver [`SDD_v2.1_SorteoParking.md §18`](SDD_v2.1_SorteoParking.md) para el detalle completo de todas las tareas.

---

## Inicio rápido (desarrollo local)

```bash
cd sorteoparking

# Instalar dependencias
pip install -r requirements.txt

# Crear SUPER_ADMIN inicial
python -m app.scripts.create_superadmin --env-only

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

Variables de entorno mínimas para local (`.env`):

```env
DATABASE_URL=sqlite:///./sorteoparking.db
RESEND_API_KEY=
OTP_PEPPER=desarrollo-local-cambiar-en-produccion
PUBLIC_BASE_URL=http://127.0.0.1:8000
SUPER_ADMIN_USER=admin
SUPER_ADMIN_PASSWORD_HASH=<generado por create_superadmin>
SUPER_ADMIN_TOKEN=<generado por create_superadmin --env-only>
```

### Acceso rápido

1. Abrir `http://127.0.0.1:8000/static/index.html` — landing page
2. Hacer clic en **Acceder** → ir a `login.html`
3. Ingresar UUID del conjunto (generado desde `superadmin.html`)
4. O entrar directamente a `superadmin.html` con usuario/contraseña

---

*Última actualización: Mayo 2026 — Documento alineado con [`SDD_v2.1_SorteoParking.md`](SDD_v2.1_SorteoParking.md) y [`DESIGN.md`](DESIGN.md).*
