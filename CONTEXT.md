# cre-underwriting — Local Context

> Referenced by `cre-underwriting` skill. Version-specific details, state overrides, and deal-specific notes live here, not in new skills.

## Current State (May 13, 2026)

- **Pipeline version**: v3.1 (12-node DAG via `orchestrator_v3.py`)
- **Dashboard design**: Anthropic Editorial Dark Theme v3 (DM Serif Display + Source Serif 4 + noise texture + staggered reveals)
- **Dashboard skill**: `cre-dashboard` v2 (finance/cre-dashboard)
- **Recent deals**:
  - 519 Millburn Ave, Short Hills, NJ (39473852) → https://millburn.vercel.app
  - 6 Crown Point Rd, West Deptford, NJ (40480939) → https://crown-point.vercel.app
- **Anthropic skills installed**: frontend-design, web-artifacts-builder, webapp-testing, brand-guidelines

## Post-Pipeline Corrections (MANDATORY — orchestrator_v3 has 4 known bugs)

After `EnhancedPipelineOrchestrator().run()`, always fix these before dashboard generation:

1. **SC geography fallback**: `r['home_price_appreciation']` and `r['demographics']` hard-fallback to Greenville SC (zip 29605, Greenville MSA). Overwrite with correct MSA data for the deal's state.
2. **UST/gas station as asset**: `valuation.py:detect_licenses()` values USTs at +$50K-$200K. For former gas stations, replace with negative $25K-$120K liability.
3. **cap_rate_pct: None → crash**: Dashboard `_build_kpi_grid()` crashes on `None` format. Set all `cap_rate_pct` to `0.0` in `enhanced.offers.points`.
4. **Scenario override**: Orchestrator generates generic e-commerce/rate-shock scenarios. Overwrite `r['property_specific_scenarios']` and `r['convexity']` with deal-specific scenarios.

## Known Issues

1. `enhanced.py:129` — crashes on `days_on_market=None`. Always set in deal JSON.
2. `loopnet_utils.detect_tax_bomb()` — NJ/PA only. For SC/NC/GA/FL, build manual analysis.
3. `setuptools.backends` — pip install -e fails. Workaround: PYTHONPATH.
4. Frontier threshold can be None — bug in `_build_frontier_data()`.
5. License detection false positives on "ust" → "investment" — fixed with `\b` boundaries.
6. Moats scored as generic 8-dimension template unless replaced with property-type-specific dimensions.

## Environment

```bash
PYTHONPATH=~/cre-underwriting/scripts:~/cre-underwriting/src
Firefox BiDi: DISPLAY=:0 /usr/lib/firefox/firefox --remote-debugging-port=9222
Vercel deploy: npx vercel deploy --prod --yes (NOT Python wrapper)
Cleanup: fuser -k 9222/tcp
```

## Dashboard Design System (v3 — Anthropic Editorial Dark)

- **Fonts**: DM Serif Display (values/headings) + Source Serif 4 (body) + Geist Mono (data/labels)
- **Colors**: Anthropic palette — orange #d97757, blue #6a9bcc, green #788c5d
- **Background**: #0d0c0a + SVG noise texture overlay (0.03 opacity)
- **Layout**: Asymmetric hero (1.2fr/0.8fr) with gradient accent line
- **Motion**: Staggered fadeUp reveals (0.1s animation-delay increments)
- **Reference skill**: `cre-dashboard` at ~/.hermes/skills/finance/cre-dashboard/
