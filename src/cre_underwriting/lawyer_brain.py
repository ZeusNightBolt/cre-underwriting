#!/usr/bin/env python3
"""
cre_underwriting.lawyer_brain — Legal & Concealment Risk Scoring.

Adds lawyer-brain methodology to CRE underwriting:
  1. Legal Risk Score (0–10): regulatory exposure, title issues, zoning risk
  2. Concealment Detection: missing data, opaque disclosures, seller red flags
  3. Environmental Liability Adjustment: $ amount to subtract from asset value
  4. Tax Bomb Severity: post-sale assessment risk quantified

Usage:
    from cre_underwriting.lawyer_brain import LawyerBrain
    lb = LawyerBrain()
    result = lb.analyze(deal_data, env_data)
    print(result["legal_risk_score"])    # 0–10
    print(result["concealment_flags"])   # list[str]
    print(result["env_liability_adj"])   # $ amount
"""

from typing import Dict, Any, List, Optional


class LawyerBrain:
    """Legal & concealment risk analysis for CRE underwriting."""

    # ── Concealment pattern detection ─────────────────────────

    @staticmethod
    def _detect_concealment(deal_data: dict) -> List[Dict[str, str]]:
        """Find evidence of seller hiding material information."""
        flags = []
        prop = deal_data.get("property", {})

        # 1. Hidden NOI / behind login wall
        income = deal_data.get("income", {})
        noi_source = income.get("noi_source", "")
        if "ESTIMATED" in noi_source or "behind login" in noi_source.lower():
            flags.append({
                "risk": "NOI deliberately hidden behind login wall",
                "severity": "HIGH",
                "detail": "Listing withholds actual financials. Seller/broker likely "
                          "hiding weak cash flow or inflated asking price. Force "
                          "broker to provide OM/rent roll before LOI.",
            })

        # 2. Assessment-to-ask ratio gap
        assessment_total = prop.get("assessment_total", 0)
        ask_price = prop.get("price", deal_data.get("ask_price", 0))
        if ask_price > 0 and assessment_total > 0:
            ratio = assessment_total / ask_price
            if ratio < 0.30:
                flags.append({
                    "risk": "Assessment massively below ask price",
                    "severity": "HIGH",
                    "detail": f"Assessment ${assessment_total:,.0f} = "
                              f"{ratio:.0%} of ${ask_price:,.0f} ask. "
                              f"NJ reassesses at sale — post-sale tax bomb "
                              f"will destroy NNN tenant economics.",
                })

        # 3. Stale listing
        dom = prop.get("days_on_market") or 0
        dom = int(dom) if dom else 0
        if dom > 360:
            flags.append({
                "risk": "Extreme stale listing (>1 year)",
                "severity": "HIGH",
                "detail": f"{dom} days on market suggests the ask price is "
                          f"detached from market reality. Price reduction "
                          f"{'present' if prop.get('price_reduction') else 'not indicated'}.",
            })
        elif dom > 180:
            flags.append({
                "risk": "Stale listing (6–12 months)",
                "severity": "MODERATE",
                "detail": f"{dom} days on market. May indicate pricing gap "
                          f"or hidden property issues.",
            })

        # 4. No renovation history on old building
        year_built = prop.get("year_built", 0)
        year_renovated = prop.get("year_renovated")
        if year_built and year_built < 1950 and not year_renovated:
            flags.append({
                "risk": f"Pre-1950 construction ({year_built}) with no renovation history",
                "severity": "MODERATE",
                "detail": "Roof, HVAC, electrical, plumbing likely near end-of-life. "
                          "Get full inspection + capex reserve study before offer.",
            })

        # 5. Price reduction on already-stale listing
        if prop.get("price_reduction") and dom > 90:
            flags.append({
                "risk": "Price cut on stale listing",
                "severity": "MODERATE",
                "detail": "Price reduction + days on market = capitulation signal. "
                          "Seller may accept below-ask offers. Leverage in negotiation.",
            })

        return flags

    # ── Legal risk scoring (0–10) ──────────────────────────────

    @staticmethod
    def _compute_legal_risk(deal_data: dict,
                            env_data: Optional[dict] = None) -> int:
        """
        Score legal risk from 0 (clean) to 10 (toxic).

        Factors:
          - Environmental Phase I recommendation (+2)
          - UST sites nearby > 1000 (+2)
          - Flood risk medium/high (+1/+2)
          - Known contamination (+3)
          - Tax bomb severity from assessment gap (+1 to +3)
          - Zoning variance required for value-add (+1)
          - No renovation on pre-1950 building (+1)
        """
        score = 0
        prop = deal_data.get("property", {})
        env = (env_data or {}).get("environmental", env_data or {})

        # Environmental
        if env.get("phase_i_recommended"):
            score += 2
        if env.get("ust_sites_nearby", 0) > 1000:
            score += 2
        if env.get("flood_risk_level") == "high":
            score += 2
        elif env.get("flood_risk_level") == "medium":
            score += 1
        if env.get("known_contamination"):
            score += 3

        # Tax bomb
        assessment = prop.get("assessment_total", 0)
        ask = prop.get("price", deal_data.get("ask_price", 0))
        if ask > 0 and assessment > 0:
            ratio = assessment / ask
            if ratio < 0.15:
                score += 3
            elif ratio < 0.30:
                score += 2
            elif ratio < 0.50:
                score += 1

        # Structural age
        year_built = prop.get("year_built", 0)
        year_renovated = prop.get("year_renovated")
        if year_built and year_built < 1950 and not year_renovated:
            score += 1

        return min(10, score)

    # ── Environmental liability adjustment ────────────────────

    @staticmethod
    def _compute_env_liability(env_data: Optional[dict],
                               sf: int = 0) -> float:
        """
        Estimate environmental liability as a $ deduction from asset value.

        UST proximity risk: $2–$5/SF cleanup reserve for high-risk counties.
        Flood zone premium: $1–$3/SF for medium/high flood risk.
        Known contamination: $10–$20/SF (Phase II + remediation).
        """
        if not env_data:
            return 0.0

        env = env_data.get("environmental", env_data)
        liability = 0.0

        # UST risk: reserve for potential tank removal
        ust_risk = env.get("ust_risk", "unknown")
        if ust_risk == "high":
            liability += sf * 5.0
        elif ust_risk == "medium":
            liability += sf * 2.5
        elif ust_risk == "low":
            liability += sf * 0.50

        # Flood zone: insurance premium NPV
        flood = env.get("flood_risk_level", "unknown")
        if flood == "high":
            liability += sf * 3.0
        elif flood == "medium":
            liability += sf * 1.0

        # Known contamination
        if env.get("known_contamination"):
            liability += sf * 15.0

        return round(liability, -3)  # Round to nearest $1K

    # ── Tax bomb severity ─────────────────────────────────────

    @staticmethod
    def _compute_tax_bomb(deal_data: dict) -> Dict[str, Any]:
        """Quantify tax reassessment risk for NJ properties."""
        tax = deal_data.get("tax_bomb", deal_data.get("tax", {}))
        deal_data.get("property", {})

        return {
            "current_tax_estimated": tax.get("current_tax_estimated", 0),
            "post_sale_tax_estimated": tax.get("post_sale_tax", 0),
            "tax_increase_pct": tax.get("tax_increase_pct", 0),
            "tax_increase_per_sf": tax.get("tax_increase_per_sf", 0),
            "verdict": tax.get("verdict", ""),
            "tenant_impact": tax.get("tenant_impact", ""),
        }

    # ── Missing data audit ────────────────────────────────────

    @staticmethod
    def _audit_missing_data(deal_data: dict) -> List[str]:
        """Catalog material facts missing from the listing."""
        missing = []
        prop = deal_data.get("property", {})
        income = deal_data.get("income", {})

        if not income.get("noi_estimated") and "ESTIMATED" in income.get("noi_source", ""):
            missing.append("NOI / Cap Rate (behind login wall)")
        if not income.get("gross_rent"):
            missing.append("In-place rent roll / lease terms")
        if not prop.get("leased_pct"):
            missing.append("Tenant names and lease expiration dates")
        if not prop.get("year_renovated") and (prop.get("year_built", 2000) < 1980):
            missing.append("Renovation history (none mentioned)")
        missing.append("Environmental Phase I status")
        missing.append("Property tax bill amount")

        return missing

    # ── Main API ──────────────────────────────────────────────

    def analyze(self, deal_data: dict,
                env_data: Optional[dict] = None) -> Dict[str, Any]:
        """Run full lawyer-brain analysis and return dict."""
        prop = deal_data.get("property", {})
        sf = prop.get("building_size_sf", prop.get("sf", 0)) or 0

        concealment = self._detect_concealment(deal_data)
        legal_risk = self._compute_legal_risk(deal_data, env_data)
        env_liability = self._compute_env_liability(env_data, sf)
        tax_bomb = self._compute_tax_bomb(deal_data)
        missing = self._audit_missing_data(deal_data)

        severity = (
            "CRITICAL" if legal_risk >= 8 else
            "HIGH" if legal_risk >= 6 else
            "MODERATE" if legal_risk >= 4 else
            "LOW" if legal_risk >= 2 else
            "MINIMAL"
        )

        return {
            "legal_risk_score": legal_risk,
            "legal_risk_severity": severity,
            "concealment_flags": concealment,
            "concealment_count": len([f for f in concealment if f["severity"] == "HIGH"]),
            "env_liability_adjustment": env_liability,
            "tax_bomb_analysis": tax_bomb,
            "missing_data": missing,
            "missing_data_count": len(missing),
            "narrative": self._build_narrative(legal_risk, concealment,
                                               env_liability, tax_bomb),
        }

    @staticmethod
    def _build_narrative(legal_risk: int,
                         concealment: List[Dict],
                         env_liability: float,
                         tax_bomb: Dict) -> str:
        high_flags = [f for f in concealment if f["severity"] == "HIGH"]
        parts = []

        if legal_risk >= 6:
            parts.append(
                f"Legal risk score {legal_risk}/10 — HIGH. "
                f"Phase I ESA strongly recommended before LOI."
            )
        elif legal_risk >= 4:
            parts.append(
                f"Legal risk score {legal_risk}/10 — MODERATE. "
                f"Standard due diligence required."
            )

        if env_liability > 0:
            parts.append(
                f"Environmental liability estimate: ${env_liability:,.0f}. "
                f"Budget for Phase I/II before closing."
            )

        if high_flags:
            parts.append(
                f"{len(high_flags)} HIGH-severity concealment flags detected: "
                + "; ".join(f["risk"] for f in high_flags[:3])
            )

        if tax_bomb.get("tax_increase_pct", 0) > 100:
            parts.append(
                f"Tax bomb: post-sale taxes increase "
                f"{tax_bomb['tax_increase_pct']:.0f}%. "
                f"Must factor into underwriting."
            )

        return " ".join(parts)
