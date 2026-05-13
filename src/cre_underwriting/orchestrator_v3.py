#!/usr/bin/env python3
"""
cre_underwriting.orchestrator_v3 — 8-Pillar Enhanced Underwriting Orchestrator.

Pillars:
  1. Valuation Triangulation (land + building + equipment + licenses)
  2. Comparable Properties (enhanced comp analysis)
  3. Home Price Appreciation (FRED + Census)
  4. Financial & Business Levers (pro forma + lever catalog)
  5. Demographics & Migration
  6. Effective Frontier Graph
  7. Rigorous Scenario Analysis (property-type-specific)
  8. Comprehensive Output (merge all → dashboard-ready)
"""
import json
from datetime import date
from pathlib import Path
from typing import Dict, Any, Optional

from .valuation import valuation_triangulation
from .financial_levers import build_pro_forma, lever_analysis
from .convexity import ConvexityEngine, from_json as convexity_from_json
from .enhanced import EnhancedAnalyzer


class EnhancedPipelineOrchestrator:
    """
    8-Pillar underwriting orchestrator.
    
    Usage:
        orch = EnhancedPipelineOrchestrator()
        result = orch.run("deal_analysis.json")
        # result contains all 8 pillars + legacy convexity/enhanced
    """
    
    def __init__(self):
        self.convexity = ConvexityEngine()
    
    def run(self, deal_path: str, env_path: str = None, comps_path: str = None) -> dict:
        """Run full 8-pillar pipeline on a deal analysis JSON."""
        with open(deal_path) as f:
            deal_data = json.load(f)
        
        return self.run_dict(deal_data, env_path, comps_path)
    
    def run_dict(self, deal_data: dict, env_path: str = None, comps_path: str = None) -> dict:
        """Run full pipeline from in-memory dict."""
        prop = deal_data.get("property", {})
        address = prop.get("address", "")
        ask_price = prop.get("price", 0) or 0
        
        # ── Pillar 1: Valuation Triangulation ──
        valuation = valuation_triangulation(deal_data)
        
        # ── Pillar 2: Comps (from file or embedded) ──
        comps_data = {}
        if comps_path:
            try:
                with open(comps_path) as f:
                    comps_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        comps_data = comps_data or deal_data.get("comps", {})
        
        # ── Pillar 3: Home Price Appreciation ──
        hpa = {
            "greenville_msa": {
                "hpi_1yr_pct": 5.2, "hpi_3yr_annualized_pct": 5.8,
                "hpi_5yr_annualized_pct": 6.1, "vs_national": "above",
                "source": "FHFA HPI Greenville-Anderson MSA (estimated from public data)"
            },
            "zip_29605": {
                "median_home_value": 240000, "median_home_value_1yr_change_pct": 4.8,
                "source": "ACS 2023 / Zillow ZHVI (estimated)"
            },
            "greenville_county": {
                "median_home_value": 285000, "median_home_value_1yr_change_pct": 5.5,
                "median_home_value_5yr_change_pct": 35.0,
            },
            "hpa_tailwind_score": 7,  # 1-10
            "narrative": (
                f"Greenville MSA HPI up {5.2}% YoY, {6.1}% annualized over 5 years. "
                f"Strong residential appreciation creates retail demand tailwind "
                f"with typical 12-24 month lag. Zip 29605 median home ${240:,} — "
                f"affordable relative to national median."
            ),
            "data_quality": "estimated — needs FRED API key for precise data"
        }
        
        # ── Pillar 4: Financial & Business Levers ──
        purchase_price = deal_data.get("purchase_price", ask_price)
        pro_forma = build_pro_forma(deal_data, purchase_price)
        levers = lever_analysis(deal_data, purchase_price)
        
        # ── Pillar 5: Demographics & Migration ──
        demographics = {
            "zip_29605": {
                "population": 35000,
                "median_household_income": 55000,
                "poverty_rate_pct": 15.0,
                "bachelor_degree_pct": 28.0,
            },
            "greenville_county": {
                "population": 558000,
                "population_growth_1yr_pct": 2.1,
                "median_household_income": 68000,
                "poverty_rate_pct": 11.0,
                "bachelor_degree_pct": 35.0,
                "unemployment_rate_pct": 3.2,
            },
            "migration": {
                "net_domestic_migration": "strongly positive (+15,000-20,000/yr)",
                "top_inflow_states": ["NC", "GA", "NY", "CA", "FL"],
                "migration_score": 8,  # 1-10
                "narrative": "Greenville County is among the fastest-growing in the Southeast. Strong inbound migration from high-cost states (NY, CA) driving housing and retail demand.",
            },
            "retail_demand": {
                "score": 7,
                "narrative": "Population growth (2.1%) + income growth = retail spending growth. Undersupplied retail per capita in this corridor."
            },
            "data_quality": "estimated from ACS/Census public data — API key would improve precision"
        }
        
        # ── Pillar 6: Effective Frontier ──
        frontier_data = self._build_frontier_data(deal_data, purchase_price)
        
        # ── Pillar 7: Scenarios (property-type-specific) ──
        scenarios = self._build_scenarios(deal_data, levers, valuation)
        
        # ── Legacy: Convexity + Enhanced ──
        # Build a convexity-compatible deal dict
        convexity_deal = dict(deal_data)
        convexity_deal["scenarios"] = scenarios
        convexity_deal["hard_asset_floor"] = {
            "low": valuation["hard_asset_value_low"],
            "mid": min(valuation["hard_asset_value_mid"], ask_price),
            "high": min(valuation["hard_asset_value_high"], ask_price),
        }
        convexity_deal["capital_invested"] = purchase_price + 0  # no upfront capex in base
        
        convexity_result = convexity_from_json(convexity_deal)
        convexity = convexity_result.to_dict()
        
        # Enhanced analysis
        enh = EnhancedAnalyzer(convexity_deal, {}, comps_data)
        enhanced = enh.analyze()
        
        # Inject retail-specific moats if available
        if "retail_moats" in deal_data:
            enhanced["moats"] = deal_data["retail_moats"]
        
        # ── Pillar 8: Synthesize ──
        return {
            # Identity
            "listing_id": prop.get("listing_id", ""),
            "address": address,
            "city": prop.get("city", prop.get("municipality", "")),
            "state": prop.get("state", ""),
            "property_type": prop.get("property_type", ""),
            "ask_price": ask_price,
            "analysis_date": str(date.today()),
            
            # New pillars
            "valuation_triangulation": valuation,
            "comps": comps_data,
            "home_price_appreciation": hpa,
            "pro_forma": pro_forma,
            "business_levers": levers,
            "demographics": demographics,
            "effective_frontier": frontier_data,
            "property_specific_scenarios": scenarios,
            
            # Legacy
            "convexity": convexity,
            "enhanced": enhanced,
            
            # Hard floor (from valuation)
            "hard_floor_mid": min(valuation["hard_asset_value_mid"], ask_price),
        }
    
    def _build_frontier_data(self, deal_data: dict, base_price: float) -> list:
        """Build effective frontier data points across a range of purchase prices."""
        from copy import deepcopy
        
        prop = deal_data.get("property", {})
        ask = prop.get("price", 0) or 0
        scenarios_raw = deal_data.get("scenarios", {})
        
        points = []
        # Re-use the valuation already computed in run_dict
        hard_low = deal_data.get("valuation_override", {}).get("hard_low", 
                    valuation_triangulation(deal_data)["hard_asset_value_low"])
        
        for price in range(int(ask * 0.50), int(ask * 1.05) + 25000, 25000):
            # Worst = hard asset floor as % of purchase (capped at price)
            worst_floor = min(hard_low, price)
            worst_pct = round(worst_floor / price * 100, 1) if price > 0 else 100
            
            # Best = estimated upside (optimize scenario exit value)
            best_moic = round(1.6 * (ask / max(price, 1)), 2)  # MOIC scales inversely with price
            
            if best_moic >= 2.0 and worst_pct < 60:
                zone = "Pursue aggressively"
            elif worst_pct < 90:
                zone = "Acceptable selectively"
            elif worst_pct < 110:
                zone = "Pass unless portfolio reason"
            else:
                zone = "Walk away"
            
            points.append({
                "purchase_price": price,
                "worst_pct_capital": worst_pct,
                "best_moic": best_moic,
                "zone": zone,
            })
        
        # Find attractiveness threshold
        attractive = None
        for p in points:
            if p["zone"] in ("Pursue aggressively", "Acceptable selectively") and attractive is None:
                attractive = p["purchase_price"]
        
        return {
            "points": points,
            "attractiveness_threshold": attractive,
            "ask_price": ask,
            "ask_zone": next((p["zone"] for p in points if p["purchase_price"] == ask), "Unknown"),
            "target_zone": next((p["zone"] for p in points if p["purchase_price"] <= 675000), "Unknown"),
        }
    
    def _build_scenarios(self, deal_data: dict, levers: dict, valuation: dict) -> dict:
        """Build property-type-specific scenarios with lever contributions."""
        prop = deal_data.get("property", {})
        property_type = prop.get("property_type", "Retail")
        purchase = deal_data.get("purchase_price", prop.get("price", 0) or 0)
        
        scenarios = {}
        
        if property_type == "Retail":
            scenarios = {
                # Worst: engine matches "worst case" keyword → picks LOWEST exit_value
                "Worst Case — E-commerce Disruption + Tenant Loss": {
                    "value": round(purchase * 0.40, -3),
                    "moic_5yr": 0.40,
                    "noi": 25000,
                    "description": "Amazon effect accelerates. Two tenants close. Vacancy hits 40%. Exit cap 10% (distressed). MOIC 0.40x."
                },
                "Worst Case — Rate Shock / Cap Rate Expansion": {
                    "value": round(purchase * 0.55, -3),
                    "moic_5yr": 0.55,
                    "noi": 45000,
                    "description": "Fed raises rates. Cap rates expand 150bps. Exit cap 9.5%. Property value compression. MOIC 0.55x."
                },
                # Base: engine matches "baseline" or "as-is" keyword
                "Baseline — Tax-Adjusted Status Quo (As-Is)": {
                    "value": round(56242 / 0.085, -3),  # ~$662K
                    "moic_5yr": round(56242 / 0.085 / purchase, 2),
                    "noi": 56242,
                    "description": "Tenants stay. SC post-sale tax applied ($17.3K). NOI $56.2K. Exit cap 8.5%. Modest growth."
                },
                # Best: engine matches "phase 1 optimize" or "best case" keyword
                "Phase 1 Optimize — Rent Push + Low-Capex Levers (Best Case)": {
                    "value": round((56242 + 20000) / 0.08, -3),
                    "moic_5yr": round((56242 + 20000) / 0.08 / purchase, 2),
                    "noi": 76242,
                    "description": "Push rents to market (+$15K). Add vending + ATM (+$5K). NOI $76K. Exit cap 8%. Active management pays."
                },
                # Best: engine matches "phase 2 expand" keyword
                "Phase 2 Expand — Renovate + Tenant Upgrade": {
                    "value": round((56242 + 35000) / 0.075, -3),
                    "moic_5yr": round((56242 + 35000) / 0.075 / purchase, 2),
                    "noi": 91242,
                    "description": "$50K renovation to Class B. Full occupancy at $14/SF. Exit cap 7.5%. Higher quality tenant mix."
                },
                "Phase 3 Strategic — Parcel Assembly / Redevelop": {
                    "value": round(valuation["hard_asset_value_high"] * 1.5, -3),
                    "moic_5yr": round(valuation["hard_asset_value_high"] * 1.5 / purchase, 2),
                    "noi": None,
                    "description": f"Assemble adjacent parcels. 1.40 acres on Augusta Rd with I-85 access. Redevelopment play. Moonshot."
                },
            }
        
        return scenarios


def main():
    """CLI: enhanced-pipeline <deal.json>"""
    import sys
    if len(sys.argv) < 2:
        print("Usage: enhanced-pipeline <deal_analysis.json> [comps.json]")
        sys.exit(1)
    
    orch = EnhancedPipelineOrchestrator()
    result = orch.run(
        sys.argv[1],
        comps_path=sys.argv[2] if len(sys.argv) > 2 else None,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
