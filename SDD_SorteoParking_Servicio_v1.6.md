# SorteoParking — Especificación de Diseño de Software

## Versión 1.6 — Hardening crítico para piloto Aliso Vivienda julio 2026

|Campo|Valor|
|-|-|
|Versión|1.6 — Hardening crítico para piloto Aliso Vivienda julio 2026|
|Fecha|Mayo 2026|
|Estado|EN ELABORACIÓN|
|Basado en|SDD SorteoParking v1.4.3 (Aliso Vivienda)|
|Autor|Michael López — Arquitectura y producto|
|Plataforma objetivo|Cloud — Railway / Render|
|IDE de desarrollo|Cursor|
|Stack|Python · FastAPI · SQLite · WhatsApp OTP · DeepSeek Flash|

\---

## 1\. Introducción

### 1.1 Propósito

Este documento define la arquitectura, contratos de datos, flujos y criterios de aceptación del sistema SorteoParking en su versión de servicio multi-tenant en la nube. Ningún componente se implementa sin que este SDD lo especifique previamente.

### 1.2 Contexto y origen

SorteoParking nació como sistema de ejecución local para el Conjunto Residencial Aliso Vivienda (Cajicá, 904 unidades, SDD v1.4.3). Su diseño — algoritmo híbrido por zona, protocolo OTP de 5 consejeros, seed reproducible y acta encadenada — demostró ser robusto ante impugnaciones y garantizó transparencia comunitaria.

Esta versión 1.3 migra ese núcleo a un servicio comercial capaz de atender múltiples conjuntos simultáneamente, con operación remota, pago por evento y despliegue en Cloud.

### 1.3 Problema que resuelve

Los conjuntos VIS en Bogotá y la Sabana están obligados por ley (Decreto Distrital 555 de 2021 y Ley 675 de 2001) a gestionar parqueaderos como bienes comunes mediante sorteo. El proceso manual genera:

* Sesiones de 4 a 7 horas en salón comunal.
* Percepción fundada de favoritismo e inequidad.
* Impugnaciones sin mecanismo de verificación.
* Reseñas negativas en Google Maps que desvalorizan el conjunto.
* Carga administrativa excesiva sobre el administrador y el consejo.

SorteoParking reemplaza ese proceso con un sorteo atómico remoto, verificable y ejecutado en menos de 15 minutos desde cualquier dispositivo.

### 1.4 Diferencia clave respecto al v1.4.3

|Dimensión|v1.4.3 (Local)|v1.3 (Servicio Cloud + IA)|
|-|-|-|
|Despliegue|Portátil local del operador|Servidor Cloud (Railway/Render)|
|Conjuntos|Uno (Aliso Vivienda)|Múltiples (multi-tenant)|
|OTP|Consejeros presentes o en Zoom|Consejeros remotos por WhatsApp|
|Configuración|Hardcodeada|Onboarding por conjunto|
|Modelo de negocio|Uso interno gratuito|Pago por evento|
|Núcleo reutilizado|—|Algoritmo híbrido, OTP, seed, acta, log|

\---

## 2\. Stakeholders y Roles

|Rol|Actor|Permisos|
|-|-|-|
|SUPER\_ADMIN|Equipo SorteoParking|Crear/suspender tenants · Ver métricas globales · Soporte|
|TENANT\_ADMIN|Administrador del conjunto|Configurar conjunto · Cargar elegibles · Registrar consejeros · Iniciar sorteo · Exportar actas · Ver historial|
|CONSEJERO|5 miembros del Consejo (dinámicos)|Recibir OTP por WhatsApp · Confirmar OTP · Observar ejecución · Descargar acta|
|RESIDENTE|Participante del sorteo|Vista pública de resultados sin login · Verificar seed|
|SISTEMA|SorteoParking Cloud|Aislar datos por tenant · Ejecutar algoritmo · Enviar OTP WhatsApp · Notificar resultados · Generar actas · Log encadenado|

\---

## 3\. Arquitectura del Sistema

### 3.1 Modelo de despliegue

SorteoParking opera como servicio web único desplegado en Cloud. Cada conjunto (tenant) tiene sus datos completamente aislados en la misma base de datos mediante un identificador único de tenant. No hay instalación local en el cliente.

### 3.2 Componentes principales

|Componente|Tecnología|Responsabilidad|
|-|-|-|
|API Backend|Python · FastAPI|Lógica de negocio · Contratos REST · Aislamiento tenant|
|Base de datos|SQLite · WAL mode|Catálogo · Eventos · Log encadenado por tenant — **Migración a PostgreSQL planificada en v1.5**|
|Motor de sorteo|Python puro|Algoritmo híbrido · PRNG determinista · Seed reproducible|
|OTP Engine|Python · SHA-256|Generación · Entrega WhatsApp · Validación · Expiración|
|Canal OTP|WhatsApp Business API|Entrega segura del código a cada consejero|
|Notificaciones|WhatsApp · Email fallback|Resultados del sorteo a participantes|
|Frontend|HTML · CSS · JS vanilla|Dashboard TENANT\_ADMIN · Panel OTP · Vista pública residente|
|Hosting|Railway o Render|Despliegue Cloud · HTTPS · Variables de entorno|
|Parser IA|DeepSeek Flash (`deepseek-chat`)|Análisis semántico de Excel · Mapeo de columnas · Detección de estructura|

### 3.3 Aislamiento multi-tenant

Todas las tablas de la base de datos incluyen la columna `tenant\_id` (UUID). Cada request de API valida que el token de autenticación corresponda al `tenant\_id` de los recursos solicitados. Ningún dato de un conjunto es accesible desde otro bajo ninguna circunstancia.

### 3.4 Estructura de carpetas del proyecto

```
sorteoparking/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── models/
│   │   ├── tenant.py
│   │   ├── catalogo.py
│   │   ├── sorteo.py
│   │   └── log.py
│   ├── routers/
│   │   ├── admin.py
│   │   ├── catalogo.py
│   │   ├── sorteos.py
│   │   └── publico.py
│   ├── services/
│   │   ├── sorteo\_engine.py
│   │   ├── otp\_service.py
│   │   ├── whatsapp.py
│   │   ├── exportadores.py
│   │   ├── excel\_parser.py
│   │   └── deepseek\_service.py
│   └── db/
│       └── database.py
├── frontend/
│   ├── dashboard.html
│   ├── otp\_panel.html
│   └── publico.html
├── requirements.txt
└── README.md
```


### 3.6 Nota de arquitectura — SQLite y plan de migración

SQLite en modo WAL es la elección correcta para v1.4 por su simplicidad operativa y costo cero. Sin embargo tiene limitaciones conocidas bajo carga concurrente — específicamente el error `database is locked` cuando múltiples workers escriben simultáneamente.

**Umbrales de migración a PostgreSQL:**

| Indicador | Umbral | Acción |
|---|---|---|
| Tenants activos | > 50 | Migrar a PostgreSQL |
| Sorteos simultáneos por día | > 10 | Migrar a PostgreSQL |
| Errores `database is locked` | > 0 en producción | Migrar a PostgreSQL inmediatamente |

**Configuración de SQLAlchemy en v1.5 — timeouts y pool:**

```python
# app/db/database.py
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "timeout": 5,           # Abortar si DB bloqueada > 5s
        "check_same_thread": False
    },
    pool_pre_ping=True,         # Verificar conexión antes de usar
    pool_size=5,                # Conexiones simultáneas máximas
    max_overflow=2,             # Conexiones extra en pico
    pool_recycle=300,           # Reciclar conexiones cada 5 min
)

# Checkpoint WAL periódico — evita crecimiento del archivo WAL
@app.on_event("startup")
async def configurar_sqlite():
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.execute(text("PRAGMA cache_size=10000"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
```

**La migración es transparente:** SQLAlchemy ORM abstrae el motor de base de datos. Cambiar de SQLite a PostgreSQL requiere solo actualizar `DATABASE_URL` en las variables de entorno y ejecutar las migraciones con Alembic.

**Para v1.5 se agrega:**
- `DATABASE_URL=postgresql://...` en Railway
- Alembic para migraciones controladas
- Connection pooling con `pool_size=10`
- Redis para sesiones y rate limiting compartido entre workers



### 3.8 Protección contra race conditions en sorteo (T-120)

El sorteo es un evento único e irrepetible. Una doble ejecución produce resultados inconsistentes que invalidan el acta.

**Puntos críticos de race condition:**

| Operación | Riesgo | Solución |
|---|---|---|
| Confirmar OTP | Doble confirmación simultánea | `with_for_update()` en query |
| Ejecutar sorteo | Doble ejecución simultánea | Estado `EJECUTANDO` como mutex |
| Cargar Excel | Doble carga simultánea | Idempotency key por archivo |

**Mutex de ejecución:**
```python
def ejecutar_sorteo(sorteo_id: int, db: Session):
    # Cambiar estado a EJECUTANDO con lock — mutex distribuido
    resultado = db.execute(
        update(Sorteo)
        .where(
            Sorteo.id == sorteo_id,
            Sorteo.estado == "LISTO"  # Solo si está en LISTO
        )
        .values(estado="EJECUTANDO")
        .returning(Sorteo.id)
    )
    db.commit()

    if not resultado.fetchone():
        raise HTTPException(409,
            "El sorteo ya está siendo ejecutado o no está en estado LISTO")

    try:
        # Ejecutar motor híbrido
        resultados = ejecutar_sorteo_hibrido(sorteo_id, db)
        db.execute(update(Sorteo).where(
            Sorteo.id == sorteo_id).values(estado="COMPLETADO"))
        db.commit()
        return resultados
    except Exception as e:
        db.execute(update(Sorteo).where(
            Sorteo.id == sorteo_id).values(estado="ERROR"))
        db.commit()
        raise
```

### 3.7 Contrato del token de tenant — TENANT_ADMIN

El token de tenant es un **UUID v4 opaco** generado al crear el conjunto con `POST /admin/tenants`. No es JWT. No tiene claims. Es una referencia a la tabla `tenants`.

**Características:**

| Atributo | Valor |
|---|---|
| Formato | UUID v4 — `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx` |
| Almacenamiento | Columna `tenants.id` en base de datos |
| Transmisión | Header `Authorization: Bearer {uuid}` |
| Validación | El middleware extrae el UUID, busca en `tenants` y verifica `estado=ACTIVO` |
| Revocación | Cambiar `tenants.estado` a `SUSPENDIDO` invalida el token inmediatamente |
| Rotación | No aplica en v1.5 — el UUID es permanente mientras el tenant existe |

**Lo que NO es:**
- No es JWT — no tiene firma, claims ni expiración
- No se almacena en cookies — solo en header Bearer
- No se comparte entre tenants — cada conjunto tiene su propio UUID

**Validación en middleware:**
```python
def parse_tenant_id_from_token(token: str, db: Session) -> str:
    try:
        uuid = str(UUID(token.strip()))
    except ValueError:
        raise HTTPException(401, "Token inválido")
    
    tenant = db.query(Tenant).filter(
        Tenant.id == uuid,
        Tenant.estado == "ACTIVO"
    ).first()
    
    if not tenant:
        raise HTTPException(403, "Tenant no encontrado o suspendido")
    
    return uuid
```

### 3.5 Reutilización del núcleo v1.4.3

Los siguientes módulos se migran directamente desde v1.4.3 con adaptación mínima (agregar `tenant\_id`):

* `sorteo\_engine.py` — algoritmo híbrido por zona (Modelo 1 / Modelo 2)
* Protocolo OTP: generación SHA-256, validación, expiración, 5 consejeros requeridos
* Seed reproducible: `secrets.token\_hex(32)` → `SHA-256(timestamp + snapshot)` → `random.Random()`
* Log encadenado (blockchain-style): cada entrada referencia hash de la anterior
* Exportadores: acta Excel y Word con consejeros, seed y resultados
* Modelo de datos de catálogo: Zona, Torre, Parqueadero
* Modelo de datos de evento: Participante, Consejero, Sorteo, SesionOTP, ResultadoSorteo

\---

## 4\. Modelo de Datos

### 4.1 Entidad Tenant (nueva en v1.2)

```python
class Tenant(Base):
    \_\_tablename\_\_ = "tenants"

    id            = Column(UUID, primary\_key=True, default=uuid4)
    nombre        = Column(Text, nullable=False)
    nit           = Column(Text, unique=True, nullable=True)
    municipio     = Column(Text, nullable=False)
    email\_admin   = Column(Text, nullable=False)
    whatsapp\_admin= Column(Text, nullable=True)
    estado        = Column(Enum("ACTIVO","SUSPENDIDO","DEMO"), default="ACTIVO")
    plan          = Column(Enum("POR\_EVENTO"), default="POR\_EVENTO")
    total\_unidades= Column(Integer, nullable=True)
    created\_at    = Column(DateTime, default=datetime.utcnow)
```

### 4.2 Entidades heredadas de v1.4.3 (con tenant\_id)

Todas las tablas existentes reciben `tenant\_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)` como primera columna adicional.

|Entidad|Descripción|
|-|-|
|Zona|Sectores geográficos del conjunto (A, B, C, D)|
|Torre|Torres del conjunto vinculadas a una zona|
|Parqueadero|Catálogo maestro de cupos con tipo CARRO/MOTO|
|Participante|Elegibles cargados desde Excel por sorteo|
|Consejero|5 garantes registrados dinámicamente por sesión|
|Sorteo|Evento de sorteo con estado, seed y tipo|
|SesionOTP|OTPs generados por sorteo con estado de confirmación|
|ResultadoSorteo|Asignaciones finales parqueadero ↔ participante|
|LogAuditoria|Log encadenado append-only con hash de integridad|

\---

## 5\. Contratos de API

> Todos los endpoints requieren header `Authorization: Bearer {token}` excepto los públicos marcados con ⭐.
> El token identifica al tenant — el sistema rechaza con HTTP 403 cualquier intento de acceder a recursos de otro tenant.

### 5.1 Gestión de Tenants (SUPER\_ADMIN)

|Método|Endpoint|Descripción|Respuestas|
|-|-|-|-|
|POST|`/admin/tenants`|Crear nuevo conjunto (onboarding)|201 Tenant · 409 NIT dup.|
|GET|`/admin/tenants`|Listar todos los conjuntos activos|200 Tenant\[]|
|PATCH|`/admin/tenants/{id}`|Suspender / reactivar tenant|200 · 404|
|GET|`/admin/metricas`|Eventos por tenant, ingresos, estado|200 Metricas|

### 5.2 Catálogo Maestro (TENANT\_ADMIN)

|Método|Endpoint|Descripción|Respuestas|
|-|-|-|-|
|POST|`/catalogo/carga-csv`|Importa Excel o CSV — parser inteligente con DeepSeek Flash|201 ResumenCarga · 422 estructura no reconocida|
|GET|`/catalogo/plantilla`|Descarga la plantilla oficial de SorteoParking|200 archivo .xlsx|
|GET|`/catalogo/zonas`|Lista zonas con conteo de parqueaderos|200 Zona\[]|
|GET|`/catalogo/parqueaderos`|Lista parqueaderos con filtros|200 Parqueadero\[]|
|PATCH|`/catalogo/parqueaderos/{num}`|Edición puntual de parqueadero|200 · 404|

### 5.3 Sorteo (TENANT\_ADMIN + CONSEJERO)

|Método|Endpoint|Descripción|Respuestas|
|-|-|-|-|
|POST|`/sorteos/carga-excel`|Carga Excel de elegibles validado|201 ResumenCarga · 400|
|POST|`/sorteos/iniciar`|Crea sorteo + consejeros + envía OTPs por WhatsApp|201 Sorteo · 409 en curso|
|POST|`/sorteos/{id}/otp/confirmar`|Consejero confirma OTP — al 5°: estado LISTO|200 · 400 inválido/expirado|
|GET|`/sorteos/{id}/otp/estado`|Progreso confirmaciones 0-5 con nombres|200 EstadoOTP|
|GET|`/sorteos/{id}/estado`|Estado actual (polling cada 2s)|200 EstadoSorteo|
|GET|`/sorteos/{id}/diagnostico`|Previsualiza modelo por zona antes de ejecutar|200 DiagnosticoZona\[]|
|POST|`/sorteos/{id}/ejecutar`|Ejecuta algoritmo — solo si estado=LISTO|200 ResultadoSorteo\[] · 409|
|GET|`/sorteos/{id}/resultados`|Resultados paginados con filtros|200 ResultadoPaginado|
|POST|`/sorteos/{id}/exportar`|Genera acta Excel o Word|200 archivo binario · 400|
|POST|`/sorteos/{id}/notificar`|Envía resultados por WhatsApp a participantes|200 ResumenEnvio · 500|
|GET|`/sorteos/historial`|Todos los sorteos del tenant con log|200 SorteoResumen\[]|

### 5.4 Vista Pública Residente ⭐ (sin autenticación)

|Método|Endpoint|Descripción|Respuestas|
|-|-|-|-|
|GET|`/p/{tenant\_slug}/sorteos/{id}`|Resultados públicos del sorteo — sin login|200 · 404|
|GET|`/p/{tenant\_slug}/sorteos/{id}/seed`|Seed público para verificación independiente|200 · 404|

\---

## 6\. Protocolo OTP Remoto por WhatsApp

### 6.1 Diferencia respecto a v1.4.3

En v1.4.3 los OTPs se confirmaban con consejeros presentes o en Zoom. En v1.0 los consejeros pueden estar en cualquier lugar — reciben su OTP por WhatsApp y confirman desde su celular accediendo a la URL del panel OTP.

### 6.2 Flujo del protocolo

1. TENANT\_ADMIN inicia el sorteo e ingresa el WhatsApp de los 5 consejeros.
2. El sistema genera 5 OTPs únicos (SHA-256) con expiración de 30 minutos.
3. Cada consejero recibe por WhatsApp: su OTP, el nombre del conjunto y un enlace directo al panel de confirmación.
4. El consejero abre el enlace desde su celular e ingresa su OTP.
5. El panel OTP del TENANT\_ADMIN actualiza en tiempo real el progreso (0/5 → 5/5).
6. Al confirmar el 5° OTP, el estado cambia a `LISTO` y se habilita el botón **Ejecutar sorteo**.
7. OTP no confirmado en 30 minutos: expira. El TENANT\_ADMIN puede regenerar sin invalidar los ya confirmados.


### 6.4 Especificación del OTP — seguridad y entropía

| Atributo | Valor | Justificación |
|---|---|---|
| Longitud | 6 dígitos | UX óptima para WhatsApp y email |
| Generación | `secrets.randbelow(1_000_000)` con `.zfill(6)` | ~20 bits de entropía — suficiente con rate limiting estricto |
| Expiración | 5 minutos en DB | No solo en UI — validado en cada intento |
| Intentos máximos | 3 por código | Al 4to intento el OTP se invalida |
| Bloqueo por IP | 15 minutos tras 3 fallos | Previene fuerza bruta distribuida |
| Bloqueo por tenant | 30 minutos tras 10 fallos totales | Previene ataques de baja frecuencia |
| Almacenamiento | SHA-256 del OTP en DB | El OTP real nunca persiste en texto plano |

**Generación correcta:**
```python
import secrets

def generar_otp() -> str:
    """Genera OTP de 6 dígitos con entropía criptográfica."""
    return str(secrets.randbelow(1_000_000)).zfill(6)
```

**Validación con rate limiting:**
```python
def confirmar_otp(session: SesionOTP, otp_ingresado: str, db: Session) -> bool:
    # 1. Verificar expiración real en DB
    if session.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "OTP expirado")
    
    # 2. Verificar intentos máximos
    if session.intentos >= 3:
        session.invalidado = True
        db.commit()
        raise HTTPException(400, "OTP invalidado por exceso de intentos")
    
    # 3. Comparar en tiempo constante contra hash
    hash_ingresado = sha256(otp_ingresado.encode()).hexdigest()
    if not hmac.compare_digest(hash_ingresado, session.otp_hash):
        session.intentos += 1
        db.commit()
        raise HTTPException(400, "OTP incorrecto")
    
    session.confirmado = True
    db.commit()
    return True
```


### 6.5 Inmutabilidad del snapshot de participantes

El snapshot se fija antes del primer OTP confirmado. En `/ejecutar` se valida que no haya cambiado.

```python
def ejecutar_sorteo(sorteo_id: int, db: Session) -> list[ResultadoSorteo]:
    sorteo = db.query(Sorteo).filter(Sorteo.id == sorteo_id).first()
    
    # Recalcular hash actual de participantes
    participantes = db.query(Participante).filter(
        Participante.sorteo_id == sorteo_id
    ).order_by(Participante.id).all()
    
    hash_actual = sha256(
        json.dumps([p.to_dict() for p in participantes], 
                   sort_keys=True).encode()
    ).hexdigest()
    
    # Validar inmutabilidad
    if not hmac.compare_digest(hash_actual, sorteo.snapshot_hash):
        raise HTTPException(
            422, 
            "Integridad comprometida: los participantes fueron "
            "modificados después de confirmar los OTPs"
        )
    
    # Continuar con el motor híbrido
    return ejecutar_sorteo_hibrido(sorteo, participantes, db)
```


### 6.6 Anti-replay de OTP — invalidación inmediata (T-118)

Un OTP confirmado debe invalidarse inmediatamente. No puede reutilizarse bajo ninguna circunstancia.

**Reglas anti-replay:**

1. Al confirmar exitosamente un OTP → `sesion_otp.confirmado = True` + `sesion_otp.confirmado_en = now()`
2. Cualquier intento posterior de confirmar el mismo OTP → HTTP 400 "OTP ya utilizado"
3. El OTP se considera usado incluso si la sesión del sorteo falla después
4. Un OTP expirado no puede reactivarse — solo regenerarse

```python
def confirmar_otp(session_id: int, otp_ingresado: str, db: Session) -> bool:
    sesion = db.query(SesionOTP).filter(
        SesionOTP.id == session_id
    ).with_for_update().first()  # Lock para prevenir race condition

    # Anti-replay: verificar si ya fue usado
    if sesion.confirmado:
        raise HTTPException(400, "OTP ya utilizado — no se puede reutilizar")

    # Verificar expiración
    if sesion.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "OTP expirado")

    # Verificar intentos
    if sesion.intentos >= 3:
        raise HTTPException(400, "OTP bloqueado por exceso de intentos")

    # Comparar en tiempo constante
    hash_ingresado = sha256(otp_ingresado.encode()).hexdigest()
    if not hmac.compare_digest(hash_ingresado, sesion.otp_hash):
        sesion.intentos += 1
        db.commit()
        raise HTTPException(400, "OTP incorrecto")

    # Marcar como usado — single-use estricto
    sesion.confirmado = True
    sesion.confirmado_en = datetime.now(timezone.utc)
    db.commit()
    return True
```

**El `with_for_update()` es obligatorio** — previene que dos requests simultáneos confirmen el mismo OTP (race condition C-10).

### 6.3 Invariantes del protocolo (no negociables)

* Los 5 OTPs deben confirmarse antes de ejecutar el sorteo — sin excepción.
* El snapshot de participantes se fija antes de la confirmación del primer OTP.
* Regenerar un OTP expirado no invalida los OTPs ya confirmados.
* El seed se deriva de `SHA-256(timestamp\_utc + hash del snapshot)` — no puede predecirse.
* El log registra la hora exacta de confirmación de cada consejero — aparece en el acta.

\---

## 7\. Flujo Operativo de un Evento

### 7.1 Responsabilidades previas al evento

> SorteoParking no valida la elegibilidad de los participantes. Esa responsabilidad es exclusiva de la administración del conjunto. El servicio recibe la lista ya depurada y ejecuta el sorteo.

|Responsable|Tarea|
|-|-|
|Administración del conjunto|Publicar lista de elegibles y periodo de reclamaciones|
|Administración del conjunto|Resolver reclamaciones hasta lista definitiva sin reclamos|
|Administración del conjunto|Entregar Excel de elegibles depurado a SorteoParking|
|Administración del conjunto|Confirmar WhatsApps de los 5 consejeros garantes|
|SorteoParking|Cargar Excel · Iniciar sorteo · Coordinar OTPs · Ejecutar · Entregar acta|

### 7.2 Duración estimada del evento (operación remota)

|Actividad|Tiempo estimado|
|-|-|
|Recibir y cargar Excel de elegibles|20 minutos|
|Configurar consejeros e iniciar sorteo|10 minutos|
|Coordinación y confirmación de 5 OTPs|15 minutos|
|Ejecución del algoritmo|< 1 minuto|
|Exportación de acta y notificaciones|10 minutos|
|**TOTAL**|**\~1 hora**|

\---

## 8\. Modelo de Negocio

### 8.1 Estructura de precios (v1.2)

|Producto|Precio|Condición|
|-|-|-|
|Sorteo individual|$400.000 COP|Pago previo al evento|
|Paquete 3 sorteos|$1.050.000 COP|12% descuento — vigencia 12 meses|
|Paquete 6 sorteos|$1.920.000 COP|20% descuento — vigencia 12 meses|

### 8.2 Capacidad operativa

Con operación remota (un operador), la capacidad máxima es de 5 sorteos por jornada. A $400.000 por evento, 5 sorteos generan $2.000.000 en una jornada.

### 8.3 Meta de viabilidad

La operación es viable comercialmente cuando genera $5.000.000 COP mensuales. Con precio promedio de $400.000 por evento se requieren 12-13 eventos mensuales, equivalente a \~50 conjuntos activos con paquete de 3 sorteos anuales.

\---

## 9\. Plan de Implementación — 90 Días

### Mes 1 — Multi-tenant y despliegue Cloud

|ID|Tarea|Spec ref.|
|-|-|-|
|T-101|Agregar entidad Tenant y `tenant\_id` a todas las tablas|§4.1 · §4.2|
|T-102|Middleware de autenticación y aislamiento por tenant|§3.3|
|T-103|Endpoints SUPER\_ADMIN: crear y listar tenants|§5.1|
|T-104|Onboarding: formulario de registro de nuevo conjunto|§3.1|
|T-105|Despliegue en Railway con HTTPS y variables de entorno|§3.2|
|T-106|Migrar catálogo, sorteo y log del v1.4.3 con tenant\_id|§3.5|
|T-107|Login seguro SUPER\_ADMIN con enmascaramiento de token|§13|

### Mes 2 — OTP remoto y notificaciones WhatsApp

|ID|Tarea|Spec ref.|
|-|-|-|
|T-201|Integración WhatsApp Business API para envío de OTPs|§6.2|
|T-202|Panel OTP remoto: URL por consejero · confirmación desde celular|§6.2|
|T-203|Polling tiempo real del estado OTP en dashboard TENANT\_ADMIN|§5.3|
|T-204|Notificaciones de resultados por WhatsApp a participantes|§5.3|
|T-205|Vista pública residente: resultados y seed sin login|§5.4|
|T-206|Email fallback si WhatsApp no disponible|§3.2|

### Mes 3 — Piloto, ajustes y primer cliente externo

|ID|Tarea|Spec ref.|
|-|-|-|
|T-301|Piloto completo con Aliso Vivienda como primer tenant real|Todos|
|T-302|Ajustes basados en piloto (bugs, UX, tiempos)|Todos|
|T-303|Panel de métricas SUPER\_ADMIN: eventos, ingresos, estado|§5.1|
|T-304|Flujo de pago previo al evento (pasarela o transferencia manual)|§8.1|
|T-305|Primer cliente externo: onboarding, sorteo y acta entregada|§8|

### Mes 4 — Parser Inteligente y Exportación

|ID|Tarea|Spec ref.|
|-|-|-|
|T-108|Parser inteligente con DeepSeek Flash para cualquier Excel|§14|
|T-109|Catálogo maestro: carga idempotente + plantilla descargable|§15|
|T-110|Exportación completa: acta con 5 hojas y log de auditoría|§16|

### Mes 5 — Hardening AppSec v1.5

|ID|Tarea|Spec ref.|
|-|-|-|
|T-111|Sesiones SUPER\_ADMIN en SQLite — tabla `admin_sessions`|§13.11|
|T-112|OTP de 6 dígitos con rate limit estricto y hash en DB|§6.4|
|T-113|Validación snapshot\_hash en `/ejecutar`|§6.5|
|T-114|SQLAlchemy con timeouts y configuración WAL|§3.6|
|T-115|Límites de seguridad en carga de Excel — ZIP bomb protection|§14.10|
|T-116|`datetime.utcnow()` → `datetime.now(timezone.utc)` en todo el proyecto|§L-03|

### Mes 6 — Hardening crítico piloto Aliso julio 2026

|ID|Tarea|Spec ref.|Hallazgo|
|-|-|-|-|
|T-117|Tests anti-IDOR automáticos para todos los endpoints|§4.3|C-03|
|T-118|Anti-replay OTP con invalidación inmediata y with\_for\_update|§6.6|C-04|
|T-119|Formula injection protection en todos los exportadores|§16.7|C-08|
|T-120|Race condition mutex en ejecución de sorteo|§3.8|C-10|
|T-121|Backup automático diario de SQLite con verificación de integridad|§18|C-12|
|T-122|HTTP Security Headers — CSP, HSTS, X-Frame-Options en middleware|§19|C-07|

\---

## 10\. Criterios de Aceptación

|#|Criterio|Valida|Estado|
|-|-|-|-|
|CA-01|Dos tenants no pueden acceder a datos del otro bajo ningún escenario|SUPER\_ADMIN|⏳|
|CA-02|Onboarding crea tenant con catálogo vacío listo para CSV|TENANT\_ADMIN|⏳|
|CA-03|OTP llega por WhatsApp en menos de 60 segundos|CONSEJERO|⏳|
|CA-04|Consejero confirma OTP desde celular sin instalar nada|CONSEJERO|⏳|
|CA-05|Panel OTP actualiza progreso sin recargar cada 2s|TENANT\_ADMIN|⏳|
|CA-06|Sorteo bloqueado hasta 5 OTPs confirmados — sin excepción|CONSEJERO|⏳|
|CA-07|Snapshot de participantes fijo antes del primer OTP confirmado|Sistema|⏳|
|CA-08|Reproducir sorteo con mismo seed produce resultados idénticos|CONSEJERO|⏳|
|CA-09|Acta incluye nombres, cargos y hora OTP de los 5 consejeros|CONSEJERO|⏳|
|CA-10|Acta NO incluye correos ni WhatsApp de participantes|Ley 1581|⏳|
|CA-11|Vista pública residente accesible sin login con URL directa|RESIDENTE|⏳|
|CA-12|Seed visible en pantalla ≥40px durante y después del sorteo|CONSEJERO|⏳|
|CA-13|Log encadenado: cada entrada referencia hash de la anterior|Sistema|⏳|
|CA-14|Piloto Aliso Vivienda ejecutado sin errores en Cloud|Piloto|⏳|
|CA-15|Primer cliente externo: sorteo ejecutado y acta entregada|Negocio|⏳|
|CA-16|Parser inteligente identifica catálogo de Aliso Vivienda sin configuración|Parser IA|⏳|
|CA-17|Resultado de exportación tiene ganadores, no asignados y log de auditoría|Exportación|⏳|
|CA-18|Sin catálogo cargado el sistema bloquea el sorteo con mensaje claro|Sistema|⏳|
|CA-19|Test anti-IDOR confirma que tenant A no accede a datos de tenant B|T-117|⏳|
|CA-20|OTP ya confirmado retorna 400 en reintento — single-use estricto|T-118|⏳|
|CA-21|Celda Excel con '=CMD' se exporta como texto sin ejecución|T-119|⏳|
|CA-22|Doble clic en Ejecutar sorteo no produce doble ejecución|T-120|⏳|
|CA-23|Backup diario ejecuta y pasa integrity\_check automático|T-121|⏳|
|CA-24|Todas las respuestas HTTP incluyen CSP y HSTS verificables|T-122|⏳|

\---

## 11\. Fuera de Alcance — v1.6



Los siguientes elementos quedan explícitamente fuera del alcance de esta versión:

* Pasarela de pagos automática — v1.0 usa transferencia manual o pago previo.
* App móvil nativa (iOS / Android) — v1.0 es web responsiva.
* Parqueaderos de visitantes — fuera del alcance heredado del v1.4.3.
* Parqueadero anteriormente asignado al participante.
* Asignación permanente por discapacidad — queda por fuera del sorteo general.
* Integración con software contable o de administración de propiedad horizontal.
* Dashboard de analytics avanzados para el TENANT\_ADMIN.
* Soporte multiidioma.


### Roadmap v2.0 — Hallazgos AppSec diferidos

Los siguientes hallazgos son válidos pero se difieren a v2.0 por complejidad de implementación vs. riesgo en el volumen actual:

| ID | Hallazgo | Por qué se difiere |
|---|---|---|
| H-04 | Log de auditoría firmado con Ed25519 o S3 Object Lock | Infraestructura adicional — el hash encadenado en DB es suficiente para el piloto |
| M-02 | CSRF para rutas `/sorteos/` | Las cookies de tenant no existen en v1.5 |
| M-03 | CI/CD completo con `gitleaks`, `pip-audit`, `checkov` | Se agrega progresivamente en cada sprint |
| L-01 | Política de retención y borrado criptográfico | Requiere definición legal con asesor |
| L-02 | Headers de seguridad HSTS, CSP, X-Frame-Options | Se configura en Railway como middleware |
| L-03 | `datetime.utcnow()` → `datetime.now(timezone.utc)` | Refactor simple — se hace en v1.5 junto con los demás cambios |
| L-04 | Rate limiting en vista pública `/p/{tenant_slug}/` | Baja prioridad hasta tener tráfico real |


### Roadmap v2.0 — escala — cuando se superen los umbrales

Los siguientes elementos se activan en v1.5 al superar los umbrales definidos en §3.6:

* **PostgreSQL** — reemplaza SQLite cuando supere 50 tenants o 10 sorteos/día
* **Redis** — reemplaza almacén en memoria para sesiones y rate limiting
* **Múltiples workers** — gunicorn multiprocess con sesiones compartidas
* **2FA / TOTP** — segundo factor para SUPER\_ADMIN
* **Múltiples usuarios SUPER\_ADMIN** — roles y permisos granulares

\---

## 12\. Seguridad

### 12.1 Principios de seguridad

SorteoParking maneja datos personales de residentes colombianos bajo **Ley 1581/2012 (Habeas Data)** y ejecuta actos con valor legal ante impugnaciones. La seguridad no es opcional — es parte del producto.

Tres principios no negociables:

1. **Aislamiento total entre tenants** — ningún dato de un conjunto es accesible desde otro bajo ninguna circunstancia.
2. **Integridad del protocolo OTP** — el sorteo no puede ejecutarse sin los 5 OTPs confirmados, sin excepción.
3. **Privacidad de datos personales** — WhatsApp y correos de participantes nunca aparecen en logs, actas ni respuestas de API.

### 12.2 Herramientas de revisión de seguridad

|Herramienta|Tipo|Cuándo corre|Costo|
|-|-|-|-|
|CodeQL|Análisis estático automático|Cada PR y lunes semanal|Gratuito|
|Claude Security Review|Revisión semántica con IA|Cada PR (cuando API key activa)|\~$5-15 USD/mes|
|`security-review.md`|Revisión manual en Cursor|Por demanda del desarrollador|Sin costo adicional|

### 12.3 Archivos de seguridad en el repositorio

```
sorteoparking/
├── .claude/
│   └── commands/
│       └── security-review.md      ← revisión manual en Cursor
├── .github/
│   └── workflows/
│       ├── codeql.yml              ← activo desde día 1, gratuito
│       └── claude-security-review.yml  ← activo cuando API key disponible
```

### 12.4 Vulnerabilidades críticas específicas del proyecto

Las siguientes vulnerabilidades son **P1 — Crítico** por la naturaleza del sistema:

|Vulnerabilidad|Por qué es crítica en SorteoParking|
|-|-|
|Query sin `tenant\_id`|Expone datos de todos los conjuntos a cualquier tenant|
|OTP en logs o errores|Permite ejecutar sorteo fraudulento suplantando consejero|
|Bypass de 5 OTPs|Invalida el acta ante impugnación legal|
|Seed predecible|Permite manipular el resultado antes de ejecutar|
|Snapshot modificable post-OTP|Altera participantes después de que los consejeros garantizaron|
|Secrets hardcodeados|Expone acceso total al sistema en repositorio público|
|UUID SUPER\_ADMIN expuesto en cliente|Permite acceso administrativo total desde el navegador|

### 12.5 Reglas de seguridad para desarrollo

Estas reglas aplican a todo el código de SorteoParking sin excepción:

* `tenant\_id` obligatorio en toda query — validado por middleware, no por el desarrollador caso a caso.
* OTPs generados con `secrets.token\_hex()` — nunca con `random()`.
* Seed derivado de `SHA-256(timestamp\_utc + hash\_snapshot)` — nunca predecible.
* Variables sensibles solo en variables de entorno — nunca en código fuente.
* Stack traces solo en logs internos — nunca retornados al cliente.
* Tokens de autenticación solo en headers `Authorization` — nunca en query params.
* `datetime.utcnow()` siempre — nunca `datetime.now()` para consistencia en Cloud.
* `SUPER\_ADMIN\_TOKEN` nunca retornado al cliente — vive solo en memoria del servidor.
* Comparaciones de tokens siempre con `hmac.compare\_digest()` — nunca con `==`.
* Cookies administrativas siempre con `HttpOnly=True`, `Secure=True`, `SameSite=Strict`.

### 12.6 Flujo de trabajo con seguridad integrada

```
Desarrollador escribe código T-XXX
        ↓
Cursor: @security-review.md revisa los cambios
        ↓
Commit → Pull Request en GitHub
        ↓
CodeQL corre automático (gratuito)
        ↓
Claude Security Review corre automático (cuando API key activa)
        ↓
Hallazgos comentados en líneas específicas del PR
        ↓
Corrección antes de merge a main
```

### 12.7 Criterios de aceptación de seguridad

|#|Criterio|Herramienta|Estado|
|-|-|-|-|
|CS-01|CodeQL activo en el repositorio sin hallazgos críticos|CodeQL|⏳|
|CS-02|Ningún secret hardcodeado en ningún archivo commiteado|CodeQL · Claude|⏳|
|CS-03|Todo endpoint validado con tenant\_id correcto en middleware|Claude · Manual|⏳|
|CS-04|OTP no aparece en logs ni en respuestas de error|Claude · Manual|⏳|
|CS-05|Piloto ejecutado sin hallazgos P1 o P2 abiertos|Claude · Manual|⏳|
|CS-06|SUPER\_ADMIN\_TOKEN nunca visible en cliente ni en logs|CodeQL · Manual|⏳|
|CS-07|Login administrativo bloqueado tras 5 intentos fallidos|Manual|⏳|

\---

## 13\. Autenticación Administrativa SUPER\_ADMIN

### 13.1 Problema que resuelve

El `SUPER\_ADMIN\_TOKEN` (UUID) no debe ser visible en ningún momento en el cliente. Exponerlo en un campo de formulario, query param o respuesta de API representa una vulnerabilidad crítica que permite acceso administrativo total al sistema desde el navegador.

### 13.2 Arquitectura de enmascaramiento

El sistema implementa un flujo de login con sesión mediada por el servidor. El UUID real nunca sale del contexto del servidor.

```
superadmin.html
    ↓ usuario + contraseña
POST /auth/login/superadmin
    ↓ verifica credenciales con Argon2id
    ↓ genera session\_id opaco (secrets.token\_urlsafe(32))
    ↓ mapea session\_id → SUPER\_ADMIN\_TOKEN en memoria
    ↓ Set-Cookie: admin\_session={session\_id} HttpOnly Secure SameSite=Strict
dashboard.html (autenticado)
    ↓ todas las llamadas a /admin/ usan la cookie
    ↓ middleware resuelve session\_id → UUID internamente
    ↓ el UUID nunca aparece en el navegador
```

### 13.3 Componentes requeridos

|Componente|Archivo|Responsabilidad|
|-|-|-|
|Pantalla de login|`frontend/superadmin.html`|Formulario usuario + contraseña — sin campos UUID|
|Endpoint de login|`POST /auth/login/superadmin`|Verifica credenciales, genera sesión, set cookie|
|Almacén de sesiones|`app/core/session\_store.py`|**SQLite** tabla `admin_sessions` — Redis se activa en v2.0 al superar 50 tenants activos|
|Middleware admin|`app/core/security.py`|Resuelve cookie → UUID antes de cada request a /admin/|
|Hash de contraseña|Argon2id|`argon2-cffi` — nunca Bcrypt ni MD5|

### 13.4 Especificación del endpoint de login

```
POST /auth/login/superadmin
Content-Type: application/json

Body:
{
  "username": "string (4-50 chars)",
  "password": "string"
}

Respuesta exitosa: HTTP 204 No Content
Set-Cookie: admin\_session={session\_id}; HttpOnly; Secure; SameSite=Strict; Max-Age=1800; Path=/admin

Respuesta fallida: HTTP 401
{"detail": "Credenciales administrativas inválidas"}
```

### 13.5 Parámetros de seguridad

|Parámetro|Valor|Justificación|
|-|-|-|
|Algoritmo hash|Argon2id|Resistencia GPU — estándar 2026|
|Memoria Argon2id|64 MB (`m=65536`)|Costo prohibitivo para ataques paralelos|
|Iteraciones Argon2id|3 (`t=3`)|Balance seguridad / tiempo de respuesta|
|Paralelismo Argon2id|4 (`p=4`)|Aprovecha múltiples núcleos del servidor|
|Tiempo objetivo login|200ms — 500ms|UX aceptable + resistencia a fuerza bruta|
|Duración de sesión|1800 segundos (30 min)|Ventana de ataque mínima|
|Rate limiting|5 intentos / 15 min por IP|Prevención de fuerza bruta|
|Comparación de tokens|`hmac.compare\_digest()`|Prevención de timing attacks|

### 13.6 Atributos de cookie obligatorios

```python
response.set\_cookie(
    key="admin\_session",
    value=session\_id,
    httponly=True,        # Inaccesible desde JavaScript
    secure=True,          # Solo HTTPS
    samesite="strict",    # Previene CSRF
    max\_age=1800,         # 30 minutos
    path="/admin"         # Solo rutas administrativas
)
```

### 13.7 Protección CSRF — patrón doble envío de cookie

Para mutaciones (`POST`, `PUT`, `DELETE`) en rutas `/admin/`:

1. Al login, generar un token CSRF adicional.
2. Enviarlo como cookie estándar (legible por JS): `csrf\_token`.
3. El frontend lo incluye en header `X-CSRF-Token` en cada mutación.
4. El servidor valida que cookie y header coincidan con `hmac.compare\_digest()`.

### 13.8 Variables de entorno requeridas

```
SUPER\_ADMIN\_USER=admin
SUPER\_ADMIN\_PASSWORD\_HASH=<hash Argon2id generado por create\_superadmin.py>
SUPER\_ADMIN\_TOKEN=<UUID generado por create\_superadmin.py>
```

> El `SUPER\_ADMIN\_PASSWORD\_HASH` se genera con:
> `python -m app.scripts.create\_superadmin --descripcion "admin inicial"`

### 13.9 Fuera de alcance en T-107

* Redis como almacén de sesiones — v1.4 usa diccionario en memoria. **Redis se activará en v1.5 cuando se superen 50 tenants activos concurrentes o 10 sorteos simultáneos.** Hasta ese umbral el diccionario en memoria es suficiente y más simple de operar.
* Múltiples usuarios SUPER\_ADMIN — v1.4 tiene un único administrador.
* 2FA / TOTP — roadmap v1.5.


### 13.11 Almacén de sesiones — SQLite en v1.5

En v1.4 las sesiones vivían en un diccionario en memoria — se perdían en cada reinicio o redeploy de Railway. En v1.5 las sesiones se persisten en SQLite.

**Tabla `admin_sessions`:**

```sql
CREATE TABLE admin_sessions (
    session_id    TEXT PRIMARY KEY,
    token_hash    TEXT NOT NULL,
    csrf_token    TEXT NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at    DATETIME NOT NULL,
    revoked_at    DATETIME
);
```

**Por qué `token_hash` y no el token directamente:**
El `SUPER_ADMIN_TOKEN` (UUID) nunca se almacena en texto plano en la DB — se guarda su SHA-256. Si la DB se compromete, el token no se puede recuperar.

**Limpieza automática:**
Al arrancar y cada 30 minutos, el sistema ejecuta:
```sql
DELETE FROM admin_sessions 
WHERE expires_at < CURRENT_TIMESTAMP 
   OR revoked_at IS NOT NULL;
```

**Impacto en Railway:**
Los reinicios ya no invalidan sesiones. El admin no necesita re-autenticarse en cada deploy.

### 13.10 Criterios de aceptación T-107

|#|Criterio|Estado|
|-|-|-|
|CA-T107-01|`superadmin.html` no contiene ningún campo UUID ni token visible|⏳|
|CA-T107-02|Login exitoso establece cookie HttpOnly — no retorna token en body|⏳|
|CA-T107-03|Login fallido retorna 401 en tiempo constante (±50ms)|⏳|
|CA-T107-04|Más de 5 intentos fallidos bloquean la IP por 15 minutos|⏳|
|CA-T107-05|El UUID nunca aparece en logs, responses ni headers de cliente|⏳|
|CA-T107-06|Sesión expira a los 30 minutos — requiere re-autenticación|⏳|
|CA-T107-07|Rutas `/admin/` retornan 403 sin cookie válida|⏳|

\---


---

## 14. Integración con DeepSeek Flash — Parser Inteligente de Excel

### 14.1 Por qué se eligió DeepSeek Flash

SorteoParking recibe Excels de conjuntos residenciales construidos sin ningún estándar — títulos decorativos, columnas con nombres arbitrarios, filas de totales, datos mezclados. Un parser con diccionario de sinónimos fijo no puede cubrir todos los casos posibles.

DeepSeek Flash (`deepseek-chat`) resuelve esto con análisis semántico real:
- Costo marginal por análisis — prácticamente cero
- Latencia menor a 2 segundos por archivo
- No requiere el modelo Pro para esta tarea — Flash es suficiente
- Compatible con la API de OpenAI — fácil de reemplazar si es necesario
- Sin riesgo de alucinación en datos reales — la IA solo analiza encabezados, Python lee los datos

### 14.2 Arquitectura de dos fases — principio fundamental

**La IA nunca toca los datos reales. Solo interpreta la estructura.**

```
Fase 1 — IA analiza la estructura (encabezados + 5 filas de muestra):
  Entrada → nombres de columnas + muestra de datos
  Salida  → mapa de columnas + reglas de limpieza + advertencias

Fase 2 — Python lee todos los datos con ese mapa:
  Sin IA. Sin latencia adicional. Sin riesgo de alucinación.
  Transformación determinista fila por fila.
  Cada fila ignorada queda registrada con su razón.
```

Este diseño garantiza que ningún dato se pierde ni se inventa.

### 14.3 Flujo completo del parser inteligente

```
Usuario sube cualquier Excel (.xlsx, .xls, .csv)
        ↓
Python (openpyxl / pandas):
  - Lee el archivo
  - Extrae nombres de columnas
  - Extrae primeras 5 filas de datos como muestra
  - Cuenta total de filas
        ↓
DeepSeek Flash recibe:
  - Nombres de columnas
  - Muestra de 5 filas
  - Tipo de carga: "catalogo_parqueaderos" | "elegibles_sorteo"
        ↓
DeepSeek Flash devuelve JSON:
  {
    "mapa_columnas": {
      "Bloque": "zona",
      "Puesto": "numero_parqueadero",
      "Auto": "tipo_vehiculo",
      "Piso-Apto": "apartamento"
    },
    "reglas_limpieza": {
      "zona": "extraer letra después de 'Zona '",
      "numero_parqueadero": "conservar tal cual",
      "tipo_vehiculo": "normalizar: carro→CARRO, moto→MOTO"
    },
    "patrones_ignorar": [
      "fila donde numero empieza con TOTAL",
      "fila completamente vacía",
      "fila donde tipo_vehiculo no es CARRO ni MOTO"
    ],
    "confianza": 0.95,
    "campos_obligatorios_encontrados": ["zona", "numero_parqueadero", "tipo_vehiculo"],
    "campos_obligatorios_faltantes": [],
    "advertencias": ["columna 'X' no identificada — se ignorará"]
  }
        ↓
Python valida el JSON de DeepSeek:
  - ¿Tiene todos los campos obligatorios?
  - ¿La confianza es >= 0.80?
        ↓
Si confianza >= 0.80 → procesar automático
Si confianza < 0.80 → retornar HTTP 422 con detalle
  de qué columnas no se pudieron identificar
        ↓
Python lee TODAS las filas aplicando el mapa:
  - Fila vacía → ignorar + registrar
  - Patrón de ignorar detectado → ignorar + registrar
  - Dato inválido → ignorar + registrar con razón
  - Dato válido → insertar en base de datos
        ↓
Resultado final al usuario:
  {
    "insertados": 96,
    "ignorados": 3,
    "detalle_ignorados": [
      {"fila": 2, "razon": "TOTAL ELEGIBLES CARRO"},
      {"fila": 45, "razon": "fila vacía"},
      {"fila": 67, "razon": "tipo_vehiculo inválido: 'BICICLETA'"}
    ],
    "advertencias": ["columna 'X' ignorada"],
    "resumen": {
      "carros": 72,
      "motos": 24,
      "zonas_detectadas": ["Zona A", "Zona B", "Zona C", "Zona D"],
      "confianza_analisis": 0.95
    }
  }
```


### 14.3b Sanitización estructural antes de llamar a DeepSeek — obligatorio por Ley 1581/2012

Enviar datos reales de residentes colombianos a una API externa viola la Ley 1581/2012 (Habeas Data).

**v1.4 DEPRECADO — sanitización heurística:**
La función `sanitizar_muestra()` basada en `es_nombre()`, `es_documento()` falla con nombres compuestos, cédulas extranjeras o campos mal formateados. **No usar.**

**v1.5 VIGENTE — sanitización estructural por tipo de dato:**

Cada celda se reemplaza por su tipo inferido por pandas. La IA recibe solo estructura — nunca contenido real. No depende de heurísticas, no falla con variaciones de formato.

```python
import pandas as pd

def sanitizar_muestra_estructural(df_muestra: pd.DataFrame) -> list[dict]:
    """
    Reemplaza cada valor por su tipo de dato inferido.
    La IA recibe solo estructura — nunca contenido real.
    Cumplimiento Ley 1581/2012 garantizado sin heurísticas.
    """
    resultado = []
    for _, fila in df_muestra.iterrows():
        fila_sanitizada = {}
        for col, valor in fila.items():
            if pd.isna(valor):
                fila_sanitizada[col] = "[VACIO]"
            elif isinstance(valor, bool):
                fila_sanitizada[col] = "[BOOL]"
            elif isinstance(valor, (int, float)):
                fila_sanitizada[col] = "[NUMERO]"
            elif isinstance(valor, pd.Timestamp):
                fila_sanitizada[col] = "[FECHA]"
            else:
                fila_sanitizada[col] = "[TEXTO]"
        resultado.append(fila_sanitizada)
    return resultado
```

**Ejemplo de transformación:**

| Columna | Valor real | Enviado a DeepSeek |
|---|---|---|
| nombre | "María García López" | `[TEXTO]` |
| apto | "T01-101" | `[TEXTO]` |
| documento | 52847291 | `[NUMERO]` |
| whatsapp | "3132054894" | `[TEXTO]` |
| vehiculo | "CARRO" | `[TEXTO]` |
| zona | "A" | `[TEXTO]` |
| numero | "P-001" | `[TEXTO]` |
| disponible | True | `[BOOL]` |

La IA identifica columnas por tipo y posición. Cero PII enviada.

**Este paso es obligatorio, no negociable y no puede desactivarse bajo ninguna circunstancia.**

### 14.4 Prompt del sistema para DeepSeek Flash

El prompt que se envía a DeepSeek varía según el tipo de carga:

**Para catálogo de parqueaderos:**
```
Eres un analizador de estructuras de Excel para el sistema 
SorteoParking. Analiza los encabezados y la muestra de datos 
proporcionados y devuelve SOLO un JSON válido con el mapa de 
columnas para un catálogo de parqueaderos.

Campos obligatorios a identificar:
- numero_parqueadero: identificador único del parqueadero (P-001, C001, etc.)
- tipo_vehiculo: CARRO o MOTO (puede estar en variantes)
- zona: sector geográfico del conjunto (A, B, C, D o nombres completos)

Campos opcionales:
- torre: número o nombre de la torre
- tipo_espacio: SENCILLO, DOBLE, TANDEM, CUBIERTO, DESCUBIERTO
- disponible: true/false
- vecino: número del parqueadero adyacente (para dobles)

Responde ÚNICAMENTE con el JSON especificado. Sin explicaciones.
```

**Para Excel de elegibles:**
```
Eres un analizador de estructuras de Excel para el sistema 
SorteoParking. Analiza los encabezados y la muestra de datos 
y devuelve SOLO un JSON válido con el mapa de columnas para 
una lista de participantes elegibles al sorteo.

Campos obligatorios a identificar:
- apartamento: identificador del apartamento (T01-101, 101, etc.)
- tipo_vehiculo: CARRO o MOTO

Campos opcionales:
- nombre: nombre del residente
- documento: número de identificación
- email: correo electrónico
- whatsapp: número de WhatsApp
- es_hatchback: true/false (para carros pequeños)

Responde ÚNICAMENTE con el JSON especificado. Sin explicaciones.
```

### 14.5 Manejo de errores de la API

| Escenario | Comportamiento |
|---|---|
| DeepSeek no disponible | Fallback a parser con sinónimos básicos |
| Respuesta no es JSON válido | Reintentar una vez — si falla: HTTP 422 |
| Confianza < 0.80 | HTTP 422 con detalle de columnas no identificadas |
| Timeout > 10 segundos | Fallback a parser con sinónimos básicos |
| API key inválida | HTTP 500 con log interno — nunca exponer key al cliente |

### 14.6 Variables de entorno requeridas

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TIMEOUT=10
DEEPSEEK_MIN_CONFIDENCE=0.80
```

### 14.7 Componente en el proyecto

```
app/services/excel_parser.py     ← servicio principal del parser
app/services/deepseek_service.py ← cliente de la API de DeepSeek
app/core/config.py               ← DeepSeekConfig (nueva clase)
```



### 14.10 Límites de seguridad en carga de archivos

Los archivos `.xlsx` son ZIPs comprimidos. Un archivo malicioso (ZIP bomb) puede agotar memoria y CPU derribando el servidor para todos los tenants.

| Límite | Valor | Razón |
|---|---|---|
| Tamaño máximo | 5 MB | Suficiente para catálogos reales |
| Filas máximas | 50.000 | Ningún conjunto VIS tiene más |
| Timeout de parseo | 15 segundos | Abortar si el archivo es malicioso |
| Hojas máximas | 10 | Evitar iteración infinita |

```python
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 50_000
PARSE_TIMEOUT = 15  # segundos

async def validar_archivo(archivo: UploadFile) -> bytes:
    # Validar Content-Length antes de leer
    contenido = await archivo.read(MAX_FILE_SIZE + 1)
    if len(contenido) > MAX_FILE_SIZE:
        raise HTTPException(413, 
            "Archivo demasiado grande. Máximo 5 MB.")
    return contenido

def cargar_excel_seguro(contenido: bytes) -> pd.DataFrame:
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Parseo de Excel excedió 15 segundos")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(PARSE_TIMEOUT)
    
    try:
        df = pd.read_excel(
            io.BytesIO(contenido),
            nrows=MAX_ROWS,
            engine='openpyxl'
        )
        if len(df) >= MAX_ROWS:
            raise HTTPException(413, 
                f"El archivo excede {MAX_ROWS} filas.")
        return df
    except MemoryError:
        raise HTTPException(503, 
            "Archivo demasiado complejo para procesar.")
    finally:
        signal.alarm(0)
```

### 14.9 Rate limiting — SlowAPI en memoria

SorteoParking usa SlowAPI (ya instalado desde T-107) para rate limiting. En v1.4 el almacén es en memoria — suficiente para un solo worker.

| Endpoint | Límite | Almacén |
|---|---|---|
| POST /auth/login/superadmin | 5 intentos / 15 min por IP | Memoria |
| POST /catalogo/carga-csv | 10 cargas / hora por tenant | Memoria |
| POST /sorteos/carga-excel | 10 cargas / hora por tenant | Memoria |

**Trade-off documentado:** Con múltiples workers (gunicorn/uvicorn multiprocess) cada worker tiene su propio contador — un atacante podría hacer N intentos por worker. Este es un riesgo aceptable en v1.4 dado el volumen esperado de usuarios.

**En v1.5:** SlowAPI se configura con Redis como backend compartido entre workers, eliminando este trade-off.

```python
# v1.4 — memoria (aceptable para un worker)
limiter = Limiter(key_func=get_remote_address)

# v1.5 — Redis compartido entre workers
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)
```

### 14.8 Criterios de aceptación T-108

| # | Criterio | Estado |
|---|---|---|
| CA-T108-01 | El parser acepta .xlsx, .xls y .csv sin configuración adicional | ⏳ |
| CA-T108-02 | El parser identifica correctamente el catálogo maestro de Aliso Vivienda | ⏳ |
| CA-T108-03 | Filas de TOTAL y filas vacías nunca se insertan como datos válidos | ⏳ |
| CA-T108-04 | El resultado siempre incluye conteo de insertados e ignorados | ⏳ |
| CA-T108-05 | Con confianza < 0.80 el sistema retorna 422 con detalle — nunca inserta datos dudosos | ⏳ |
| CA-T108-06 | Si DeepSeek no está disponible el parser funciona con sinónimos básicos | ⏳ |
| CA-T108-07 | La API key de DeepSeek nunca aparece en logs ni responses | ⏳ |

---

## 15. Catálogo Maestro de Parqueaderos

### 15.1 Propósito

El catálogo maestro es la fuente de verdad de los parqueaderos disponibles en un conjunto. Define contra qué espacios el motor híbrido puede hacer asignaciones. Sin catálogo cargado el sorteo ejecuta pero produce cero resultados.

### 15.2 Cuándo se carga

- **Una vez** al incorporar un nuevo conjunto al servicio
- **Cuando cambia la infraestructura** — nuevos parqueaderos, cambios de zona
- El catálogo es idempotente — cargar el mismo archivo dos veces no duplica datos

### 15.3 Campos del catálogo

| Campo | Obligatorio | Descripción | Ejemplo |
|---|---|---|---|
| numero | ✅ | Identificador único del parqueadero | P-001, C001, M003 |
| tipo_vehiculo | ✅ | CARRO o MOTO | CARRO |
| zona | ✅ | Sector geográfico del conjunto | Zona A, A, Bloque Norte |
| tipo_espacio | ⬜ | SENCILLO, DOBLE, TANDEM | SENCILLO |
| torre | ⬜ | Torre o bloque asociado | 1, T01, Torre 3 |
| disponible | ⬜ | Si está habilitado para sorteo | true |
| vecino | ⬜ | Número del parqueadero adyacente (dobles) | P-002 |

### 15.4 Plantilla descargable — camino feliz

SorteoParking provee una plantilla Excel descargable con la estructura correcta. Los conjuntos que usan la plantilla no pasan por el parser inteligente — el sistema la lee directamente.

La plantilla está disponible en:
```
GET /catalogo/plantilla
```
Retorna: `SorteoParking_CATALOGO_MAESTRO_plantilla.xlsx`

### 15.5 Flujo en el dashboard

```
Paso 1 — Catálogo de parqueaderos (una vez por conjunto)
  ↓ Descargar plantilla (opcional)
  ↓ Subir archivo Excel o CSV
  ↓ Parser inteligente analiza la estructura (§14)
  ↓ Confirmación: "96 parqueaderos cargados — 4 zonas — 24 torres"

Paso 2 — Excel de elegibles (cada sorteo)
  ↓ Subir lista de participantes habilitados
  ↓ Parser inteligente analiza la estructura (§14)
  ↓ Confirmación: "28 elegibles cargados — 20 carros — 8 motos"

Paso 3 — Ejecutar sorteo
  ↓ Motor híbrido asigna parqueaderos del catálogo a elegibles
  ↓ Resultados con ganadores y no asignados
```

### 15.6 Endpoint actualizado

El endpoint `POST /catalogo/carga-csv` se actualiza para:
- Aceptar `.xlsx`, `.xls` y `.csv`
- Usar el parser inteligente con DeepSeek Flash (§14)
- Retornar siempre el resumen de insertados e ignorados
- Ser idempotente — no duplicar parqueaderos existentes

```
POST /catalogo/carga-csv
Authorization: Bearer {tenant_uuid}
Content-Type: multipart/form-data

Body: archivo (.xlsx | .xls | .csv)

Respuesta exitosa: HTTP 201
{
  "insertados": 96,
  "actualizados": 0,
  "ignorados": 3,
  "resumen": {
    "carros": 72,
    "motos": 24,
    "zonas": ["Zona A", "Zona B", "Zona C", "Zona D"],
    "torres": 24
  }
}

Respuesta con estructura no reconocida: HTTP 422
{
  "detail": "No se pudo identificar la estructura del archivo",
  "columnas_no_identificadas": ["X", "Y"],
  "confianza": 0.65,
  "sugerencia": "Use la plantilla descargable en GET /catalogo/plantilla"
}
```

### 15.7 Criterios de aceptación T-109

| # | Criterio | Estado |
|---|---|---|
| CA-T109-01 | Sin catálogo cargado el endpoint /sorteos/iniciar retorna 400 con mensaje claro | ⏳ |
| CA-T109-02 | El catálogo de Aliso Vivienda (96 parqueaderos) carga correctamente desde el dashboard | ⏳ |
| CA-T109-03 | Cargar el mismo catálogo dos veces no duplica parqueaderos | ⏳ |
| CA-T109-04 | El dashboard muestra el resumen de carga con conteos reales | ⏳ |
| CA-T109-05 | La plantilla descargable está disponible en GET /catalogo/plantilla | ⏳ |

---

## 16. Exportación de Resultados del Sorteo

### 16.1 Propósito

El acta del sorteo es el documento legal que protege al administrador ante impugnaciones. Debe contener toda la información necesaria para reproducir y verificar el sorteo de forma independiente.

### 16.2 Contenido obligatorio del acta

| Sección | Contenido |
|---|---|
| Encabezado | Nombre del conjunto, fecha, hora, tipo de sorteo |
| Consejeros garantes | Nombre, cargo y timestamp de confirmación OTP de cada uno de los 5 |
| Seed reproducible | Hash SHA-256 completo visible — permite verificación independiente |
| Resumen | Total participantes, ganadores, no asignados |
| Ganadores | Apartamento → parqueadero asignado, zona, tipo de vehículo |
| No asignados | Apartamento, tipo de vehículo, razón (pool agotado) |
| Log de auditoría | Cadena de hashes desde inicio hasta fin del evento |

### 16.3 Lo que el acta NO debe contener (Ley 1581/2012)

- Correos electrónicos de participantes
- Números de WhatsApp de participantes
- Números de documento de identidad
- Cualquier dato personal más allá de apartamento y tipo de vehículo

### 16.4 Formatos disponibles

| Formato | Endpoint | Uso recomendado |
|---|---|---|
| Excel (.xlsx) | POST /sorteos/{id}/exportar?formato=excel | Archivo de trabajo del administrador |
| Word (.docx) | POST /sorteos/{id}/exportar?formato=word | Acta formal para archivo |
| Vista pública | GET /p/{tenant_slug}/sorteos/{id} | Publicación a residentes sin login |

### 16.5 Hojas del Excel de resultados

| Hoja | Contenido |
|---|---|
| Resumen | Métricas del sorteo — totales, modelo aplicado, seed |
| Ganadores | Lista completa de asignaciones exitosas |
| No Asignados | Lista de participantes sin parqueadero asignado |
| Consejeros | Los 5 garantes con timestamps de confirmación |
| Log Auditoría | Cadena completa de eventos con hashes |


### 16.7 Protección contra Formula Injection en exportaciones (T-119)

Los archivos Excel y CSV exportados pueden contener datos controlados por usuarios (nombres de apartamentos, observaciones). Si un valor empieza con `=`, `+`, `-` o `@`, Excel lo interpreta como fórmula y puede ejecutar código.

```python
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')

def sanitizar_celda_excel(valor: str) -> str:
    """Previene Formula Injection en exportaciones Excel/CSV."""
    if not isinstance(valor, str):
        return valor
    if valor.startswith(FORMULA_PREFIXES):
        return "'" + valor  # Prefijo apóstrofo — Excel trata como texto
    return valor

def exportar_df_seguro(df: pd.DataFrame) -> pd.DataFrame:
    """Sanitiza todas las columnas de texto antes de exportar."""
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(
            lambda x: sanitizar_celda_excel(x) if isinstance(x, str) else x
        )
    return df
```

Aplicar en todos los exportadores: Excel y Word.

### 16.6 Criterios de aceptación T-110

| # | Criterio | Estado |
|---|---|---|
| CA-T110-01 | El Excel exportado tiene las 5 hojas especificadas con datos reales | ⏳ |
| CA-T110-02 | El acta incluye el seed completo en formato legible ≥ 40px | ⏳ |
| CA-T110-03 | El acta NO incluye emails ni WhatsApp de participantes | ⏳ |
| CA-T110-04 | Los 5 consejeros aparecen con nombre y timestamp exacto de confirmación | ⏳ |
| CA-T110-05 | Un tercero puede reproducir el sorteo usando el seed del acta | ⏳ |



---

## 17. Clasificación de Hallazgos AppSec — Auditoría OpenAI

### 17.1 Criterio de clasificación

Los 92 hallazgos de la auditoría AppSec se clasifican en tres categorías según el objetivo inmediato del producto:

| Categoría | Criterio | Cuándo |
|---|---|---|
| **A — Piloto Aliso julio 2026** | Pueden hacer fallar el sorteo o comprometer su validez legal | Antes del sorteo de julio |
| **B — Primer cliente externo** | Deben estar antes de cobrarle a alguien más | Después de Aliso, antes de escalar |
| **C — v2.0** | Infraestructura de empresa mediana — correctos pero prematuros | Roadmap futuro |

### 17.2 Categoría A — Críticos para el sorteo de Aliso (julio 2026)

Estos seis hallazgos pueden invalidar el acta, comprometer la integridad del sorteo o perder datos irreversiblemente.

| ID OpenAI | Hallazgo | Impacto en Aliso | Tarea |
|---|---|---|---|
| C-03 | IDOR multi-tenant — query sin tenant_id | Una query olvidada expone datos cross-tenant — invalida el acta legalmente | T-117 |
| C-04 | Replay de OTP — sin invalidación inmediata | Un consejero puede confirmar dos veces — el acta pierde validez ante impugnación | T-118 |
| C-08 | Formula injection en Excel exportado | Datos de Aliso en el acta pueden ejecutar código en el PC del administrador | T-119 |
| C-10 | Race conditions en ejecución de sorteo | Doble ejecución produce resultados inconsistentes — acta inválida | T-120 |
| C-12 | Sin backup de la base de datos | Si se pierde la DB antes del sorteo, se pierde todo — sin recuperación | T-121 |
| C-07 | Sin CSP/HSTS/X-Frame-Options | Panel admin vulnerable a XSS y clickjacking durante el sorteo en vivo | T-122 |

### 17.3 Categoría B — Críticos antes del primer cliente externo

Estos hallazgos son inaceptables en un SaaS multi-tenant comercial pero no bloquean el piloto interno de Aliso.

| ID OpenAI | Hallazgo | Por qué se difiere |
|---|---|---|
| C-01 | UUID Bearer permanente como token de tenant | El piloto de Aliso es interno — el UUID no se expone en Internet |
| C-02 | Sin autenticación real de usuario TENANT_ADMIN | Aliso tiene un solo administrador conocido |
| C-05 | Vista pública permite enumeración | Aliso no tiene tráfico externo significativo |
| C-06 | SQLite vulnerable a DoS bajo carga | Aliso hace 2 sorteos al año — concurrencia mínima |
| C-09 | Sin protección XSS formal en frontend | Se mitiga parcialmente con CSP en T-122 |
| C-11 | DeepSeek supply-chain sin DPA | Se documenta el riesgo — no bloquea el piloto |
| H-01 a H-21 | Hallazgos altos varios | Se priorizan según calendario post-Aliso |

### 17.4 Categoría C — Roadmap v2.0

Infraestructura correcta para una empresa mediana. Prematura para el volumen actual.

- WAF (Cloudflare)
- Redis cluster
- PostgreSQL HA con réplicas
- MFA para SUPER_ADMIN
- Firma digital de actas con PKI
- SBOM CycloneDX
- Container hardening
- DAST con OWASP ZAP
- Pentest externo
- SIEM y observabilidad
- Secrets Manager (HashiCorp Vault / AWS)
- RBAC granular multi-usuario
- Device binding para OTP

### 17.5 Criterio de graduación entre categorías

Un hallazgo pasa de Categoría B a Categoría A cuando:
- Hay un cliente externo pagando
- El sistema procesa datos de conjuntos que no son Aliso Vivienda
- El volumen supera 10 sorteos simultáneos

Un hallazgo pasa de Categoría C a Categoría B cuando:
- El sistema supera 50 tenants activos
- Hay ingresos recurrentes que justifican la infraestructura



---

## 18. Estrategia de Backup — Protección de Datos del Sorteo (T-121)

### 18.1 Riesgo sin backup

Sin backup, la pérdida de `sorteoparking.db` significa:
- Pérdida irreversible de todas las actas
- Pérdida del log de auditoría
- Imposibilidad de defender impugnaciones
- Pérdida de todos los tenants y catálogos

### 18.2 Estrategia para v1.6 (Railway)

Railway persiste el filesystem entre reinicios normales pero NO garantiza durabilidad ante fallos de hardware o migraciones de infraestructura.

**Backup automático diario:**

```python
# app/scripts/backup_db.py
import shutil
import os
from datetime import datetime
import boto3  # o httpx para Railway Volume

def backup_sqlite():
    """Copia la DB a storage externo diariamente."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = f"/tmp/sorteoparking_backup_{timestamp}.db"

    # Usar SQLite backup API — consistente incluso con WAL activo
    import sqlite3
    src = sqlite3.connect("sorteoparking.db")
    dst = sqlite3.connect(backup_path)
    src.backup(dst)
    dst.close()
    src.close()

    # Subir a Railway Volume o S3
    # En v1.6: copiar a directorio Railway Volume montado
    shutil.copy(backup_path, f"/data/backups/sorteoparking_{timestamp}.db")

    # Retener solo los últimos 30 backups
    limpiar_backups_antiguos("/data/backups/", retener=30)
```

**Variables de entorno requeridas:**
```
BACKUP_DIR=/data/backups
BACKUP_RETENTION_DAYS=30
```

**Frecuencia:**
- Backup diario automático via `@app.on_event("startup")` + scheduler
- Backup manual antes de cada sorteo ejecutado

### 18.3 Verificación de integridad del backup

```python
def verificar_backup(path: str) -> bool:
    """Verifica que el backup es una DB SQLite válida y legible."""
    try:
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA integrity_check")
        conn.execute("SELECT COUNT(*) FROM tenants")
        conn.close()
        return True
    except Exception:
        return False
```

### 18.4 Criterios de aceptación T-121

| # | Criterio | Estado |
|---|---|---|
| CA-T121-01 | Backup automático diario ejecuta sin errores | ⏳ |
| CA-T121-02 | El backup es legible y pasa integrity_check | ⏳ |
| CA-T121-03 | Se ejecuta backup manual antes del sorteo de Aliso | ⏳ |
| CA-T121-04 | Los últimos 30 backups se conservan y los anteriores se purgan | ⏳ |


---

## 19. HTTP Security Headers — CSP, HSTS, XFO (T-122)

### 19.1 Por qué es crítico para el sorteo en vivo

Durante el sorteo, el panel del TENANT_ADMIN está abierto en el navegador por 30-60 minutos. Sin headers de seguridad, un ataque XSS o clickjacking puede manipular la sesión en tiempo real — invalidando el acta.

### 19.2 Headers obligatorios en v1.6

```python
# app/core/security_headers.py
from fastapi import Request
from fastapi.responses import Response

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cache-Control": "no-store, no-cache, must-revalidate",
}

# En main.py — middleware de headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
```

### 19.3 Excepción para vista pública

La vista pública `/p/{tenant_slug}/sorteos/{id}` puede cachearse:
```python
"Cache-Control": "public, max-age=300, stale-while-revalidate=60"
```

### 19.4 Criterios de aceptación T-122

| # | Criterio | Estado |
|---|---|---|
| CA-T122-01 | Todas las respuestas incluyen HSTS, XFO y CSP | ⏳ |
| CA-T122-02 | El panel admin no puede cargarse en un iframe | ⏳ |
| CA-T122-03 | CSP bloquea scripts externos no autorizados | ⏳ |
| CA-T122-04 | Vista pública tiene Cache-Control apropiado | ⏳ |


## Control de Cambios

|Versión|Fecha|Cambios|Autor|
|-|-|-|-|
|1.0|Abril 2026|Versión inicial — migración a servicio multi-tenant Cloud|Michael López|
|1.1|Mayo 2026|Agregada §12 Seguridad — CodeQL, Claude Security Review, reglas y criterios|Michael López|
|1.2|Mayo 2026|Agregada §13 Autenticación Administrativa — T-107 login seguro SUPER\_ADMIN con Argon2id y cookies HttpOnly|Michael López|
|1.3|Mayo 2026|Agregadas §14 Parser Inteligente DeepSeek Flash · §15 Catálogo Maestro · §16 Exportación de Resultados · T-108/109/110|Michael López|
|1.4|Mayo 2026|Correcciones arquitectónicas: copy-paste §1.2 · contradicción Redis §13 · nota migración SQLite→PostgreSQL §3.6 · sanitización PII §14.3b · rate limiting §14.9|Michael López|
|1.6|Mayo 2026|Hardening crítico piloto Aliso — §4.3 IDOR · §6.6 anti-replay OTP · §3.8 race conditions · §16.7 formula injection · §18 backup strategy · §19 HTTP security headers · §17 clasificación hallazgos AppSec · T-117 a T-122|Michael López|
|1.5|Mayo 2026|Auditoría AppSec: C-01 §3.7 contrato token · C-02 §13.11 sesiones SQLite · C-03 §14.3b sanitización estructural · H-01 §6.4 OTP seguro · H-02 §6.5 snapshot inmutable · H-03 §3.6 timeouts SQLAlchemy · M-01 §14.10 ZIP bomb · T-111 a T-116 · Roadmap v2.0|Michael López|

\---

*SorteoParking © 2026 · Documento confidencial · Todos los derechos reservados*

### 4.3 Protección IDOR — tenant-scoped queries obligatorias (T-117)

El IDOR (Insecure Direct Object Reference) multi-tenant es el fallo más común en SaaS. Basta una query sin `tenant_id` para exponer datos de otro conjunto.

**Regla absoluta:** toda query a la DB debe incluir `tenant_id`. Sin excepción.

**Patrón correcto:**
```python
# ✅ CORRECTO — siempre con tenant_id
sorteo = db.query(Sorteo).filter(
    Sorteo.id == sorteo_id,
    Sorteo.tenant_id == tenant_id  # OBLIGATORIO
).first()

# ❌ INCORRECTO — expone datos cross-tenant
sorteo = db.query(Sorteo).filter(
    Sorteo.id == sorteo_id
).first()
```

**Test automático anti-IDOR obligatorio (T-117):**
```python
def test_idor_sorteo():
    """Verifica que un tenant no puede acceder a sorteos de otro."""
    tenant_a = crear_tenant_test("A")
    tenant_b = crear_tenant_test("B")
    sorteo_b = crear_sorteo_test(tenant_b.id)

    response = client.get(
        f"/sorteos/{sorteo_b.id}/estado",
        headers={"Authorization": f"Bearer {tenant_a.id}"}
    )
    assert response.status_code == 403
```

Este test debe ejecutarse en CI/CD para cada endpoint antes de merge a main.


