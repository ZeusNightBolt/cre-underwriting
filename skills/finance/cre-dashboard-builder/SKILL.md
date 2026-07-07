---
name: cre-dashboard-builder
description: "Generate anti-slop CRE dashboards from underwriting analysis. 10-tab HTML with Georgia/Inter typography, dark theme, mobile-responsive KPI grids. Wraps cre_underwriting.dashboard.generate_dashboard()."
version: 1.0.0
metadata:
  hermes:
    tags: [cre, dashboard, html, anti-slop, vercel]
    related_skills: [deal-underwriter, vercel-deploy]
---

# CRE Dashboard Builder

Generates a 10-tab anti-slop CRE dashboard from underwriting analysis. Wraps `cre_underwriting.dashboard.generate_dashboard()`.

## Quick Start

```bash
python3 scripts/build_dashboard.py --input analysis.json --output dashboard.html
```

## Input Contract

A complete analysis JSON from `deal-underwriter`:

```json
{
  "convexity": { "verdict": "PURSUE AT $380K", "convexity_ratio": 1.85, "scenario_analysis": {...} },
  "enhanced": { "moat_score": 14, "moats": {...}, "offers": [...] },
  "environmental": { "flood_zone": {...}, "ust_risk": "low", "economic_profile": {...} },
  "comps": { "comps": [...] }
}
```

## Output

Single self-contained HTML file with:
- 10 tabs: Scenarios, Valuation, Divergence, Moats, Offers, Risks, Demographics, Environmental, Comps, Recommendation
- Anti-slop design: dark theme (#0D0D0D background), Georgia/Inter/JetBrains Mono typography
- Mobile-responsive: 2-col KPI grid at 375px, 44pt touch targets, 16px+ fonts
- No external dependencies (inline CSS/JS)

## Design Rules (enforced)

- Typography: Georgia for numbers, Inter for labels, JetBrains Mono for codes only
- Colors: bg #0D0D0D, surface #141414, accent #C96442 (terracotta)
- Cards: linear-gradient, 1px border, 6px radius — NO glassmorphism, NO border-left accents
- KPI grid: 1px gap, border-radius 6px, overflow hidden
- ALL CAPS labels: letter-spacing 0.06em-0.1em
- tabular-nums on every financial value

## Pitfalls

1. **Mobile KPI grid**: Never 1-col at 375px. Minimum 2 columns to prevent text overlap.
2. **Type guards**: `$()` and `pct()` must handle null/undefined — `.toFixed is not a function` crashes.
3. **iOS zoom**: All interactive elements need font-size ≥16px.
4. **Tab buttons**: Need `font-size: 16px` minimum to prevent iOS zoom-on-focus.


---
## Project Specialization: cre-underwriting
*Specialized: 2026-05-13 12:53*
*Master: finance/cre-dashboard-builder*

> ⚠ This is a specialized copy. Changes to the master skill do NOT propagate here.
> To update: re-run `skill_specialize.py copy` with `--force`.
