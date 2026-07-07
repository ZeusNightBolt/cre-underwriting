"""v4 Pipeline Orchestrator -- Dynamic API-first underwriting.

Wires live data sources into the 9-node pipeline:
  - Node 2: Comps (LoopNet BiDi + web search)
  - Node 3: HPA (FRED API -- real MSA data)
  - Node 5: Demographics (FRED API)
  - Node 8: Environmental/legal (web search)

Triple-LLM analysis called at moats, scenarios, legal, and recommendation nodes.
"""

import json
from datetime import date
from pathlib import Path
from typing import Optional

from .models import LiveContext, DealContext
from .llm_client import get_triple_analysis, call_deepseek
from .fred_client import get_msa_economics
from .web_search import (
    search_corridor_intel, search_environmental,
    search_recent_sales, search_county_records,
)
from .llm_analysis import (
    analyze_moats, analyze_scenarios,
    analyze_legal_risk, analyze_levers,
)


class V4PipelineOrchestrator:
    """Dynamic, live-data CRE underwriting orchestrator.

    Usage:
        orch = V4PipelineOrchestrator()
        result = orch.run("deal_analysis.json")
    """

    def __init__(self):
        self.ctx = LiveContext()

    def run(self, deal_path: str) -> dict:
        """Run full v4 pipeline on a deal analysis JSON."""
        with open(deal_path) as f:
            deal_data = json.load(f)
        return self.run_dict(deal_data)

    def run_dict(self, deal_data: dict) -> dict:
        """Run full pipeline from in-memory dict."""
        prop = deal_data.get("property", {})
        address = prop.get("address", deal_data.get("deal", {}).get("address", ""))
        ask_price = prop.get("price", 0) or deal_data.get("pricing", {}).get("ask", 0) or 0

        # Normalize fields
        if "unit_sf" in prop and "building_size_sf" not in prop:
            prop["building_size_sf"] = prop["unit_sf"]
        deal_data.setdefault("income", deal_data.get("income", {}))
        if "pricing" in deal_data and "price" not in prop:
            prop["price"] = deal_data["pricing"].get("ask", 0)
            prop["price_per_sf"] = deal_data["pricing"].get("price_psf", 0)

        city = prop.get("city", prop.get("municipality", ""))
        state = prop.get("state", "NJ")
        ptype = prop.get("property_type", deal_data.get("deal", {}).get("property_type", ""))

        # Build DealContext
        dc = DealContext(
            deal_data=deal_data, address=address, city=city, state=state,
            property_type=ptype, ask_price=ask_price,
            sf=prop.get("building_size_sf", prop.get("sf", prop.get("unit_sf", 0))) or 0,
            lot_acres=prop.get("lot_acres", prop.get("lot_size_ac", 0)) or 0,
            year_built=prop.get("year_built", 0) or 0,
            zoning=prop.get("zoning", ""),
        )

        # --- Node 3: HPA -- FRED API (live MSA-level data) ---
        try:
            econ = get_msa_economics(city, state)
            self.ctx.msa_name = econ.get("msa_name", "")
            self.ctx.msa_hpi_1yr_pct = econ.get("hpi_1yr_pct")
            self.ctx.msa_hpi_5yr_annualized_pct = econ.get("hpi_5yr_annualized_pct")
            self.ctx.msa_hpi_source = econ.get("source", "")
            self.ctx.county_median_income = econ.get("median_household_income")
            self.ctx.county_unemployment_pct = econ.get("unemployment_rate_pct")
            self.ctx.county_population = econ.get("population")
            self.ctx.data_sources["economics"] = "%s (%s)" % (econ.get("source", ""), econ.get("data_freshness", ""))
        except Exception as e:
            self.ctx.warnings.append("FRED economics failed: %s" % e)

        # --- Node 5: Demographics (same FRED call, county-level when available) ---
        self.ctx.data_sources["demographics"] = self.ctx.data_sources.get("economics", "FRED")
        # MSA-level data is already populated above

        # --- Node 2: Comps -- web search for recent sales ---
        try:
            sales_results = search_recent_sales(city, state, ptype)
            self.ctx.web_search_comps = sales_results
            self.ctx.data_sources["comps_web"] = "Brave Search (%d results)" % len(sales_results)
        except Exception as e:
            self.ctx.warnings.append("Web search comps failed: %s" % e)

        # --- Node 8: Corridor intel (web search) ---
        try:
            corridor = search_corridor_intel(city, state)
            self.ctx.corridor_news = corridor
            self.ctx.data_sources["corridor"] = "Brave Search (%d results)" % len(corridor)
        except Exception as e:
            self.ctx.warnings.append("Corridor intel failed: %s" % e)

        # --- Node 8: Environmental (web search) ---
        try:
            env = search_environmental(address, city, state)
            self.ctx.environmental_findings = env
            self.ctx.data_sources["environmental"] = "Brave Search (%d results)" % len(env)
        except Exception as e:
            self.ctx.warnings.append("Environmental search failed: %s" % e)

        # --- Node 8: County records (web search) ---
        try:
            records = search_county_records(city, state, ptype)
            self.ctx.zoning_changes = records[:5]
            self.ctx.data_sources["county_records"] = "Brave Search (%d results)" % len(records)
        except Exception as e:
            self.ctx.warnings.append("County records failed: %s" % e)

        # ── Phase 3: LLM Analysis Nodes ──
        # Node 6: Moat Analysis (triple-LLM)
        try:
            moat_result = analyze_moats(dc, self.ctx)
            self.ctx.moat_analysis = moat_result
            self.ctx.data_sources["moats"] = "Triple-LLM (DeepSeek + OpenRouter + Mistral → DeepSeek synthesis)"
        except Exception as e:
            self.ctx.warnings.append("Moat analysis failed: %s" % e)
            moat_result = {"scores": {}, "total": 0, "classification": "NO MOAT", "verdict": "LLM failed"}

        # Node 7: Scenario Generation (triple-LLM)
        try:
            scenario_result = analyze_scenarios(dc, self.ctx)
            self.ctx.scenario_analysis = scenario_result
            self.ctx.data_sources["scenarios"] = "Triple-LLM (deal-specific, corridor-grounded)"
        except Exception as e:
            self.ctx.warnings.append("Scenario generation failed: %s" % e)
            scenario_result = {"scenarios": [], "scenario_narratives": []}

        # Node 8: Legal Risk / Environmental / Concealment (triple-LLM)
        try:
            legal_result = analyze_legal_risk(dc, self.ctx)
            self.ctx.legal_risk_analysis = legal_result
            self.ctx.data_sources["legal_risk"] = "Triple-LLM + web search environmental findings"
        except Exception as e:
            self.ctx.warnings.append("Legal risk analysis failed: %s" % e)
            legal_result = {"risk_score": 5.0, "risk_level": "MODERATE", "summary": "LLM failed"}

        # Node 9: Business Levers + Recommendation (triple-LLM)
        try:
            levers_result = analyze_levers(dc, self.ctx)
            self.ctx.lever_suggestions = levers_result
            self.ctx.data_sources["levers"] = "Triple-LLM (deal-specific creative levers)"
        except Exception as e:
            self.ctx.warnings.append("Lever analysis failed: %s" % e)
            levers_result = {"levers": [], "recommendation": {}, "offers": []}

        # ── Legacy bridge: produce v3-compatible output ──
        # Valuation triangulation (use v3 logic or fixture data)
        hf = deal_data.get("hard_asset_floor", deal_data.get("hard_floor", {}))
        pricing = deal_data.get("pricing", {})
        hard_mid = (hf.get("mid", 0) or pricing.get("hard_floor_mid", 0) or 0)
        hard_low = (hf.get("low", 0) or pricing.get("hard_floor_low", 0) or 0)
        hard_high = (hf.get("high", 0) or pricing.get("hard_floor_high", 0) or 0)
        ask = ask_price or 1
        floor_to_ask = round(hard_mid / ask * 100) if hard_mid > 0 and ask > 0 else 0
        psf = prop.get("price_per_sf", 0) or (ask_price / max(prop.get("sf", prop.get("building_size_sf", 1)), 1))

        # Comps from web search (format for dashboard)
        comps_list = []
        for item in (self.ctx.web_search_comps or [])[:8]:
            if isinstance(item, dict):
                comps_list.append({
                    "address": item.get("title", item.get("address", "")),
                    "price": item.get("price", 0),
                    "sf": item.get("sf", 0),
                    "psf": item.get("psf", 0),
                    "source": item.get("url", item.get("source", "Brave Search")),
                })

        return {
            "listing_id": prop.get("listing_id", deal_data.get("deal", {}).get("listing_id", "")),
            "address": address,
            "city": city,
            "state": state,
            "property_type": ptype,
            "ask_price": ask_price,
            "analysis_date": str(date.today()),
            "hard_floor_mid": min(hard_mid, ask_price) if hard_mid else 0,

            # Live FRED data
            "home_price_appreciation": {
                "msa_name": self.ctx.msa_name,
                "hpi_1yr_pct": self.ctx.msa_hpi_1yr_pct,
                "hpi_5yr_annualized_pct": self.ctx.msa_hpi_5yr_annualized_pct,
                "source": self.ctx.msa_hpi_source,
            },
            "demographics": {
                "median_household_income": self.ctx.county_median_income,
                "unemployment_rate_pct": self.ctx.county_unemployment_pct,
                "population": self.ctx.county_population,
                "source": self.ctx.data_sources.get("demographics", ""),
            },

            # Pricing (dashboard-compatible)
            "pricing": {
                "hard_floor_low": hard_low,
                "hard_floor_mid": hard_mid,
                "hard_floor_high": hard_high,
                "floor_to_ask_pct": floor_to_ask,
                "price_psf": psf,
                "ask": ask_price,
                "stabilized_re_value": round(ask_price * 0.85, -3) if ask_price > 0 else 0,
            },

            # LLM analysis outputs (dashboard-ready)
            "moats": moat_result,
            "scenarios": scenario_result.get("scenarios", []),
            "scenario_narratives": scenario_result.get("scenario_narratives", []),
            "comps": comps_list,
            "legal_risk": legal_result,
            "levers": levers_result.get("levers", []),
            "recommendation": levers_result.get("recommendation", {}),
            "offers": levers_result.get("offers", []),

            # Live context audit trail
            "live_context": self.ctx.to_dict(),
            "data_sources": self.ctx.data_sources,
            "warnings": self.ctx.warnings,
        }
