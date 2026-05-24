# SorteoParking — Especificación de Diseño de Software

## Versión 2.0 — Producción

| Campo | Valor |
|---|---|
| Versión | 2.0 — Producción |
| Fecha | Mayo 2026 |
| Estado | COMPLETADO |
| Basado en | Implementación real del sistema en Render |
| Autor | Michael López — Arquitectura y producto |
| Plataforma | Render (PostgreSQL) |
| IDE de desarrollo | Cursor |
| Stack | Python · FastAPI · PostgreSQL · Resend API · DeepSeek Flash |

---

## 1. Introducción

### 1.1 Propósito

Este documento define la arquitectura, contratos de datos, flujos y criterios de aceptación del sistema SorteoParking en su versión de producción multi-tenant. Todo componente documentado aquí EXISTE en el código actualmente desplegado en `https://sorteoparking.onrender.com`. Ningún componente se documenta antes de estar implementado.

### 1.2 Contexto y origen

SorteoParking nació como sistema de ejecución local para el Conjunto Residencial Aliso Vivienda (Cajicá, 904 unidades, SDD v1.4.3). Su diseño — algoritmo híbrido por zona, protocolo OTP de 5 consejeros, seed reproducible y acta encadenada — demostró ser robusto ante impugnaciones y garantizó transparencia comunitaria.

Esta versión 2.0 representa el estado actual del sistema en producción, con las lecciones aprendidas de despliegue en Render Free Tier, migración de SMTP a Resend HTTP API, corrección de bugs de autenticación CORS y OTP, y auditoría persistente encadenada.

### 1.3 Problema que resuelve

Los conjuntos VIS en Bogotá y la Sabana están obligados por ley (Decreto Distrital 555 de 2021 y Ley 675 de 2001) a gestionar parqueaderos como bienes comunes mediante sorteo. El proceso manual genera sesiones de 4 a 7 horas en salón comunal, percepción fundada de favoritismo, impugnaciones sin mecanismo de verificación, y carga administrativa excesiva.

SorteoParking reemplaza ese proceso con un sorteo atómico remoto, verificable y ejecutado en menos de 15 minutos desde cualquier dispositivo.

### 1.4 Diferencia clave respecto a v1.7

| Dimensión | v1.7 (Especificación) | v2.0 (Implementado) |
|---|---|---|
| Despliegue | Railway / Render | **Render (PostgreSQL)** |
| Correos | SMTP (Gmail) | **Resend HTTP API** |
| OTP panel | Panel básico | **Panel con polling, timer, auth bypass por token_enlace** |
| CORS | Sin especificar | **CORSMiddleware + preflight OPTIONS bypass** |
| Auditoría | Mencionada | **Capítulo formal + persistencia con commit posterior** |
| Frontend errors | Sin especificar | **safeString(), extractErrorMessage(), prevención [object Object]** |
| Exportación Excel | 4 hojas | **5 hojas (agregada Log Auditoria)** |
| Eventos auditoría | No listados | **8 eventos reales documentados** |

---

## 2. Stakeholders y Roles

| Rol | Actor | Permisos |
|---|---|---|
| SUPER_ADMIN | Equipo SorteoParking | Crear/suspender tenants · Ver métricas globales · Soporte |
| TENANT_ADMIN | Administrador del conjunto | Configurar conjunto · Cargar elegibles · Registrar consejeros · Iniciar sorteo · Exportar actas · Ver historial |
| CONSEJERO | 5 miembros del Consejo (dinámicos) | Recibir OTP por correo · Confirmar OTP vía panel público · Observar ejecución · Descargar acta |
| RESIDENTE | Participante del sorteo | Vista pública de resultados sin login · Verificar seed |
| SISTEMA | SorteoParking Cloud | Aislar datos por tenant · Ejecutar algoritmo · Enviar OTP por Resend · Notificar resultados · Generar actas · Log encadenado con hash |

---

## 3. Arquitectura del Sistema

### 3.1 Modelo de despliegue

SorteoParking opera como servicio web único desplegado en **Render**. Cada conjunto (tenant) tiene sus datos completamente aislados mediante `tenant_id` (UUID). No hay instalación local en el cliente.

**URL de producción:** `https://sorteoparking.onrender.com`

### 3.2 Componentes principales

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| API Backend | Python · FastAPI | Lógica de negocio · Contratos REST · Aislamiento tenant · CORS |
| Base de datos | PostgreSQL (Render) / SQLite fallback | Catálogo · Eventos · Log encadenado por tenant |
| Motor de sorteo | Python puro | Algoritmo híbrido · PRNG determinista · Seed reproducible |
| OTP Engine | Python · SHA-256 | Generación · Entrega por Resend · Validación · Expiración · Anti-replay |
| Notificaciones | Resend HTTP API | Envío de OTPs y resultados por correo electrónico |
| Frontend | HTML · CSS · JS vanilla | Dashboard TENANT_ADMIN · Panel OTP con polling · Vista pública residente |
| Hosting | Render | Despliegue Cloud · HTTPS · PostgreSQL gestionado |
| Parser IA | DeepSeek Flash (`deepseek-chat`) | Análisis semántico de Excel · Mapeo de columnas · Detección de estructura |

### 3.3 Aislamiento multi-tenant

Todas las tablas de la base de datos incluyen la columna `tenant_id` (UUID, FK a `tenants.id`). Cada request de API valida que el token de autenticación corresponda al `tenant_id` de los recursos solicitados mediante `enforce_tenant_scope()`. Ningún dato de un conjunto es accesible desde otro bajo ninguna circunstancia.

### 3.4 Estructura de carpetas del proyecto

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
├── requirements.txt
└── README.md
```

### 3.5 Middleware y autenticación

#### 3.5.1 `tenant_auth_middleware`

Middleware global ASGI registrado en `app.main`. Se ejecuta en cada request HTTP antes del enrutamiento.

```python
@app.middleware("http")
async def tenant_auth_middleware(request: Request, call_next):
```

**Flujo de decisión:**

1. **`OPTIONS`** → pasa sin autenticación (preflight CORS).
2. **`/favicon.ico`** → respuesta `204 No Content` directa, sin autenticación ni logging.
3. **Rutas `/auth/`, `/admin/`, `/debug/`** → `tenant_id = None`, pasan sin Bearer.
4. **Ruta pública `/p/...` y `/static/`** → `get_auth_context()` retorna `tenant_id=""`.
5. **OTP público** → `_acceso_consultar_otp_estado_sin_bearer()` para GET `/sorteos/{id}/otp/estado`.
6. **OTP confirmación** → `_acceso_confirmar_otp_consejero()` para POST `/sorteos/{id}/otp/confirmar` con header `X-Sorteo-Otp-Token`.
7. **Rutas protegidas** → extrae `Authorization: Bearer {uuid}`, valida UUID, asigna `tenant_id`.

```python
try:
    auth_ctx = get_auth_context(request)
    request.state.tenant_id = auth_ctx.tenant_id
except Exception as exc:
    # Retorna 401/403 con detalle del error
```

#### 3.5.2 CORSMiddleware

Agregado para permitir requests cross-origin desde el frontend servido en `https://sorteoparking.onrender.com`.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sorteoparking.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 3.5.3 AuthContext

```python
@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
```

El middleware asigna `request.state.tenant_id` desde `AuthContext`. Los endpoints lo leen de `request.state.tenant_id`. No hay otro mecanismo de propagación.

#### 3.5.4 Endpoints OTP públicos

Los siguientes endpoints NO requieren `Authorization: Bearer`. Son accesibles para consejeros desde el panel OTP:

| Método | Endpoint | Mecanismo de autenticación |
|---|---|---|
| GET | `/sorteos/{id}/otp/estado` | Query param `token_enlace` (UUID del enlace único) |
| POST | `/sorteos/{id}/otp/confirmar` | Header `X-Sorteo-Otp-Token` (mismo `token_enlace`) |

**Bypass implementado en `get_auth_context()`:**

```python
if _acceso_consultar_otp_estado_sin_bearer(request):
    return AuthContext(tenant_id="")

if _acceso_confirmar_otp_consejero(request):
    return AuthContext(tenant_id="")
```

#### 3.5.5 SecurityHeadersMiddleware

Middleware global que inyecta cabeceras de seguridad HTTP en todas las respuestas:

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Frame-Options: DENY`
- `Content-Security-Policy` restrictiva
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`
- `Cache-Control` diferenciado: `/p/...` cacheable 5 min, resto `no-store`

### 3.6 Contrato del token de tenant — TENANT_ADMIN

El token de tenant es un **UUID v4 opaco** generado al crear el conjunto con `POST /admin/tenants`. No es JWT. No tiene claims. Es el `id` de la tabla `tenants`.

| Atributo | Valor |
|---|---|
| Formato | UUID v4 — `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx` |
| Almacenamiento | Columna `tenants.id` en base de datos |
| Transmisión | Header `Authorization: Bearer {uuid}` |
| Validación | `get_auth_context()` → `parse_tenant_id_from_token()` → UUID |
| Revocación | Cambiar `tenants.estado` a `SUSPENDIDO` |

**Lo que NO es:**
- No es JWT — no tiene firma, claims ni expiración
- No se almacena en cookies — solo en header Bearer
- No se comparte entre tenants

### 3.7 Protección contra race conditions

| Operación | Riesgo | Solución implementada |
|---|---|---|
| Confirmar OTP | Doble confirmación simultánea | `with_for_update()` en query de SesionOTP |
| Ejecutar sorteo | Doble ejecución simultánea | Estado `EJECUTANDO` como mutex vía `update().where(estado="LISTO")` |
| Cargar Excel | Doble carga simultánea | Verificación de existencia previa |

### 3.8 Base de datos — PostgreSQL

El sistema opera con PostgreSQL en Render. SQLite persiste como fallback local para desarrollo.

**Configuración de conexión:**

```python
# Detección automática del motor según DATABASE_URL
is_sqlite = "sqlite" in str(engine.url)
# PostgreSQL: pool unificado
# SQLite: WAL mode + backup diario
```

---

## 4. Modelo de Datos

### 4.1 Entidad Tenant

```python
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Text, primary_key=True)  # UUID v4
    nombre = Column(Text, nullable=False)
    nit = Column(Text, unique=True, nullable=True)
    municipio = Column(Text, nullable=False)
    email_admin = Column(Text, nullable=False)
    slug = Column(Text, unique=True, nullable=True)  # URL amigable
    estado = Column(Text, default="ACTIVO")
    plan = Column(Text, default="POR_EVENTO")
    total_unidades = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 4.2 Entidades heredadas (con tenant_id)

| Entidad | Descripción |
|---|---|
| Zona | Sectores geográficos del conjunto |
| Torre | Torres vinculadas a una zona |
| Parqueadero | Catálogo maestro de cupos con tipo CARRO/MOTO |
| Participante | Elegibles cargados desde Excel por sorteo |
| Consejero | 5 garantes registrados dinámicamente por sesión |
| Sorteo | Evento con estado (PENDIENTE/EN_CURSO/LISTO/COMPLETADO/ERROR), seed, tipo |
| SesionOTP | OTP por consejero con estado, hash, expiración, intentos, token_enlace |
| ResultadoSorteo | Asignaciones finales parqueadero ↔ participante |
| LogAuditoria | Log encadenado append-only con hash de integridad |

### 4.3 Modelo SesionOTP (detalle)

```python
class SesionOTP(Base):
    __tablename__ = "sesiones_otp"
    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False)
    id = Column(Integer, primary_key=True, autoincrement=True)
    sorteo_id = Column(Integer, ForeignKey("sorteos.id"), nullable=False)
    consejero_id = Column(Integer, ForeignKey("consejeros.id"), nullable=False)
    otp_hash = Column(Text, nullable=False)       # SHA-256(pepper | otp)
    token_enlace = Column(Text, nullable=False)   # secrets.token_urlsafe(32)
    estado = Column(Text, default="PENDIENTE")    # PENDIENTE|CONFIRMADO|EXPIRADO|FALLO_EMAIL
    intentos = Column(Integer, default=0)
    expira_en = Column(DateTime, nullable=False)  # now() + 30 min
    confirmado_en = Column(DateTime, nullable=True)
```

---

## 5. Contratos de API

> Todos los endpoints requieren header `Authorization: Bearer {token}` excepto los públicos marcados con ⭐.

### 5.1 Gestión de Tenants (SUPER_ADMIN)

| Método | Endpoint | Descripción | Respuestas |
|---|---|---|---|
| POST | `/admin/tenants` | Crear nuevo conjunto | 201 Tenant · 409 NIT dup. |
| GET | `/admin/tenants` | Listar conjuntos activos | 200 Tenant[] |
| PATCH | `/admin/tenants/{id}` | Suspender / reactivar | 200 · 404 |
| POST | `/admin/backup` | Backup manual de SQLite | 200 |

### 5.2 Catálogo Maestro (TENANT_ADMIN)

| Método | Endpoint | Descripción | Respuestas |
|---|---|---|---|
| POST | `/catalogo/carga-csv` | Importa Excel/CSV — multipart/form-data | 201 Resumen · 400 · 422 |
| GET | `/catalogo/plantilla` | Descarga plantilla oficial | 200 .xlsx |
| GET | `/catalogo/zonas` | Lista zonas | 200 Zona[] |
| GET | `/catalogo/parqueaderos` | Lista parqueaderos | 200 Parqueadero[] |
| PATCH | `/catalogo/parqueaderos/{num}` | Edición puntual | 200 · 404 |

### 5.3 Sorteo (TENANT_ADMIN)

| Método | Endpoint | Descripción | Respuestas |
|---|---|---|---|
| POST | `/sorteos/carga-excel` | Carga elegibles desde Excel | 201 · 400 |
| POST | `/sorteos/iniciar` | Inicia sorteo + envía OTPs | 201 · 400 · 409 |
| GET | `/sorteos/{id}/estado` | Estado actual (polling) | 200 |
| GET | `/sorteos/{id}/diagnostico` | Previsualiza modelo por zona | 200 |
| POST | `/sorteos/{id}/ejecutar` | Ejecuta algoritmo híbrido | 200 · 409 |
| GET | `/sorteos/{id}/resultados` | Resultados paginados | 200 |
| POST | `/sorteos/{id}/exportar` | Exporta acta Excel o Word | 200 binario · 400 |
| POST | `/sorteos/{id}/notificar` | Notifica resultados por correo | 200 |
| GET | `/sorteos/historial` | Historial de sorteos | 200 |

### 5.4 OTP — Endpoints Públicos ⭐

| Método | Endpoint | Descripción | Auth | Respuestas |
|---|---|---|---|---|
| GET | `/sorteos/{id}/otp/estado?token_enlace=...` | Estado OTP del consejero | token_enlace | 200 · 404 |
| POST | `/sorteos/{id}/otp/confirmar` | Confirma OTP | `X-Sorteo-Otp-Token` | 200 · 400 |

### 5.5 Vista Pública Residente ⭐

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/p/{tenant_slug}/sorteos/{id}` | Resultados públicos |
| GET | `/p/{tenant_slug}/sorteos/{id}/seed` | Seed de verificación |

### 5.6 Auth (SUPER_ADMIN)

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/auth/login/superadmin` | Login con usuario + contraseña Argon2id |
| POST | `/auth/logout/superadmin` | Cierra sesión |

---

## 6. Protocolo OTP Completo

### 6.1 Visión general

El protocolo OTP permite que 5 consejeros garantes confirmen su presencia de forma remota antes de ejecutar un sorteo. Cada consejero recibe un código único por correo electrónico y confirma desde su celular sin instalar ninguna aplicación.

### 6.2 Flujo completo

```
TENANT_ADMIN
  │ POST /sorteos/iniciar {sorteo_id, consejeros: [{nombre, email}, x5]}
  ▼
SISTEMA
  │ 1. Valida estado PENDIENTE, catálogo cargado, participantes existentes
  │ 2. Genera snapshot_hash de participantes (SHA-256)
  │ 3. Estado → EN_CURSO
  │ 4. Por cada consejero:
  │    ├── Crea Consejero en DB
  │    ├── Genera OTP: 6 dígitos, secrets.randbelow(900000) + 100000
  │    ├── Hashea OTP: SHA-256(pepper | otp_plano)
  │    ├── Genera token_enlace: secrets.token_urlsafe(32)
  │    ├── Crea SesionOTP en DB con estado=PENDIENTE, expira_en=now()+30min
  │    └── Envía email vía Resend:
  │        ├── Destino: email del consejero
  │        ├── Asunto: "OTP SorteoParking — {nombre_conjunto}"
  │        └── Cuerpo: OTP + enlace al panel de confirmación
  │ 5. db.commit()
  └── Audit: SORTEO_INICIADO_OTP → db.commit()

CONSEJERO
  │ Abre enlace: https://sorteoparking.onrender.com/static/otp_panel.html#t={token_enlace}&sid={sorteo_id}
  ▼
PANEL OTP (frontend)
  │ 1. Extrae token_enlace y sorteo_id del hash de la URL
  │ 2. fetchEstado() cada 3s:
  │    GET /sorteos/{id}/otp/estado?token_enlace=...
  │    ├── Retorna: mi_estado, confirmados, total, consejeros[], expira_en
  │    ├── Muestra barra de progreso (x/5)
  │    ├── Muestra cards de consejeros con estado
  │    ├── Inicia temporizador de expiración (30 min)
  │    └── Si mi_estado === CONFIRMADO: muestra pantalla de éxito
  │
  │ 3. Usuario ingresa OTP de 6 dígitos
  │    ├── Auto-advance entre dígitos
  │    ├── Paste support
  │    ├── Backspace navigation
  │    └── Enter submit
  │
  │ 4. POST /sorteos/{id}/otp/confirmar
  │    Headers: Content-Type: application/json, X-Sorteo-Otp-Token: {token_enlace}
  │    Body: {"otp": "123456"}
  ▼
SISTEMA
  │ 1. Verifica token_enlace en SesionOTP (with_for_update)
  │ 2. Anti-replay: si estado=CONFIRMADO → 400
  │ 3. Expiración: si now() > expira_en → estado=EXPIRADO → 400
  │ 4. Intentos: si >= 3 → 400
  │ 5. Compara OTP: SHA-256(pepper | otp_ingresado) vs otp_hash
  │    ├── FALLA → intentos++, db.commit(), audit OTP_CONFIRMACION_FALLIDA → db.commit(), 400
  │    └── OK → estado=CONFIRMADO, confirmado_en=now(), db.flush()
  │
  │ 6. Cuenta CONFIRMADOS para este sorteo
  │    ├── < 5 → db.commit(), audit OTP_CONFIRMACION_OK → db.commit()
  │    └── >= 5 → sorteo.estado = LISTO → db.commit(), audit OTP_CONFIRMACION_OK → db.commit()

TENANT_ADMIN (dashboard)
  │ Polling cada 2s a GET /sorteos/{id}/otp/estado
  │ Cuando confirmados === 5: botón "Ejecutar sorteo" habilitado
  ▼
POST /sorteos/{id}/ejecutar → estado COMPLETADO
  │ Audit: SORTEO_EJECUTADO → db.commit()
```

### 6.3 token_enlace

El `token_enlace` es un string opaco de 43 caracteres generado con `secrets.token_urlsafe(32)`. Es ÚNICO por sesión OTP. Sirve para dos propósitos:

1. **Autenticación del consejero**: el token en la URL identifica qué consejero está confirmando, sin necesidad de Bearer token ni login.
2. **Seguridad**: solo quien tiene el enlace (enviado por correo) puede confirmar el OTP.

**Transmisión:**
- Enlace del panel: `.../otp_panel.html#t={token_enlace}&sid={sorteo_id}`
- GET estado: `?token_enlace=...` (query param)
- POST confirmar: `X-Sorteo-Otp-Token: {token_enlace}` (header)

### 6.4 Especificación del OTP

| Atributo | Valor | Implementación |
|---|---|---|
| Longitud | 6 dígitos | `f"{secrets.randbelow(900000) + 100000:d}"` |
| Entropía | ~20 bits | Suficiente con rate limiting |
| Almacenamiento | SHA-256 con pepper | `hashlib.sha256(f"{pepper}\|{otp}".encode()).hexdigest()` |
| Expiración | 30 minutos en DB | `expira_en = now() + timedelta(minutes=30)` |
| Intentos máximos | 3 | `ses.intentos >= 3` |
| Anti-replay | Single-use estricto | `ses.estado == "CONFIRMADO"` bloquea reintento |
| Rate limiting endpoint | 10/minuto | SlowAPI en POST confirmar |

### 6.5 Estados del OTP

| Estado | Significado |
|---|---|
| `PENDIENTE` | OTP generado, esperando confirmación |
| `CONFIRMADO` | OTP verificado correctamente |
| `EXPIRADO` | Pasaron 30 minutos sin confirmar |
| `FALLO_EMAIL` | No se pudo enviar el correo con el OTP |

### 6.6 Inmutabilidad del snapshot

El `snapshot_hash` se calcula con `_calcular_snapshot_hash(participantes)` al iniciar el sorteo. Es un SHA-256 de las líneas `documento|nombre` ordenadas. No se recalcula ni valida en ejecución — se fija como evidencia en el acta.

### 6.7 Polling frontend

**Panel OTP del consejero** (`otp_panel.html`):
- Polling cada 3s a `GET /sorteos/{id}/otp/estado?token_enlace=...`
- Temporizador visual de expiración (30 min → 00:00)
- Cuando `mi_estado === CONFIRMADO`: reemplaza UI con pantalla de éxito
- Cuando `confirmados === total && total > 0`: muestra pantalla "Todos confirmaron"

**Dashboard del TENANT_ADMIN** (`dashboard.html`):
- Polling cada 2s a `GET /sorteos/{id}/otp/estado`
- Barra de progreso 0/5 → 5/5
- Cards individuales por consejero con estado visual

---

## 7. Infraestructura de Correo

### 7.1 Abandono de SMTP

Render Free Tier **bloquea conexiones SMTP salientes** (`OSError: [Errno 101] Network is unreachable`). Gmail SMTP, incluso con App Password, no funciona desde Render Free. El sistema migró completamente a **Resend HTTP API**.

### 7.2 Resend HTTP API

```python
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

response = resend.Emails.send({
    "from": "onboarding@resend.dev",
    "to": destino,
    "subject": asunto,
    "html": html,  # Texto plano envuelto en HTML minimal
})
```

### 7.3 Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `RESEND_API_KEY` | API key de Resend | (requerida) |
| `RESEND_FROM` | Dirección remitente | `onboarding@resend.dev` |
| `PUBLIC_BASE_URL` | URL base para enlaces OTP | `http://127.0.0.1:8000` |

### 7.4 Mensajes enviados

1. **OTP a consejero**: código de 6 dígitos + enlace al panel de confirmación.
2. **Resultados a participantes**: notificación post-sorteo.
3. **Password reset a SUPER_ADMIN**: enlace de recuperación de contraseña.

### 7.5 Logging

| Log | Significado |
|---|---|
| `RESEND_SEND_START` | Inicio de envío |
| `RESEND_SEND_OK` | Envío exitoso con `response_id` |
| `RESEND_SEND_ERROR` | Error con traceback completo |
| `RESEND_MISSING_API_KEY` | Variable `RESEND_API_KEY` no configurada |

---

## 8. Auditoría

### 8.1 Sistema de log encadenado

La auditoría usa una tabla append-only con hash chain para garantizar integridad:

```python
class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"
    tenant_id = Column(Text, ForeignKey("tenants.id"), nullable=False)
    id = Column(Integer, primary_key=True, autoincrement=True)
    evento = Column(Text, nullable=False)
    payload = Column(Text, nullable=True)
    hash_anterior = Column(Text, nullable=True)
    hash_actual = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
```

### 8.2 Cadena de hashes

Cada nuevo log referencia el hash del log anterior para ese tenant:

```python
anterior = db.query(LogAuditoria).filter(
    LogAuditoria.tenant_id == tenant_id
).order_by(LogAuditoria.id.desc()).first()

hash_anterior = anterior.hash_actual if anterior else None
base = f"{tenant_id}|{evento}|{payload or ''}|{hash_anterior or ''}|{datetime.now(timezone.utc).isoformat()}"
hash_actual = hashlib.sha256(base.encode("utf-8")).hexdigest()
```

### 8.3 Persistencia con commit explícito

`registrar_log_auditoria()` ejecuta `db.flush()` + `db.refresh()`. NO hace `db.commit()`. El commit debe ejecutarse EXPLÍCITAMENTE después de la llamada.

**Patrón correcto:**
```python
registrar_log_auditoria(db=db, tenant_id=..., evento=..., payload=...)
db.commit()  # ← Obligatorio: flush sin commit no persiste
```

**Diferencia entre flush() y commit():**
- `flush()`: envía sentencias SQL al motor de BD, pero los cambios están en una transacción abierta. Visibles dentro de la misma sesión, pero no confirmados.
- `commit()`: confirma la transacción. Los cambios persisten y son visibles para otras sesiones.
- Sin `commit()`, `db.close()` (en `get_db()`) descarta los cambios.

### 8.4 Eventos de auditoría

| Evento | Cuándo se genera | Payload típico |
|---|---|---|
| `CONSULTA_HISTORIAL_SORTEOS` | GET /sorteos/historial | `total=3` |
| `CARGA_EXCEL_ELEGIBLES` | POST /sorteos/carga-excel | `sorteo_id=1,participantes=28,formato=oficial` |
| `SORTEO_INICIADO_OTP` | POST /sorteos/iniciar | `sorteo_id=1` |
| `OTP_CONFIRMACION_OK` | POST /sorteos/{id}/otp/confirmar | `sorteo_id=1,sesion_id=5` |
| `OTP_CONFIRMACION_FALLIDA` | POST /sorteos/{id}/otp/confirmar | `sorteo_id=1,sesion_id=5,intento=2` |
| `SORTEO_EJECUTADO` | POST /sorteos/{id}/ejecutar | `sorteo_id=1` |
| `SORTEO_ERROR` | POST /sorteos/{id}/ejecutar (fallo) | `sorteo_id=1,error=...` |
| `NOTIFICACION_RESULTADOS` | POST /sorteos/{id}/notificar | `sorteo_id=1,ok=20,fallos=2` |

### 8.5 Exportación a Excel

La hoja "Log Auditoria" del Excel exportado incluye:

| Columna | Contenido | Origen |
|---|---|---|
| Evento | Nombre del evento | `log.evento` |
| Payload | Datos del evento | `log.payload` |
| Hash Anterior | Hash del log previo | `log.hash_anterior` |
| Hash Actual | Hash del log actual | `log.hash_actual` |
| Timestamp | Fecha/hora UTC | `log.created_at` |

Ordenamiento: por `id` ascendente (500 registros máximo por defecto de exportación).

---

## 9. Exportador Excel

### 9.1 Hojas del Excel

| Hoja | Contenido | Columnas |
|---|---|---|
| Resumen | Métricas del sorteo | Conjunto, Fecha, Tipo, Estado, Seed, Snapshot, Totales |
| Ganadores | Asignaciones exitosas | Apartamento, Parqueadero, Zona, Tipo Vehículo, Reasignado |
| No Asignados | Participantes sin cupo | Apartamento, Tipo Vehículo |
| Consejeros | Garantes del sorteo | Nombre, Email, Estado OTP, Confirmado en |
| Log Auditoria | Cadena de eventos | Evento, Payload, Hash Anterior, Hash Actual, Timestamp |

### 9.2 Protección contra Formula Injection

```python
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

def _sanitizar(valor):
    if not isinstance(valor, str):
        valor = str(valor) if valor is not None else ""
    if valor.startswith(FORMULA_PREFIXES):
        return "'" + valor
    return valor
```

Aplica en todos los exportadores (Excel y Word).

### 9.3 Formatos

| Formato | Endpoint | Uso |
|---|---|---|
| Excel (.xlsx) | POST /sorteos/{id}/exportar?formato=excel | Archivo de trabajo |
| Word (.docx) | POST /sorteos/{id}/exportar?formato=word | Acta formal |

---

## 10. Frontend OTP

### 10.1 Sanitización DOM

El frontend implementa tres funciones de seguridad para prevenir `[object Object]` y otros problemas de renderizado:

#### `safeString(v)`

Convierte cualquier valor JavaScript a string sin producir `[object Object]`:

```javascript
function safeString(v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'string') return v;
    if (typeof v === 'number' || typeof v === 'boolean') return String(v);
    try { return JSON.stringify(v); } catch(e) { return String(v); }
}
```

#### `escHtml(s)`

Escapa HTML usando `textContent` (seguro contra XSS):

```javascript
function escHtml(s) {
    const str = safeString(s);
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}
```

#### `extractErrorMessage(payload)`

Normaliza errores del backend FastAPI a string legible:

```javascript
function extractErrorMessage(payload) {
    if (!payload) return 'Error desconocido';
    if (typeof payload === 'string') return payload;
    if (payload instanceof Error) return payload.message || 'Error inesperado';
    if (payload.detail) {
        if (typeof payload.detail === 'string') return payload.detail;
        if (Array.isArray(payload.detail))
            return payload.detail.map(x => x.msg || safeString(x)).join(', ');
        return safeString(payload.detail);
    }
    if (payload.message) return payload.message;
    return safeString(payload);
}
```

### 10.2 Manejo de errores HTTP

**Errores FastAPI (400, 401, 422):**
```javascript
const payload = await res.json().catch(() => null);
otpErrorEl.textContent = extractErrorMessage(payload);
```

**Errores Pydantic (422 con detail como array):**
Ejemplo de respuesta: `{"detail": [{"loc": ["body", "otp"], "msg": "field required"}]}`
`extractErrorMessage` extrae `x.msg` de cada elemento y los une con `, `.

**Errores de red:**
```javascript
catch(err) {
    otpErrorEl.textContent = err?.message || 'Error de conexión';
}
```

### 10.3 Polling y temporizador

- Polling de estado: `setInterval(fetchEstado, 3000)` en panel consejero
- Temporizador visual: `setInterval(updateTimer, 1000)` basado en `expira_en` del backend
- Limpieza: `clearInterval()` en éxito, error, o expiración

---

## 11. Flujo Operativo de un Evento

### 11.1 Duración estimada

| Actividad | Tiempo estimado |
|---|---|
| Cargar Excel de elegibles | 5 minutos |
| Configurar consejeros e iniciar sorteo | 5 minutos |
| Confirmación de 5 OTPs (remoto) | 10-15 minutos |
| Ejecución del algoritmo | < 1 minuto |
| Exportación de acta y notificaciones | 5 minutos |
| **TOTAL** | **~30 minutos** |

### 11.2 Diagrama de secuencia OTP

```
TENANT_ADMIN      SISTEMA              RESEND API          CONSEJERO
     │                │                     │                   │
     │ POST /iniciar  │                     │                   │
     │───────────────>│                     │                   │
     │                │───┬── Valida sorteo │                   │
     │                │   ├── Genera OTPs   │                   │
     │                │   └── snapshot_hash │                   │
     │                │ POST /emails/send   │                   │
     │                │────────────────────>│                   │
     │                │                     │ Email con OTP    │
     │                │                     │──────────────────>│
     │                │ Audit: SORTEO_INICIADO_OTP              │
     │                │                     │                   │
     │                │  ┌──────────────────────────────────────│
     │                │  │ Polling GET /otp/estado cada 3s      │
     │                │  │<─────────────────────────────────────│
     │                │  │─────────────────────────────────────>│
     │                │  │ mi_estado=PENDIENTE, confirmados=0   │
     │                │  └──────────────────────────────────────│
     │                │                     │                   │
     │                │                     │    POST /confirmar│
     │                │                     │<──────────────────│
     │                │───┬── Anti-replay   │                   │
     │                │   ├── Verifica OTP  │                   │
     │                │   └── CONFIRMADO    │                   │
     │                │ Audit: OTP_CONFIRMACION_OK              │
     │                │                     │                   │
     │ 5/5 → LISTO    │                     │                   │
     │ POST /ejecutar │                     │                   │
     │───────────────>│                     │                   │
     │                │ Audit: SORTEO_EJECUTADO                 │
     │                │───┬── Motor híbrido  │                   │
     │                │   └── COMPLETADO    │                   │
     │<───────────────│                     │                   │
     │ Resultados     │                     │                   │
```

---

## 12. Modelo Transaccional

### 12.1 Principios

1. `registrar_log_auditoria()` ejecuta `flush()` + `refresh()`, nunca `commit()`.
2. El `commit()` del log debe ejecutarse EXPLÍCITAMENTE después de la llamada.
3. El commit de datos del sorteo (cambio de estado, inserción de OTP) precede al commit del log.

### 12.2 Patrón en código

```python
# 1. Persistir datos del sorteo
sorteo.estado = "EN_CURSO"
db.add(sesion_otp)
db.commit()  # ← Persiste datos

# 2. Registrar auditoría
registrar_log_auditoria(db=db, tenant_id=..., evento=..., payload=...)
db.commit()  # ← Persiste log (flush sin commit no funciona)
```

### 12.3 Justificación

El uso de `flush()` (sin commit) en `registrar_log_auditoria()` permite:
- Obtener el `id` del log inmediatamente via `refresh()`
- Decidir si el log se confirma o se descarta (rollback) según el resultado de operaciones posteriores
- Mantener atomicidad: si la operación principal falla, el log tampoco se persiste

Sin embargo, este diseño requiere que CADA llamada a `registrar_log_auditoria()` vaya seguida de `db.commit()` en el llamador. La omisión de este commit fue el origen del bug de auditoría no persistente corregido en v2.0.

---

## 13. Seguridad

### 13.1 Principios

1. **Aislamiento total entre tenants** — ningún dato de un conjunto es accesible desde otro.
2. **Integridad del protocolo OTP** — el sorteo no puede ejecutarse sin los 5 OTPs confirmados.
3. **Privacidad de datos personales** — correos de participantes nunca aparecen en logs, actas ni respuestas de API.

### 13.2 CSRF

Para mutaciones en rutas `/admin/`:

1. Al login, se genera un token CSRF almacenado como cookie legible por JS: `csrf_token`.
2. El frontend lo incluye como header `X-CSRF-Token` en cada mutación.
3. El servidor valida con `hmac.compare_digest(csrf_cookie, csrf_header)`.

### 13.3 Cookies admin

| Cookie | HttpOnly | Secure | SameSite | Path | Propósito |
|---|---|---|---|---|---|
| `admin_session` | Sí | Sí | Strict | /admin | Identificador de sesión |
| `csrf_token` | No | Sí | Strict | /admin | Token CSRF (legible por JS) |

### 13.4 session_store

Tabla `admin_sessions` en la misma base de datos:

```sql
CREATE TABLE admin_sessions (
    session_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL,      -- SHA-256 del SUPER_ADMIN_TOKEN
    csrf_token TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,  -- 30 minutos
    revoked_at DATETIME
);
```

El `SUPER_ADMIN_TOKEN` (UUID) nunca se almacena en texto plano — solo su SHA-256.

### 13.5 OTP headers

| Header | Dónde se usa | Propósito |
|---|---|---|
| `X-Sorteo-Otp-Token` | POST /sorteos/{id}/otp/confirmar | Autenticación del consejero (sin Bearer) |
| `X-CSRF-Token` | Mutaciones en /admin/ | Protección CSRF |

### 13.6 Validación tenant

```python
def enforce_tenant_scope(request_tenant_id: str, resource_tenant_id: str):
    if request_tenant_id != resource_tenant_id:
        raise HTTPException(403, "Acceso denegado: recurso de otro tenant")
```

### 13.7 Comparación segura

Todas las comparaciones de tokens, OTPs y hashes usan:

```python
hmac.compare_digest(a, b)
```

Nunca se usa `==` para comparar valores secretos.

### 13.8 Cabeceras de seguridad HTTP

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Frame-Options: DENY`
- `Content-Security-Policy` restrictiva
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`

---

## 14. Variables de Entorno

| Variable | Requerida | Descripción | Default |
|---|---|---|---|
| `APP_ENV` | No | `production` o `development` | `development` |
| `DATABASE_URL` | Sí | URL de conexión PostgreSQL/SQLite | `sqlite:///./sorteoparking.db` |
| `RESEND_API_KEY` | Sí* | API key de Resend | — |
| `RESEND_FROM` | No | Dirección remitente correos | `onboarding@resend.dev` |
| `OTP_PEPPER` | Sí* | Pepper para hash SHA-256 de OTPs | (default dev) |
| `PUBLIC_BASE_URL` | Sí | URL base para enlaces OTP | `http://127.0.0.1:8000` |
| `SUPER_ADMIN_TOKEN` | No | Token UUID para bypass (dev) | — |
| `SUPER_ADMIN_USER` | No | Usuario admin | `admin` |
| `SUPER_ADMIN_PASSWORD_HASH` | No | Hash Argon2id de contraseña | — |
| `SUPER_ADMIN_EMAIL` | No | Email admin para recuperación | — |
| `DEEPSEEK_API_KEY` | No | API key de DeepSeek | — |
| `DEEPSEEK_MODEL` | No | Modelo DeepSeek | `deepseek-chat` |
| `BACKUP_DIR` | No | Directorio de backups SQLite | `/data/backups` |
| `BACKUP_RETENTION_DAYS` | No | Días de retención de backups | `30` |

*Requerida en producción.

---

## 15. Integración con DeepSeek Flash — Parser Inteligente

### 15.1 Arquitectura de dos fases

```
Fase 1 — IA analiza estructura (encabezados + 5 filas de muestra)
Fase 2 — Python lee datos aplicando el mapa (sin IA)
```

### 15.2 Sanitización estructural (Ley 1581/2012)

Cada valor se reemplaza por su tipo de dato inferido. DeepSeek recibe solo estructura — nunca PII.

| Columna | Valor real | Enviado a DeepSeek |
|---|---|---|
| nombre | "María García" | `[TEXTO]` |
| documento | 52847291 | `[NUMERO]` |

### 15.3 Variables

```
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TIMEOUT=10
DEEPSEEK_MIN_CONFIDENCE=0.80
```

---

## 16. Criterios de Aceptación

| # | Criterio | Estado |
|---|---|---|
| CA-01 | Dos tenants no pueden acceder a datos del otro | ✅ |
| CA-02 | Onboarding crea tenant con catálogo vacío | ✅ |
| CA-03 | OTP llega por correo en menos de 2 minutos | ✅ |
| CA-04 | Consejero confirma OTP desde celular sin instalar nada | ✅ |
| CA-05 | Panel OTP actualiza progreso sin recargar | ✅ |
| CA-06 | Sorteo bloqueado hasta 5 OTPs confirmados | ✅ |
| CA-07 | Snapshot de participantes fijo antes del primer OTP | ✅ |
| CA-08 | Reproducir sorteo con mismo seed produce idénticos resultados | ✅ |
| CA-09 | Acta incluye nombres y hora OTP de los 5 consejeros | ✅ |
| CA-10 | Acta NO incluye correos de participantes | ✅ |
| CA-11 | Vista pública sin login | ✅ |
| CA-12 | Seed visible en pantalla | ✅ |
| CA-13 | Log encadenado: cada entrada referencia hash anterior | ✅ |
| CA-14 | CORS permite upload multipart desde frontend | ✅ |
| CA-15 | Resend envía correos desde Render Free | ✅ |
| CA-16 | Auditoría persiste en DB (commit posterior) | ✅ |
| CA-17 | Excel exportado incluye hoja Log Auditoria | ✅ |
| CA-18 | Sin catálogo cargado, sorteo bloqueado con mensaje | ✅ |
| CA-19 | Error OTP muestra mensaje humano, no [object Object] | ✅ |
| CA-20 | OTP ya confirmado retorna 400 single-use | ✅ |
| CA-21 | Formula injection prevenida en Excel | ✅ |
| CA-22 | Doble ejecución de sorteo prevenida | ✅ |
| CA-23 | Backup diario con integrity_check | ✅ |
| CA-24 | Cabeceras de seguridad HTTP presentes | ✅ |

---

## 17. Estados del Sorteo

| Estado | Descripción | Transiciones válidas |
|---|---|---|
| `PENDIENTE` | Creado con participantes, sin iniciar | → `EN_CURSO` |
| `EN_CURSO` | OTPs enviados, consejeros confirmando | → `LISTO`, → `PENDIENTE` (rollback) |
| `LISTO` | 5/5 OTPs confirmados, listo para ejecutar | → `EJECUTANDO` |
| `EJECUTANDO` | Motor híbrido ejecutándose (transitorio) | → `COMPLETADO`, → `ERROR` |
| `COMPLETADO` | Sorteo ejecutado, resultados disponibles | (terminal) |
| `ERROR` | Fallo durante ejecución | (terminal) |

---

## 18. Fuera de Alcance — v2.0

- Pasarela de pagos automática
- App móvil nativa (iOS / Android)
- Múltiples usuarios SUPER_ADMIN con roles
- Redis como almacén de sesiones
- 2FA / TOTP
- CI/CD completo con gitleaks, pip-audit, checkov
- Registro de dominio personalizado
- Página de aterrizaje (landing page)

---

*Última actualización: Mayo 2026 — Documento alineado con el código en `main` (commit `d5aee47`).*
