# SorteoParking

Sistema multi-tenant de asignación de parqueaderos residenciales con validación distribuida vía OTP, seed reproducible y exportación verificable.

**URL producción:** `https://sorteoparking.onrender.com`  
**Documento de diseño:** [`SDD_v2_SorteoParking.md`](SDD_v2_SorteoParking.md)

---

## Fuente de verdad

| Documento | Descripción |
|---|---|
| [`SDD_v2_SorteoParking.md`](SDD_v2_SorteoParking.md) | Especificación completa del sistema actual en producción |
| `SDD_SorteoParking_Servicio_v1.7.md` | Versión archivada del diseño original |

El `SDD_v2_SorteoParking.md` es el documento maestro. Contiene: arquitectura, contratos API, flujo OTP, modelo de datos, auditoría, seguridad, despliegue y plan de implementación con estado de todas las tareas T-xxx.

---

## Stack

| Componente | Tecnología |
|---|---|
| Backend | Python · FastAPI |
| Base de datos | PostgreSQL (Render) / SQLite (desarrollo) |
| Correos | Resend HTTP API |
| Parser IA | DeepSeek Flash (`deepseek-chat`) |
| Exportación | openpyxl · python-docx |
| Frontend | HTML · CSS · JS vanilla |
| Hosting | Render |

---

## Estructura del proyecto

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
├── SDD_v2_SorteoParking.md
├── SDD_SorteoParking_Servicio_v1.7.md
├── requirements.txt
└── README.md
```

---

## Endpoints principales

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| POST | `/admin/tenants` | SUPER_ADMIN | Crear conjunto |
| POST | `/catalogo/carga-csv` | Bearer token | Cargar catálogo (Excel/CSV) |
| POST | `/sorteos/iniciar` | Bearer token | Iniciar sorteo + enviar OTPs |
| GET | `/sorteos/{id}/otp/estado` | token_enlace ⭐ | Estado OTP del consejero |
| POST | `/sorteos/{id}/otp/confirmar` | X-Sorteo-Otp-Token ⭐ | Confirmar OTP |
| POST | `/sorteos/{id}/ejecutar` | Bearer token | Ejecutar sorteo |
| POST | `/sorteos/{id}/exportar` | Bearer token | Exportar acta Excel/Word |
| GET | `/p/{slug}/sorteos/{id}` | Público ⭐ | Resultados públicos |

⭐ Endpoints públicos (sin Bearer token)

Ver el [`SDD_v2_SorteoParking.md`](SDD_v2_SorteoParking.md) para la especificación completa de todos los endpoints.

---

## Variables de Entorno en Render

| Variable | Requerida | Descripción |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL URL (Render la inyecta) |
| `RESEND_API_KEY` | ✅ | API key de Resend para correos |
| `OTP_PEPPER` | ✅ | Pepper para hash SHA-256 de OTPs |
| `PUBLIC_BASE_URL` | ✅ | `https://sorteoparking.onrender.com` |
| `DEEPSEEK_API_KEY` | ❓ | API key de DeepSeek (opcional, fallback a sinónimos) |
| `SUPER_ADMIN_PASSWORD_HASH` | ✅ | Hash Argon2id de la contraseña admin |

---

## Estado del proyecto

**26/30 tareas completadas.** Las 4 pendientes corresponden a:

- `T-303` — Panel de métricas SUPER_ADMIN
- `T-304` — Flujo de pago previo al evento
- `T-305` — Primer cliente externo

Ver [`SDD_v2_SorteoParking.md §18`](SDD_v2_SorteoParking.md) para el detalle completo de todas las tareas.

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

```
DATABASE_URL=sqlite:///./sorteoparking.db
RESEND_API_KEY=
OTP_PEPPER=desarrollo-local-cambiar-en-produccion
PUBLIC_BASE_URL=http://127.0.0.1:8000
SUPER_ADMIN_TOKEN=<generado por create_superadmin --env-only>
```

---

*Última actualización: Mayo 2026 — Documento alineado con [`SDD_v2_SorteoParking.md`](SDD_v2_SorteoParking.md).*
