# Skill: frontend-design
# Fuente: https://github.com/anthropics/skills --skill frontend-design
# Adaptado para: SDD_v2.1_SorteoParking

## Propósito

Este skill guía la creación de interfaces frontend distintivas y de nivel producción
que evitan la estética genérica de IA. Se aplica a las tres pantallas de SorteoParking:
`dashboard.html`, `otp_panel.html` y `publico.html`.

---

## Contexto de SorteoParking

**Producto:** Servicio digital de sorteos para conjuntos residenciales VIS en Colombia.
**Usuarios:**
- TENANT_ADMIN — administrador del conjunto, desktop/laptop, requiere control total.
- CONSEJERO — garante del sorteo, **prioritariamente celular**, flujo de un solo paso.
- RESIDENTE — participante, celular, solo consulta resultados.

**Tono:** Institucional pero accesible. Transmite confianza, transparencia y seriedad.
No es una app de juegos — es un acto legal con consecuencias reales para las familias.

---

## Dirección estética — antes de escribir código

Antes de generar cualquier pantalla, definir:

1. **Propósito:** ¿Qué problema resuelve esta pantalla específica?
2. **Tono:** Elegir una dirección clara — no mezclar estilos.
3. **Lo memorable:** ¿Qué va a recordar el usuario de esta pantalla?
4. **Restricciones técnicas:** HTML · CSS · JS vanilla — sin frameworks.

### Dirección recomendada para SorteoParking

- **Estética:** Institucional refinada — no corporativo frío, no juguetón.
- **Referencia:** Documentos legales bien diseñados + interfaces de votación electrónica.
- **Paleta:** Azul profundo `#1A3A5C` como dominante · Blanco roto como fondo · Acento verde esmeralda para estados positivos · Rojo sobrio para errores.
- **Tipografía:** Display font con carácter (ej. Playfair Display, DM Serif) para títulos · Body font legible y moderno (ej. DM Sans, Outfit) para contenido. Nunca Inter, Roboto ni Arial.
- **Movimiento:** Un solo efecto de entrada bien orquestado por pantalla. Micro-interacciones en botones de acción crítica (Ejecutar sorteo, Confirmar OTP).

---

## Reglas de implementación

### Typography
- Usar Google Fonts — dos fuentes máximo por pantalla.
- Títulos: display font con peso 700+.
- Cuerpo: mínimo 16px, line-height 1.6.
- Nunca usar fuentes del sistema como fallback principal.

### Color y tema
- Definir CSS variables en `:root` para toda la paleta.
- Fondo nunca blanco puro — usar `#F8F7F4` o similar.
- Estados del sorteo con color semántico:
  - `PENDIENTE` → gris neutro
  - `EN_CURSO` → azul medio
  - `LISTO` → verde esmeralda (todos los OTPs confirmados)
  - `EJECUTADO` → azul profundo con checkmark
  - `ERROR` → rojo sobrio, nunca rojo brillante

### Movimiento
- CSS-only para HTML vanilla.
- Un `@keyframes` de entrada por pantalla — staggered con `animation-delay`.
- Hover states en todos los elementos interactivos.
- El botón **Ejecutar sorteo** tiene micro-interacción especial — es el momento culminante.
- El seed visible durante el sorteo: efecto de revelación progresiva (caracteres aparecen de izquierda a derecha).

### Composición espacial
- Generoso espacio negativo — estas pantallas no son dashboards de datos.
- El elemento más importante de cada pantalla ocupa el centro visual.
- Jerarquía clara: un solo CTA principal por pantalla.

### Lo que NUNCA hacer
- Gradientes púrpura sobre fondo blanco.
- Layouts de tarjetas genéricas en grid 3 columnas.
- Botones redondeados al máximo (border-radius > 8px en botones principales).
- Iconos de emoji como UI.
- Sombras box-shadow genéricas — si se usan, que sean dramáticas o ausentes.
- Tipografía Inter, Roboto, Arial, system-ui como elección principal.

---

## Especificaciones por pantalla

### dashboard.html — TENANT_ADMIN

**Propósito:** Control total del evento de sorteo.
**Flujo principal:** Cargar Excel → Iniciar sorteo → Monitorear OTPs → Ejecutar → Exportar acta.
**Lo memorable:** El progreso de los 5 OTPs como elemento visual central — 5 círculos que se llenan en tiempo real.
**Responsive:** Desktop prioritario, funcional en tablet.

Secciones requeridas:
- Header con nombre del conjunto y estado del tenant.
- Panel de carga de Excel con drag & drop visual.
- Panel de consejeros: 5 slots con nombre + estado OTP (pendiente/confirmado).
- Botón **Ejecutar sorteo** — deshabilitado hasta 5/5, con estado visual claro.
- Seed visible en pantalla ≥40px durante y después del sorteo.
- Tabla de resultados paginada post-ejecución.
- Botón exportar acta (Excel / Word).

### otp_panel.html — CONSEJERO (celular)

**Propósito:** El consejero confirma su OTP en un solo paso desde su celular.
**Flujo principal:** Abrir URL → Ingresar OTP de 6 dígitos → Confirmar → Pantalla de éxito.
**Lo memorable:** Pantalla fullscreen centrada — un solo campo, un solo botón. Sin distracciones.
**Responsive:** Mobile-first obligatorio. Funcionar en pantallas de 360px de ancho.

Secciones requeridas:
- Logo/nombre SorteoParking en header mínimo.
- Nombre del conjunto y nombre del consejero.
- Campo OTP: 6 dígitos, teclado numérico en móvil (`inputmode="numeric"`).
- Botón **Confirmar** con estado de carga.
- Pantalla de éxito con checkmark animado post-confirmación.
- Mensaje de error claro si OTP inválido o expirado.

### publico.html — RESIDENTE (sin login)

**Propósito:** El residente consulta los resultados del sorteo y verifica el seed.
**Flujo principal:** Abrir URL → Ver resultados → Buscar su apartamento → Verificar seed.
**Lo memorable:** Transparencia como valor visual — el seed es el protagonista de la página.
**Responsive:** Mobile-first. La mayoría de residentes accede desde celular.

Secciones requeridas:
- Header con nombre del conjunto y fecha del sorteo.
- Seed público en tipografía monospace grande — elemento destacado.
- Buscador por número de apartamento.
- Tabla de resultados: apartamento → parqueadero asignado.
- Sección "¿Cómo verificar?" — explicación simple del seed reproducible.

---

## Checklist antes de entregar cualquier pantalla

- [ ] ¿Usa CSS variables para toda la paleta?
- [ ] ¿Las fuentes son distintivas (no Inter/Roboto/Arial)?
- [ ] ¿Hay al menos una animación de entrada?
- [ ] ¿El elemento principal de la pantalla ocupa el centro visual?
- [ ] ¿Funciona en 360px de ancho (para otp_panel y publico)?
- [ ] ¿El seed es visible en ≥40px en dashboard y publico?
- [ ] ¿El botón Ejecutar sorteo tiene estado deshabilitado visualmente claro?
- [ ] ¿Los estados de OTP (pendiente/confirmado) son distinguibles en escala de grises?

---

*Skill sincronizado con SDD_SorteoParking_Servicio_v1.0.md — Abril 2026*
