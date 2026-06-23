---
name: The Midnight Console
description: A sleek, dark cockpit for single-user productivity with ambient glassmorphism and laser-sharp contrast.
colors:
  midnight-base: "#0d150f"
  translucent-obsidian: "#0f1712"
  muted-glass-card: "#121d16"
  accent-gold: "#c9a227"
  accent-gold-hover: "#dbb63b"
  warning-crimson: "#ef4444"
  subtle-frost-border: "#ffffff14"
  frost-white: "#f3f4f6"
  cool-gray: "#9ca3af"
  muted-charcoal: "#6b7280"
typography:
  display:
    fontFamily: "Outfit, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.2
  headline:
    fontFamily: "Outfit, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.3
  title:
    fontFamily: "Outfit, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Outfit, sans-serif"
    fontSize: "16px"
    fontWeight: 500
    lineHeight: 1.5
  label:
    fontFamily: "Outfit, sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-send:
    backgroundColor: "{colors.accent-gold}"
    textColor: "{colors.midnight-base}"
    rounded: "{rounded.md}"
    padding: "0 20px"
  button-log-habit:
    backgroundColor: "rgba(201, 162, 39, 0.12)"
    textColor: "{colors.accent-gold}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  button-delete:
    backgroundColor: "transparent"
    textColor: "{colors.muted-charcoal}"
    rounded: "{rounded.xs}"
    padding: "4px"
  chat-input:
    backgroundColor: "#ffffff0d"
    textColor: "{colors.frost-white}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
  nav-link:
    backgroundColor: "transparent"
    textColor: "{colors.cool-gray}"
    rounded: "{rounded.full}"
    padding: "6px 18px"
  nav-link-active:
    backgroundColor: "{colors.accent-gold}"
    textColor: "{colors.midnight-base}"
    rounded: "{rounded.full}"
    padding: "6px 18px"
---

# Design System: The Midnight Console

## 1. Overview

**Creative North Star: "The Midnight Console"**

A sleek, dark cockpit for personal productivity, designed for single-user daily tracking. It balances a high-contrast data layout with a single solid gold/amber highlight and sharp, clear divisions, ensuring the user can digest their day in under 10 seconds. Every visual element has a functional purpose, prioritizing clean typography and flat, clean layouts over heavy borders.

This system rejects typical SaaS clutter, fitness neon, warm-neutral body backgrounds, gradients, and backdrop blurs. It feels intentional, fast to use, and personal.

**Key Characteristics:**
- Deep, dark forest base (`#0d150f`) with solid opaque green panels.
- Solid Accent Gold (`#fbbf24`) for primary highlights, buttons, and active states.
- High-density data layout utilizing the clean, geometric Outfit typeface.
- Tactile, responsive micro-animations that respect accessibility preferences.

## 2. Colors

A dark green forest theme featuring a single gold/amber highlight and clean ice-white tints.

### Primary
- **Accent Gold** (`#fbbf24`): The primary accent color used for main actions, active navigation states, timestamps, due dates, input focus, and key highlights.

### Secondary
- **Warning Crimson** (`#ef4444`): Accent color reserved exclusively for destructive actions like delete buttons or cancel options.

### Neutral
- **Midnight Base** (`#0d150f`): Base background for the entire page, creating a deep dark green environment.
- **Translucent Obsidian** (`#142019`): Solid background for dashboard panels.
- **Muted Glass Card** (`#1b2a21`): Solid background for individual task, habit, and workout items.
- **Frost White** (`#f3f4f6`): Primary text color, offering excellent contrast on dark backgrounds.
- **Cool Gray** (`#9ca3af`): Secondary text color for description and metadata.
- **Muted Charcoal** (`#6b7280`): Muted text color for timestamps and inactive states.
- **Subtle Frost Border** (`#ffffff14`): Border stroke color for all panels, cards, and input fields (`rgba(255, 255, 255, 0.08)`).
- **Indigo Aura Border** (`#6366f126`): Glow border for dashboard components (`rgba(99, 102, 241, 0.15)`).

### Named Rules
**The 10% Accent Rule.** Accent colors (Gold, Red) should collectively occupy less than 10% of any screen. Their rarity ensures high visibility.
**The High-Contrast Text Rule.** All body copy must maintain a minimum contrast ratio of 4.5:1 against its background. Never use text lighter than `Cool Gray` (`#9ca3af`) on cards. Elements on solid Accent Gold background must use the dark green base color (`#0d150f`) to meet the contrast requirement.

## 3. Typography

**Display Font:** Outfit (with sans-serif fallback)
**Body Font:** Outfit (with sans-serif fallback)

**Character:** The geometric, modern Outfit typeface is used uniformly, varying only in size, weight, and opacity to establish hierarchy without visual noise.

### Hierarchy
- **Display** (700 weight, 24px, 1.2 line-height): Header title, styled with the primary gradient.
- **Headline** (600 weight, 18px, 1.3 line-height): Panel headings and main section headers.
- **Title** (600 weight, 16px, 1.4 line-height): Section titles, workout exercises.
- **Body** (500 weight, 14px, 1.5 line-height): Task titles, calendar items, habit names.
- **Label** (500 weight, 12px, 1.4 line-height): Metadata, descriptions, badges, and timestamps.

### Named Rules
**The Outfit Only Rule.** Do not introduce any other font families. All hierarchy must be expressed through Outfit's weight and opacity scale.

## 4. Elevation

The system uses a flat, layered strategy to build depth. Interactive panels sit over the deep space base utilizing flat, solid card backgrounds and subtle borders. Depth is conveyed strictly via borders and minimal elevation, avoiding any colored glow shadows or backdrop blurs.

### Shadow Vocabulary
- **Neutral Elevation Shadow** (`0 1px 2px rgba(0, 0, 0, 0.3)`): A subtle, neutral black shadow used sparingly for modal container depth.

### Named Rules
**The Frost Border Rule.** Elevation changes are denoted by subtle color differences and a translucent frost border (`rgba(255, 255, 255, 0.08)`), never solid black or high-contrast borders.

## 5. Components

### Buttons
- **Shape:** Rounded (12px, `var(--radius-md)` for send button; 8px, `var(--radius-sm)` for log habit).
- **Primary Send Button:** Uses a solid Accent Gold (`#fbbf24`) background, dark green text (`#0d150f`), and padding `0 20px`. On hover, shifts background color to a lighter gold (`#fcd360`).
- **Log Habit Button:** Uses a semi-transparent gold background (`rgba(251, 191, 36, 0.12)`), border `1px solid rgba(251, 191, 36, 0.25)`, and text color `#fbbf24`. On hover, transitions to solid Accent Gold (`#fbbf24`) background, dark green text (`#0d150f`). No glow shadow.
- **Delete Button:** Transparent background, `var(--text-muted)` text color. On hover, transitions to warning red text and `rgba(239, 68, 68, 0.1)` background.

### Inputs / Fields
- **Style:** Background `rgba(255, 255, 255, 0.05)`, border `1px solid var(--border-subtle)`, radius `12px` (`var(--radius-md)`), padding `12px 16px`.
- **Focus:** Transitions border color to primary Accent Gold (`#fbbf24`) with no glow ring.

### Cards / Containers
- **Corner Style:** Rounded `16px` (`var(--radius-lg)`) for major panels; `12px` (`var(--radius-md)`) for items.
- **Background:** Solid `#142019` for panels; solid `#1b2a21` for card items. No blur.
- **Border:** `1px solid rgba(255, 255, 255, 0.08)` (Subtle Frost). Hovering increases border color to `var(--text-muted)` for interaction feedback.

### Navigation
- **Style:** Outer nav pill with `rgba(255, 255, 255, 0.03)` background, 1px frost border, and `30px` radius. Links have `20px` radius.
- **Active State:** Background solid Accent Gold (`#fbbf24`) and dark green text (`#0d150f`). No gradient, no box shadow.

## 6. Do's and Don'ts

### Do:
- **Do** respect the user's reduced-motion preference by disabling transforms and transitions when requested.
- **Do** use `rgba(255, 255, 255, 0.08)` for container boundaries to maintain a soft glass border.
- **Do** use the Console Indigo/Laser Violet gradient (`#6366f1` to `#a855f7`) for primary call-to-actions and dashboard navigation highlights.

### Don't:
- **Don't** use Notion-style corporate blue or generic SaaS cream/beige backgrounds (`Obsidian light`, `Bear`, `Things 3`) which represent the generic AI app default.
- **Don't** use fitness-app neon orange (`Strava orange` or `MyFitnessPal`) or motivational gamification badges that create visual noise.
- **Don't** fall back to monospace "developer cosplay" hacker terminal green-on-black aesthetics.
- **Don't** add notification indicators, red badges, or infinite scroll elements that trigger user anxiety.
- **Don't** use backdrop-filter/blur, gradients, or colored/tinted glow shadows anywhere — flat opaque surfaces, solid accent colors, and neutral (black-only) shadows or no shadow.
