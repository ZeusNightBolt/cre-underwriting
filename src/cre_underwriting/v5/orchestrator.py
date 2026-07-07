"""
v5 Pipeline Orchestrator — Kanban DAG-based execution.

Creates 12 Kanban cards across 4 phases with dependency gates.
Monitors card progress, validates outputs, and triggers dashboard deploy.

Usage:
    orch = V5PipelineOrchestrator()
    result = orch.run("https://www.loopnet.com/Listing/37-39-Main-St-Succasunna-NJ/35674774/")
    # or
    result = orch.run_fixture("tests/fixtures/succasunna_35674774.json")
"""

import json
import time
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import (
    LiveContext, Range, DealInput,
    MoatOutput, ScenarioOutput, LegalOutput,
    LeverOutput, ValuationOutput, SynthesisOutput,
)


class V5PipelineOrchestrator:
    """
    Kanban-orchestrated v5 CRE underwriting pipeline.

    Phases:
      A (K1-K5): Parallel data gathering
      B (K6-K10): Parallel analysis (v3 engines + LLM cross-validation)
      C (K11): Synthesis + validation + learning
      D (K12): Dashboard generation + Vercel deploy
    """

    def __init__(self, output_dir: str = None, deal_slug: str = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            slug = deal_slug or "unnamed"
            self.output_dir = Path(f"/tmp/cre_v5_{date.today().isoformat()}_{slug}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ctx = LiveContext()

    def run(self, deal_input: DealInput) -> Dict[str, Any]:
        """Run full v5 pipeline from a DealInput."""
        if deal_input.source_type == "fixture":
            return self._run_from_fixture(deal_input.source_value)
        elif deal_input.source_type == "url":
            return self._run_from_url(deal_input.source_value)
        else:
            raise ValueError(f"Unknown source_type: {deal_input.source_type}")

    def run_fixture(self, fixture_path: str) -> Dict[str, Any]:
        """Run pipeline from a fixture JSON file."""
        with open(fixture_path) as f:
            fixture = json.load(f)

        self.ctx = LiveContext()

        # Extract known fields from fixture
        prop = fixture.get("property", {})
        income = fixture.get("income", {})
        pricing = fixture.get("pricing", {})
        hf = fixture.get("hard_asset_floor", {})

        self.ctx.address = prop.get("address", "") or fixture.get("deal", {}).get("address", "")
        self.ctx.city = prop.get("city", prop.get("municipality", ""))
        self.ctx.state = prop.get("state", "NJ")
        self.ctx.property_type = prop.get("property_type",
                                           fixture.get("deal", {}).get("property_type", ""))
        self.ctx.ask_price = prop.get("price", 0) or pricing.get("ask", 0)
        self.ctx.building_sf = prop.get("building_size_sf", prop.get("unit_sf", 0)) or 0
        self.ctx.lot_acres = prop.get("lot_acres", prop.get("lot_size_ac", prop.get("lot_ac", 0))) or 0
        self.ctx.year_built = prop.get("year_built", 0) or 0
        self.ctx.zoning = prop.get("zoning", "")
        self.ctx.building_class = prop.get("building_class", "")
        self.ctx.days_on_market = prop.get("days_on_market", 0) or 0
        self.ctx.listing_id = prop.get("listing_id",
                                       fixture.get("deal", {}).get("listing_id", ""))
        self.ctx.listing_source = "fixture"

        # Income / rent roll (robust parsing)
        rent_raw = income.get("rent_range_per_sf", income.get("rent_range", ""))
        self.ctx.rent_psf_range = _parse_rent_range(rent_raw)
        self.ctx.cap_rate_estimated = income.get("cap_rate_est_pct", 0) or 0

        # Assign NOI from fixture if available (will be overridden by LLM reconstruction)
        if income.get("noi_estimated"):
            self.ctx.noi_estimated = Range(mid=income["noi_estimated"])

        # Pricing
        self.ctx.data_sources["fixture"] = f"Loaded from {fixture_path}"

        # ── Run Phase A: Live Data Gathering ──
        self._phase_a_data_gathering()

        # ── Run Phase B: Analysis ──
        analysis = self._phase_b_analysis()

        # ── Phase B Retry Loop: re-run failed nodes until cohesive output ──
        max_retries = 2
        for retry_round in range(1, max_retries + 1):
            failed = [
                name for name in ["scenarios", "levers", "moats", "valuation", "legal"]
                if analysis.get(name, {}).get("_error") or (
                    name == "scenarios" and len(analysis.get(name, {}).get("scenarios", [])) < 3
                ) or (
                    name == "levers" and len(analysis.get(name, {}).get("levers", [])) < 3
                ) or (
                    name == "moats" and not analysis.get(name, {}).get("scores")
                )
            ]
            if not failed:
                break
            self.ctx.warnings.append(f"Phase B retry {retry_round}/{max_retries}: re-running {failed}")
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=len(failed)) as executor:
                futs = {executor.submit(self._run_single_analysis, name): name for name in failed}
                try:
                    for future in as_completed(futs, timeout=1200):
                        try:
                            name, result = future.result()
                            analysis[name] = result
                        except Exception as e:
                            name = futs[future]
                            self.ctx.errors.append(f"Phase B retry {name}: {e}")
                except TimeoutError:
                    for future, name in {f: n for n, f in futs.items() if not f.done()}.items():
                        future.cancel()
                        self.ctx.errors.append(f"Phase B retry {name}: timed out")

        # ── Run Phase C: Synthesis ──
        synthesis = self._phase_c_synthesis(analysis)

        # ── Run Phase D: Dashboard ──
        dashboard_url = self._phase_d_dashboard(synthesis)

        return {
            "synthesis": synthesis,
            "dashboard_url": dashboard_url,
            "warnings": self.ctx.warnings,
            "errors": self.ctx.errors,
        }

    # ═══════════════════════════════════════════════════════
    # Phase A: Data Gathering (K1-K5)
    # ═══════════════════════════════════════════════════════

    def _phase_a_data_gathering(self):
        """Execute K1-K5. For fixtures, K1 is skipped (data from fixture)."""
        # K2: FRED Economics
        try:
            from . import fred_client
            econ = fred_client.get_msa_economics(self.ctx.city, self.ctx.state)
            self.ctx.msa_name = econ.get("msa_name", "")
            self.ctx.hpi_1yr_pct = econ.get("hpi_1yr_pct")
            self.ctx.hpi_5yr_annualized_pct = econ.get("hpi_5yr_annualized_pct")
            self.ctx.hpi_source = econ.get("source", "")
            self.ctx.county_median_income = econ.get("median_household_income")
            self.ctx.county_unemployment_pct = econ.get("unemployment_rate_pct")
            self.ctx.county_population = econ.get("population")
            self.ctx.data_sources["fred"] = econ.get("source", "FRED")
        except Exception as e:
            self.ctx.warnings.append(f"K2 FRED: {e}")

        # K3: Demographics (web search for granular data)
        try:
            from .web_search import search_corridor_intel, search_county_records
            corridor = search_corridor_intel(self.ctx.city, self.ctx.state)
            self.ctx.corridor_news = corridor
            records = search_county_records(self.ctx.city, self.ctx.state,
                                           self.ctx.property_type)
            self.ctx.county_records = records
            self.ctx.data_sources["demographics_web"] = f"Brave Search ({len(corridor)} corridor, {len(records)} county)"
        except Exception as e:
            self.ctx.warnings.append(f"K3 Demographics: {e}")

        # K4: Comps
        try:
            from .web_search import search_recent_sales
            comps = search_recent_sales(self.ctx.city, self.ctx.state,
                                       self.ctx.property_type)
            self.ctx.comps = comps
            self.ctx.data_sources["comps_web"] = f"Brave Search ({len(comps)} results)"
        except Exception as e:
            self.ctx.warnings.append(f"K4 Comps: {e}")

        # K4b: Generate synthetic comps if none found or all are empty/zero
        has_valid_comps = self.ctx.comps and any(
            isinstance(c, dict) and c.get("price", 0) > 0
            for c in self.ctx.comps
        )
        if not has_valid_comps:
            ask = self.ctx.ask_price or 1
            sf = self.ctx.building_sf or 1
            ppsf = ask / max(sf, 1)
            synthetic = [
                {"address": f"Nearby {self.ctx.property_type} — Small", "price": int(ask * 0.75),
                 "sf": int(sf * 0.7), "price_per_sf": int(ppsf * 1.07),
                 "sale_date": "2025-Q4", "source": "estimated", "note": "Extrapolated from listing metrics"},
                {"address": f"Nearby {self.ctx.property_type} — Mid", "price": int(ask * 1.05),
                 "sf": int(sf * 1.1), "price_per_sf": int(ppsf * 0.95),
                 "sale_date": "2025-Q3", "source": "estimated", "note": "Extrapolated from listing metrics"},
                {"address": f"Nearby {self.ctx.property_type} — Large", "price": int(ask * 1.5),
                 "sf": int(sf * 1.8), "price_per_sf": int(ppsf * 0.83),
                 "sale_date": "2025-Q2", "source": "estimated", "note": "Extrapolated from listing metrics"},
            ]
            self.ctx.comps = synthetic
            self.ctx.data_sources["comps_synthetic"] = "3 synthetic comps (extrapolated from deal metrics)"

        # K5: Environmental
        try:
            from .web_search import search_environmental
            env = search_environmental(self.ctx.address, self.ctx.city, self.ctx.state)
            self.ctx.environmental_findings = env
            self.ctx.data_sources["environmental"] = f"Brave Search ({len(env)} results)"
        except Exception as e:
            self.ctx.warnings.append(f"K5 Environmental: {e}")

    # ═══════════════════════════════════════════════════════
    # Phase B: Analysis (K6-K10)
    # ═══════════════════════════════════════════════════════

    def _run_single_analysis(self, name: str) -> tuple:
        """Run LLM analysis + v3 cross-validation. Returns (name, merged_result)."""
        try:
            from .llm_analysis import (
                analyze_moats, analyze_scenarios, analyze_legal_risk,
                analyze_levers, analyze_valuation,
            )
            from .cross_validator import run_cross_validation

            fns = {
                "moats": analyze_moats,
                "scenarios": analyze_scenarios,
                "legal": analyze_legal_risk,
                "levers": analyze_levers,
                "valuation": analyze_valuation,
            }

            # Step 1: Run LLM analysis
            llm_result = fns[name](self.ctx)

            # Step 2: If LLM produced valid output, cross-validate with v3 engine
            if llm_result and "_error" not in llm_result:
                try:
                    merged, v3_divergences = run_cross_validation(name, llm_result, self.ctx)
                    # Attach divergences to context for synthesis
                    for d in v3_divergences:
                        self.ctx.warnings.append(f"v3⨂LLM divergence ({name}): {d}")
                    return (name, merged)
                except Exception as e:
                    self.ctx.errors.append(f"v3 cross-val {name}: {e}")
                    return (name, llm_result)  # fallback to LLM-only

            return (name, llm_result)
        except Exception as e:
            self.ctx.errors.append(f"K6-K10 {name}: {e}")
            return (name, {"_error": str(e)})

    def _phase_b_analysis(self) -> Dict[str, Any]:
        """Execute K6-K10 analysis nodes IN PARALLEL via thread pool."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        analysis = {}
        analysis_names = ["moats", "scenarios", "legal", "levers", "valuation"]

        # Fire all 5 in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._run_single_analysis, name): name
                       for name in analysis_names}
            try:
                for future in as_completed(futures, timeout=2400):
                    try:
                        name, result = future.result()
                        analysis[name] = result
                    except Exception as e:
                        name = futures[future]
                        self.ctx.errors.append(f"K6-K10 {name}: {e}")
                        analysis[name] = {"_error": str(e)}
            except TimeoutError:
                for future, name in {f: n for n, f in futures.items() if not f.done()}.items():
                    future.cancel()
                    self.ctx.errors.append(f"K6-K10 {name}: timed out after 2400s")
                    analysis[name] = {"_error": f"timed out after 2400s"}

        return analysis

    # ═══════════════════════════════════════════════════════
    # Phase C: Synthesis (K11)
    # ═══════════════════════════════════════════════════════

    def _phase_c_synthesis(self, analysis: Dict[str, Any]) -> SynthesisOutput:
        """Validate, cross-check, synthesize — with deterministic fallbacks for failed nodes."""
        validation_errors = []
        divergences = []

        # Strip _raw audit fields before unpacking into models
        moats_raw = _strip_audit(analysis.get("moats", {}))
        scenarios_raw = _strip_audit(analysis.get("scenarios", {}))
        legal_raw = _strip_audit(analysis.get("legal", {}))
        levers_raw = _strip_audit(analysis.get("levers", {}))
        valuation_raw = _strip_audit(analysis.get("valuation", {}))

        # ── Generate fallbacks for empty/failed analysis nodes ──
        moats = self._ensure_moats(moats_raw)
        scenarios = self._ensure_scenarios(scenarios_raw)
        legal = self._ensure_legal(legal_raw)
        levers = self._ensure_levers(levers_raw)
        valuation = self._ensure_valuation(valuation_raw)

        # ── Cross-validate moats ──
        if isinstance(moats, dict):
            total = moats.get("total", 0)
            scores = moats.get("scores", {})
            computed = sum(s.get("score", 0) for s in scores.values())
            if computed != total:
                validation_errors.append(f"Moats: scores sum to {computed}, declared {total}")

        # ── Cross-validate scenarios ──
        if isinstance(scenarios, dict):
            scenario_list = scenarios.get("scenarios", [])
            if len(scenario_list) != 5:
                validation_errors.append(f"Scenarios: expected 5, got {len(scenario_list)}")
            prob_sum = sum(s.get("probability", 0) for s in scenario_list)
            if abs(prob_sum - 1.0) > 0.03:
                validation_errors.append(f"Scenarios: probabilities sum to {prob_sum:.3f}")

        # ── Compute divergences (LLM vs deterministic v3 engines) ──
        divergences = self._compute_divergences(analysis, moats, scenarios)

        return SynthesisOutput(
            moats=MoatOutput(**(moats if isinstance(moats, dict) else {})),
            scenarios=ScenarioOutput(**(scenarios if isinstance(scenarios, dict) else {})),
            legal_risk=LegalOutput(**(legal if isinstance(legal, dict) else {})),
            levers=LeverOutput(**(levers if isinstance(levers, dict) else {})),
            valuation=ValuationOutput(**(valuation if isinstance(valuation, dict) else {})),
            validation_errors=validation_errors,
            divergences=divergences,
        )

    # ── Fallback generators ──

    def _ensure_moats(self, raw: dict) -> dict:
        """Ensure moats dict has data — generate from context if empty."""
        if not raw or not raw.get("scores"):
            ask = self.ctx.ask_price or 1
            sf = self.ctx.building_sf or 1
            hf_mid = ask * 0.45  # conservative hard floor estimate
            scores = {
                "license_barrier": {"score": 1, "rationale": f"No documented UST/liquor license — check during DD"},
                "tourism_corridor": {"score": 1, "rationale": f"{self.ctx.city} corridor needs verification"},
                "multi_revenue": {"score": 2, "rationale": f"Property type {self.ctx.property_type} may support multiple tenants"},
                "zoning_optionality": {"score": 1, "rationale": f"Zoning {self.ctx.zoning} — check redevelopment potential"},
                "rent_gap": {"score": 1, "rationale": f"Rent range ${self.ctx.rent_psf_range.mid:.0f}/SF — verify market"},
                "brand_value": {"score": 0, "rationale": "Not an operating business — brand value not applicable"},
                "asset_stack": {"score": 2, "rationale": f"Estimated hard floor ${hf_mid:,.0f} is {hf_mid/ask*100:.0f}% of ask"},
                "seller_asymmetry": {"score": 1, "rationale": f"On market {self.ctx.days_on_market}d — monitor for price reductions"},
            }
            total = sum(s["score"] for s in scores.values())
            raw["scores"] = scores
            raw["total"] = total
            raw["classification"] = "NO MOAT" if total < 12 else "WEAK MOAT" if total < 18 else "STRONG MOAT"
            raw["verdict"] = f"Deterministic estimate: {total}/24 ({raw['classification']}) — LLM analysis unavailable"
        return raw

    def _ensure_scenarios(self, raw: dict) -> dict:
        """Ensure scenarios dict has 5 scenarios — generate from context if empty."""
        if not raw or len(raw.get("scenarios", [])) < 3:
            ask = self.ctx.ask_price or 1
            sf = self.ctx.building_sf or 1
            cap_base = max(self.ctx.cap_rate_estimated / 100 if self.ctx.cap_rate_estimated > 1
                          else (self.ctx.cap_rate_estimated or 0.08), 0.06)
            hf_mid = ask * 0.45
            # Estimate NOI from cap rate
            noi_est = int(ask * cap_base)
            scenarios = [
                {
                    "name": "Worst Case — Recession / Tenant Loss",
                    "probability": 0.05,
                    "noi": int(noi_est * 0.6),
                    "exit_cap": cap_base + 0.02,
                    "exit_value": int(int(noi_est * 0.6) / (cap_base + 0.02)),
                    "moic": round(int(noi_est * 0.6) / (cap_base + 0.02) / ask, 2),
                    "description": "Severe recession, tenant vacates, NOI collapses. Cap rates expand.",
                    "triggers": ["Recession", "Major tenant loss", "Cap rate expansion"],
                    "key_assumptions": ["NOI drops 40%", "Cap rate expands 200bps"]
                },
                {
                    "name": "Baseline — Steady-State Hold",
                    "probability": 0.50,
                    "noi": noi_est,
                    "exit_cap": cap_base,
                    "exit_value": int(noi_est / cap_base),
                    "moic": round(noi_est / cap_base / ask, 2),
                    "description": "Property performs as underwritten. Stable occupancy, market cap rates.",
                    "triggers": ["Stable market", "No tenant turnover"],
                    "key_assumptions": ["NOI = ask × cap rate", "Cap rate flat"]
                },
                {
                    "name": "Phase 1 — Optimize Operations",
                    "probability": 0.25,
                    "noi": int(noi_est * 1.15),
                    "exit_cap": cap_base - 0.0025,
                    "exit_value": int(int(noi_est * 1.15) / (cap_base - 0.0025)),
                    "moic": round(int(noi_est * 1.15) / (cap_base - 0.0025) / ask, 2),
                    "description": "Minor operational improvements, slight rent bump, expense optimization.",
                    "triggers": ["Rent increase 5%", "Expense optimization"],
                    "key_assumptions": ["NOI +15%", "Cap rate tightens 25bps"]
                },
                {
                    "name": "Phase 2 — Expand / Add Value",
                    "probability": 0.15,
                    "noi": int(noi_est * 1.35),
                    "exit_cap": cap_base - 0.005,
                    "exit_value": int(int(noi_est * 1.35) / (cap_base - 0.005)),
                    "moic": round(int(noi_est * 1.35) / (cap_base - 0.005) / ask, 2),
                    "description": "Add square footage or repurpose space. Significant NOI growth.",
                    "triggers": ["Expansion complete", "New tenant signed"],
                    "key_assumptions": ["NOI +35%", "Cap rate tightens 50bps"]
                },
                {
                    "name": "Phase 3 — Strategic Sale",
                    "probability": 0.05,
                    "noi": int(noi_est * 1.50),
                    "exit_cap": cap_base - 0.0075,
                    "exit_value": int(int(noi_est * 1.50) / (cap_base - 0.0075)),
                    "moic": round(int(noi_est * 1.50) / (cap_base - 0.0075) / ask, 2),
                    "description": "Full repositioning, premium exit to institutional buyer.",
                    "triggers": ["Institutional demand", "Market peak"],
                    "key_assumptions": ["NOI +50%", "Cap rate tightens 75bps"]
                },
            ]
            raw["scenarios"] = scenarios
            raw["purchase_price"] = ask
            raw["hard_floor_mid"] = hf_mid
            raw["scenario_narratives"] = [
                {"name": s["name"], "detail": s["description"], "drivers": s["triggers"]}
                for s in scenarios
            ]
        return raw

    def _ensure_legal(self, raw: dict) -> dict:
        """Ensure legal risk dict has data."""
        if not raw or raw.get("risk_score") is None:
            raw["risk_score"] = 5.0
            raw["risk_level"] = "MODERATE"
            raw["summary"] = f"No LLM legal analysis. Based on {self.ctx.days_on_market}d DOM, {self.ctx.property_type}, {self.ctx.year_built} build."
            raw["top_3_risks"] = ["Environmental (Phase I needed)", "Tax reassessment on sale", "Zoning compliance"]
            raw["concealment_flags"] = []
        return raw

    def _ensure_levers(self, raw: dict) -> dict:
        """Ensure levers dict has data."""
        if not raw or not raw.get("levers"):
            ask = self.ctx.ask_price or 1
            raw["levers"] = [
                {"name": "Expense Optimization", "category": "Cost", "effort": "LOW",
                 "noi_impact_pct": 5.0, "timeline_months": 3,
                 "description": "Review all operating expenses, renegotiate contracts, energy efficiency upgrades."},
                {"name": "Rent Roll Optimization", "category": "Revenue", "effort": "MEDIUM",
                 "noi_impact_pct": 10.0, "timeline_months": 12,
                 "description": "Bring below-market rents to market, reduce vacancy, improve tenant mix."},
                {"name": "Capital Improvements", "category": "Capital", "effort": "HIGH",
                 "noi_impact_pct": 15.0, "timeline_months": 18,
                 "description": "Deferred maintenance, cosmetic upgrades, curb appeal improvements."},
                {"name": "Refinance / Recapitalize", "category": "Financing", "effort": "MEDIUM",
                 "noi_impact_pct": 8.0, "timeline_months": 12,
                 "description": "Refinance at lower rate after stabilization, reduce debt service."},
                {"name": "Use Change / Reposition", "category": "Use-Change", "effort": "HIGH",
                 "noi_impact_pct": 25.0, "timeline_months": 24,
                 "description": "Explore zoning variance for higher-value use. Check entitlement path."},
            ]
            raw["recommendation"] = {
                "verdict": "ANALYZE",
                "target_offer": int(ask * 0.90),
                "walk_away": int(ask * 1.05),
                "target_cap_rate": self.ctx.cap_rate_estimated / 100 if self.ctx.cap_rate_estimated > 1 else 0.08,
                "key_conditions": ["Phase I environmental", "Rent roll verification", "Physical inspection"],
                "negotiation_strategy": f"Offer {int(ask*0.85):,} initial, walk at {int(ask*1.05):,}. Leverage {self.ctx.days_on_market}d DOM.",
                "single_biggest_risk": f"Verification of actual NOI vs {self.ctx.cap_rate_estimated}% cap rate estimate",
                "confidence": "LOW",
            }
            raw["offers"] = [
                {"label": "Conservative", "amount": int(ask * 0.80), "cap_rate": self.ctx.cap_rate_estimated},
                {"label": "Target", "amount": int(ask * 0.90), "cap_rate": self.ctx.cap_rate_estimated},
                {"label": "Walk-away", "amount": int(ask * 1.05), "cap_rate": self.ctx.cap_rate_estimated},
            ]
        return raw

    def _ensure_valuation(self, raw: dict) -> dict:
        """Ensure valuation dict has data."""
        if not raw or raw.get("hard_floor_mid", 0) <= 0:
            ask = self.ctx.ask_price or 1
            hf_low = int(ask * 0.35)
            hf_mid = int(ask * 0.45)
            hf_high = int(ask * 0.55)
            raw["hard_floor_low"] = hf_low
            raw["hard_floor_mid"] = hf_mid
            raw["hard_floor_high"] = hf_high
            raw["exit_cap_rate"] = self.ctx.cap_rate_estimated / 100 if self.ctx.cap_rate_estimated > 1 else 0.08
            raw["noi_reconstructed"] = {
                "mid": int(ask * raw["exit_cap_rate"]),
                "low": int(ask * raw["exit_cap_rate"] * 0.85),
                "high": int(ask * raw["exit_cap_rate"] * 1.15),
            }
            raw["stabilized_re_value"] = int(raw["noi_reconstructed"]["mid"] / raw["exit_cap_rate"])
            raw["pwev"] = (hf_mid * 0.1 + raw["stabilized_re_value"] * 0.9)
            raw["approach_breakdown"] = f"Deterministic: {raw['exit_cap_rate']:.1%} cap on estimated NOI ${raw['noi_reconstructed']['mid']:,}"
        return raw

    def _compute_divergences(self, analysis, moats, scenarios) -> List[str]:
        """Collect real v3⨂LLM divergences from ctx.warnings + per-node v3 comparisons."""
        divs = []

        # Real divergences from v3⨂LLM cross-validation (produced in _run_single_analysis)
        for w in self.ctx.warnings:
            if "v3⨂LLM divergence" in str(w):
                divs.append(str(w).replace("v3⨂LLM divergence ", ""))

        # Add v3-vs-LLM total score comparison for moats
        if moats.get("v3_total") is not None and moats.get("total", 0) > 0:
            v3_total = moats.get("v3_total", 0)
            llm_total = moats.get("total", 0)
            if abs(v3_total - llm_total) >= 3:
                divs.append(f"Moat total: v3={v3_total}/24 vs LLM={llm_total}/24 (Δ{abs(v3_total-llm_total)})")

        # Add v3-vs-LLM risk score comparison for legal
        legal = _strip_audit(analysis.get("legal", {}))
        if legal.get("v3_legal_risk_score") is not None:
            v3_risk = legal.get("v3_legal_risk_score", 0)
            llm_risk = legal.get("risk_score", 0)
            if abs(v3_risk - llm_risk) >= 2:
                divs.append(f"Legal risk: v3={v3_risk}/10 vs LLM={llm_risk}/10")

        return divs

    # ═══════════════════════════════════════════════════════
    # Phase D: Dashboard (K12)
    # ═══════════════════════════════════════════════════════

    def _phase_d_dashboard(self, synthesis: SynthesisOutput) -> str:
        """Generate dashboard HTML from SynthesisOutput + LiveContext. Returns URL."""
        try:
            import subprocess, tempfile
            from datetime import date

            # Normalize v5 output into v4 dashboard format
            normalized = self._normalize_for_dashboard(synthesis)

            # Write to temp file
            tmp_path = self.output_dir / "dashboard_input.json"
            tmp_path.write_text(json.dumps(normalized, indent=2, default=str))

            # Call v4 dashboard builder
            builder = Path(__file__).parent.parent.parent.parent / "scripts/build_dashboard_v4.py"
            out_html = self.output_dir / "dashboard.html"
            result = subprocess.run(
                ["python3", str(builder), str(tmp_path), "--output", str(out_html)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                self.ctx.errors.append(f"Dashboard build: {result.stderr[:300]}")
                return "dashboard FAILED"

            self.ctx.data_sources["dashboard_html"] = str(out_html)
            return f"dashboard written to {out_html} ({out_html.stat().st_size:,} bytes)"
        except Exception as e:
            self.ctx.errors.append(f"K12 Dashboard: {e}")
            return f"dashboard FAILED: {e}"

    def _normalize_for_dashboard(self, synthesis: SynthesisOutput) -> dict:
        """Flatten v5 SynthesisOutput + LiveContext into v4 dashboard format."""
        from datetime import date
        ctx = self.ctx
        moats = synthesis.moats
        scenarios_out = synthesis.scenarios
        legal = synthesis.legal_risk
        levers = synthesis.levers
        valuation = synthesis.valuation
        ask = ctx.ask_price or 1
        hf_mid = valuation.hard_floor_mid or ask * 0.45

        # Pricing section
        pricing = {
            "ask": ask,
            "price_psf": int(ask / max(ctx.building_sf, 1)),
            "hard_floor_low": valuation.hard_floor_low or int(ask * 0.35),
            "hard_floor_mid": hf_mid,
            "hard_floor_high": valuation.hard_floor_high or int(ask * 0.55),
            "floor_to_ask_pct": int(hf_mid / ask * 100) if ask > 0 else 0,
            "stabilized_re_value": valuation.stabilized_re_value or int(ask * 0.95),
            "exit_cap_rate": valuation.exit_cap_rate or 0.08,
        }

        # Scenarios (from ScenarioOutput — handles both dict and dataclass)
        scenarios_list = []
        for s in scenarios_out.scenarios:
            if hasattr(s, 'name'):
                scenarios_list.append({
                    "name": s.name, "probability": s.probability,
                    "noi": s.noi, "exit_cap": s.exit_cap,
                    "exit_value": s.exit_value, "moic": s.moic,
                    "description": s.description, "triggers": s.triggers,
                    "key_assumptions": s.key_assumptions,
                })
            else:
                scenarios_list.append({
                    "name": s.get("name", ""), "probability": s.get("probability", 0),
                    "noi": s.get("noi", 0), "exit_cap": s.get("exit_cap", 0.08),
                    "exit_value": s.get("exit_value", 0), "moic": s.get("moic", 0),
                    "description": s.get("description", ""), "triggers": s.get("triggers", []),
                    "key_assumptions": s.get("key_assumptions", []),
                })
        # Fallback: use scenario_narratives if scenarios are empty
        if not scenarios_list and hasattr(scenarios_out, 'scenario_narratives'):
            for n in scenarios_out.scenario_narratives:
                scenarios_list.append({
                    "name": n.get("name", ""),
                    "moic": n.get("moic", 0),
                    "exit_value": n.get("exit_value", 0),
                    "noi": n.get("noi", 0),
                    "probability": n.get("probability", 0),
                    "description": n.get("detail", ""),
                    "triggers": n.get("drivers", []),
                })

        # Scenario narratives
        if hasattr(scenarios_out, 'scenario_narratives'):
            scenario_narratives = scenarios_out.scenario_narratives
        else:
            scenario_narratives = [
                {"name": s["name"], "detail": s.get("description", ""),
                 "drivers": s.get("triggers", [])}
                for s in scenarios_list
            ]

        # Moats (convert dataclass to dict)
        moat_scores = {}
        for k, v in moats.scores.items():
            moat_scores[k] = {"score": v.get("score", 0) if isinstance(v, dict) else 0,
                              "rationale": v.get("rationale", "") if isinstance(v, dict) else str(v)}
        moats_dict = {
            "scores": moat_scores,
            "total": moats.total,
            "classification": moats.classification,
            "verdict": moats.verdict,
        }

        # Legal
        legal_dict = {
            "risk_score": legal.risk_score,
            "risk_level": legal.risk_level,
            "top_3_risks": legal.top_3_risks,
            "concealment_flags": legal.concealment_flags,
            "summary": legal.summary,
        }

        # Levers (handles both dict and dataclass)
        levers_list = []
        for l in levers.levers:
            if hasattr(l, 'name'):
                levers_list.append({
                    "name": l.name, "category": l.category, "effort": l.effort,
                    "noi_impact_pct": l.noi_impact_pct, "timeline_months": l.timeline_months,
                    "description": l.description,
                })
            else:
                levers_list.append({
                    "name": l.get("name", ""), "category": l.get("category", ""),
                    "effort": l.get("effort", "MEDIUM"),
                    "noi_impact_pct": l.get("noi_impact_pct", 0),
                    "timeline_months": l.get("timeline_months", 0),
                    "description": l.get("description", ""),
                })
        rec = levers.recommendation
        recommendation_dict = {
            "verdict": rec.verdict if hasattr(rec, 'verdict') else rec.get("verdict", "ANALYZE"),
            "target_offer": rec.target_offer if hasattr(rec, 'target_offer') else rec.get("target_offer", 0),
            "walk_away": rec.walk_away if hasattr(rec, 'walk_away') else rec.get("walk_away", 0),
            "confidence": rec.confidence if hasattr(rec, 'confidence') else rec.get("confidence", "MEDIUM"),
            "key_conditions": rec.key_conditions if hasattr(rec, 'key_conditions') else rec.get("key_conditions", []),
            "single_biggest_risk": rec.single_biggest_risk if hasattr(rec, 'single_biggest_risk') else rec.get("single_biggest_risk", ""),
        }
        offers_list = levers.offers if hasattr(levers, 'offers') else levers.dict().get("offers", []) if hasattr(levers, 'dict') else []

        # Divergence (computed from ConvexityEngine-style metrics)
        divergence = self._compute_divergence_metrics(scenarios_list, pricing)

        # Comps
        comps_list = ctx.comps or []

        # Demographics
        demographics = {
            "msa_name": ctx.msa_name or "",
            "county_population": ctx.county_population or 0,
            "county_median_income": ctx.county_median_income or 0,
            "county_unemployment_pct": ctx.county_unemployment_pct or 0,
            "hpi_1yr_pct": ctx.hpi_1yr_pct or 0,
        }

        return {
            "address": ctx.address,
            "city": ctx.city,
            "state": ctx.state,
            "property_type": ctx.property_type,
            "ask_price": ask,
            "building_sf": ctx.building_sf,
            "lot_acres": ctx.lot_acres,
            "year_built": ctx.year_built,
            "zoning": ctx.zoning,
            "building_class": ctx.building_class,
            "days_on_market": ctx.days_on_market,
            "analysis_date": str(date.today()),
            "pricing": pricing,
            "scenarios": scenarios_list,
            "scenario_narratives": scenario_narratives,
            "moats": moats_dict,
            "legal_risk": legal_dict,
            "levers": levers_list,
            "recommendation": recommendation_dict,
            "offers": offers_list,
            "valuation": {
                "hard_floor_low": pricing["hard_floor_low"],
                "hard_floor_mid": pricing["hard_floor_mid"],
                "hard_floor_high": pricing["hard_floor_high"],
                "stabilized_re_value": pricing["stabilized_re_value"],
                "noi_reconstructed": valuation.noi_reconstructed,
                "pwev": valuation.pwev,
                "exit_cap_rate": pricing["exit_cap_rate"],
            },
            "divergence": divergence,
            "comps": comps_list,
            "demographics": demographics,
            "divergences": synthesis.divergences,
            "validation_errors": synthesis.validation_errors,
            "warnings": ctx.warnings,
            "errors": ctx.errors,
        }

    def _compute_divergence_metrics(self, scenarios_list: list, pricing: dict) -> dict:
        """Compute convexity/divergence metrics from scenarios."""
        if not scenarios_list:
            return {"convexity_ratio": 1.0, "pwev": pricing.get("ask", 0),
                    "pwev_vs_ask_pct": 0, "frontier_zone": "UNKNOWN",
                    "best_moic": 1.0, "worst_moic": 1.0}

        moics = [s.get("moic", 0) for s in scenarios_list]
        evs = [s.get("exit_value", 0) for s in scenarios_list]
        probs = [s.get("probability", 0.01) for s in scenarios_list]

        worst_moic = min(moics) if moics else 1.0
        best_moic = max(moics) if moics else 1.0
        pwev = sum(ev * p for ev, p in zip(evs, probs)) / sum(probs) if sum(probs) > 0 else pricing.get("ask", 0)
        ask = pricing.get("ask", 1) or 1
        pwev_vs_ask_pct = (pwev / ask - 1) * 100 if ask > 0 else 0
        convexity_ratio = (best_moic - 1) / max(1 - worst_moic, 0.01) if worst_moic < 1 else (best_moic - worst_moic) + 1
        zone = "COASTAL" if convexity_ratio > 2 else "BIFURCATED" if convexity_ratio > 1.5 else "MARGINAL"
        absolute_spread = max(evs) - min(evs) if evs else 0

        return {
            "convexity_ratio": round(convexity_ratio, 1),
            "risk_reward_ratio": round(convexity_ratio, 1),
            "effective_worst": min(evs) if evs else 0,
            "absolute_spread": absolute_spread,
            "capital_normalized_spread": round(absolute_spread / ask, 1) if ask > 0 else 0,
            "frontier_zone": zone,
            "pwev": round(pwev),
            "pwev_vs_ask_pct": round(pwev_vs_ask_pct, 1),
            "best_moic": round(best_moic, 2),
            "worst_moic": round(worst_moic, 2),
        }

    def _run_from_url(self, url: str) -> Dict[str, Any]:
        """Run pipeline from a listing URL. Will be implemented with K1 scraper."""
        raise NotImplementedError("URL-based pipeline not yet implemented (K1 scraper pending)")


# ── CLI ──

def _parse_rent_range(raw: str) -> Range:
    """Parse rent range from strings like '$18-$22/SF NNN' or '$14/SF'."""
    import re
    if not raw:
        return Range()
    # Extract all dollar amounts
    numbers = re.findall(r'\$?([\d,.]+)', raw.replace(',', ''))
    nums = []
    for n in numbers:
        try:
            nums.append(float(n))
        except ValueError:
            continue
    if len(nums) >= 2:
        return Range(mid=sum(nums)/len(nums), low=min(nums), high=max(nums))
    elif len(nums) == 1:
        return Range(mid=nums[0], low=nums[0]*0.85, high=nums[0]*1.15)
    return Range()


def _strip_audit(d: dict) -> dict:
    """Remove audit trail fields (_raw, _errors, v3_* cross-val fields) before unpacking into models."""
    if not isinstance(d, dict):
        return d
    return {k: v for k, v in d.items()
            if not k.startswith("_") and not k.startswith("v3_")
            and k not in ("divergence_level", "scenario_divergence_count")}


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: v5-run <fixture.json>")
        sys.exit(1)

    orch = V5PipelineOrchestrator()
    result = orch.run_fixture(sys.argv[1])
    print(json.dumps({k: str(v) if hasattr(v, 'to_dict') else v
                      for k, v in result.items()}, indent=2, default=str))


if __name__ == "__main__":
    main()
