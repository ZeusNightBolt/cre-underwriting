# CRE Underwriting Pipeline

**Commercial real estate deal analysis engine — convexity-driven, forensic-grade.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What It Does

Analyzes CRE deals through a 5-scenario convexity framework:

- **5-Scenario Architecture** — Worst, Baseline, Phase 1 Optimize, Phase 2 Expand, Phase 3 Strategic
- **Convexity Engine** — Effective worst, divergence metrics, PWEV, effective frontier zone
- **8-Moat Scoring** — License, corridor, multi-revenue, zoning, rent gap, brand, asset stack, seller asymmetry
- **Offer Ladder** — 5-point price staircase anchored from hard floor with cap rates at each level
- **4-Method Triangulation** — Asset-based, income-based, revenue multiple, probability-weighted EV
- **Environmental & Demographic Risk** — FEMA flood, UST, county economic profiles
- **Comparable Sales** — Zillow integration (LoopNet + NJ ACTB stubbed)

## Quick Start

```bash
git clone https://github.com/ZeusNightBolt/cre-underwriting.git
cd cre-underwriting
pip install -e ".[all]"

# Run on a test deal
cre-pipeline tests/fixtures/fords_34554176.json
```

## Usage

### Python API

```python
from cre_underwriting.pipeline import PipelineOrchestrator
from cre_underwriting.enhanced import MoatScorer, OfferAnalyzer

# Full pipeline
orch = PipelineOrchestrator()
result = orch.run("my_deal.json")
print(result["convexity"]["verdict"]["verdict"])  # "CONDITIONAL"
print(result["enhanced"]["moats"]["total_score"])  # 15

# Individual engines
moats = MoatScorer.score(deal_data)
offers = OfferAnalyzer.ladder(ask_price=799000, noi=57368, hard_floor_mid=530000)
```

### CLI

```bash
# Run full pipeline
cre-pipeline deal_analysis.json

# Convexity analysis only
cre-analyze deal_analysis.json
```

## Project Structure

```
src/cre_underwriting/
├── __init__.py          # Public API
├── constants.py         # All thresholds and configuration
├── models.py            # Shared dataclasses
├── convexity.py         # ConvexityEngine, divergence, PWEV, verdict
├── enhanced.py          # MoatScorer, OfferAnalyzer, EnhancedAnalyzer
├── comps.py             # Comparable sales (Zillow)
├── environmental.py     # Environmental + economic risk (NJ counties)
├── pipeline.py          # PipelineOrchestrator
scripts/
├── loopnet_search.py    # LoopNet search via Firefox BiDi
├── loopnet_listing.py   # LoopNet listing detail scraper
├── loopnet_batch.py     # Batch orchestration
└── loopnet_utils.py     # Shared BiDi lifecycle
```

## Documentation

- `docs/underwriting-playbook.md` — Complete 19-section methodology
- `docs/claude-analysis-pattern.md` — 10-section complex deal handoff
- `docs/open-design-fusion.md` — Dashboard design tokens

## Requirements

- Python 3.11+
- `requests`, `beautifulsoup4`, `lxml`
- For scraping: Firefox 150+ with BiDi, `websockets`, X11 display
- For dev: `pytest`, `ruff`, `mypy`

## License

MIT — see [LICENSE](LICENSE)
