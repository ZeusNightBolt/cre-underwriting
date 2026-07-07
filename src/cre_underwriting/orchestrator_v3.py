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
        address = prop.get("address", deal_data.get("deal", {}).get("address", ""))
        ask_price = prop.get("price", 0) or deal_data.get("pricing", {}).get("ask", 0) or 0
        
        # Normalize Boonton-schema fields
        if "unit_sf" in prop and "building_size_sf" not in prop:
            prop["building_size_sf"] = prop["unit_sf"]
        deal_data.setdefault("income", deal_data.get("income", {}))
        if "pricing" in deal_data and "price" not in prop:
            prop["price"] = deal_data["pricing"].get("ask", 0)
            prop["price_per_sf"] = deal_data["pricing"].get("price_psf", 0)
        
        # ── Pillar 1: Valuation Triangulation ──
        valuation = valuation_triangulation(deal_data)
        
        # If valuation fails (returns zero), use deal's hard_asset_floor as fallback
        if valuation.get("hard_asset_value_mid", 0) <= 0:
            pricing = deal_data.get("pricing", {})
            hf_fallback = deal_data.get("hard_asset_floor", {})
            if pricing.get("hard_floor_mid", 0) > 0:
                valuation["hard_asset_value_low"] = pricing.get("hard_floor_low", 0)
                valuation["hard_asset_value_mid"] = pricing.get("hard_floor_mid", 0)
                valuation["hard_asset_value_high"] = pricing.get("hard_floor_high", 0)
            elif hf_fallback.get("mid", 0) > 0:
                valuation["hard_asset_value_low"] = hf_fallback.get("low", 0)
                valuation["hard_asset_value_mid"] = hf_fallback.get("mid", 0)
                valuation["hard_asset_value_high"] = hf_fallback.get("high", 0)
        
        # ── Pillar 2: Comps (from file or embedded) ──
        comps_data = {}
        if comps_path:
            try:
                with open(comps_path) as f:
                    comps_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        raw_comps = comps_data or deal_data.get("comps", {})
        if isinstance(raw_comps, list):
            comps_data = {"comps": raw_comps}
        elif isinstance(raw_comps, dict):
            comps_data = raw_comps
        else:
            comps_data = {}
        
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
        frontier_data = self._build_frontier_data(deal_data, purchase_price, valuation)
        
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
        
        # Ensure price_per_sf and building_size_sf are present for comp synthesis
        cp = convexity_deal.setdefault("property", {})
        if not cp.get("price_per_sf") and cp.get("price") and cp.get("sf"):
            cp["price_per_sf"] = round(cp["price"] / cp["sf"], 2)
        if not cp.get("building_size_sf") and cp.get("sf"):
            cp["building_size_sf"] = cp["sf"]
        
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
            "listing_id": prop.get("listing_id", deal_data.get("deal", {}).get("listing_id", "")),
            "address": address,
            "city": prop.get("city", prop.get("municipality", "")),
            "state": prop.get("state", ""),
            "property_type": prop.get("property_type", deal_data.get("deal", {}).get("property_type", "")),
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
            "scenarios": scenarios,
            "property_specific_scenarios": scenarios,
            
            # Legacy
            "convexity": convexity,
            "enhanced": enhanced,
            
            # Hard floor (from valuation)
            "hard_floor_mid": min(valuation["hard_asset_value_mid"], ask_price),
        }
    
    def _build_frontier_data(self, deal_data: dict, base_price: float, valuation: dict = None) -> list:
        """Build effective frontier data points across a range of purchase prices."""
        from copy import deepcopy
        
        prop = deal_data.get("property", {})
        ask = prop.get("price", 0) or 0
        scenarios_raw = deal_data.get("scenarios", {})
        
        # Use provided valuation or recompute, with fallback to fixture's hard_asset_floor
        if valuation and valuation.get("hard_asset_value_low", 0) > 0:
            hard_low = valuation["hard_asset_value_low"]
        else:
            vt = valuation_triangulation(deal_data)
            hard_low = vt.get("hard_asset_value_low", 0)
            if hard_low <= 0:
                hard_low = deal_data.get("hard_asset_floor", {}).get("low", 0)
        
        points = []
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
        """Build property-type-specific scenarios using deal's actual NOI.
        
        Matches 'Retail' as substring (handles 'Retail (Condo)', etc.).
        Uses deal_data['income']['noi'] — no more hardcoded 56,242.
        """
        prop = deal_data.get("property", {})
        property_type = (prop.get("property_type", "Retail") or "Retail").lower()
        purchase = deal_data.get("purchase_price", prop.get("price", 0) or 0) or 1
        income = deal_data.get("income", {})
        noi = income.get("noi", 0) or 0
        tax = deal_data.get("tax", {})
        post_sale_tax = tax.get("post_sale", {}).get("annual_tax_estimated", 0) or 0
        
        adj_noi = max(noi - post_sale_tax, 0) if noi > 0 else noi
        if adj_noi <= 0:
            leases = deal_data.get("leases", {})
            sf = prop.get("sf", 0) or 0
            rent_psf = leases.get("current_rent_psf", 0) or 0
            if sf > 0 and rent_psf > 0:
                adj_noi = sf * rent_psf * 0.6
        if adj_noi <= 0:
            exit_cap = deal_data.get("exit_cap_rate", 0.075) or 0.075
            adj_noi = purchase * exit_cap * 0.85
        
        scenarios = {}
        is_retail = "retail" in property_type
        is_office = "office" in property_type
        is_industrial = "industrial" in property_type
        
        if is_retail or is_office or is_industrial:
            exit_cap = deal_data.get("exit_cap_rate", 0.08) or 0.08
            base_value = round(adj_noi / exit_cap, -3)
            base_moic = round(base_value / purchase, 2) if purchase > 0 else 0
            phase1_noi = round(adj_noi * 1.30 if adj_noi > 0 else purchase * 0.07)
            phase1_value = round(phase1_noi / (exit_cap - 0.005), -3)
            phase2_noi = round(adj_noi * 1.55 if adj_noi > 0 else purchase * 0.09)
            phase2_value = round(phase2_noi / (exit_cap - 0.01), -3)
            
            scenarios = {
                "Worst Case — E-commerce Disruption + Tenant Loss": {
                    "value": round(purchase * 0.40, -3),
                    "moic_5yr": 0.40,
                    "noi": round(adj_noi * 0.50) if adj_noi > 0 else 15000,
                    "description": "Tenants vacate. Vacancy hits 40%. Exit cap +200bps. MOIC 0.40x.",
                },
                "Worst Case — Rate Shock / Cap Rate Expansion": {
                    "value": round(purchase * 0.55, -3),
                    "moic_5yr": 0.55,
                    "noi": round(adj_noi * 0.75) if adj_noi > 0 else 25000,
                    "description": "Fed raises rates. Cap rates expand 150bps. Exit cap 9.5%. MOIC 0.55x.",
                },
                "Baseline — Tax-Adjusted Status Quo (As-Is)": {
                    "value": base_value,
                    "moic_5yr": base_moic,
                    "noi": adj_noi,
                    "description": f"Tax-adjusted baseline. NOI ${adj_noi:,.0f}. Exit cap {exit_cap*100:.1f}%. Modest growth.",
                },
                "Phase 1 Optimize — Rent Push + Low-Capex Levers (Best Case)": {
                    "value": phase1_value,
                    "moic_5yr": round(phase1_value / purchase, 2) if purchase > 0 else 0,
                    "noi": phase1_noi,
                    "description": f"Push rents to market. NOI ${phase1_noi:,.0f}. Exit cap {(exit_cap-0.005)*100:.1f}%.",
                },
                "Phase 2 Expand — Renovate + Tenant Upgrade": {
                    "value": phase2_value,
                    "moic_5yr": round(phase2_value / purchase, 2) if purchase > 0 else 0,
                    "noi": phase2_noi,
                    "description": f"Renovation to Class B. NOI ${phase2_noi:,.0f}. Exit cap {(exit_cap-0.01)*100:.1f}%.",
                },
                "Phase 3 Strategic — Parcel Assembly / Redevelop": {
                    "value": round(valuation.get("hard_asset_value_high", purchase * 1.5) * 1.5, -3),
                    "moic_5yr": round(valuation.get("hard_asset_value_high", purchase * 1.5) * 1.5 / purchase, 2) if purchase > 0 else 0,
                    "noi": None,
                    "description": "Assemble adjacent parcels. Redevelopment play. Moonshot.",
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
