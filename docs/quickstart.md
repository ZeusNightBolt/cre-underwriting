# Quick Start — CRE Underwriting

## 5-Minute Setup

```bash
git clone https://github.com/girnarholdings/cre-underwriting.git
cd cre-underwriting
pip install -e ".[all]"
```

## Analyze Your First Deal

```bash
# Run full pipeline on a deal JSON
cre-pipeline tests/fixtures/fords_34554176.json

# Convexity only
cre-analyze tests/fixtures/fords_34554176.json
```

## Python API

```python
from cre_underwriting.pipeline import PipelineOrchestrator
from cre_underwriting.dashboard import generate_dashboard

# Analyze a deal
orch = PipelineOrchestrator()
result = orch.run("my_deal.json")

# Get the verdict
print(result["convexity"]["verdict"]["verdict"])  # "CONDITIONAL"
print(result["enhanced"]["moats"]["total_score"])  # "15/24"

# Generate an anti-slop dashboard
html = generate_dashboard(result)
with open("dashboard.html", "w") as f:
    f.write(html)
```

## Individual Engines

```python
from cre_underwriting.enhanced import MoatScorer, OfferAnalyzer
from cre_underwriting.environmental import assess_location
from cre_underwriting.comps import find_comps

# 8-moat scoring
moats = MoatScorer.score(deal_data)

# Offer ladder
offers = OfferAnalyzer.ladder(ask_price=799000, noi=57368, hard_floor_mid=530000)

# Environmental assessment
env = assess_location("123 Main St, Princeton, NJ 08540")

# Comps (Zillow + LoopNet BiDi)
comps = find_comps("123 Main St, Princeton, NJ 08540")
```

## Scraping a Deal from LoopNet

```python
from cre_underwriting.scraping import scrape_with_cascade, detect_protection

# Check protection level
detection = detect_protection("https://www.loopnet.com/listing/.../")
print(detection["level"])  # "akamai" → needs Firefox BiDi

# Full cascade: curl_cffi → Camoufox → Firefox BiDi
html, source = scrape_with_cascade("https://www.loopnet.com/listing/.../")
print(f"Fetched via {source}")  # "bidi"
```

## Deal JSON Format

```json
{
  "property": {"listing_id": "...", "price": 799000, "address": "...", ...},
  "hard_asset_floor": {"low": 400000, "mid": 530000, "high": 650000},
  "income": {"noi_estimated": 57368, "gross_rent_per_sf": 16.0, ...},
  "scenarios": {
    "Worst Case": {"value": 292632, "moic_5yr": 0.7},
    "Baseline": {"value": 796778, "moic_5yr": 1.4},
    "Phase 1 Optimize": {"value": 854129, "moic_5yr": 1.76},
    ...
  }
}
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest -v
```

## Next Steps

- Read `docs/underwriting-playbook.md` for the full methodology
- Read `docs/architecture.md` for the pipeline design
- See `docs/claude-analysis-pattern.md` for complex going-concern deals
