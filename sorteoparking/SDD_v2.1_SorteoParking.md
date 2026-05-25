# SorteoParking — Especificación de Diseño de Software

## Versión 2.1 — Producción

| Campo | Valor |
|---|---|
| Versión | 2.1 |
| Fecha | Mayo 2026 |
| Estado | EN DESARROLLO |
| Basado en | v2.0 — commit `d5aee47` |
| Autor | Michael López — Arquitectura y producto |
| Plataforma | Render (PostgreSQL) |
| IDE de desarrollo | Cursor |
| Stack | Python · FastAPI · PostgreSQL · Resend API · DeepSeek Flash |
| Diseño frontend | Apple Design System (ver [`DESIGN.md`](DESIGN.md)) |

---

## Control de cambios respecto a v2.0

| ID | Categoría | Descripción | Hallazgo origen |
|---|---|---|---|
| C-01 | Feature | CRUD completo de tenants en SUPER_ADMIN (editar + eliminar) | H-01 |
| C-02 | Bug | Vista pública siempre muestra "Sorteo no encontrado" | H-02 |
| C-03 | UX | Responsividad completa en todos los paneles (Apple Design System breakpoints) | H-03 |
| C-04 | UX/Bug | Dashboard desde SUPER_ADMIN: flujo post-catálogo cargado + manejo 409 | H-04 |
| C-05 | Feature | Número de garantes configurable por sorteo (reemplaza hardcoded 5) | H-05 |
| C-06 | Nomenclatura | "consejeros" → "garantes" en toda la interfaz y documentación | H-05 |
| C-07 | UX | Animación de resultados del sorteo (Apple Design System fade-in) | H-06 |
| C-08 | Feature | Correo de bienvenida al crear conjunto | H-07 |
| C-09 | UX | Navegación entre paneles + acceso a vista pública desde dashboard | H-08 |
| C-10 | Feature | Landing page / index.html público (Apple Design System) | H-09 |
| C-11 | Infra | Dominio propio (sorteoparking.com o .co) con SSL | H-10 |
| C-12 | Infra | Mitigación de cold start en Render Free Tier | H-11 |
| C-13 | Feature | Recuperación de token para TENANT_ADMIN | H-12 |
| C-14 | Observabilidad | Logging de errores observable sin acceso a consola Render | H-13 |
| C-15 | Infra | Health check endpoint `/health` | H-14 |
| C-16 | Infra | Backups en almacenamiento persistente externo | H-15 |
| C-17 | Ops | Purga de tenants de prueba y política de retención | H-16 |
| C-18 | Infra | Separación de ambientes dev/staging/prod | H-17 |
| C-19 | Seguridad | Recuperación de contraseña SUPER_ADMIN por correo | H-18 |
| C-20 | Seguridad | Rotación de token de tenant | H-19 |
| C-21 | Seguridad | 2FA para SUPER_ADMIN | H-21 |
| C-22 | Seguridad | Audit trail de accesos SUPER_ADMIN | H-22 |
| C-23 | Seguridad | Política de acceso server-side a paneles HTML | H-24 |

---

## 1. Introducción

### 1.1 Propósito

Este documento define la arquitectura, contratos de datos, flujos y criterios de aceptación del sistema SorteoParking en su versión 2.1. Extiende la v2.0 incorporando correcciones de bugs identificados en producción, mejoras de UX, hardening de seguridad y nuevas funcionalidades derivadas de la validación con clientes reales.

El diseño de todos los paneles frontend sigue el **Apple Design System** definido en [`DESIGN.md`](DESIGN.md): Action Blue #0066cc, botones pill, SF Pro Text (system-ui), sin sombras decorativas, tarjetas 18px border-radius, nav oscuro 44px.

### 1.2 Contexto y origen

SorteoParking nació como sistema de ejecución local para el Conjunto Residencial Aliso Vivienda (Cajicá, 904 unidades, SDD v1.4.3). Su diseño — algoritmo híbrido por zona, protocolo OTP de garantes, seed reproducible y acta encadenada — demostró ser robusto ante impugnaciones y garantizó transparencia comunitaria.

### 1.3 Problema que resuelve

Los conjuntos VIS en Bogotá y la Sabana están obligados por ley (Decreto Distrital 555 de 2021 y Ley 675 de 2001) a gestionar parqueaderos como bienes comunes mediante sorteo.

### 1.4 Diferencia clave respecto a v2.0

| Dimensión | v2.0 | v2.1 |
|---|---|---|
| Garantes | Hardcoded 5 | Configurable por sorteo |
| Nomenclatura | "consejeros" | "garantes" |
| CRUD tenants | Crear + suspender | Crear + editar + eliminar + suspender |
| Acceso paneles | HTML estático accesible por URL | Política server-side |
| Vista pública | Bug: siempre "no encontrado" | Corregido |
| Responsividad | Solo parcial | Todos los paneles (Apple Design System) |
| Landing page | No existe | index.html (Apple Design System) |
| Recuperación contraseña | Manual vía Render | Flujo por correo |
| Correo al crear conjunto | No | Sí |
| Navegación entre paneles | Rota | Completa |
| Animación resultados | Aparición abrupta | Fade-in progresivo |
| Health check | No existe | `GET /health` |
| Audit trail SUPER_ADMIN | No existe | Login/logout/acciones |

---

## 2. Stakeholders y Roles

| Rol | Actor | Permisos |
|---|---|---|
| SUPER_ADMIN | Equipo SorteoParking | CRUD tenants · Métricas · Soporte · Purga |
| TENANT_ADMIN | Administrador del conjunto | Configurar conjunto · Cargar elegibles · Registrar garantes · Iniciar/ejecutar/exportar |
| GARANTE | N miembros (3–10) | Recibir OTP · Confirmar vía panel público |
| RESIDENTE | Participante | Vista pública sin login · Verificar seed |
| SISTEMA | SorteoParking Cloud | Aislar datos · Ejecutar algoritmo · Enviar correos · Log encadenado |

---

## 3. Arquitectura del Sistema

### 3.1 Modelo de despliegue

Servicio web único en **Render**. Aislamiento multi-tenant por `tenant_id` (UUID).

**URL producción:** `https://sorteoparking.onrender.com`
**Dominio objetivo:** `https://sorteoparking.co` (pendiente)

### 3.2 Componentes principales

| Componente | Tecnología |
|---|---|
| API Backend | Python · FastAPI |
| Base de datos | PostgreSQL (Render) / SQLite fallback |
| Motor de sorteo | Python puro · Algoritmo híbrido · Seed reproducible |
| OTP Engine | Python · SHA-256 con pepper |
| Notificaciones | Resend HTTP API |
| Frontend | HTML · CSS · JS vanilla (Apple Design System) |
| Parser IA | DeepSeek Flash (`deepseek-chat`) |

### 3.3 Aislamiento multi-tenant

`tenant_id` en toda tabla. `enforce_tenant_scope()` en todo endpoint. Violación → HTTP 403.

### 3.4 Estructura de carpetas

```
sorteoparking/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py, security.py, security_headers.py, session_store.py, scheduler.py, slug.py
│   ├── models/
│   │   ├── tenant.py, catalogo.py, sorteo.py, log.py, superadmin.py
│   ├── routers/
│   │   ├── admin.py, auth.py, catalogo.py, sorteos.py, publico.py
│   ├── services/
│   │   ├── sorteo_engine.py, sorteos_service.py, catalogo_service.py, otp_service.py,
│   │   │   email_service.py, log_service.py, excel_parser.py, deepseek_service.py, exportadores.py
│   ├── scripts/
│   │   ├── backup_db.py, create_superadmin.py
│   └── db/
│       └── database.py
├── frontend/
│   ├── index.html ← NUEVO v2.1 (Apple Design System)
│   ├── dashboard.html, otp_panel.html, publico.html, superadmin.html
├── DESIGN.md ← Apple Design System
├── apple/DESIGN.md
├── agents.md, SDD_v2.1_SorteoParking.md, README.md, requirements.txt
```

### 3.5 Middleware y autenticación

#### 3.5.1 `tenant_auth_middleware`

1. `OPTIONS` → pasa (preflight CORS)
2. `/favicon.ico` → 204
3. `/auth/`, `/admin/`, `/debug/` → `tenant_id = None`
4. `/p/...`, `/static/` → público (`tenant_id=""`)
5. GET `/sorteos/{id}/otp/estado` → público condicionado por `token_enlace`
6. POST `/sorteos/{id}/otp/confirmar` → público condicionado por `X-Sorteo-Otp-Token`
7. Demás rutas → `Authorization: Bearer {uuid}`

#### 3.5.2 CORSMiddleware

Origen: `https://sorteoparking.onrender.com`. Credentials, métodos y headers permitidos.

#### 3.5.3 Política de acceso a paneles HTML (NUEVA v2.1)

| Panel | Acceso | Sin credencial |
|---|---|---|
| `index.html` | Público | — |
| `publico.html` | Público | — |
| `otp_panel.html` | Solo con `token_enlace` válido | Redirect a `index.html` |
| `dashboard.html` | Solo con Bearer UUID válido | HTTP 401 |
| `superadmin.html` | Solo con sesión SUPER_ADMIN activa | HTTP 401 |

#### 3.5.4 SecurityHeadersMiddleware

HSTS, X-Frame-Options, CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, Cache-Control.

### 3.6 Contrato del token de tenant

UUID v4. Header `Authorization: Bearer {uuid}`. Revocación por `estado=SUSPENDIDO`. Rotación: `POST /admin/tenants/{id}/rotar-token`.

### 3.7 Protección contra race conditions

| Operación | Solución |
|---|---|
| Confirmar OTP | `with_for_update()` |
| Ejecutar sorteo | Estado `EJECUTANDO` como mutex |
| Cargar Excel | Verificación de existencia previa |

### 3.8 Base de datos

PostgreSQL en Render. SQLite como fallback local.

### 3.9 Health Check (NUEVA v2.1)

```
GET /health
→ 200 {"status": "ok", "version": "2.1", "db": "ok", "timestamp": "..."}
→ 503 si DB no responde
```

### 3.10 Mitigación de Cold Start (NUEVA v2.1)

Ping externo (UptimeRobot) cada 10 min a `/health`. Mensaje de carga en vista pública. Upgrade a Render Starter ($7/mes) con primer cliente de pago.

---

## 4. Modelo de Datos

### 4.1 Entidad Tenant

```python
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Text, primary_key=True)         # UUID v4
    nombre = Column(Text, nullable=False)
    nit = Column(Text, unique=True, nullable=True)
    municipio = Column(Text, nullable=False)
    email_admin = Column(Text, nullable=False)
    slug = Column(Text, unique=True, nullable=True)
    estado = Column(Text, default="ACTIVO")
    plan = Column(Text, default="POR_EVENTO")
    total_unidades = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 4.2 Entidades heredadas (con tenant_id)

Zona, Torre, Parqueadero, Participante, **Garante** (antes Consejero), Sorteo, SesionOTP, ResultadoSorteo, LogAuditoria.

### 4.3 Cambio en modelo Sorteo (v2.1)

```python
class Sorteo(Base):
    # ... campos existentes ...
    num_garantes = Column(Integer, nullable=False, default=5)  # rango 3-10
```

### 4.4 Modelo SesionOTP

```python
class SesionOTP(Base):
    __tablename__ = "sesiones_otp"
    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False)
    id = Column(Integer, primary_key=True, autoincrement=True)
    sorteo_id = Column(Integer, ForeignKey("sorteos.id"), nullable=False)
    garante_id = Column(Integer, ForeignKey("garantes.id"), nullable=False)
    otp_hash = Column(Text, nullable=False)
    token_enlace = Column(Text, nullable=False)
    estado = Column(Text, default="PENDIENTE")
    intentos = Column(Integer, default=0)
    expira_en = Column(DateTime, nullable=False)
    confirmado_en = Column(DateTime, nullable=True)
```

---

## 5. Contratos de API

> Endpoints con ⭐ son públicos (sin Bearer).

### 5.1 Gestión de Tenants (SUPER_ADMIN) — AMPLIADO v2.1

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/admin/tenants` | Crear + enviar correo bienvenida |
| GET | `/admin/tenants` | Listar activos |
| GET | `/admin/tenants/{id}` | Detalle |
| PATCH | `/admin/tenants/{id}` | Editar nombre/NIT/email/municipio/unidades/estado |
| DELETE | `/admin/tenants/{id}` | Eliminar (solo si sin sorteos completados → 409) |
| POST | `/admin/tenants/{id}/rotar-token` | Rotar UUID |
| POST | `/admin/backup` | Backup manual |
| GET | `/health` ⭐ | Health check |

### 5.2 Catálogo Maestro (TENANT_ADMIN)

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/catalogo/carga-csv` | Importar Excel/CSV |
| GET | `/catalogo/plantilla` | Descargar plantilla |
| GET | `/catalogo/zonas` | Listar zonas |
| GET | `/catalogo/parqueaderos` | Listar parqueaderos |
| PATCH | `/catalogo/parqueaderos/{num}` | Editar parqueadero |

**Manejo 409 catálogo ya cargado (v2.1):** El dashboard muestra opciones: "Ver catálogo actual" o "Ir al sorteo".

### 5.3 Sorteo (TENANT_ADMIN) — AMPLIADO v2.1

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/sorteos/carga-excel` | Cargar elegibles |
| POST | `/sorteos/iniciar` | Iniciar + enviar OTPs |
| GET | `/sorteos/{id}/estado` | Estado (polling) |
| GET | `/sorteos/{id}/diagnostico` | Previsualizar modelo |
| POST | `/sorteos/{id}/ejecutar` | Ejecutar algoritmo |
| GET | `/sorteos/{id}/resultados` | Resultados paginados |
| POST | `/sorteos/{id}/exportar` | Exportar acta Excel/Word |
| POST | `/sorteos/{id}/notificar` | Notificar resultados |
| GET | `/sorteos/historial` | Historial |

**`POST /sorteos/iniciar` (v2.1):**
```json
{
    "sorteo_id": 1,
    "num_garantes": 5,
    "garantes": [{"nombre": "...", "email": "..."}, ...]
}
```

`num_garantes` requerido (3–10). `garantes` debe tener exactamente `num_garantes` elementos.

### 5.4 OTP — Endpoints Públicos ⭐

| Método | Endpoint | Auth |
|---|---|---|
| GET | `/sorteos/{id}/otp/estado?token_enlace=...` | token_enlace |
| POST | `/sorteos/{id}/otp/confirmar` | `X-Sorteo-Otp-Token` |

### 5.5 Vista Pública Residente ⭐

| Método | Endpoint |
|---|---|
| GET | `/p/{tenant_slug}/sorteos/{id}` |
| GET | `/p/{tenant_slug}/sorteos/{id}/seed` |

### 5.6 Auth (SUPER_ADMIN) — AMPLIADO v2.1

| Método | Endpoint | Auth |
|---|---|---|
| POST | `/auth/login/superadmin` | — |
| POST | `/auth/logout/superadmin` | Sesión |
| POST | `/auth/superadmin/recuperar-password` ⭐ | — |
| POST | `/auth/superadmin/reset-password` ⭐ | Token |

**Flujo recuperación:** Solicitud → token UUID (30 min) → correo con enlace → formulario nueva contraseña → invalidación inmediata del token.

---

## 6. Protocolo OTP Completo

### 6.1 Visión general

N garantes configurable (3–10, default 5). Cada garante recibe OTP único por correo y lo confirma desde su celular sin instalar nada.

### 6.2 Flujo completo

```
TENANT_ADMIN → POST /sorteos/iniciar {num_garantes: N, garantes: xN}
  → SISTEMA valida estado, catálogo, participantes, 3≤N≤10
  → snapshot_hash, estado=EN_CURSO, sorteo.num_garantes=N
  → Por cada garante: crea Garante, OTP, token_enlace, SesionOTP, email
  → db.commit() + audit SORTEO_INICIADO_OTP

GARANTE → Abre enlace: .../otp_panel.html#t={token_enlace}&sid={id}
  → Verifica token_enlace en hash (si ausente → redirect index.html)
  → fetchEstado() cada 3s: barra confirmados/num_garantes
  → Ingresa OTP 6 dígitos → POST /confirmar
  → SISTEMA: with_for_update, anti-replay, expiración, intentos
  → CONFIRMADO → cuenta >= num_garantes → LISTO
```

### 6.3 token_enlace

`secrets.token_urlsafe(32)` — 43 caracteres, único por sesión. En URL (hash), query param y header.

### 6.4 Especificación del OTP

6 dígitos, ~20 bits entropía, SHA-256(pepper|otp), expiración 30 min, 3 intentos, anti-replay single-use, rate limit 10/min.

### 6.5 Estados del OTP

`PENDIENTE` → `CONFIRMADO` | `EXPIRADO` | `FALLO_EMAIL`

### 6.6 Polling frontend

**Panel garante:** cada 3s. Barra `confirmados / num_garantes`. Temporizador.
**Dashboard TENANT_ADMIN:** cada 2s. Barra `0/N → N/N`. Cards individuales.

---

## 7. Infraestructura de Correo

### 7.1 Resend HTTP API

```python
resend.api_key = os.getenv("RESEND_API_KEY")
resend.Emails.send({"from": ..., "to": ..., "subject": ..., "html": ...})
```

### 7.2 Mensajes enviados

| # | Destinatario | Trigger | Contenido |
|---|---|---|---|
| 1 | TENANT_ADMIN | Crear conjunto | Bienvenida + UUID + instrucciones |
| 2 | Garante | Iniciar sorteo | OTP + enlace panel |
| 3 | Participante | Notificar | Resultado asignación |
| 4 | SUPER_ADMIN | Recuperar contraseña | Enlace reset (30 min) |

### 7.3 Variables de entorno

`RESEND_API_KEY`, `RESEND_FROM` (default `onboarding@resend.dev`), `PUBLIC_BASE_URL`.

---

## 8. Auditoría

### 8.1 Log encadenado

```python
class LogAuditoria(Base):
    tenant_id, id, evento, payload, hash_anterior, hash_actual, created_at
```

### 8.2 Eventos — AMPLIADO v2.1

| Evento | Generado por |
|---|---|
| `CONSULTA_HISTORIAL_SORTEOS` | GET /sorteos/historial |
| `CARGA_EXCEL_ELEGIBLES` | POST /sorteos/carga-excel |
| `SORTEO_INICIADO_OTP` | POST /sorteos/iniciar |
| `OTP_CONFIRMACION_OK` | POST /sorteos/{id}/otp/confirmar |
| `OTP_CONFIRMACION_FALLIDA` | POST /sorteos/{id}/otp/confirmar |
| `SORTEO_EJECUTADO` | POST /sorteos/{id}/ejecutar |
| `SORTEO_ERROR` | POST /sorteos/{id}/ejecutar (fallo) |
| `NOTIFICACION_RESULTADOS` | POST /sorteos/{id}/notificar |
| `SUPERADMIN_LOGIN_OK` | POST /auth/login/superadmin (NUEVO) |
| `SUPERADMIN_LOGIN_FALLO` | POST /auth/login/superadmin (NUEVO) |
| `SUPERADMIN_LOGOUT` | POST /auth/logout/superadmin (NUEVO) |
| `TENANT_CREADO` | POST /admin/tenants (NUEVO) |
| `TENANT_EDITADO` | PATCH /admin/tenants/{id} (NUEVO) |
| `TENANT_ELIMINADO` | DELETE /admin/tenants/{id} (NUEVO) |
| `TOKEN_ROTADO` | POST /admin/tenants/{id}/rotar-token (NUEVO) |
| `PASSWORD_RESET_SOLICITADO` | POST /auth/superadmin/recuperar-password (NUEVO) |
| `PASSWORD_RESET_APLICADO` | POST /auth/superadmin/reset-password (NUEVO) |

### 8.3 Persistencia con commit explícito

```python
registrar_log_auditoria(db, ...)  # flush() + refresh()
db.commit()  # ← Obligatorio
```

---

## 9. Exportador Excel

### 9.1 Hojas

| Hoja | Columnas |
|---|---|
| Resumen | Conjunto, Fecha, Tipo, Estado, Seed, Snapshot, Totales, Num. Garantes |
| Ganadores | Apartamento, Parqueadero, Zona, Tipo Vehículo, Reasignado |
| No Asignados | Apartamento, Tipo Vehículo |
| Garantes | Nombre, Email, Estado OTP, Confirmado en |
| Log Auditoria | Evento, Payload, Hash Anterior, Hash Actual, Timestamp |

### 9.2 Formula Injection

`_sanitizar()`: antepone `'` si el valor empieza con `=`, `+`, `-`, `@`, `\t`, `\r`.

---

## 10. Frontend

### 10.1 Apple Design System

Todos los paneles siguen el sistema definido en [`DESIGN.md`](DESIGN.md):

- **Action Blue** #0066cc como único color interactivo
- **Botones pill** (`border-radius: 9999px`)
- **SF Pro Text** (`system-ui, -apple-system, sans-serif`)
- **Sin sombras decorativas** — solo la sombra de producto fotográfico
- **Tarjetas** 18px `border-radius`
- **Nav oscuro** 44px de alto
- **Responsivo** mobile-first con breakpoints Apple: 1440px, 1068px, 833px, 734px, 640px, 480px

### 10.2 index.html — Landing page (NUEVA v2.1)

Página pública con Apple Design System. Contenido:
- Qué es SorteoParking y problema que resuelve
- Cómo funciona (3 pasos)
- Marco legal (Decreto 555/2021, Ley 675/2001)
- Cumplimiento Habeas Data (Ley 1581/2012)
- Información de contacto
- Enlace oculto a `superadmin.html`
- Diseño responsivo mobile-first con breakpoints Apple

### 10.3 Responsividad (v2.1)

Breakpoints Apple: < 768px mobile (1 columna), 768–1024px tablet (2 columnas), > 1024px desktop (layout completo). Paneles: index, dashboard, otp_panel, publico, superadmin.

### 10.4 Animación resultados (v2.1)

Spinner "Ejecutando sorteo..." → fade-in progresivo de resultados en parte superior del viewport.

### 10.5 Navegación (v2.1)

| Desde | Hacia | Mecanismo |
|---|---|---|
| `superadmin.html` | `dashboard.html` | Botón "Dashboard" por tenant |
| `dashboard.html` | Vista pública | Botón post-ejecución |
| `dashboard.html` | `superadmin.html` | Botón "Volver" |
| `otp_panel.html` sin token | `index.html` | Redirect |
| Cualquier panel | `index.html` | Logo/header |

### 10.6 Sanitización DOM

```javascript
safeString(), escHtml(), extractErrorMessage()
```

Sin cambios respecto a v2.0.

---

## 11. Flujo Operativo

| Actividad | Tiempo |
|---|---|
| Cargar elegibles | 5 min |
| Configurar garantes + iniciar | 5 min |
| Confirmación N OTPs | 10–15 min |
| Ejecución algoritmo | < 1 min |
| Exportar + notificar | 5 min |
| **TOTAL** | **~30 min** |

---

## 12. Modelo Transaccional

1. `registrar_log_auditoria()` → `flush()` + `refresh()`, nunca `commit()`
2. Commit explícito después de cada log
3. Datos del sorteo primero, log después

```python
db.commit()  # datos
registrar_log_auditoria(db, ...)
db.commit()  # log
```

---

## 13. Seguridad

### 13.1 Principios

1. Aislamiento total entre tenants
2. Integridad del protocolo OTP
3. Privacidad de datos personales (Ley 1581/2012)
4. Acceso mínimo necesario a paneles HTML

### 13.2 CSRF

Cookie `csrf_token` + header `X-CSRF-Token`. Validación con `hmac.compare_digest()`.

### 13.3 Cookies admin

`admin_session` (HttpOnly, Secure, SameSite=Strict) y `csrf_token` (Secure, SameSite=Strict).

### 13.4 session_store

Tabla `admin_sessions`: `session_id`, `token_hash` (SHA-256 del UUID), `csrf_token`, `created_at`, `expires_at` (30 min), `revoked_at`.

### 13.5 2FA para SUPER_ADMIN (NUEVA v2.1)

TOTP RFC 6238. Secreto en `SUPER_ADMIN_TOTP_SECRET`. Login requiere: usuario + contraseña + TOTP de 6 dígitos. Sin 2FA configurado, login solo en `development`.

### 13.6 Rotación de token de tenant (NUEVA v2.1)

`POST /admin/tenants/{id}/rotar-token` → nuevo UUID v4, invalida anterior inmediatamente, audit `TOKEN_ROTADO`.

### 13.7 Comparación segura

`hmac.compare_digest()` siempre. Nunca `==`.

### 13.8 Cabeceras de seguridad

HSTS, X-Frame-Options: DENY, CSP restrictiva, X-Content-Type-Options: nosniff, Referrer-Policy, Permissions-Policy.

---

## 14. Variables de Entorno

| Variable | Req. | Default |
|---|---|---|
| `DATABASE_URL` | Sí | `sqlite:///./sorteoparking.db` |
| `RESEND_API_KEY` | Sí* | — |
| `OTP_PEPPER` | Sí* | (dev default) |
| `PUBLIC_BASE_URL` | Sí | `http://127.0.0.1:8000` |
| `SUPER_ADMIN_PASSWORD_HASH` | Sí* | — |
| `SUPER_ADMIN_EMAIL` | Sí* | — |
| `SUPER_ADMIN_TOTP_SECRET` | Sí* | — |
| `DEEPSEEK_API_KEY` | No | — |
| `BACKUP_DIR` | No | `/data/backups` |
| `BACKUP_RETENTION_DAYS` | No | 30 |

*Requerida en producción.

---

## 15. DeepSeek Flash — Parser Inteligente

### 15.1 Dos fases

Fase 1: IA analiza estructura (encabezados + 5 filas).
Fase 2: Python lee datos aplicando el mapa (sin IA).

### 15.2 Sanitización estructural (Ley 1581/2012)

Valores reales → tipos: `[TEXTO]`, `[NUMERO]`, `[FECHA]`, `[BOOL]`, `[VACIO]`. DeepSeek nunca recibe PII.

---

## 16. Criterios de Aceptación

### v2.0 (✅ completados)

CA-01 a CA-24 — todos marcados ✅. Ver SDD v2.0 para detalle.

### v2.1

| # | Criterio | Estado |
|---|---|---|
| CA-25 | SUPER_ADMIN edita nombre/NIT/email/municipio/unidades | ✅ |
| CA-26 | SUPER_ADMIN elimina tenant sin sorteos completados | ✅ |
| CA-27 | SUPER_ADMIN no elimina tenant con sorteos completados (409) | ✅ |
| CA-28 | Vista pública muestra resultados correctamente | ✅ |
| CA-29 | Todos los paneles responsivos (Apple Design System) | ⬜ |
| CA-30 | 409 catálogo cargado presenta opciones de acción | ✅ |
| CA-31 | Número de garantes configurable 3–10 | ✅ |
| CA-32 | Interfaz usa "garantes" no "consejeros" | ✅ |
| CA-33 | Resultados con animación fade-in | ✅ |
| CA-34 | Correo de bienvenida al crear conjunto | ✅ |
| CA-35 | Dashboard navega a vista pública post-ejecución | ✅ |
| CA-36 | index.html (Apple Design System) | ✅ |
| CA-37 | SUPER_ADMIN recupera contraseña por correo | ✅ |
| CA-38 | Token de tenant rotable | ✅ |
| CA-39 | 2FA TOTP para SUPER_ADMIN en producción | ✅ |
| CA-40 | Audit trail de accesos SUPER_ADMIN | ✅ |
| CA-41 | dashboard.html sin Bearer → 401 | ✅ |
| CA-42 | superadmin.html sin sesión → 401 | ✅ |
| CA-43 | otp_panel.html sin token_enlace → redirect | ✅ |
| CA-44 | GET /health → 200 con estado DB | ✅ |

---

## 17. Estados del Sorteo

`PENDIENTE` → `EN_CURSO` → `LISTO` → `EJECUTANDO` → `COMPLETADO` | `ERROR`

---

## 18. Plan de Implementación

### Completado en v2.0

T-101 a T-122 y T-201 a T-211 (✅). Ver SDD v2.0.

### v2.1

#### Bloque A — Bugs críticos

| ID | Tarea | CA | Estado |
|---|---|---|---|
| T-301 | Bug vista pública | CA-28 | ⬜ |
| T-302 | Manejo 409 catálogo cargado | CA-30 | ⬜ |
| T-303 | Animación resultados | CA-33 | ⬜ |

#### Bloque B — Responsividad (Apple Design System)

| ID | Tarea | CA | Estado |
|---|---|---|---|
| T-304 | dashboard.html responsivo | CA-29 | ⬜ |
| T-305 | otp_panel.html responsivo | CA-29 | ⬜ |
| T-306 | publico.html responsivo | CA-29 | ⬜ |
| T-307 | superadmin.html responsivo | CA-29 | ⬜ |

#### Bloque C — Features

| ID | Tarea | CA | Estado |
|---|---|---|---|
| T-308 | Garantes configurables | CA-31 | ⬜ |
| T-309 | "consejeros" → "garantes" | CA-32 | ⬜ |
| T-310 | CRUD tenants (editar + eliminar + rotar) | CA-25,26,27,38 | ⬜ |
| T-311 | Correo bienvenida | CA-34 | ⬜ |
| T-312 | Navegación entre paneles | CA-35 | ⬜ |
| T-313 | Landing page index.html (Apple Design System) | CA-36 | ⬜ |

#### Bloque D — Seguridad

| ID | Tarea | CA | Estado |
|---|---|---|---|
| T-314 | Política acceso server-side paneles | CA-41,42,43 | ⬜ |
| T-315 | Recuperación contraseña SUPER_ADMIN | CA-37 | ⬜ |
| T-316 | 2FA TOTP SUPER_ADMIN | CA-39 | ⬜ |
| T-317 | Audit trail SUPER_ADMIN | CA-40 | ⬜ |

#### Bloque E — Infraestructura

| ID | Tarea | CA | Estado |
|---|---|---|---|
| T-318 | Health check /health | CA-44 | ⬜ |
| T-319 | Ping externo anti-cold-start (configurar UptimeRobot a GET /health cada 10 min) | — | ✅ |
| T-320 | Dominio sorteoparking.co + SSL (pendiente registro de dominio) | — | 📝 |

---

## 19. Fuera de Alcance — v2.1

Pasarela de pagos, app móvil, múltiples SUPER_ADMIN, Redis, CI/CD completo, SEO avanzado, multi-idioma.

---

*Última actualización: Mayo 2026 — Versión 2.1. Diseño frontend: [Apple Design System](DESIGN.md).*
