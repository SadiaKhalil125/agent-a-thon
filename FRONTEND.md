# Frontend guidelines — hackathon app

**Product name and hero copy** live in `branding.py`, injected into `templates/index.html`. The repo folder name can stay `Agent-a-thon`; change user-facing strings only in `branding.py` when you have an idea.

Use this document for every UI change so the product stays **cohesive**, **human**, and **polished** — not generic “AI startup” chrome (no purple gradients, glow blobs, or sparkle motifs).

Official typeface: **[Poppins](https://fonts.google.com/specimen/Poppins)** (Google Fonts).

---

## Design intent

| Principle | What it means |
| --- | --- |
| Editorial calm | Feels like a refined tool or magazine layout: paper tones, ink text, one warm accent. |
| Restraint | One accent color, soft borders, light shadows only where depth is needed. |
| Clarity | Obvious hierarchy, comfortable reading width, generous line height. |
| Craft | Rounded corners in one radius family; buttons and inputs share the same height logic. |

---

## Color tokens

Always use CSS variables from `static/css/main.css`. Do not hard-code new hex values in HTML or one-off inline styles.

| Token | Hex | Use |
| --- | --- | --- |
| `--color-bg` | `#F5F1EB` | Page background (warm linen) |
| `--color-surface` | `#FFFFFF` | Cards, inputs on white |
| `--color-surface-muted` | `#FAF8F5` | Reply panel, secondary surfaces |
| `--color-border` | `#E2DDD4` | Dividers, input borders |
| `--color-border-strong` | `#C9C2B8` | Focus rings, emphasized borders |
| `--color-ink` | `#1A1918` | Headings, primary text |
| `--color-ink-muted` | `#5E5A55` | Labels, hints, metadata |
| `--color-ink-faint` | `#8A8580` | Placeholders, disabled text |
| `--color-accent` | `#8B5E3C` | Primary actions, links, key emphasis (cognac) |
| `--color-accent-hover` | `#734C31` | Button hover |
| `--color-accent-soft` | `#F0E6DC` | Soft highlight backgrounds |
| `--color-success` | `#4A5D4E` | Success states |
| `--color-error` | `#8B4049` | Errors (dusty rose, not neon red) |

**Do not use:** violet/indigo gradients, cyan-on-black, glassmorphism blur stacks, or multicolor gradients.

### Dark theme

Dark mode uses the same tokens, overridden on `html[data-theme="dark"]` in `main.css` (warm charcoal + light cognac accent, not blue-black).

| Token | Hex (dark) | Notes |
| --- | --- | --- |
| `--color-bg` | `#141312` | Page |
| `--color-surface` | `#22201E` | Cards |
| `--color-ink` | `#F2EFE9` | Primary text |
| `--color-accent` | `#C49A6C` | Slightly lighter cognac for contrast |

- **Toggle:** `.theme-toggle` in the header — **inline SVG** sun/moon (not Unicode); state in `localStorage` key `agent-a-thon-theme`.
- **Default:** If nothing stored, follow `prefers-color-scheme`.
- **Boot:** Inline `static/js/theme.js` in `<head>` (before paint) to avoid flash of wrong theme.
- New colors for dark → add to **both** `[data-theme="light"]` and `[data-theme="dark"]` blocks in CSS.

---

## Typography (Poppins)

Load weights **400**, **500**, **600** only.

| Role | Weight | Size (desktop) | Line height | Letter-spacing |
| --- | --- | --- | --- | --- |
| Display / `h1` | 600 | `2rem` (32px) | 1.2 | `-0.02em` |
| Section title / `h2` | 600 | `1.25rem` (20px) | 1.3 | `-0.01em` |
| Body | 400 | `1rem` (16px) | 1.65 | `0` |
| UI label | 500 | `0.8125rem` (13px) | 1.4 | `0.04em` (uppercase optional) |
| Small / caption | 400 | `0.875rem` (14px) | 1.5 | `0` |

- Maximum reading width for long text: **`42rem` (~672px)** inside the main column.
- Use **sentence case** for buttons (`Send message`, not `SEND MESSAGE`), except tiny nav labels if needed.

---

## Spacing scale

Use multiples of **4px**. Prefer these steps:

`4, 8, 12, 16, 24, 32, 48, 64`

| Context | Spacing |
| --- | --- |
| Card padding | `24px` mobile, `32px` desktop |
| Gap between form fields | `16px` |
| Section gap below header | `32px` |
| Page top/bottom padding | `48px` min |

---

## Radius & elevation

| Token | Value | Use |
| --- | --- | --- |
| `--radius-sm` | `8px` | Chips, small controls |
| `--radius-md` | `12px` | Buttons, inputs |
| `--radius-lg` | `16px` | Main card |
| `--shadow-card` | `0 1px 2px rgba(26, 25, 24, 0.04), 0 8px 24px rgba(26, 25, 24, 0.06)` | Primary card only |

Avoid large drop shadows and colored shadows.

---

## Layout

```
┌─────────────────────────────────────────────┐
│  Agent-a-thon (wordmark)     theme · year   │  ← site-header, max-width 72rem
├─────────────────────────────────────────────┤
│              hero strip (optional)           │
│  ┌─────────────────────────────────────┐    │
│  │  card: prompt + actions              │    │  ← .shell max-width 40rem
│  │  reply panel                         │    │
│  └─────────────────────────────────────┘    │
│              site-footer                     │
└─────────────────────────────────────────────┘
```

- Outer wrapper: `.page` on `<body>` — **flex column**, `min-height: 100dvh`
- Main content: `.main` with `flex: 1 1 auto` so `.site-footer` sits at the **bottom of the viewport** on short pages
- Center column: `.shell` (`max-width: 40rem`, horizontal auto margin)
- Site chrome: `.site-header`, `.site-footer` (`flex-shrink: 0`)

When adding pages, reuse `.page`, `.site-header`, `.shell`, and `.card`.

---

## Components

### Primary button (`.btn.btn--primary`)

- Background `--color-accent`, text white, weight 500
- Padding: `12px 20px`, min-height `44px` (touch target)
- Hover: `--color-accent-hover`; disabled: opacity `0.55`, no hover jump
- Loading: change label to `Thinking…` (unicode ellipsis) and disable

### Text input / textarea (`.field`)

- Full width, border `1px solid var(--color-border)`
- Focus: `border-color: var(--color-border-strong)` + `box-shadow: 0 0 0 3px var(--color-accent-soft)`
- Textarea min-height: `120px`, resize vertical only

### Reply panel (`.reply`)

- Background `--color-surface-muted`, border `1px solid var(--color-border)`
- Class `.reply.is-error` for error copy (`--color-error`)
- Preserve line breaks: `white-space: pre-wrap`

### Wordmark (`.brand`)

- Text only: `.brand__title` + optional `.brand__tagline` (no empty logo box or stock icons)
- Title: Poppins 600, `--color-ink`

---

## Motion

- Transitions: `150–200ms` on `color`, `background`, `border-color`, `box-shadow`
- No infinite animations except subtle optional loading dots (if added later)
- Respect `prefers-reduced-motion: reduce` (already in `main.css`)

---

## Accessibility

- Text contrast: body on background ≥ **4.5:1**; large text ≥ **3:1**
- Visible focus styles on all interactive elements (never `outline: none` without replacement)
- Associate `<label>` with inputs via `for` / `id`
- `aria-busy="true"` on the form or button while a request is in flight (see `chat.js`)

---

## File map

| File | Responsibility |
| --- | --- |
| `static/css/main.css` | Tokens, layout, components — **single source of truth** |
| `static/js/chat.js` | Homepage chat behavior |
| `static/js/theme.js` | Light/dark theme + `localStorage` |
| `templates/index.html` | Homepage markup — structure only, styles in CSS |
| `app.py` | Serves template + mounts `/static` |

**Workflow for new UI:**

1. Add tokens or component rules to `main.css` (or extend this doc first if new pattern).
2. Use existing BEM-ish classes: `.card`, `.btn`, `.field`, `.reply`.
3. New page → new template under `templates/`, link `main.css`, reuse header/footer blocks from `index.html`.
4. No inline `style=""` except rare prototypes (remove before merge).

---

## Copy tone

- Short, confident, human sentences.
- Avoid: “Powered by AI”, “Unlock insights”, “Supercharge”, rocket/sparkle emoji.
- Prefer: plain verbs (`Send`, `Try again`, `Your answer`).

---

## Pre-ship checklist

- [ ] Poppins loaded; no fallback-only body text in production
- [ ] Only palette tokens from this doc
- [ ] Focus states visible on tab navigation
- [ ] Works at 375px and 1280px width
- [ ] Light and dark themes readable; theme toggle works and persists