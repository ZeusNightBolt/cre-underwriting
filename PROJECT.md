---
name: cre-underwriting
display_name: CRE Underwriting
status: active
created: 2026-05-13T12:51:52.056916
objective: End-to-end CRE deal pipeline — scrape LoopNet → parse → underwrite → dashboard → deploy
tags: [cre, underwriting, loopnet, convexity, dashboard, nj, pa, tier-2, tier-3]
---

# CRE Underwriting v3

**Status:** active
**Package:** `cre-underwriting` (pip-installable, GitHub: ZeusNightBolt/cre-underwriting)
**Markets:** NJ/PA/Tier-3 under $2M
**Skill:** Consolidated `cre-underwriting` v3 (8-pillar framework: scrape → parse → underwrite → comps → environmental → dashboard → deploy → verify)

## Pipeline Summary

Single consolidated pipeline: LoopNet Firefox BiDi scrape → structured parsing (condo/tax-bomb/hidden-NOI detection) → full underwriting (5 scenarios, 4 valuations, 8 moats, convexity, offer ladder) + environmental + comps → 10-tab anti-slop dashboard → Vercel deploy.

Supporting utilities: `loopnet-scraper` (standalone Firefox BiDi scraper, kept as separate skill for reuse).

## Key Decisions

- Firefox BiDi is the ONLY working method for LoopNet (Akamai blocks everything else)
- Underwriting engine is a pip-installable Python package at `~/cre-underwriting/`
- All 7 legacy discrete skills absorbed into one consolidated `cre-underwriting` v3 skill (May 13, 2026)
- `loopnet-scraper` retained as standalone utility for scraping without underwriting
- Dashboard follows anti-slop design rules (Georgia/Inter, dark theme, 2-col KPI grid minimum)
- Convexity uses hard floor as effective worst case
- Phase 3 Strategic (moonshot) excluded from convexity best-case
- NNN vs Gross lease distinction is critical for NOI modeling

## Data Architecture

Per-deal deep nesting at `os/projects/cre-underwriting/deals/<id-slug>/`:
- `listing.json` — Raw LoopNet scrape data
- `analysis.json` — Full underwriting output
- `environmental.json` — Environmental site assessment
- `dashboard.html` — Self-contained 10-tab dashboard

## Geographic Tiers

| Tier | Area | Min Cap Rate (Stabilized) |
|------|------|--------------------------|
| 1 | NJ: Middlesex-Somerset-etc | 5.5% |
| 2 | Eastern PA, DE, Southern NJ | 7.0% |
| 3 | NC/SC/GA/FL growth | 6.5% w/ mitigant |
