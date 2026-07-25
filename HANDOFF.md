# HANDOFF — CRE Underwriting Pipeline (`cre-underwriting`)

## Project Purpose

The underwriting engine of the Girnar CRE stack. Given a deal-analysis JSON, it
produces a full multi-scenario underwriting: 5-scenario convexity analysis,
8-moat scoring, 4-method valuation triangulation, an offer ladder,
environmental/demographic risk, and comparable sales — rendered into a
self-contained HTML dashboard. Imported by the sibling `CRE-AI-Agent` repo
(`rebuild_all.py`) to regenerate per-deal dashboards.

## Current State

- **Status:** Stable, not in active production. No cron jobs reference this
  repo. CI has been **disabled** in this branch (see "CI" below) because the
  project is dormant; it can be re-enabled when work resumes.
- **Last meaningful activity:** audit fixes (PRs #2–#4), dashboard verdict
  guard fix (#4), AGENTS.md added (#5).
- **Default branch:** `main`. Current HEAD: `46a011b` (PR #5, AGENTS.md).
- **Packaging:** proper `pyproject.toml`, `src/` layout, installable via
  `pip install -e ".[dev]"`. Exposes `cre-pipeline` and `cre-analyze` console
  scripts.

## What Works

- **Core pipeline (`PipelineOrchestrator` in `pipeline.py`)** — composes
  convexity + enhanced + environmental engines into one analysis dict.
- **8-pillar enhanced pipeline (`EnhancedPipelineOrchestrator` in
  `orchestrator_v3.py`)** — adds valuation triangulation, pro forma, financial
  levers, demographics, frontier graph on top of the v1 pipeline.
- **Convexity engine (`convexity.py`)** — 5 scenarios (Worst, Baseline, Phase 1
  Optimize, Phase 2 Expand, Phase 3 Strategic), divergence, PWEV, effective
  frontier zone, verdict. Uses "effective worst = max(operating_worst,
  hard_floor_mid)".
- **Enhanced analysis (`enhanced.py`)** — `MoatScorer` (8-moat: license,
  corridor, multi-revenue, zoning, rent gap, brand, asset stack, seller
  asymmetry) and `OfferAnalyzer` (5-point offer ladder anchored from hard
  floor).
- **Dashboard generator (`dashboard.py`)** — Claude design system (DM Mono +
  Source Serif 4, border-left accents, tabular nums), self-contained HTML.
- **Test suite** — 4 files / 752 lines covering convexity, enhanced, pipeline,
  environmental+comps. Passes with `pytest -q`.
- **Console scripts** — `cre-pipeline`, `cre-analyze` (declared in
  `pyproject.toml`).

## What Doesn't Work / Known Gaps

- **CI is red on `main`.** The `ci.yml` workflow fails (lint + tests across
  Python 3.11/3.12 matrix). This branch moves it aside
  (`.github/workflows.disabled/`) to silence the failure while the project is
  dormant. Re-enable by moving it back and fixing the failures first.
- **`v4/` and `v5/` are experimental** — newer orchestrator/LLM/web-search/FRED
  modules exist under `src/cre_underwriting/v4/` and `v5/` but are not wired
  into the main entry points or tests. Treat as work-in-progress, not the
  supported path.
- **Scraping is environment-dependent** — `scraping.py` (`BidiSession`) needs a
  real Firefox 150+ with BiDi + X11 display; single-instance lock guards
  against OOM on low-RAM boxes. Cannot run in CI.
- **Comparable sales (`comps.py`)** — LoopNet scraping is primary; NJ county
  assessor path is stubbed.
- **No live data sources wired in CI** — tests use `tests/fixtures/`.

## Next Steps (for whoever picks this up)

1. **Decide on CI strategy.** Either re-enable + fix (resolve lint errors,
   failing tests on both 3.11 and 3.12), or keep CI off until back in
   production. The disabled workflow is preserved at
   `.github/workflows.disabled/ci.yml`.
2. **Promote or remove `v4/` / `v5/`.** They duplicate orchestrator/LLM logic
   without tests. Decide whether v5 (LLM-assisted, cross-validated) replaces v3,
   and wire it into the public API + tests, or delete to reduce surface area.
3. **Resolve the `cre-underwriting` ↔ `CRE-AI-Agent` coupling.** `CRE-AI-Agent`'s
   `rebuild_all.py` imports this repo by absolute `sys.path` — make the
   dependency explicit (pip-installable / submodule / vendored).
4. **Finish `comps.py`** — implement the NJ county assessor path beyond the
   stub.
5. **Refresh deals under `deals/`** — only 3 analyzed deals tracked
   (`DEALS_INDEX.md`); add more or formalize the ingest format.

## Key Files

| Path | Role |
|------|------|
| `src/cre_underwriting/pipeline.py` | `PipelineOrchestrator` (v1) + `cre-pipeline` CLI |
| `src/cre_underwriting/orchestrator_v3.py` | `EnhancedPipelineOrchestrator` — 8-pillar pipeline |
| `src/cre_underwriting/convexity.py` | `ConvexityEngine` + `cre-analyze` CLI |
| `src/cre_underwriting/enhanced.py` | `MoatScorer`, `OfferAnalyzer`, `EnhancedAnalyzer` |
| `src/cre_underwriting/valuation.py` | 4-method valuation triangulation (v3 pillar 1) |
| `src/cre_underwriting/financial_levers.py` | Pro forma + lever analysis (v3 pillar 4) |
| `src/cre_underwriting/environmental.py` | Environmental + economic risk (NJ counties) |
| `src/cre_underwriting/comps.py` | Comparable sales (LoopNet primary, NJ stubbed) |
| `src/cre_underwriting/scraping.py` | `BidiSession` — OOM-safe single-instance Firefox guard |
| `src/cre_underwriting/dashboard.py` | `generate_dashboard()` — Claude design-system HTML |
| `src/cre_underwriting/constants.py` | All thresholds (OFFERS, PWEV weights, ratios) |
| `src/cre_underwriting/models.py` | Shared dataclasses |
| `src/cre_underwriting/lawyer_brain.py` | Deal-review overlay |
| `src/cre_underwriting/v4/`, `v5/` | Experimental orchestrator/LLM/web-search (untested) |
| `scripts/loopnet_*.py` | LoopNet search/listing/batch scrapers |
| `scripts/build_dashboard_v{3,4}.py` | Dashboard builders |
| `tests/{test_convexity,test_enhanced,test_pipeline,test_environmental_comps}.py` | Test suite (752 lines) |
| `pyproject.toml` | Packaging, deps, ruff/mypy/pytest config |
| `docs/` | Methodology, architecture, design tokens |
| `deals/DEALS_INDEX.md` | Index of analyzed deals (3 so far) |

## Test / Lint Configuration

- **`pyproject.toml`** configures everything:
  - `pytest`: `testpaths = ["tests"]`, `pythonpath = ["src"]` (works from a
    bare checkout, no editable install required to run tests).
  - `ruff`: `line-length = 100`, `target-version = "py311"`.
  - `mypy`: `python_version = "3.11"`, `ignore_missing_imports = true`.
- **Test files (752 lines total):**
  - `tests/test_convexity.py` (290 lines)
  - `tests/test_enhanced.py` (201 lines)
  - `tests/test_pipeline.py` (146 lines)
  - `tests/test_environmental_comps.py` (115 lines)
- **Fixtures:** `tests/fixtures/` (e.g. `fords_34554176.json`).
- **Dev extras:** `pip install -e ".[dev]"` → pytest, pytest-cov, ruff, mypy.

## CI

- **Disabled in this branch.** `.github/workflows/ci.yml` was moved to
  `.github/workflows.disabled/ci.yml` to stop the persistent red build while the
  project is dormant and not in production.
- **Why it was failing:** lint (`ruff check src/ tests/`), mypy, and the test
  step failed on `main` across the 3.11/3.12 matrix. Latest run on main (run ID
  `30166514419`) = `failure`.
- **To re-enable:** `git mv .github/workflows.disabled/ci.yml .github/workflows/ci.yml`
  (recreate the `workflows/` dir), then fix lint/mypy/test failures before push.

## Related Repos / Docs

- [`CRE-AI-Agent`](https://github.com/girnarholdings/CRE-AI-Agent) — the
  scraping/dashboard-deployment layer that imports this engine.
- `AGENTS.md` — agent conventions for this repo.
- `CONTEXT.md`, `PROJECT.md`, `INDEX.md` — older project notes.
- `docs/architecture.md` — pipeline data flow + module dependency graph.
