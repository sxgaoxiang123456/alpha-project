---
name: Precision Finance
colors:
  surface: '#11131c'
  surface-dim: '#11131c'
  surface-bright: '#373943'
  surface-container-lowest: '#0c0e17'
  surface-container-low: '#191b25'
  surface-container: '#1d1f29'
  surface-container-high: '#282934'
  surface-container-highest: '#32343f'
  on-surface: '#e1e1ef'
  on-surface-variant: '#c3c5d9'
  inverse-surface: '#e1e1ef'
  inverse-on-surface: '#2e303a'
  outline: '#8d90a2'
  outline-variant: '#434656'
  surface-tint: '#b7c4ff'
  primary: '#b7c4ff'
  on-primary: '#002682'
  primary-container: '#0052ff'
  on-primary-container: '#dfe3ff'
  inverse-primary: '#004ced'
  secondary: '#b7c8e1'
  on-secondary: '#213145'
  secondary-container: '#3a4a5f'
  on-secondary-container: '#a9bad3'
  tertiary: '#ffb4a1'
  on-tertiary: '#611300'
  tertiary-container: '#bf3003'
  on-tertiary-container: '#ffddd5'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#dde1ff'
  primary-fixed-dim: '#b7c4ff'
  on-primary-fixed: '#001452'
  on-primary-fixed-variant: '#0038b6'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdbd2'
  tertiary-fixed-dim: '#ffb4a1'
  on-tertiary-fixed: '#3c0800'
  on-tertiary-fixed-variant: '#891e00'
  background: '#11131c'
  on-background: '#e1e1ef'
  surface-variant: '#32343f'
  market-up: '#F43F5E'
  market-down: '#10B981'
  market-warning: '#F59E0B'
  surface-lowest: '#020617'
  surface-base: '#0F172A'
  surface-raised: '#1E293B'
typography:
  display-price:
    fontFamily: JetBrains Mono
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-table:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  container-gap: 24px
  card-padding: 16px
  table-row-height: 40px
  stack-tight: 4px
  stack-md: 12px
---

## Brand & Style
The design system is engineered for **High-Velocity Financial Intelligence**. It targets professional traders and quantitative analysts who require rapid data synthesis without the cognitive fatigue associated with traditional, cluttered brokerage platforms.

The aesthetic follows a **Corporate / Modern** direction with a focus on **Information Density**. It utilizes a "Low Density" philosophy for layout—meaning generous margins between functional blocks—but "High Density" for the content within those blocks (tight tables, monospaced figures). This ensures that while the data is packed, the structural hierarchy remains calm and navigable.

**Design Principles:**
- **Analytical Clarity:** Use distinct surface tiers to separate AI-generated insights from raw market data.
- **Urgency through Semantics:** Color is used sparingly, reserved almost exclusively for market movement (Red/Up, Green/Down) and system alerts.
- **Precision:** Reliance on monospaced numerics and sharp, clean borders to evoke a sense of mathematical accuracy.

## Colors
The palette is optimized for long-duration monitoring. The **Default Dark Mode** uses a deep navy-slate base (`#020617`) to reduce eye strain, while the **Professional Blue** primary color acts as the "Action" anchor for interactive elements.

**A-Share Semantic Standards:**
- **Market Up:** `#F43F5E` (Vivid Red). In the A-share context, Red signifies gains.
- **Market Down:** `#10B981` (Emerald Green). Signifies losses.
- **Neutral/Stable:** `#94A3B8` (Slate Gray).

**Layering Logic:**
- **Surface Lowest:** Background for the entire application.
- **Surface Base:** Standard card and container background.
- **Surface Raised:** Tooltips, modals, and active state highlights.

## Typography
The system employs a dual-font strategy. **Hanken Grotesk** provides a modern, high-tech feel for headers and brand moments. **Inter** handles standard UI text for its exceptional legibility. 

Crucially, **JetBrains Mono** is used for all financial figures, price ticks, and percentage changes. This ensures that numbers remain tabular and do not "jump" during real-time updates, allowing traders to track digit changes purely by vertical alignment.

**Mobile Scaling:**
- Headlines scale down by a factor of 0.85x on mobile.
- `data-table` remains at 13px but allows for horizontal scrolling to preserve tabular integrity.

## Layout & Spacing
The layout uses a **Fixed Grid** approach for the main dashboard (1280px center-aligned) to ensure that complex data tables do not stretch awkwardly on ultra-wide monitors. 

**Grid Rhythm:**
- **Desktop:** 12-column grid, 24px gutters, 40px outer margins.
- **Information Density:** Vertical spacing within tables is kept to a strict 40px row height (`table-row-height`) to maximize the number of visible stocks on one screen.
- **Reflow:** On Tablet, the "Market Indices" (SH/SZ/CYB) stack from a horizontal row into a 2x2 or 1x3 vertical stack. On Mobile, the sidebar collapses into a bottom navigation bar.

## Elevation & Depth
In Dark Mode, depth is communicated through **Tonal Layers** rather than heavy shadows. 

1. **Level 0 (Background):** Deepest navy (`#020617`).
2. **Level 1 (Cards/Tables):** Slightly lighter slate (`#0F172A`).
3. **Level 2 (Active/Hover):** Thin, 1px borders using `#1E293B` to define boundaries.
4. **Popovers/Modals:** Use a subtle **Ambient Shadow** (0.2 opacity black) combined with a 1px border to ensure they separate from the base layers. 

Avoid glassmorphism for data-heavy sections to maintain maximum contrast and readability. Semi-transparent blurs are only permitted for the top navigation bar to indicate content scrolling underneath.

## Shapes
A **Soft (0.25rem)** roundedness is applied to buttons, input fields, and tags. Large containers and metric cards use **rounded-lg (0.5rem)**. 

This restrained rounding maintains a professional, "tool-like" feel, avoiding the overly consumer-friendly look of fully rounded "pill" shapes, except for specific status badges (e.g., "Market Open" status).

## Components

### Stock Data Tables
- **Header:** Sticky positioning, using `label-caps` typography with a subtle bottom border.
- **Cells:** Use `data-table` font. Price changes must be color-coded (Red/Green) with a "+" or "-" prefix.
- **Mini-Charts:** Sparklines embedded in rows should use a 2px stroke width, colored based on the net change of the period shown.

### Metric Cards
- **Style:** Flat background (`surface-base`) with a 1px border.
- **Hierarchy:** Title in `headline-md`, followed by a large `display-price`. 
- **Indicator:** A small percentage change badge in the top-right corner using the semantic market colors.

### Input Forms (Command Bar)
- **Style:** Large, centered search bar with a `surface-raised` background.
- **Command Suggestions:** As the user types (e.g., "Moutai"), show a dropdown list with stock codes (monospaced) and current prices.

### Alert Badges
- **Urgency Levels:** 
  - *Level 1 (Normal):* Primary Blue border.
  - *Level 2 (Warning):* Market-Warning fill with black text.
  - *Level 3 (Critical):* Market-Up (Red) pulsing background.

### Checkboxes & Radios
- Follow shadcn/ui defaults but use `primary_color_hex` for the checked state and a square-off shape (0.125rem radius) to match the professional aesthetic.