# Open Design Fusion — Dashboard Design Patterns

**Source:** [nexu-io/open-design](https://github.com/nexu-io/open-design) — 35K stars, 129 design systems, 31 skills. Open-source alternative to Claude Design.

## Fusion Pattern: Trading Terminal × Warm Editorial

### Design Tokens
```css
:root {
  --bg:        #0d0d0d;   /* Trading Terminal dark */
  --surface:   #141414;   /* Panel background */
  --surface2:  #1a1a1a;   /* Hover/alt */
  --border:    #2a2a2a;   /* 1px hairline grids */
  --text:      #faf9f5;   /* Warm ivory (not pure white) */
  --text2:     #b0aea5;   /* Warm silver */
  --text3:     #87867f;   /* Stone gray */
  --accent:    #c96442;   /* Terracotta — CRE warmth */
  --positive:  #00d4aa;   /* Cyan gain */
  --negative:  #ff4757;   /* Coral loss */
  --warn:      #ffb800;   /* Amber caution */
}
```

### Font Stack
- **KPI numbers**: Georgia, Times New Roman, serif (weight 500, NOT bold)
- **Tables/monetary**: JetBrains Mono, IBM Plex Mono, DM Mono
- **Labels/body**: Inter, -apple-system, system-ui, sans-serif

### Anti-Slop Rules (NON-NEGOTIABLE)
- ❌ NO glassmorphism / backdrop-blur anywhere
- ❌ NO purple→pink or blue→cyan gradients
- ❌ NO 4px left-border accent cards
- ❌ NO emoji icon strips
- ❌ NO colored progress bars under KPI numbers
- ❌ NO Tailwind indigo (#6366f1, #4f46e5)
- ✅ Accent used ≤ 2 visible times per screen
- ✅ `font-variant-numeric: tabular-nums` on ALL financial values
- ✅ 1px hairline KPI grid (gap: 1px, background: var(--border))
- ✅ Ring shadows (0px 0px 0px 1px) instead of drop shadows
- ✅ `prefers-reduced-motion: reduce` respected

### Key Patterns
1. **Ambient glow**: `radial-gradient(1200px 500px at 20% -10%, rgba(201,100,66,0.08), transparent), var(--bg)`
2. **Card gradient**: `linear-gradient(140deg, var(--surface), color-mix(in srgb, var(--surface2) 94%, transparent))`
3. **KPI grid**: `gap: 1px; background: var(--border)` — the gap IS the grid line
4. **Tab active**: `border-bottom: 2px solid var(--accent)` — no pill backgrounds
5. **Verdict banner**: Terracotta border + subtle background, monospace, letter-spacing 0.06em

### Formatter Guard (MANDATORY)
```js
const $ = (n, d = 0) => {
  if (typeof n !== "number" && typeof n !== "bigint") return String(n);
  if (Math.abs(n) >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
  if (Math.abs(n) >= 1e3) return "$" + (n / 1e3).toFixed(d > 0 ? d : 0) + "K";
  return "$" + n.toFixed(d);
};
```

### When to Use Each Accent
| Context | Accent | Rationale |
|---------|--------|-----------|
| CRE/Real Estate | #c96442 (terracotta) | Warm, earthy, property-appropriate |
| Financial/Earnings | #3ebd93 (green) | Trading/growth context |
| General dark dashboard | #00d4aa (cyan) | Neutral, high-tech |

## Pattern Sources in open-design repo

| Pattern | Source File | What It Provides |
|---------|-------------|------------------|
| Trading Terminal | `design-systems/trading-terminal/DESIGN.md` | Dark palette, monospace tables, card gradients |
| Warm Editorial | `design-systems/claude/DESIGN.md` | Terracotta accent, serif authority, warm neutrals |
| Live Dashboard | `skills/live-dashboard/SKILL.md` | KPI grid, tabular-nums, anti-slop rules |
| Anti-AI-Slop | `craft/anti-ai-slop.md` | 7 cardinal sins + soft tells |
| Animation | `craft/animation-discipline.md` | 150ms micros, prefers-reduced-motion |
