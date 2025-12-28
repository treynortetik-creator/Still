# Liquid Premium UI Facelift Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Still's UI from functional to premium SaaS with glassmorphism, refined colors, micro-animations, and polished interactions.

**Architecture:** CSS-first approach - update the central `styles.css` with new design tokens, utility classes, and component styles. Then systematically update each HTML page to use new classes. Minimal JavaScript changes.

**Tech Stack:** Tailwind CSS (via CDN), CSS custom properties, CSS animations, backdrop-filter for glassmorphism.

---

## Design System: Liquid Premium

### Color Palette Evolution

| Token | Current | New (Dark) | New (Light) |
|-------|---------|------------|-------------|
| `--still-bg` | `#0D0D0D` | `#09090B` | `#FAFAFA` |
| `--still-card` | `#1A1A1A` | `#18181B` | `#FFFFFF` |
| `--still-card-elevated` | N/A | `#27272A` | `#F4F4F5` |
| `--still-border` | `#2A2A2A` | `#27272A` | `#E4E4E7` |
| `--still-border-subtle` | N/A | `#1F1F23` | `#F4F4F5` |
| `--still-text` | `#F5F5F5` | `#FAFAFA` | `#18181B` |
| `--still-muted` | `#A3A3A3` | `#A1A1AA` | `#71717A` |

### New Design Tokens

```css
/* Glow effects */
--copper-glow: 0 0 20px rgba(184, 115, 51, 0.3);
--copper-glow-intense: 0 0 30px rgba(184, 115, 51, 0.5);

/* Glassmorphism */
--glass-bg: rgba(24, 24, 27, 0.7);
--glass-border: rgba(255, 255, 255, 0.08);
--glass-blur: 12px;

/* Enhanced shadows */
--shadow-premium: 0 4px 20px rgba(0, 0, 0, 0.4);
--shadow-card: 0 2px 8px rgba(0, 0, 0, 0.3);
--shadow-elevated: 0 8px 32px rgba(0, 0, 0, 0.5);

/* Gradient borders */
--border-gradient: linear-gradient(135deg, rgba(184, 115, 51, 0.5), rgba(212, 165, 116, 0.2));
```

### Component Upgrades

1. **Cards**: Glassmorphism with subtle gradient borders on hover
2. **Buttons**: Glow effect on primary, scale on hover
3. **Navigation**: Frosted glass backdrop, active indicator glow
4. **Inputs**: Focus glow ring, smooth border transitions
5. **Hero sections**: Animated gradient backgrounds
6. **Loading states**: Refined spinner with glow

---

## Task 1: Update CSS Variables and Base Styles

**Files:**
- Modify: `frontend/static/styles.css:1-161`

**Step 1: Update dark theme color variables**

Replace the `:root` block (lines 7-86) with enhanced Liquid Premium colors:

```css
:root {
    /* Dark theme (default) - Liquid Premium */
    --still-bg: #09090B;
    --still-card: #18181B;
    --still-card-elevated: #27272A;
    --still-border: #27272A;
    --still-border-subtle: #1F1F23;
    --still-text: #FAFAFA;
    --still-muted: #A1A1AA;
    --still-disabled: #52525B;

    /* Accent colors - refined */
    --still-copper: #B87333;
    --still-copper-hover: #C4844A;
    --still-copper-glow: rgba(184, 115, 51, 0.4);
    --still-amber: #D4A574;
    --still-green: #22C55E;
    --still-green-muted: #4ADE80;
    --still-error: #EF4444;
    --still-error-muted: #F87171;

    /* Gradient colors */
    --still-gradient-start: #B87333;
    --still-gradient-end: #D4A574;
    --still-gradient-hover-start: #C4844A;
    --still-gradient-hover-end: #E0B68A;

    /* Glassmorphism */
    --glass-bg: rgba(24, 24, 27, 0.7);
    --glass-bg-solid: rgba(24, 24, 27, 0.95);
    --glass-border: rgba(255, 255, 255, 0.08);
    --glass-border-hover: rgba(255, 255, 255, 0.12);

    /* Glow effects */
    --glow-copper: 0 0 20px rgba(184, 115, 51, 0.3);
    --glow-copper-intense: 0 0 30px rgba(184, 115, 51, 0.5);
    --glow-green: 0 0 15px rgba(34, 197, 94, 0.3);
    --glow-error: 0 0 15px rgba(239, 68, 68, 0.3);

    /* Shadows - enhanced depth */
    --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.2);
    --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
    --shadow-xl: 0 12px 40px rgba(0, 0, 0, 0.6);

    /* Premium card shadow */
    --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.3), 0 0 1px rgba(255, 255, 255, 0.05);
    --shadow-card-hover: 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 1px rgba(255, 255, 255, 0.1);

    /* Scrollbar */
    --scrollbar-track: #18181B;
    --scrollbar-thumb: #3F3F46;
    --scrollbar-thumb-hover: #52525B;

    /* Focus ring - copper glow */
    --focus-ring: var(--still-copper);
    --focus-ring-offset: #09090B;

    /* Skeleton loading */
    --skeleton-base: #27272A;
    --skeleton-highlight: #3F3F46;

    /* Modal backdrop */
    --backdrop-color: rgba(0, 0, 0, 0.8);
    --backdrop-blur: 8px;

    /* Animation timing */
    --transition-fast: 150ms;
    --transition-base: 200ms;
    --transition-slow: 300ms;
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);

    /* Border radius - slightly larger */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --radius-xl: 20px;
    --radius-full: 9999px;
}
```

**Step 2: Update light theme variables**

Replace the `[data-theme="light"]` block with refined light theme:

```css
/* Light theme - Liquid Premium */
[data-theme="light"] {
    --still-bg: #FAFAFA;
    --still-card: #FFFFFF;
    --still-card-elevated: #F4F4F5;
    --still-border: #E4E4E7;
    --still-border-subtle: #F4F4F5;
    --still-text: #18181B;
    --still-muted: #71717A;
    --still-disabled: #A1A1AA;

    /* Accent colors - adjusted for light */
    --still-copper: #A66329;
    --still-copper-hover: #8B5324;
    --still-copper-glow: rgba(166, 99, 41, 0.25);
    --still-amber: #B8894A;
    --still-green: #16A34A;
    --still-green-muted: #22C55E;
    --still-error: #DC2626;
    --still-error-muted: #EF4444;

    /* Glassmorphism - light mode */
    --glass-bg: rgba(255, 255, 255, 0.8);
    --glass-bg-solid: rgba(255, 255, 255, 0.95);
    --glass-border: rgba(0, 0, 0, 0.06);
    --glass-border-hover: rgba(0, 0, 0, 0.1);

    /* Glow effects - subtle for light */
    --glow-copper: 0 0 20px rgba(166, 99, 41, 0.15);
    --glow-copper-intense: 0 0 30px rgba(166, 99, 41, 0.25);
    --glow-green: 0 0 15px rgba(22, 163, 74, 0.2);
    --glow-error: 0 0 15px rgba(220, 38, 38, 0.2);

    /* Shadows - softer for light mode */
    --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.04);
    --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.06);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
    --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.1);
    --shadow-xl: 0 12px 40px rgba(0, 0, 0, 0.12);

    /* Premium card shadow - light */
    --shadow-card: 0 2px 8px rgba(0, 0, 0, 0.06), 0 0 1px rgba(0, 0, 0, 0.1);
    --shadow-card-hover: 0 8px 24px rgba(0, 0, 0, 0.1), 0 0 1px rgba(0, 0, 0, 0.15);

    /* Scrollbar */
    --scrollbar-track: #F4F4F5;
    --scrollbar-thumb: #D4D4D8;
    --scrollbar-thumb-hover: #A1A1AA;

    /* Focus ring offset */
    --focus-ring-offset: #FAFAFA;

    /* Skeleton loading */
    --skeleton-base: #E4E4E7;
    --skeleton-highlight: #F4F4F5;

    /* Modal backdrop */
    --backdrop-color: rgba(0, 0, 0, 0.5);
}
```

**Step 3: Verify changes compile**

Open the app in browser and verify no CSS errors in console.

**Step 4: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): update color palette to Liquid Premium design system"
```

---

## Task 2: Add Glassmorphism and Premium Card Styles

**Files:**
- Modify: `frontend/static/styles.css` (add after line 180)

**Step 1: Add glassmorphism utility classes**

```css
/* ============================================
   GLASSMORPHISM COMPONENTS
   ============================================ */

.glass {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur, 12px));
    -webkit-backdrop-filter: blur(var(--glass-blur, 12px));
    border: 1px solid var(--glass-border);
}

.glass-solid {
    background: var(--glass-bg-solid);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--glass-border);
}

.glass:hover,
.glass-solid:hover {
    border-color: var(--glass-border-hover);
}

/* Premium card with gradient border on hover */
.card-premium {
    background: var(--still-card);
    border: 1px solid var(--still-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-card);
    transition: all var(--transition-base) var(--ease-out);
    position: relative;
}

.card-premium::before {
    content: '';
    position: absolute;
    inset: -1px;
    border-radius: inherit;
    padding: 1px;
    background: linear-gradient(135deg, transparent, transparent);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    opacity: 0;
    transition: opacity var(--transition-base) var(--ease-out);
    pointer-events: none;
}

.card-premium:hover {
    box-shadow: var(--shadow-card-hover);
    transform: translateY(-2px);
    border-color: var(--still-border-subtle);
}

.card-premium:hover::before {
    background: linear-gradient(135deg, var(--still-copper), var(--still-amber));
    opacity: 0.6;
}

/* Elevated card variant */
.card-elevated {
    background: var(--still-card-elevated);
    border: 1px solid var(--still-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
}

/* Glowing border effect */
.glow-border {
    position: relative;
}

.glow-border::after {
    content: '';
    position: absolute;
    inset: -2px;
    border-radius: inherit;
    background: linear-gradient(135deg, var(--still-copper), var(--still-amber));
    opacity: 0;
    z-index: -1;
    filter: blur(8px);
    transition: opacity var(--transition-base) var(--ease-out);
}

.glow-border:hover::after {
    opacity: 0.4;
}
```

**Step 2: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): add glassmorphism and premium card styles"
```

---

## Task 3: Add Micro-Animations and Transitions

**Files:**
- Modify: `frontend/static/styles.css` (add after glassmorphism section)

**Step 1: Add animation keyframes and utilities**

```css
/* ============================================
   MICRO-ANIMATIONS
   ============================================ */

/* Fade in with slide */
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(12px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes fadeInDown {
    from {
        opacity: 0;
        transform: translateY(-12px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes fadeInScale {
    from {
        opacity: 0;
        transform: scale(0.95);
    }
    to {
        opacity: 1;
        transform: scale(1);
    }
}

/* Subtle pulse for loading/attention */
@keyframes subtlePulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.7;
    }
}

/* Glow pulse for accents */
@keyframes glowPulse {
    0%, 100% {
        box-shadow: var(--glow-copper);
    }
    50% {
        box-shadow: var(--glow-copper-intense);
    }
}

/* Shimmer effect for skeletons */
@keyframes shimmer {
    0% {
        background-position: -200% 0;
    }
    100% {
        background-position: 200% 0;
    }
}

/* Gradient shift for hero backgrounds */
@keyframes gradientShift {
    0%, 100% {
        background-position: 0% 50%;
    }
    50% {
        background-position: 100% 50%;
    }
}

/* Animation utilities */
.animate-fade-in-up {
    animation: fadeInUp var(--transition-slow) var(--ease-out) forwards;
}

.animate-fade-in-down {
    animation: fadeInDown var(--transition-slow) var(--ease-out) forwards;
}

.animate-fade-in-scale {
    animation: fadeInScale var(--transition-slow) var(--ease-out) forwards;
}

.animate-pulse-subtle {
    animation: subtlePulse 2s var(--ease-in-out) infinite;
}

.animate-glow-pulse {
    animation: glowPulse 2s var(--ease-in-out) infinite;
}

/* Staggered animation delays */
.animate-delay-1 { animation-delay: 50ms; }
.animate-delay-2 { animation-delay: 100ms; }
.animate-delay-3 { animation-delay: 150ms; }
.animate-delay-4 { animation-delay: 200ms; }
.animate-delay-5 { animation-delay: 250ms; }

/* Hover scale effect */
.hover-scale {
    transition: transform var(--transition-fast) var(--ease-out);
}

.hover-scale:hover {
    transform: scale(1.02);
}

.hover-scale:active {
    transform: scale(0.98);
}

/* Enhanced hover lift */
.hover-lift-premium {
    transition: transform var(--transition-base) var(--ease-out),
                box-shadow var(--transition-base) var(--ease-out);
}

.hover-lift-premium:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-lg);
}
```

**Step 2: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): add micro-animations and transition utilities"
```

---

## Task 4: Refactor Buttons and Interactive Elements

**Files:**
- Modify: `frontend/static/styles.css` (add after animations section)

**Step 1: Add premium button styles**

```css
/* ============================================
   PREMIUM BUTTONS
   ============================================ */

/* Base button reset */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.625rem 1.25rem;
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.25rem;
    border-radius: var(--radius-md);
    border: 1px solid transparent;
    cursor: pointer;
    transition: all var(--transition-fast) var(--ease-out);
    outline: none;
}

.btn:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
}

.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
}

/* Primary button - copper gradient with glow */
.btn-primary {
    background: linear-gradient(135deg, var(--still-gradient-start), var(--still-gradient-end));
    color: #FFFFFF;
    border: none;
    box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.btn-primary:hover {
    background: linear-gradient(135deg, var(--still-gradient-hover-start), var(--still-gradient-hover-end));
    box-shadow: var(--glow-copper), var(--shadow-md);
    transform: translateY(-1px);
}

.btn-primary:active {
    transform: translateY(0);
    box-shadow: var(--shadow-xs);
}

/* Secondary button - ghost with border */
.btn-secondary {
    background: transparent;
    color: var(--still-text);
    border-color: var(--still-border);
}

.btn-secondary:hover {
    background: var(--still-card);
    border-color: var(--still-muted);
}

/* Ghost button - no border */
.btn-ghost {
    background: transparent;
    color: var(--still-muted);
    border: none;
}

.btn-ghost:hover {
    background: var(--still-card);
    color: var(--still-text);
}

/* Copper text button */
.btn-copper {
    background: transparent;
    color: var(--still-copper);
    border: 1px solid var(--still-copper);
}

.btn-copper:hover {
    background: rgba(184, 115, 51, 0.1);
    box-shadow: var(--glow-copper);
}

/* Danger button */
.btn-danger {
    background: var(--still-error);
    color: #FFFFFF;
    border: none;
}

.btn-danger:hover {
    background: var(--still-error-muted);
    box-shadow: var(--glow-error);
}

/* Icon button */
.btn-icon {
    padding: 0.5rem;
    border-radius: var(--radius-md);
    color: var(--still-muted);
    background: transparent;
    border: none;
}

.btn-icon:hover {
    background: var(--still-card);
    color: var(--still-text);
}

/* Button sizes */
.btn-sm {
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
}

.btn-lg {
    padding: 0.875rem 1.75rem;
    font-size: 1rem;
}

/* ============================================
   PREMIUM FORM INPUTS
   ============================================ */

.input-premium {
    width: 100%;
    padding: 0.75rem 1rem;
    background: var(--still-card);
    border: 1px solid var(--still-border);
    border-radius: var(--radius-md);
    color: var(--still-text);
    font-size: 0.875rem;
    transition: all var(--transition-fast) var(--ease-out);
}

.input-premium::placeholder {
    color: var(--still-disabled);
}

.input-premium:hover {
    border-color: var(--still-muted);
}

.input-premium:focus {
    outline: none;
    border-color: var(--still-copper);
    box-shadow: 0 0 0 3px var(--still-copper-glow);
}

/* Select dropdown */
.select-premium {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%23A1A1AA'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 0.75rem center;
    background-size: 1rem;
    padding-right: 2.5rem;
}

/* Checkbox and radio - copper accent */
.checkbox-premium,
.radio-premium {
    width: 1.125rem;
    height: 1.125rem;
    accent-color: var(--still-copper);
    cursor: pointer;
}
```

**Step 2: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): add premium button and form input styles"
```

---

## Task 5: Update Navigation and Header

**Files:**
- Modify: `frontend/static/styles.css` (add after form inputs section)

**Step 1: Add premium navigation styles**

```css
/* ============================================
   PREMIUM NAVIGATION
   ============================================ */

.nav-premium {
    background: var(--glass-bg-solid);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--glass-border);
    position: sticky;
    top: 0;
    z-index: 50;
}

.nav-link {
    position: relative;
    padding: 0.5rem 0.75rem;
    color: var(--still-muted);
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: var(--radius-md);
    transition: all var(--transition-fast) var(--ease-out);
}

.nav-link:hover {
    color: var(--still-text);
    background: var(--still-card-elevated);
}

.nav-link.active {
    color: var(--still-copper);
}

.nav-link.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 50%;
    transform: translateX(-50%);
    width: 24px;
    height: 2px;
    background: var(--still-copper);
    border-radius: var(--radius-full);
    box-shadow: 0 0 8px var(--still-copper-glow);
}

/* Theme toggle - premium */
.theme-toggle-premium {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: var(--radius-md);
    background: var(--still-card);
    border: 1px solid var(--still-border);
    color: var(--still-muted);
    cursor: pointer;
    transition: all var(--transition-fast) var(--ease-out);
}

.theme-toggle-premium:hover {
    background: var(--still-card-elevated);
    color: var(--still-copper);
    border-color: var(--still-copper);
    box-shadow: var(--glow-copper);
}

.theme-toggle-premium svg {
    width: 20px;
    height: 20px;
}

/* ============================================
   PREMIUM HERO SECTIONS
   ============================================ */

.hero-premium {
    background: linear-gradient(135deg, var(--still-gradient-start) 0%, var(--still-gradient-end) 50%, var(--still-copper-hover) 100%);
    background-size: 200% 200%;
    animation: gradientShift 8s ease infinite;
    position: relative;
    overflow: hidden;
}

.hero-premium::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 30% 50%, rgba(255, 255, 255, 0.1) 0%, transparent 50%);
    pointer-events: none;
}

.hero-premium::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 120px;
    background: linear-gradient(to top, var(--still-bg), transparent);
    pointer-events: none;
}

/* ============================================
   PREMIUM PAGE HEADER
   ============================================ */

.page-header {
    margin-bottom: 2rem;
}

.page-title {
    font-size: 1.875rem;
    font-weight: 700;
    color: var(--still-text);
    letter-spacing: -0.025em;
}

.page-subtitle {
    color: var(--still-muted);
    margin-top: 0.25rem;
}
```

**Step 2: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): add premium navigation and hero section styles"
```

---

## Task 6: Update Loading States and Feedback

**Files:**
- Modify: `frontend/static/styles.css` (update skeleton and add new loaders)

**Step 1: Replace skeleton and add premium loaders**

```css
/* ============================================
   PREMIUM LOADING STATES
   ============================================ */

/* Skeleton with shimmer */
.skeleton-premium {
    background: linear-gradient(
        90deg,
        var(--skeleton-base) 0%,
        var(--skeleton-highlight) 20%,
        var(--skeleton-base) 40%,
        var(--skeleton-base) 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite linear;
    border-radius: var(--radius-md);
}

/* Premium spinner */
.spinner-premium {
    width: 40px;
    height: 40px;
    border: 3px solid var(--still-border);
    border-top-color: var(--still-copper);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    box-shadow: 0 0 12px var(--still-copper-glow);
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

/* Progress bar */
.progress-premium {
    width: 100%;
    height: 6px;
    background: var(--still-card);
    border-radius: var(--radius-full);
    overflow: hidden;
}

.progress-premium-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--still-gradient-start), var(--still-gradient-end));
    border-radius: var(--radius-full);
    transition: width var(--transition-slow) var(--ease-out);
    box-shadow: 0 0 8px var(--still-copper-glow);
}

/* Toast - premium */
.toast-premium {
    background: var(--glass-bg-solid);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 1rem 1.5rem;
    box-shadow: var(--shadow-lg);
    animation: fadeInUp var(--transition-slow) var(--ease-out);
}

.toast-success {
    border-left: 3px solid var(--still-green);
}

.toast-error {
    border-left: 3px solid var(--still-error);
}

.toast-info {
    border-left: 3px solid var(--still-copper);
}

/* ============================================
   PREMIUM TABS
   ============================================ */

.tabs-premium {
    display: flex;
    gap: 0.5rem;
    border-bottom: 1px solid var(--still-border);
    padding-bottom: 0;
}

.tab-premium {
    padding: 0.75rem 1rem;
    color: var(--still-muted);
    font-size: 0.875rem;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: all var(--transition-fast) var(--ease-out);
    cursor: pointer;
    background: none;
    border-top: none;
    border-left: none;
    border-right: none;
}

.tab-premium:hover {
    color: var(--still-text);
}

.tab-premium.active {
    color: var(--still-copper);
    border-bottom-color: var(--still-copper);
}

/* ============================================
   PREMIUM BADGES & TAGS
   ============================================ */

.badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.625rem;
    font-size: 0.75rem;
    font-weight: 500;
    border-radius: var(--radius-full);
    white-space: nowrap;
}

.badge-copper {
    background: rgba(184, 115, 51, 0.15);
    color: var(--still-copper);
}

.badge-green {
    background: rgba(34, 197, 94, 0.15);
    color: var(--still-green);
}

.badge-amber {
    background: rgba(212, 165, 116, 0.15);
    color: var(--still-amber);
}

.badge-error {
    background: rgba(239, 68, 68, 0.15);
    color: var(--still-error);
}

.badge-muted {
    background: var(--still-card-elevated);
    color: var(--still-muted);
}
```

**Step 2: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): add premium loading states, tabs, and badges"
```

---

## Task 7: Update Drop Zones and Interactive Areas

**Files:**
- Modify: `frontend/static/styles.css` (add at end)

**Step 1: Add premium drop zone and interactive area styles**

```css
/* ============================================
   PREMIUM DROP ZONES
   ============================================ */

.dropzone-premium {
    border: 2px dashed var(--still-border);
    border-radius: var(--radius-lg);
    padding: 3rem 2rem;
    text-align: center;
    background: var(--still-card);
    transition: all var(--transition-base) var(--ease-out);
    cursor: pointer;
}

.dropzone-premium:hover {
    border-color: var(--still-muted);
    background: var(--still-card-elevated);
}

.dropzone-premium.active,
.dropzone-premium:focus-within {
    border-color: var(--still-copper);
    border-style: solid;
    background: rgba(184, 115, 51, 0.05);
    box-shadow: 0 0 0 4px var(--still-copper-glow);
}

.dropzone-icon {
    width: 48px;
    height: 48px;
    margin: 0 auto 1rem;
    color: var(--still-muted);
    transition: all var(--transition-base) var(--ease-out);
}

.dropzone-premium:hover .dropzone-icon,
.dropzone-premium.active .dropzone-icon {
    color: var(--still-copper);
    transform: scale(1.1);
}

/* ============================================
   EMPTY STATES
   ============================================ */

.empty-state {
    text-align: center;
    padding: 4rem 2rem;
}

.empty-state-icon {
    width: 64px;
    height: 64px;
    margin: 0 auto 1.5rem;
    color: var(--still-disabled);
}

.empty-state-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--still-text);
    margin-bottom: 0.5rem;
}

.empty-state-text {
    color: var(--still-muted);
    max-width: 24rem;
    margin: 0 auto;
}

/* ============================================
   DIVIDERS
   ============================================ */

.divider {
    height: 1px;
    background: var(--still-border);
    margin: 1.5rem 0;
}

.divider-vertical {
    width: 1px;
    height: 100%;
    background: var(--still-border);
    margin: 0 1rem;
}

/* ============================================
   SCROLLBAR REFINEMENTS
   ============================================ */

::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: var(--scrollbar-track);
    border-radius: var(--radius-full);
}

::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: var(--radius-full);
    border: 2px solid var(--scrollbar-track);
}

::-webkit-scrollbar-thumb:hover {
    background: var(--scrollbar-thumb-hover);
}

/* Firefox */
* {
    scrollbar-width: thin;
    scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
}

/* ============================================
   FOCUS VISIBLE REFINEMENTS
   ============================================ */

:focus-visible {
    outline: 2px solid var(--still-copper);
    outline-offset: 2px;
}

/* Remove focus for mouse users */
:focus:not(:focus-visible) {
    outline: none;
}

/* ============================================
   SELECTION COLORS
   ============================================ */

::selection {
    background: var(--still-copper);
    color: #FFFFFF;
}

::-moz-selection {
    background: var(--still-copper);
    color: #FFFFFF;
}
```

**Step 2: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): add premium drop zones, empty states, and global refinements"
```

---

## Task 8: Update copper-gradient Class

**Files:**
- Modify: `frontend/static/styles.css:167-180`

**Step 1: Enhance the copper gradient with premium effects**

Replace the existing copper-gradient styles:

```css
/* ============================================
   STILL BRAND COLORS - COPPER GRADIENT
   ============================================ */

.copper-gradient {
    background: linear-gradient(135deg, var(--still-gradient-start) 0%, var(--still-gradient-end) 100%);
    transition: all var(--transition-base) var(--ease-out);
}

.copper-gradient:hover {
    background: linear-gradient(135deg, var(--still-gradient-hover-start) 0%, var(--still-gradient-hover-end) 100%);
    box-shadow: var(--glow-copper);
}

.copper-gradient-text {
    background: linear-gradient(135deg, var(--still-gradient-start) 0%, var(--still-gradient-end) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* Animated gradient background */
.copper-gradient-animated {
    background: linear-gradient(135deg, var(--still-gradient-start) 0%, var(--still-gradient-end) 50%, var(--still-copper-hover) 100%);
    background-size: 200% 200%;
    animation: gradientShift 6s ease infinite;
}
```

**Step 2: Commit**

```bash
git add frontend/static/styles.css
git commit -m "feat(ui): enhance copper gradient with premium effects"
```

---

## Task 9: Update Index.html (Landing Page)

**Files:**
- Modify: `frontend/index.html`

**Step 1: Update navigation to use premium classes**

Replace navigation section with:

```html
<!-- Navigation -->
<nav class="nav-premium">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
            <div class="flex items-center space-x-8">
                <a href="/" class="flex items-center">
                    <img src="/static/images/Still Logo.svg" alt="Still" class="h-12">
                </a>
                <div class="hidden md:flex space-x-1">
                    <a href="/upload.html" class="nav-link">Upload</a>
                    <a href="/reserve.html" class="nav-link">Reserve</a>
                    <a href="/workshop.html" class="nav-link">Workshop</a>
                    <a href="/calendar.html" class="nav-link">Calendar</a>
                    <a href="/autopilot.html" class="nav-link">Autopilot</a>
                    <a href="/analytics.html" class="nav-link">Analytics</a>
                    <a href="/settings.html" class="nav-link">Settings</a>
                </div>
            </div>
            <div class="flex items-center space-x-3">
                <button onclick="ThemeManager.toggle()" class="theme-toggle-premium" title="Toggle light/dark mode">
                    <svg class="theme-icon-sun" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                    </svg>
                    <svg class="theme-icon-moon hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
                    </svg>
                </button>
                <div id="navbar-user" class="flex items-center"></div>
            </div>
        </div>
    </div>
</nav>
```

**Step 2: Update hero section**

Replace hero section with:

```html
<!-- Hero Section -->
<div class="hero-premium text-white py-24 relative">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        <h1 class="text-5xl font-bold mb-6 tracking-tight animate-fade-in-up">Transform Your Content</h1>
        <p class="text-xl opacity-90 mb-10 max-w-2xl mx-auto animate-fade-in-up animate-delay-1">
            Upload once, create everywhere. AI-powered content repurposing for busy marketers.
        </p>
        <a href="/upload.html" class="btn btn-lg bg-white/10 backdrop-blur border border-white/20 text-white hover:bg-white/20 hover:border-white/30 animate-fade-in-up animate-delay-2">
            Get Started
        </a>
    </div>
</div>
```

**Step 3: Update How It Works section**

Replace the How It Works grid items with card-premium class:

```html
<!-- How It Works -->
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
    <h2 class="text-3xl font-bold text-center mb-16 text-still-text">How It Works</h2>

    <div class="grid md:grid-cols-4 gap-6">
        <div class="card-premium p-6 text-center">
            <div class="w-14 h-14 bg-still-copper/10 rounded-xl flex items-center justify-center mx-auto mb-4">
                <span class="text-2xl font-bold text-still-copper">1</span>
            </div>
            <h3 class="font-semibold mb-2 text-still-text">Upload</h3>
            <p class="text-still-muted text-sm">Upload your webinar, podcast, PDF, or paste text</p>
        </div>

        <div class="card-premium p-6 text-center">
            <div class="w-14 h-14 bg-still-copper/10 rounded-xl flex items-center justify-center mx-auto mb-4">
                <span class="text-2xl font-bold text-still-copper">2</span>
            </div>
            <h3 class="font-semibold mb-2 text-still-text">Distill</h3>
            <p class="text-still-muted text-sm">AI extracts reusable quotes, stats, and stories</p>
        </div>

        <div class="card-premium p-6 text-center">
            <div class="w-14 h-14 bg-still-copper/10 rounded-xl flex items-center justify-center mx-auto mb-4">
                <span class="text-2xl font-bold text-still-copper">3</span>
            </div>
            <h3 class="font-semibold mb-2 text-still-text">Draft & Edit</h3>
            <p class="text-still-muted text-sm">Generate brand-aligned content for each channel</p>
        </div>

        <div class="card-premium p-6 text-center">
            <div class="w-14 h-14 bg-still-copper/10 rounded-xl flex items-center justify-center mx-auto mb-4">
                <span class="text-2xl font-bold text-still-copper">4</span>
            </div>
            <h3 class="font-semibold mb-2 text-still-text">Publish</h3>
            <p class="text-still-muted text-sm">Get fact-checked content ready for each platform</p>
        </div>
    </div>
</div>
```

**Step 4: Update Content Types section cards**

Replace with glass effect cards:

```html
<!-- Content Types -->
<div class="bg-still-card py-20 border-y border-still-border">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 class="text-3xl font-bold text-center mb-16 text-still-text">One Upload, Multiple Outputs</h2>

        <div class="grid md:grid-cols-3 gap-6">
            <div class="card-premium p-8">
                <h3 class="font-semibold text-lg mb-3 text-still-text">LinkedIn Posts</h3>
                <p class="text-still-muted mb-4">Engaging posts optimized for your target persona with hooks, bullets, and CTAs.</p>
                <span class="badge badge-copper">3 variations per job</span>
            </div>

            <div class="card-premium p-8">
                <h3 class="font-semibold text-lg mb-3 text-still-text">Blog Posts</h3>
                <p class="text-still-muted mb-4">SEO-friendly articles with proper structure, headings, and internal link suggestions.</p>
                <span class="badge badge-copper">800-1,200 words</span>
            </div>

            <div class="card-premium p-8">
                <h3 class="font-semibold text-lg mb-3 text-still-text">Email Campaigns</h3>
                <p class="text-still-muted mb-4">Subject lines, preview text, and body copy designed for conversions.</p>
                <span class="badge badge-copper">Ready to send</span>
            </div>
        </div>
    </div>
</div>
```

**Step 5: Update The Reserve section**

```html
<!-- The Reserve -->
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
    <div class="md:flex items-center gap-16">
        <div class="md:w-1/2 mb-8 md:mb-0">
            <h2 class="text-3xl font-bold mb-6 text-still-text">Your Reserve Grows</h2>
            <p class="text-still-muted mb-4 text-lg">
                Every piece of content you upload adds to your permanent Reserve of reusable stills -
                quotes, statistics, stories, and insights tagged by persona relevance.
            </p>
            <p class="text-still-muted mb-8">
                Generate fresh content anytime by combining stills from your Reserve. No new uploads needed.
            </p>
            <a href="/reserve.html" class="btn btn-copper">
                Browse Your Reserve
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                </svg>
            </a>
        </div>
        <div class="md:w-1/2">
            <div class="card-premium p-8 space-y-4">
                <div class="bg-still-bg p-4 rounded-lg border-l-4 border-l-still-amber">
                    <span class="badge badge-amber mb-2">DATA</span>
                    <p class="text-sm text-still-text">"40% reduction in staff documentation time..."</p>
                </div>
                <div class="bg-still-bg p-4 rounded-lg border-l-4 border-l-still-green">
                    <span class="badge badge-green mb-2">STORY</span>
                    <p class="text-sm text-still-text">"Sunrise Senior Living implemented this in 30 days..."</p>
                </div>
                <div class="bg-still-bg p-4 rounded-lg border-l-4 border-l-still-copper">
                    <span class="badge badge-copper mb-2">INSIGHT</span>
                    <p class="text-sm text-still-text">"The 3-step framework for reducing burnout..."</p>
                </div>
            </div>
        </div>
    </div>
</div>
```

**Step 6: Update CTA section**

```html
<!-- CTA -->
<div class="hero-premium text-white py-20 relative">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        <h2 class="text-3xl font-bold mb-6">Ready to Multiply Your Content?</h2>
        <p class="text-xl opacity-90 mb-10">Upload your first piece and see the magic happen.</p>
        <a href="/upload.html" class="btn btn-lg bg-white/10 backdrop-blur border border-white/20 text-white hover:bg-white/20 hover:border-white/30">
            Upload Content Now
        </a>
    </div>
</div>
```

**Step 7: Update Footer**

```html
<!-- Footer -->
<footer class="bg-still-card text-still-muted py-10 border-t border-still-border">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <p class="text-sm">&copy; 2025 Still. All rights reserved.</p>
    </div>
</footer>
```

**Step 8: Commit**

```bash
git add frontend/index.html
git commit -m "feat(ui): apply Liquid Premium design to landing page"
```

---

## Task 10: Create Shared Navigation Component File

To avoid duplicating navigation updates across all 18 HTML files, we'll extract common HTML patterns.

**Files:**
- Create: `frontend/static/components.js`

**Step 1: Create components.js with navigation render function**

```javascript
// Premium Navigation Component
function renderPremiumNav(activePage = '') {
    const navLinks = [
        { href: '/upload.html', label: 'Upload' },
        { href: '/reserve.html', label: 'Reserve' },
        { href: '/workshop.html', label: 'Workshop' },
        { href: '/calendar.html', label: 'Calendar' },
        { href: '/autopilot.html', label: 'Autopilot' },
        { href: '/analytics.html', label: 'Analytics' },
        { href: '/settings.html', label: 'Settings' },
    ];

    const linksHtml = navLinks.map(link => {
        const isActive = link.href.includes(activePage);
        return `<a href="${link.href}" class="nav-link${isActive ? ' active' : ''}">${link.label}</a>`;
    }).join('');

    return `
        <nav class="nav-premium">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between h-16">
                    <div class="flex items-center space-x-8">
                        <a href="/" class="flex items-center">
                            <img src="/static/images/Still Logo.svg" alt="Still" class="h-12">
                        </a>
                        <div class="hidden md:flex space-x-1">
                            ${linksHtml}
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <button onclick="ThemeManager.toggle()" class="theme-toggle-premium" title="Toggle light/dark mode">
                            <svg class="theme-icon-sun" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
                            </svg>
                            <svg class="theme-icon-moon hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
                            </svg>
                        </button>
                        <div id="navbar-user" class="flex items-center"></div>
                    </div>
                </div>
            </div>
        </nav>
    `;
}

// Initialize navigation on page load
document.addEventListener('DOMContentLoaded', () => {
    const navContainer = document.getElementById('nav-container');
    if (navContainer) {
        const currentPage = window.location.pathname.split('/').pop().replace('.html', '');
        navContainer.innerHTML = renderPremiumNav(currentPage);
    }
});
```

**Step 2: Commit**

```bash
git add frontend/static/components.js
git commit -m "feat(ui): add shared navigation component"
```

---

## Task 11: Update Upload Page

**Files:**
- Modify: `frontend/upload.html`

**Step 1: Add components.js script and replace nav with container**

In `<head>`, add after auth.js:
```html
<script src="/static/components.js"></script>
```

Replace `<nav>...</nav>` with:
```html
<div id="nav-container"></div>
```

**Step 2: Update drop zone to use premium styles**

Replace the drop zone div:
```html
<div class="dropzone-premium" id="drop-zone">
    <input type="file" id="file-input" class="hidden" multiple
           accept=".mp4,.mov,.avi,.webm,.mp3,.wav,.m4a,.pdf,.txt,.md,.docx,.png,.jpg,.jpeg,.gif,.webp">
    <div class="space-y-3">
        <svg class="dropzone-icon" stroke="currentColor" fill="none" viewBox="0 0 48 48">
            <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <p class="text-still-muted">
            <label for="file-input" class="text-still-copper font-medium cursor-pointer hover:text-still-amber">Upload files</label>
            or drag and drop
        </p>
        <p class="text-sm text-still-muted">Video, Audio, PDF, Word, Images, or Text (max 100MB per file)</p>
        <p class="text-xs text-still-disabled">Select up to 5 files for batch processing</p>
    </div>
</div>
```

**Step 3: Update tabs to premium style**

Replace tab buttons container:
```html
<div class="tabs-premium mb-6">
    <button id="tab-file" class="tab-premium active" onclick="showTab('file')">
        Full Pipeline
    </button>
    <button id="tab-text" class="tab-premium" onclick="showTab('text')">
        Paste Text
    </button>
    <button id="tab-quick" class="tab-premium" onclick="showTab('quick')">
        Quick Distill
    </button>
</div>
```

**Step 4: Update form inputs**

Replace input/select/textarea elements with premium classes:
- Add `input-premium` class to all text inputs
- Add `input-premium select-premium` classes to selects
- Add `input-premium` class to textareas

**Step 5: Update submit button**

```html
<button type="submit" id="submit-btn" class="btn btn-primary btn-lg w-full">
    Start Processing
</button>
```

**Step 6: Commit**

```bash
git add frontend/upload.html
git commit -m "feat(ui): apply Liquid Premium design to upload page"
```

---

## Tasks 12-18: Update Remaining Pages

Apply the same pattern to each remaining page:
1. Add `<script src="/static/components.js"></script>` to head
2. Replace `<nav>` with `<div id="nav-container"></div>`
3. Update cards to use `card-premium` class
4. Update buttons to use `btn btn-*` classes
5. Update inputs to use `input-premium` class
6. Update tabs to use `tabs-premium` and `tab-premium` classes
7. Update drop zones to use `dropzone-premium` class

**Pages to update:**
- `results.html`
- `status.html`
- `reserve.html`
- `library.html`
- `workshop.html`
- `settings.html`
- `analytics.html`
- `autopilot.html`
- `calendar.html`
- `batch-status.html`
- `brand-voice.html`
- `personas.html`
- `remix.html`
- `swipes.html`
- `login.html`
- `register.html`

Each page commit:
```bash
git add frontend/<page>.html
git commit -m "feat(ui): apply Liquid Premium design to <page> page"
```

---

## Task 19: Final Theme Testing

**Step 1: Test dark mode**
- Open app in browser
- Verify all colors render correctly
- Check glassmorphism effects on cards
- Verify hover states and animations work
- Check navigation active state glow

**Step 2: Test light mode**
- Toggle to light theme
- Verify all colors adapt correctly
- Check contrast ratios are accessible
- Verify glassmorphism adapts to light mode

**Step 3: Test responsive**
- Check mobile navigation
- Verify cards stack properly on mobile
- Test touch interactions on mobile

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(ui): complete Liquid Premium UI facelift"
```

---

## Summary

This plan transforms Still from a functional MVP to a premium SaaS with:

1. **Refined color palette** - Richer darks, warmer accents, proper zinc scale
2. **Glassmorphism** - Frosted glass effects on cards and navigation
3. **Micro-animations** - Fade-in, scale, glow pulse effects
4. **Premium buttons** - Gradient fills, glow on hover, proper states
5. **Enhanced inputs** - Copper focus glow, smooth transitions
6. **Premium navigation** - Sticky glass nav, active indicator glow
7. **Hero sections** - Animated gradient backgrounds
8. **Consistent badges/tags** - Proper color-coded system
9. **Drop zones** - Premium dashed borders with active states
10. **Loading states** - Shimmer skeletons, glowing spinners

Total estimated changes: ~2500 lines of CSS, ~500 lines per HTML file (18 files)

---

Plan complete and saved to `docs/plans/2025-12-26-liquid-premium-ui-facelift.md`.

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
