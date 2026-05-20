# SorteoParking Design System v2.0

Apple HIG-inspired institutional SaaS for auditable parking lottery processes.

---

## 1. Design Philosophy

*Software institucional moderno con estandares Apple para procesos auditables.*

Core principles (priorizadas):
1. Claridad — cada pantalla responde "el sorteo fue justo"
2. Confianza — legitimidad institucional, no startup hype
3. Simplicidad — minimo pasos, maximo entendimiento
4. Verificabilidad — todo es comprobable, nada es opaco
5. Rendimiento — 60fps, instantaneo en laptops economicas
6. UX operacional — reduce ansiedad, no la aumenta

---

## 2. Visual Identity

### Not Allowed
- Glow/blur excesivo
- Gradientes agresivos
- Efectos tipo casino/tragamonedas
- Animaciones largas (>2s)
- Sombras pesadas
- Motion distractivo
- Neon/cyberpunk
- Crypto/blockchain aesthetics
- Neobrutalism
- Glassmorphism extremo

### Allowed
- Profundidad sutil (box-shadow suave)
- Spacing amplio (24-48px)
- Jerarquia tipografica estricta
- Motion funcional (transform + opacity only)
- Disclosure progresivo
- Feedback inmediato
- Alto contraste (AA min)
- Minimalismo extremo
- Microinteracciones (<300ms)

---

## 3. Design Tokens

### Color System

```css
:root {
  /* Brand */
  --accent: #0066cc;              /* Action Blue - Apple standard */
  --accent-hover: #0071e3;
  --accent-pressed: #0055b3;
  --accent-on-dark: #2997ff;

  /* Surface */
  --canvas-dark: #000000;         /* Global nav bar */
  --canvas: #ffffff;
  --canvas-parchment: #f5f5f7;    /* Page background */
  --canvas-pearl: #fafafc;        /* Card background */
  --canvas-elevated: #ffffff;     /* Modal/overlay */
  --canvas-otp: #1a1a2e;         /* OTP panel dark bg */
  --canvas-otp-card: #16213e;    /* OTP consejero card */

  /* Text */
  --ink: #1d1d1f;
  --ink-secondary: #6e6e73;
  --ink-tertiary: #86868b;
  --ink-inverse: #ffffff;
  --ink-link: #0066cc;
  --ink-success: #248a3d;
  --ink-error: #c41e3a;
  --ink-warning: #b86200;

  /* Semantic */
  --green: #30d158;
  --green-bg: #e8f8ed;
  --error: #c41e3a;
  --error-bg: #fdf0f2;
  --warning: #ff9f0a;
  --warning-bg: #fff6e5;
  --blue-fill: #007aff;
  --blue-bg: #e8f0fe;

  /* Borders */
  --hairline: #d2d2d7;
  --hairline-light: #e5e5ea;
  --divider: #f0f0f0;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04), 0 1px 4px rgba(0,0,0,0.04);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
  --shadow-xl: 0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.06);
  --shadow-otp: 0 0 40px rgba(0,102,204,0.10);

  /* Translucency - OTP panels only */
  --overlay-bg: rgba(0,0,0,0.4);
  --modal-bg: rgba(255,255,255,0.85);
  --backdrop-blur: blur(20px);
  -webkit-backdrop-filter: var(--backdrop-blur);
  backdrop-filter: var(--backdrop-blur);
}
```

### Typography System

```css
:root {
  /* Scale */
  --text-xs:   12px;  line-height: 1.333; /* 16px */
  --text-sm:   13px;  line-height: 1.384; /* 18px */
  --text-base: 15px;  line-height: 1.4;   /* 21px */
  --text-md:   17px;  line-height: 1.412; /* 24px */
  --text-lg:   20px;  line-height: 1.3;   /* 26px */
  --text-xl:   24px;  line-height: 1.25;  /* 30px */
  --text-2xl:  28px;  line-height: 1.214; /* 34px */
  --text-3xl:  34px;  line-height: 1.176; /* 40px */
  --text-4xl:  40px;  line-height: 1.1;   /* 44px */

  /* Weight */
  --font-normal: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;

  /* Family */
  --font-sans: system-ui, -apple-system, 'SF Pro Text', 'Helvetica Neue', sans-serif;
  --font-display: system-ui, -apple-system, 'SF Pro Display', 'Helvetica Neue', sans-serif;
  --font-mono: 'SF Mono', ui-monospace, 'Cascadia Code', 'Fira Code', monospace;

  /* Letter spacing */
  --tracking-tight: -0.02em;
  --tracking-normal: 0em;
  --tracking-wide: 0.02em;
  --tracking-mono: 0.04em;
}
```

### Spacing System (4px grid)

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
}
```

### Border Radius

```css
:root {
  --radius-sm:  6px;
  --radius-md:  10px;
  --radius-lg:  14px;
  --radius-xl:  18px;    /* Apple standard card */
  --radius-pill: 9999px; /* Buttons, badges */
  --radius-full: 50%;
}
```

### Apple Navigation Bar

```css
:root {
  --nav-height: 44px;
  --nav-bg: #000000;
  --nav-text: #ffffff;
  --nav-text-dim: rgba(255,255,255,0.65);
  --nav-active: #2997ff;
}
```

### Otp Panel (Dark Theme)

```css
:root {
  --otp-bg: #0a0a1a;
  --otp-card-bg: rgba(255,255,255,0.06);
  --otp-card-border: rgba(255,255,255,0.10);
  --otp-card-hover: rgba(255,255,255,0.10);
  --otp-text: #f5f5f7;
  --otp-text-dim: rgba(255,255,255,0.55);
  --otp-accent: #2997ff;
  --otp-green: #30d158;
  --otp-input-bg: rgba(255,255,255,0.08);
  --otp-input-border: rgba(255,255,255,0.15);
  --otp-input-focus: #2997ff;
}
```

---

## 4. Component Architecture

### 4.1 Apple Nav Bar
- Height: 44px fixed
- Background: #000
- Sticky top
- Brand left, actions right
- No shadows, no dividers

### 4.2 Cards
- border-radius: 18px
- background: var(--canvas-pearl) or var(--canvas)
- padding: 24px
- box-shadow: --shadow-sm
- margin-bottom: 16px
- No borders, use shadows instead

### 4.3 Buttons

**Primary (fill)**
```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 9999px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  -webkit-font-smoothing: antialiased;
}
.btn-primary {
  background: #0066cc;
  color: #fff;
}
.btn-primary:hover {
  background: #0071e3;
}
.btn-primary:active {
  background: #0055b3;
  transform: scale(0.98);
}

/* Secondary - bordered */
.btn-secondary {
  background: transparent;
  color: #0066cc;
  border: 1px solid #d2d2d7;
}
.btn-secondary:hover {
  background: rgba(0,102,204,0.04);
  border-color: #0066cc;
}

/* Destructive */
.btn-destructive {
  background: #c41e3a;
  color: #fff;
}
.btn-destructive:hover {
  background: #a01830;
}

/* Ghost */
.btn-ghost {
  background: transparent;
  color: #6e6e73;
}
.btn-ghost:hover {
  background: rgba(0,0,0,0.04);
  color: #1d1d1f;
}

/* Sizes */
.btn-sm { padding: 6px 16px; font-size: 13px; }
.btn-lg { padding: 16px 32px; font-size: 17px; }
```

### 4.4 Inputs
```css
.input {
  width: 100%;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid #d2d2d7;
  background: #fff;
  font-size: 15px;
  font-family: inherit;
  color: #1d1d1f;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.input:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 3px rgba(0,102,204,0.12);
}
.input-error {
  border-color: #c41e3a;
  box-shadow: 0 0 0 3px rgba(196,30,58,0.12);
}
```

### 4.5 OTP Digit Input
- 6 individual inputs
- Each: 48x64px, center-aligned
- border-radius: 10px
- Focus auto-advances to next
- Paste support (6 digits at once)
- Pill submit button below

### 4.6 Status Badge
```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
}
.badge-success { background: #e8f8ed; color: #248a3d; }
.badge-error { background: #fdf0f2; color: #c41e3a; }
.badge-warning { background: #fff6e5; color: #b86200; }
.badge-info { background: #e8f0fe; color: #0066cc; }
.badge-neutral { background: #f5f5f7; color: #6e6e73; }
```

### 4.7 Progress Steps (Stepper)
- Numbers separated by thin lines
- Completed: blue circle, white check
- Active: blue ring, number
- Pending: gray circle, number
- Labels below each step

### 4.8 Status Segments (OTP Panel)
- 5 consejero cards in a row (horizontal)
- Each shows: name, status (pending/confirmed/expired)
- Status indicator dot + text
- Progress bar at top

---

## 5. Motion Guidelines

### Timing
- Micro-interactions: 200ms
- State transitions: 250ms
- Page transitions: 300ms
- Sorteo execution animation: 1.5s max
- OTP confirm feedback: 400ms
- Alert/notification: 300ms in, auto-dismiss after 4s

### Easing
- Standard: `cubic-bezier(0.25, 0.1, 0.25, 1)`
- Enter: `cubic-bezier(0.175, 0.885, 0.32, 1.275)`
- Exit: `cubic-bezier(0.6, -0.28, 0.735, 0.045)`
- OTP panel: `cubic-bezier(0.22, 1, 0.36, 1)`

### What to animate (ONLY)
- `transform` (translate, scale)
- `opacity`

### What NOT to animate
- `width`, `height`, `top`, `left`, `margin`, `padding`
- `box-shadow` changes (no glow transitions)

### Sorteo Execution Sequence (1.5s)
1. 0-300ms: fade out action panel, show "Preparando sorteo..."
2. 300-800ms: Spinning indicator with deterministic seed display
3. 800-1200ms: Deceleration phase
4. 1200-1500ms: Reveal results with entrance animation

---

## 6. Page Architecture

### 6.1 Login SUPER_ADMIN
- Apple-style centered card on light gray bg
- Email/password or token input
- Clean, minimal, no branding clutter
- Error states below fields

### 6.2 Dashboard (TENANT_ADMIN)
- Apple nav bar with tenant name
- Cards: Sorteos actuales, Historial, Carga Excel, Catalogo
- Status badges for each sorteo
- Quick actions: "Nuevo sorteo", "Exportar acta"
- Empty state: "No hay sorteos activos" with CTA

### 6.3 Carga Excel Flow
- Drop zone (dashed border, subtle)
- File selected: show preview table (first 5 rows)
- Column mapping with validation
- IA parsing progress indicator
- Errors per row shown inline
- Confirm button: "Cargar [N] participantes"

### 6.4 OTP Panel (Dark Theme)
- Full dark background (#0a0a1a)
- 5 consejero status cards in row
- OTP digit input (6 boxes)
- Progress bar at top
- "Consejeros confirmados: 3/5"
- Each card: name, status dot, time remaining
- On complete: transition to "todos confirmados" state

### 6.5 Ejecucion Sorteo Screen
- "Todo listo" state (all 5 OTPs confirmed)
- Ejecutar button (large, prominent)
- 1.5s animation sequence
- Result reveal: winners list, seed, hash
- "Descargar acta" immediately available

### 6.6 Public Verification Panel
- Ultra minimal
- Header: conjunto name + sorteo date
- Search by apartment number
- Result row: apartment, asignado/perdedor, parqueadero
- Bottom: verification section with seed + hash
- "Como verificar" disclosure section
- "Descargar acta" button

### 6.7 Historial Sorteos
- List with date, status, participant count
- Click to expand details
- Each item shows: fecha, estado, ganadores/perdedores
- "Ver acta" and "Descargar" actions

---

## 7. Empty States

All empty states follow this pattern:
- Icon (SF Symbol style, monoline)
- Title (17px, semibold)
- Description (15px, secondary)
- CTA button

Examples:
- "No hay participantes cargados" + CTA "Cargar Excel"
- "No hay sorteos anteriores" + CTA "Iniciar primer sorteo"
- "Catalogo vacio" + CTA "Cargar catalogo"

---

## 8. Loading States

- Skeleton screens preferred over spinners
- Pulse animation: `@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.5 } }`
- Skeleton: light gray rectangles matching content shape
- Duration: 1.5s pulse infinite
- NO spinning wheel for content loading

---

## 9. Error States

- Inline below relevant field or card
- Red text at --text-sm (13px)
- With alert icon before message
- Banner for system errors (top of page, dismissible)
- "Reintentar" link for network errors

---

## 10. Accessibility

- All text: minimum 15px body
- Touch targets: minimum 44x44px
- Focus visible: 3px ring at --accent
- Color contrast: AA minimum (4.5:1 text, 3:1 large text)
- All interactive elements keyboard navigable
- aria-labels for icon buttons
- Role attributes for custom components
- Color not sole indicator of state (use text + icon)
- Reduced motion: respect prefers-reduced-motion

---

## 11. Performance Rules

- CSS transitions: `will-change: transform, opacity` on animated elements
- Images: lazy loading
- Lists: virtualize if >100 items
- CSS: single file, no runtime CSS-in-JS
- JS: vanilla, <50kb per page
- No WebFonts loading (use system-ui)
- Animations: GPU-composited (transform + opacity only)
- No requestAnimationFrame for simple transitions
- Use content-visibility for below-fold content

---

## 12. Responsive Breakpoints

```css
/* Mobile first */
/* <640px: single column */
/* 640-1024: two columns */
/* >1024: full layout */

@media (max-width: 640px) {
  .otp-cards { flex-direction: column; }
  .nav-actions { gap: 8px; }
  .btn { width: 100%; justify-content: center; }
}
```

---

## 13. File Structure

```
frontend/
  DESIGN_SYSTEM.md        ← this file
  global.css             ← all design tokens + base styles
  dashboard.html         ← tenant admin dashboard
  superadmin.html        ← super admin panel
  otp_panel.html         ← consejero OTP panel (dark theme)
  publico.html           ← public verification page
  components/            ← reusable partials (for Jinja2)
    nav.html
    card.html
    badge.html
    stepper.html
    otp-input.html
    skeleton.html
    empty-state.html
    status-indicator.html
```
