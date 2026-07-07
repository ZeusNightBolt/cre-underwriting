# v5 Wired — Cross-Validation Deployment (May 14, 2026)

## Architecture

LLM triple-LLM pipeline with v3 deterministic cross-validation via `cross_validator.py`:

- **MoatScorer** — 8-dimension moat assessment
- **LawyerBrain** — legal/regulatory analysis (tax bomb detection, assessment ratio analysis)
- **_build_scenarios** — 5-scenario financial projection
- **lever_analysis** — leverage sensitivity modeling
- **valuation_triangulation** — 4-method valuation convergence

## Cross-Validation Results

| Component | LLM Score | v3 Score | Delta |
|-----------|-----------|----------|-------|
| MoatScorer | 8/24 | 12/24 | +4 (v3 outperformed) |
| LawyerBrain | — | 0 (NJ) | Assessment ratio 0.58 missed tax bomb tiers |

Real v3⨂LLM divergences captured in `ctx.warnings` → surfaced on dashboard Divergence tab.

## Fixes Applied

- 5 deterministic fallbacks from LiveContext for LLM hallucination recovery
- Dashboard normalization bridges SynthesisOutput → v4 flat dict for display
- All 4 dashboard tabs populated with zero NaN/undefined values

## Deployments

- Fords, NJ: `deploysuccasunna.vercel.app`
- Boonton, NJ: `deployboonton.vercel.app`
