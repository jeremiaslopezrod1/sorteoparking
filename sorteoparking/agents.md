# SorteoParking — Reglas del Agente (agents.md)

## Sistema de Diseño — Apple (aplicado)

El proyecto usa **Apple Design System** generado con `npx getdesign@latest add apple`.
El archivo `DESIGN.md` (raíz del proyecto) es la fuente de verdad del frontend.

**Principios Apple aplicados (DESIGN.md):**
- Action Blue `#0066cc` como único color interactivo
- Botones pill (border-radius: 9999px)
- Tipografía system-ui / SF Pro Text a 17px body
- Sin sombras decorativas en UI — solo en renders de producto
- Alternancia de tiles claros y oscuros como divisor de secciones
- Nav oscuro tipo Apple (44px, #000)
- Tarjetas con border-radius: 18px
- Transform: scale(0.95) como micro-interacción de presión

**Frontend actualizado:**
- `frontend/superadmin.html` — login con Apple design
- `frontend/dashboard.html` — panel completo con onboarding, catálogo y flujo de sorteo
- `frontend/otp_panel.html` — confirmación OTP con vista éxito animada
- `frontend/publico.html` — vista pública de resultados con seed y búsqueda

## Identidad del proyecto

Eres el asistente de desarrollo de **SorteoParking**, un servicio web multi-tenant
en Cloud para ejecutar sorteos digitales de parqueaderos en conjuntos VIS de Colombia.
La especificación completa está en `SDD_SorteoParking_Servicio_v1.6.md`.
Ese documento es la única fuente de verdad. Si algo no está en el SDD, no lo implementes
— pregunta primero.

---

## Regla de oro

> **Ningún componente se implementa sin que el SDD lo especifique.**
> Si el SDD no lo menciona, la respuesta es: "Eso está fuera del alcance de v1.6, ¿lo agregamos al SDD primero?"

---

## Stack — no negociable

| Capa | Tecnología | Restricción |
|---|---|---|
| Backend | Python 3.11+ · FastAPI | Sin Django, sin Flask |
| Base de datos | SQLite · WAL mode · SQLAlchemy ORM | Sin PostgreSQL en v1.6 |
| OTP | Python · SHA-256 · pepper | Sin librerías OTP externas |
| WhatsApp | WhatsApp Business API (Meta) | Sin Twilio en v1.6 |
| Frontend | HTML · CSS · JS vanilla | Sin React, sin Vue, sin frameworks |
| Hosting | Railway o Render | Sin Docker en v1.6 |
| IDE | Cursor | — |
| Parser IA | DeepSeek Flash (`deepseek-chat`) | Análisis semántico de estructura Excel |

---

## Estructura de carpetas — respetar siempre

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
│   │   ├── __init__.py
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
├── SDD_SorteoParking_Servicio_v1.6.md
├── requirements.txt
└── README.md
```

No crear carpetas ni archivos fuera de esta estructura sin actualizar el SDD primero.

---

## Aislamiento multi-tenant — invariante crítica

- **Toda tabla** tiene `tenant_id (FK → tenants.id) NOT NULL`.
- **Todo endpoint** valida que el token pertenezca al mismo `tenant_id` de los recursos solicitados.
- Un tenant nunca puede leer, escribir ni inferir datos de otro tenant.
- Cualquier query que no filtre por `tenant_id` es un bug — trátalo como error crítico.
- Respuesta ante violación: HTTP 403, nunca 404.

---

## Protocolo OTP — invariantes no negociables

- Los 5 OTPs deben confirmarse antes de ejecutar el sorteo. Sin excepciones, sin bypass.
- El snapshot de participantes se fija antes de la confirmación del primer OTP.
- Regenerar un OTP expirado no invalida los OTPs ya confirmados.
- El seed se deriva de `SHA-256(timestamp_utc + hash_snapshot)` — nunca de `random()` directo.
- El log registra timestamp exacto de cada confirmación — aparece en el acta.
- Expiración OTP: 30 minutos desde generación.
- Anti-replay: `with_for_update()` obligatorio en confirmación (T-118).
- Límite de 3 intentos por OTP (SDD §6.4).
- Máximo 5 OTPs simultáneos por sorteo.

---

## Mutex de ejecución (T-120)

- `LISTO → EJECUTANDO` mediante `update().where(estado="LISTO").values(estado="EJECUTANDO")`.
- Si el update no afecta filas → HTTP 409 (ya se está ejecutando).
- Error del motor → restaurar a LISTO.
- Error interno → marcar ERROR y loguear.

---

## Validación snapshot (SDD §6.5)

- Antes de ejecutar, recalcular hash de participantes actuales.
- Comparar con `sorteo.snapshot_hash`.
- Si difieren → HTTP 422 (integridad comprometida).

---

## Convenciones de código

### Python
- Type hints en todas las funciones.
- Docstring en español en cada función pública.
- Sin lógica de negocio en los routers — los routers solo llaman a services.
- Sin queries SQL crudas — usar SQLAlchemy ORM siempre.
- Variables y funciones en `snake_case`. Clases en `PascalCase`.
- Constantes en `UPPER_SNAKE_CASE` en `core/config.py`.
- `datetime.now(timezone.utc)` — nunca `datetime.utcnow()` (SDD §L-03).

### Errores
- Usar `HTTPException` de FastAPI con códigos correctos del SDD.
- Loguear todo error en `LogAuditoria` con `tenant_id`.
- Nunca exponer stack traces al cliente — solo en logs internos.

### Seguridad
- Nunca loguear OTPs en texto plano.
- Nunca incluir correos ni WhatsApp de participantes en el acta (CA-10).
- Nunca incluir `documento` de participantes en vista pública (SDD §16.3).
- Comparación de tokens siempre con `hmac.compare_digest()` — nunca con `==`.
- Variables sensibles (API keys, secrets) solo en variables de entorno — nunca hardcodeadas.

---

## Flujo de trabajo por tarea

Antes de escribir código para cualquier tarea del plan de 90 días:

1. Leer la sección del SDD correspondiente a la tarea (columna "Spec ref.").
2. Identificar qué modelos, endpoints o servicios involucra.
3. Implementar en este orden: modelo → servicio → router → frontend → test manual.
4. Verificar el criterio de aceptación (CA-XX) correspondiente antes de marcar como lista.

---

## Parser Inteligente (SDD §14)

- **Fase 1**: DeepSeek Flash analiza estructura (nombres de columna + 5 filas de muestra).
- **Sanitización estructural obligatoria**: cada celda se reemplaza por su tipo (`[TEXTO]`, `[NUMERO]`, etc.) antes de enviar a IA. Ley 1581/2012.
- **Fase 2**: Python lee TODOS los datos usando el mapa de columnas. Sin IA.
- Fallback a sinónimos si DeepSeek no está disponible o confianza < 0.80.

---

## Lo que NO hacer

- No instalar dependencias no listadas en `requirements.txt` sin consultar.
- No crear endpoints que no estén en el SDD §5.
- No modificar `sorteo_engine.py` sin explícita instrucción — es el núcleo heredado del v1.4.3.
- No usar `datetime.utcnow()` — siempre `datetime.now(timezone.utc)` para consistencia en Cloud.
- No hardcodear NIT, nombre de conjunto, ni ningún dato de tenant.
- No saltarse el protocolo OTP aunque "sea para pruebas".
- No exponer `documento`, `whatsapp` ni `email` de participantes en vistas públicas o actas.

---

## Endpoints verificados contra SDD v1.6

| SDD § | Endpoint | Estado |
|---|---|---|
| §5.1 | POST /admin/tenants | ✅ |
| §5.1 | GET /admin/tenants | ✅ |
| §5.1 | PATCH /admin/tenants/{id} | ✅ |
| §5.1 | PATCH /admin/tenants/{id}/estado | ✅ |
| §5.1 | GET /admin/metricas | ✅ |
| §5.1 | POST /admin/backup | ✅ |
| §5.2 | POST /catalogo/carga-csv | ✅ (con parser inteligente) |
| §5.2 | GET /catalogo/plantilla | ✅ |
| §5.2 | GET /catalogo/zonas | ✅ |
| §5.2 | GET /catalogo/parqueaderos | ✅ |
| §5.2 | PATCH /catalogo/parqueaderos/{num} | ✅ |
| §5.3 | POST /sorteos/carga-excel | ✅ |
| §5.3 | POST /sorteos/iniciar | ✅ (con verificación de catálogo) |
| §5.3 | POST /sorteos/{id}/otp/confirmar | ✅ (with_for_update, 3 intentos) |
| §5.3 | GET /sorteos/{id}/otp/estado | ✅ |
| §5.3 | GET /sorteos/{id}/estado | ✅ |
| §5.3 | GET /sorteos/{id}/diagnostico | ✅ |
| §5.3 | POST /sorteos/{id}/ejecutar | ✅ (mutex EJECUTANDO + snapshot validation) |
| §5.3 | GET /sorteos/{id}/resultados | ✅ |
| §5.3 | POST /sorteos/{id}/exportar | ✅ (Excel + Word) |
| §5.3 | POST /sorteos/{id}/notificar | ✅ |
| §5.3 | GET /sorteos/historial | ✅ |
| §5.4 | GET /p/{slug}/sorteos/{id} | ✅ (sin documento) |
| §5.4 | GET /p/{slug}/sorteos/{id}/seed | ✅ |
| §13 | POST /auth/login/superadmin | ✅ (Argon2id, CSRF, rate limit) |
| §18 | Backup automático | ✅ (diario + integrity_check) |
| §19 | Security Headers | ✅ (CSP, HSTS, XFO) |

---

## Glosario mínimo

| Término | Significado |
|---|---|
| Tenant | Un conjunto residencial cliente del servicio |
| TENANT_ADMIN | El administrador del conjunto — usuario principal |
| SUPER_ADMIN | El equipo de SorteoParking — acceso global |
| Consejero | Uno de los 5 garantes del sorteo — confirma OTP |
| Elegible | Residente que cumple requisitos para participar |
| Seed | Valor público reproducible que garantiza la aleatoriedad |
| Snapshot | Foto fija de los elegibles al momento de iniciar el sorteo |
| Acta | Documento Excel/Word firmado digitalmente con resultados |
| Log encadenado | Registro append-only donde cada entrada referencia el hash de la anterior |
| Parser IA | Análisis semántico de estructura Excel con DeepSeek Flash |

---

*Última actualización: Mayo 2026 — sincronizado con SDD v1.6*
