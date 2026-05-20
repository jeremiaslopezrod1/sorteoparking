# SorteoParking — Reglas del Agente (agents.md)

## Identidad del proyecto

Eres el asistente de desarrollo de **SorteoParking**, un servicio web multi-tenant
en Cloud para ejecutar sorteos digitales de parqueaderos en conjuntos VIS de Colombia.
La especificación completa está en `SDD_SorteoParking_Servicio_v1.0.md`.
Ese documento es la única fuente de verdad. Si algo no está en el SDD, no lo implementes
— pregunta primero.

---

## Regla de oro

> **Ningún componente se implementa sin que el SDD lo especifique.**
> Si el SDD no lo menciona, la respuesta es: "Eso está fuera del alcance de v1.0, ¿lo agregamos al SDD primero?"

---

## Stack — no negociable

| Capa | Tecnología | Restricción |
|---|---|---|
| Backend | Python 3.11+ · FastAPI | Sin Django, sin Flask |
| Base de datos | SQLite · WAL mode · SQLAlchemy ORM | Sin PostgreSQL en v1.0 |
| OTP | Python · SHA-256 | Sin librerías OTP externas |
| WhatsApp | WhatsApp Business API (Meta) | Sin Twilio en v1.0 |
| Frontend | HTML · CSS · JS vanilla | Sin React, sin Vue, sin frameworks |
| Hosting | Railway o Render | Sin Docker en v1.0 |
| IDE | Cursor | — |

---

## Estructura de carpetas — respetar siempre

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
│   │   ├── sorteo_engine.py
│   │   ├── otp_service.py
│   │   ├── whatsapp.py
│   │   └── exportadores.py
│   └── db/
│       └── database.py
├── frontend/
│   ├── dashboard.html
│   ├── otp_panel.html
│   └── publico.html
├── agents.md
├── SDD_SorteoParking_Servicio_v1.0.md
├── requirements.txt
└── README.md
```

No crear carpetas ni archivos fuera de esta estructura sin actualizar el SDD primero.

---

## Aislamiento multi-tenant — invariante crítica

- **Toda tabla** tiene `tenant_id UUID FK → tenants.id NOT NULL`.
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

---

## Convenciones de código

### Python
- Type hints en todas las funciones.
- Docstring en español en cada función pública.
- Sin lógica de negocio en los routers — los routers solo llaman a services.
- Sin queries SQL crudas — usar SQLAlchemy ORM siempre.
- Variables y funciones en `snake_case`. Clases en `PascalCase`.
- Constantes en `UPPER_SNAKE_CASE` en `core/config.py`.

### Errores
- Usar `HTTPException` de FastAPI con códigos correctos del SDD.
- Loguear todo error en `LogAuditoria` con `tenant_id`.
- Nunca exponer stack traces al cliente — solo en logs internos.

### Seguridad
- Nunca loguear OTPs en texto plano.
- Nunca incluir correos ni WhatsApp de participantes en el acta (CA-10).
- Tokens de autenticación en headers, nunca en query params.
- Variables sensibles (API keys, secrets) solo en variables de entorno — nunca hardcodeadas.

---

## Flujo de trabajo por tarea

Antes de escribir código para cualquier tarea del plan de 90 días:

1. Leer la sección del SDD correspondiente a la tarea (columna "Spec ref.").
2. Identificar qué modelos, endpoints o servicios involucra.
3. Implementar en este orden: modelo → servicio → router → test manual.
4. Verificar el criterio de aceptación (CA-XX) correspondiente antes de marcar como lista.

---

## Lo que NO hacer

- No instalar dependencias no listadas en `requirements.txt` sin consultar.
- No crear endpoints que no estén en el SDD §5.
- No modificar `sorteo_engine.py` sin explícita instrucción — es el núcleo heredado del v1.4.3.
- No usar `datetime.now()` — siempre `datetime.utcnow()` para consistencia en Cloud.
- No hardcodear NIT, nombre de conjunto, ni ningún dato de tenant.
- No saltarse el protocolo OTP aunque "sea para pruebas".

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
| Acta | Documento PDF/Word firmado digitalmente con resultados |
| Log encadenado | Registro append-only donde cada entrada referencia el hash de la anterior |

---

*Última actualización: Abril 2026 — sincronizado con SDD v1.0*
