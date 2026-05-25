# SorteoParking — Reglas del Agente (agents.md)

## Identidad del proyecto

Eres el asistente de desarrollo de **SorteoParking**, un servicio web multi-tenant
en Cloud para ejecutar sorteos digitales de parqueaderos en conjuntos VIS de Colombia.
La especificación completa está en `SDD_v2.1_SorteoParking.md`.
Ese documento es la única fuente de verdad. Si algo no está en el SDD, no lo implementes
— pregunta primero.

El diseño frontend sigue el **Apple Design System** definido en [`DESIGN.md`](DESIGN.md).
Todos los paneles HTML deben alinearse con: Action Blue #0066cc, botones pill,
SF Pro Text (system-ui), tarjetas 18px border-radius, nav oscuro 44px, diseño responsivo
mobile-first con breakpoints Apple.

---

## Regla de oro

> **Ningún componente se implementa sin que el SDD lo especifique.**
> Si el SDD no lo menciona, la respuesta es: "Eso está fuera del alcance de v2.1, ¿lo agregamos al SDD primero?"

---

## Stack — no negociable

| Capa | Tecnología | Restricción |
|---|---|---|
| Backend | Python 3.11+ · FastAPI | Sin Django, sin Flask |
| Base de datos | PostgreSQL (Render) · SQLAlchemy ORM | SQLite solo como fallback local |
| OTP | Python · SHA-256 con pepper | Sin librerías OTP externas |
| 2FA SUPER_ADMIN | TOTP RFC 6238 | pyotp o equivalente |
| Correo | Resend HTTP API | Sin SMTP, sin Twilio, sin SendGrid |
| Parser IA | DeepSeek Flash (`deepseek-chat`) | Sin OpenAI, sin Gemini |
| Frontend | HTML · CSS · JS vanilla | Sin React, sin Vue, sin frameworks, sin Bootstrap |
| Diseño frontend | Apple Design System | Ver `DESIGN.md` |
| Hosting | Render | Sin Docker en v2.1 |
| IDE | Cursor | — |

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
│   ├── index.html ← NUEVO v2.1 (Apple Design System)
│   ├── dashboard.html
│   ├── otp_panel.html
│   ├── publico.html
│   └── superadmin.html
├── DESIGN.md ← Apple Design System
├── apple/DESIGN.md
├── agents.md
├── SDD_v2.1_SorteoParking.md
├── SDD_SorteoParking_Servicio_v1.7.md
├── requirements.txt
└── README.md
```

No crear carpetas ni archivos fuera de esta estructura sin actualizar el SDD primero.

---

## Aislamiento multi-tenant — invariante crítica

- **Toda tabla** tiene `tenant_id UUID FK → tenants.id NOT NULL`.
- **Todo endpoint** valida que el token pertenezca al mismo `tenant_id` de los recursos solicitados mediante `enforce_tenant_scope()`.
- Un tenant nunca puede leer, escribir ni inferir datos de otro tenant.
- Cualquier query que no filtre por `tenant_id` es un bug — trátalo como error crítico.
- Respuesta ante violación: HTTP 403, nunca 404.

---

## Protocolo OTP — invariantes no negociables

- El número de OTPs requeridos es `sorteo.num_garantes` (configurable, rango 3–10). No hay valor hardcoded.
- Todos los OTPs deben confirmarse antes de ejecutar el sorteo. Sin excepciones, sin bypass.
- El snapshot de participantes se fija antes de la confirmación del primer OTP.
- Regenerar un OTP expirado no invalida los OTPs ya confirmados.
- El seed se deriva de `SHA-256(timestamp_utc + hash_snapshot)` — nunca de `random()` directo.
- El log registra timestamp exacto de cada confirmación — aparece en el acta.
- Expiración OTP: 30 minutos desde generación.
- El término correcto en toda la interfaz y el código es **garante**, no "consejero".

---

## Política de acceso a paneles HTML — invariante de seguridad

| Panel | Acceso permitido | Comportamiento sin credencial |
|---|---|---|
| `index.html` | Público | — |
| `publico.html` | Público | — |
| `otp_panel.html` | Solo con `token_enlace` válido en URL | Redirect a `index.html` |
| `dashboard.html` | Solo con Bearer UUID válido | HTTP 401 |
| `superadmin.html` | Solo con sesión SUPER_ADMIN activa | HTTP 401 |

El servidor valida autenticación **antes** de servir el HTML. No es suficiente validar solo en las llamadas a la API.

---

## Apple Design System — guías de frontend

El diseño frontend está definido en [`DESIGN.md`](DESIGN.md). Las reglas clave:

- **Action Blue** (#0066cc) como único color interactivo — links, botones, CTAs
- **Botones pill** con `border-radius: 9999px`
- **Sin sombras decorativas** — solo la sombra de producto fotográfico
- **Sin gradientes decorativos** — la atmósfera viene de la fotografía
- **SF Pro Text** como familia tipográfica (`system-ui, -apple-system, sans-serif`)
- **Body copy a 17px** (no 16px)
- **Headlines weight 600** (no 700), con negative letter-spacing
- **Nav oscuro** de 44px de alto
- **Tarjetas** con 18px `border-radius`
- **Responsivo mobile-first** con breakpoints Apple: ≤640px, 641–833px, 834–1068px, ≥1069px
- **Sin frameworks CSS** — solo CSS vanilla

---

## Convenciones de código

### Python
- Type hints en todas las funciones.
- Docstring en español en cada función pública.
- Sin lógica de negocio en los routers — los routers solo llaman a services.
- Sin queries SQL crudas — usar SQLAlchemy ORM siempre.
- Variables y funciones en `snake_case`. Clases en `PascalCase`.
- Constantes en `UPPER_SNAKE_CASE` en `core/config.py`.
- Usar `datetime.now(timezone.utc)` — nunca `datetime.now()` ni `datetime.utcnow()` (deprecado en Python 3.12+).

### Auditoría — patrón obligatorio

```python
# Siempre en este orden: datos primero, log después, commit explícito en cada paso
db.commit()  # Persiste datos del negocio
registrar_log_auditoria(db, ...)  # flush() interno, sin commit
db.commit()  # Persiste el log
```

Omitir el segundo `db.commit()` es el bug de auditoría no persistente de v2.0. No repetirlo.

### Errores
- Usar `HTTPException` de FastAPI con códigos correctos del SDD.
- Loguear todo error en `LogAuditoria` con `tenant_id`.
- Nunca exponer stack traces al cliente — solo en logs internos.
- Errores 409 deben incluir mensaje accionable, no solo el código.

### Seguridad
- Nunca loguear OTPs en texto plano.
- Nunca incluir correos ni datos personales de participantes en el acta (CA-10).
- Tokens de autenticación en headers, nunca en query params (excepción: `token_enlace` en OTP público, por diseño).
- Variables sensibles solo en variables de entorno — nunca hardcodeadas.
- Comparaciones de tokens y hashes siempre con `hmac.compare_digest()` — nunca con `==`.
- El `SUPER_ADMIN_TOTP_SECRET` se almacena encriptado — nunca en texto plano.

---

## Flujo de trabajo por tarea

Antes de escribir código para cualquier tarea del plan de implementación:

1. Leer la sección del SDD correspondiente a la tarea (columna "CA" en §18).
2. Identificar qué modelos, endpoints o servicios involucra.
3. Implementar en este orden: modelo → servicio → router → frontend → test manual.
4. Verificar el criterio de aceptación (CA-XX) correspondiente antes de marcar como lista.
5. Actualizar el estado de la tarea en el SDD (⬜ → ✅).

---

## Lo que NO hacer

- No instalar dependencias no listadas en `requirements.txt` sin consultar.
- No crear endpoints que no estén en el SDD §5.
- No modificar `sorteo_engine.py` sin explícita instrucción — es el núcleo heredado del v1.4.3.
- No usar `datetime.utcnow()` — usar `datetime.now(timezone.utc)`.
- No hardcodear NIT, nombre de conjunto, ni ningún dato de tenant.
- No hardcodear el número de garantes — siempre usar `sorteo.num_garantes`.
- No saltarse el protocolo OTP aunque "sea para pruebas".
- No usar la palabra "consejero" — el término correcto es "garante".
- No servir paneles HTML protegidos sin validar autenticación server-side.
- No eliminar un tenant con sorteos en estado `COMPLETADO` — retornar 409.
- No usar frameworks CSS ni JavaScript — el frontend es vanilla con Apple Design System.
- No agregar sombras ni gradientes decorativos al frontend (ver `DESIGN.md`).

---

## Glosario mínimo

| Término | Significado |
|---|---|
| Tenant | Un conjunto residencial cliente del servicio |
| TENANT_ADMIN | El administrador del conjunto — usuario principal |
| SUPER_ADMIN | El equipo de SorteoParking — acceso global |
| Garante | Uno de los N garantes del sorteo — confirma OTP (antes: "consejero") |
| Elegible | Residente que cumple requisitos para participar |
| Seed | Valor público reproducible que garantiza la aleatoriedad |
| Snapshot | Foto fija de los elegibles al momento de iniciar el sorteo |
| Acta | Documento Excel/Word con resultados y log de auditoría |
| Log encadenado | Registro append-only donde cada entrada referencia el hash de la anterior |
| num_garantes | Número de garantes requeridos para un sorteo (rango 3–10, por defecto 5) |
| token_enlace | UUID opaco de 43 chars que autentica a un garante en el panel OTP |
| Cold start | Hibernación de Render Free tras inactividad — mitigado con ping externo |

---

*Última actualización: Mayo 2026 — sincronizado con SDD v2.1. Diseño frontend: [Apple Design System](DESIGN.md).*
