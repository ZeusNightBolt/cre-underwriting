# CRE Underwriting Pipeline

**Commercial real estate deal-analysis engine — convexity-driven, forensic-grade.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

This repo is the **underwriting engine** of the Girnar CRE stack. It ingests a
deal-analysis JSON and produces a full multi-scenario underwriting result with
convexity scoring, moat analysis, an offer ladder, environmental/demographic
risk, and comparable sales — rendered into a self-contained HTML dashboard. The
sibling repo
[`CRE-AI-Agent`](https://github.com/girnarholdings/CRE-AI-Agent) is the
scraping/dashboard-deployment layer that imports this engine.

## Architecture (1 paragraph)

`PipelineOrchestrator` (v1, in `pipeline.py`) and
`EnhancedPipelineOrchestrator` (v3, in `orchestrator_v3.py`) compose four core
engines — `ConvexityEngine` (5-scenario worst→baseline→Phase1/2/3 analysis,
divergence, PWEV, verdict), `EnhancedAnalyzer` / `MoatScorer` /
`OfferAnalyzer` (8-moat scoring + 5-point offer ladder), `environmental.py`
(FEMA flood, UST, county economics), and `comps.py` (comparable sales via
LoopNet Firefox BiDi scraping, primary) — into a single pipeline that returns
one analysis dict. `generate_dashboard()` renders that dict into a
self-contained, Claude-design-system HTML dashboard (DM Mono + Source Serif 4,
border-left accents, tabular nums). Entry points are exposed as `cre-pipeline`
and `cre-analyze` console scripts, and the engine is also imported directly by
`CRE-AI-Agent`'s `rebuild_all.py` to regenerate per-deal dashboards.

## Quick Start

```bash
git clone https://github.com/girnarholdings/cre-underwriting.git
cd cre-underwriting

# Install (dev extras include pytest, ruff, mypy)
pip install -e ".[dev]"

# Run the full pipeline on a test deal
cre-pipeline tests/fixtures/fords_34554176.json

# Or via Python API
python -c "
from cre_underwriting.orchestrator_v3 import EnhancedPipelineOrchestrator
orch = EnhancedPipelineOrchestrator()
result = orch.run('tests/fixtures/fords_34554176.json')
print(result['convexity']['verdict']['verdict'])
"
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `cre-pipeline <deal.json>` | Run the full underwriting pipeline on a deal JSON (console script) |
| `cre-analyze <deal.json>` | Convexity analysis only (console script) |
| `pytest -q` | Run the test suite (752 lines across 4 test files) |
| `ruff check src/ tests/` | Lint |
| `mypy src/ --ignore-missing-imports` | Type check |
| `python scripts/build_dashboard_v4.py` | Build a v4-style dashboard from a deal result |

## Usage

### Python API

```python
from cre_underwriting.pipeline import PipelineOrchestrator
from cre_underwriting.enhanced import MoatScorer, OfferAnalyzer
from cre_underwriting.dashboard import generate_dashboard

# Full pipeline (v1)
orch = PipelineOrchestrator()
result = orch.run("my_deal.json")
print(result["convexity"]["verdict"]["verdict"])  # "CONDITIONAL"

# 8-pillar enhanced pipeline (v3)
from cre_underwriting.orchestrator_v3 import EnhancedPipelineOrchestrator
v3 = EnhancedPipelineOrchestrator()
result = v3.run("my_deal.json")   # adds valuation triangulation, pro forma, levers

# Individual engines
moats = MoatScorer.score(deal_data)
offers = OfferAnalyzer.ladder(ask_price=799000, noi=57368, hard_floor_mid=530000)

# Render the HTML dashboard
html = generate_dashboard(result, title="6 Boonton Ave — Butler, NJ")
```

### CLI

```bash
cre-pipeline deal_analysis.json        # full pipeline
cre-analyze deal_analysis.json         # convexity only
```

## Project Structure

```
src/cre_underwriting/
├── __init__.py            # Public API surface
├── constants.py           # All thresholds (OFFERS, PWEV weights, scenario ratios)
├── models.py              # Shared dataclasses (Scenario, DealInput, VerdictOutput, …)
├── utils.py               # Address parsing (zero deps)
├── convexity.py           # ConvexityEngine — 5 scenarios, divergence, PWEV, verdict
├── enhanced.py            # MoatScorer (8-moat), OfferAnalyzer (offer ladder)
├── comps.py               # Comparable sales (LoopNet primary, NJ ACTB stubbed)
├── environmental.py       # Environmental + economic risk (NJ counties)
├── valuation.py           # 4-method valuation triangulation (v3 pillar 1)
├── financial_levers.py    # Pro forma + lever analysis (v3 pillar 4)
├── scraping.py            # BidiSession — single-instance Firefox guard (OOM-safe)
├── orchestrator_v3.py     # 8-pillar EnhancedPipelineOrchestrator
├── pipeline.py            # PipelineOrchestrator (v1) + main() CLI entry
├── lawyer_brain.py        # Deal-review "lawyer brain" overlay
├── dashboard.py           # generate_dashboard() — Claude-design-system HTML
└── v4/, v5/               # Newer orchestrator/LLM/web-search experiment dirs
scripts/
├── loopnet_search.py      # LoopNet search via Firefox BiDi
├── loopnet_listing.py     # LoopNet listing detail scraper
├── loopnet_batch.py       # Batch orchestration
├── loopnet_utils.py       # Shared BiDi lifecycle
├── build_dashboard_v3.py  # v3 dashboard builder
└── build_dashboard_v4.py  # v4 dashboard builder
skills/finance/            # Hermes skills: deal-underwriter, comp-finder, …
docs/                      # Methodology, architecture, design tokens
deals/                     # Per-deal deep dirs (listing.json, analysis.json, …)
tests/                     # 4 test files, fixtures under tests/fixtures/
```

## Documentation

- `docs/underwriting-playbook.md` — complete 19-section methodology
- `docs/architecture.md` — pipeline data flow + module dependency graph
- `docs/convexity-engine.md` — convexity math (effective worst, divergence, PWEV)
- `docs/claude-analysis-pattern.md` — 10-section complex-deal handoff template
- `docs/open-design-fusion.md` — dashboard design tokens

## Requirements

- Python 3.11+
- Core: `requests`, `beautifulsoup4`, `lxml`
- Scraping: Firefox 150+ with BiDi, `websockets`, X11 display
- Dev: `pytest`, `ruff`, `mypy` (via `pip install -e ".[dev]"`)

## Related

- [`CRE-AI-Agent`](https://github.com/girnarholdings/CRE-AI-Agent) — the
  scraping/dashboard-deployment layer that imports this engine via `rebuild_all.py`.
- `HANDOFF.md` — current project state, what works, what doesn't, next steps.
- `AGENTS.md` — conventions for AI agents working in this repo.

## License

MIT — see [LICENSE](LICENSE).
