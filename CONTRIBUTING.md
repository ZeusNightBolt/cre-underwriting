# Contributing to CRE Underwriting

## Adding a New NJ County Profile

1. Add the county's economic data to `src/cre_underwriting/environmental.py` in `_load_nj_profiles()`.
2. Use Census ACS 2023 5-year estimates + BLS Q4 2024 data.
3. Required fields: population, median_income, poverty_pct, bachelor_pct, employment, median_home, rental_vacancy, top_employers, tailwinds, headwinds.
4. Add the city-to-county mapping in `src/cre_underwriting/utils.py` → `city_to_county()`.
5. Run `pytest tests/test_environmental_comps.py -v` to verify.

## Adding a New City-to-County Mapping

Add to `city_to_county()` in `src/cre_underwriting/utils.py`:
```python
"cityname": "CountyName",
```

## Adjusting Moat Scoring Thresholds

All thresholds are in `src/cre_underwriting/constants.py` → `MoatThresholds`:
```python
MOATS.wide_moat_min = 19      # ≥19 → WIDE MOAT
MOATS.narrow_moat_min = 12    # ≥12 → NARROW MOAT
MOATS.stack_high_pct = 66.0   # Asset stack coverage thresholds
```

## Adding a New Scraping Source

1. Add a `_new_source_comps()` function in `src/cre_underwriting/comps.py`
2. Add it to the cascade in `find_comps()`:
   ```python
   try:
       all_comps.extend(_new_source_comps(address, property_type))
   except Exception as exc:
       logger.warning("New source comps failed: %s", exc)
   ```
3. Add the source to `source_statuses` dict in the summary section.
4. Run `pytest tests/test_environmental_comps.py -v`.

## Running Tests

```bash
pip install -e ".[dev]"
pytest -v                    # All 43 tests
pytest tests/test_convexity.py -v  # Convexity only
```

## Code Style

- Python 3.11+, type hints on public APIs
- Ruff for linting: `ruff check src/ tests/`
- 100-char line length
- Docstrings on all public functions/classes
- No `import` inside functions (use module-level imports)
- No hardcoded paths — use `Path(__file__).parent` for fixtures

## Adding a New Deal Fixture

1. Create `tests/fixtures/listing_NNNNNNNN.json` with the standard format
2. Add a test in the appropriate test file:
   ```python
   def test_new_deal(self):
       with open(FIXTURES / "listing_NNNNNNNN.json") as f:
           data = json.load(f)
       result = from_json(data)
       assert result.verdict.verdict in ("CONDITIONAL", "PURSUE", "PASS")
   ```
