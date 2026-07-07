"""
cre_underwriting.convexity — Core convexity analysis engine.

Implements divergence analysis, effective frontier classification, PWEV
computation, and verdict generation for CRE deals.

Usage:
    from cre_underwriting.convexity import ConvexityEngine
    from cre_underwriting.models import DealInput, Scenario

    engine = ConvexityEngine()
    result = engine.analyze(deal)
    print(result.verdict.verdict)         # "CONDITIONAL"
    print(result.divergence.convexity_ratio)  # 1.21
"""

import json
import math
from typing import List, Optional, Tuple

from .constants import (
    CONVEXITY, DEFAULT_PROBABILITIES, FRONTIER_ZONES, OFFERS, SCENARIO_CATEGORIES,
)
from .models import (
    ConvexityResult, DealInput, DivergenceOutput, FrontierPoint,
    PWEVOutput, Scenario, VerdictOutput, extract_pricing,
)


class ConvexityEngine:
    """
    Core convexity analysis engine.

    Pipeline:
      1. Identify worst/base/best scenarios by name
      2. Compute effective worst (max of operating worst and hard floor mid)
      3. Compute divergence metrics (spread, convexity ratio, risk/reward)
      4. Compute PWEV
      5. Classify effective frontier zone
      6. Generate verdict
    """

    def __init__(self):
        self._scenario_names = SCENARIO_CATEGORIES

    # ── Scenario identification ─────────────────────────────

    def _find_scenario(self, scenarios: List[Scenario],
                       names: List[str]) -> Optional[Scenario]:
        """Find a scenario by name (case-insensitive match)."""
        names_lower = [n.lower() for n in names]
        for s in scenarios:
            if s.name.lower() in names_lower:
                return s
        return None

    def _get_worst_base_best(self, deal: DealInput) -> Tuple[Scenario, Scenario, Scenario]:
        """Extract worst, base, best scenarios from deal. Raises ValueError if missing.

        For 'worst': picks the matching scenario with LOWEST exit_value.
        For 'best': picks the matching scenario with HIGHEST exit_value.
        """
        worst_matches = []
        base_matches = []
        best_matches = []

        worst_names_lower = [n.lower() for n in self._scenario_names["worst"]]
        base_names_lower = [n.lower() for n in self._scenario_names["base"]]
        best_names_lower = [n.lower() for n in self._scenario_names["best"]]

        for s in deal.scenarios:
            nl = s.name.lower()
            if any(w in nl for w in worst_names_lower):
                worst_matches.append(s)
            if any(b in nl for b in base_names_lower):
                base_matches.append(s)
            if any(b in nl for b in best_names_lower):
                best_matches.append(s)

        if not worst_matches:
            raise ValueError(
                f"No worst-case scenario found. Expected one of: "
                f"{self._scenario_names['worst']}. Got: {[s.name for s in deal.scenarios]}")
        if not base_matches:
            raise ValueError(
                f"No baseline scenario found. Expected one of: "
                f"{self._scenario_names['base']}")
        if not best_matches:
            raise ValueError(
                f"No best-case scenario found. Expected one of: "
                f"{self._scenario_names['best']}")

        worst = min(worst_matches, key=lambda s: s.exit_value)
        base = base_matches[0]
        best = max(best_matches, key=lambda s: s.exit_value)
        return worst, base, best

    # ── Divergence computation ──────────────────────────────

    def compute_divergence(self, deal: DealInput) -> DivergenceOutput:
        """
        Compute divergence metrics for the deal.

        CRITICAL: Effective worst = max(worst_scenario_value, hard_floor_mid).
        If the operating worst-case falls below the hard asset floor,
        the owner would liquidate before letting operations deteriorate
        that far. (Bug documented from Fords 34554176.)
        """
        worst, base, best = self._get_worst_base_best(deal)

        worst_value = worst.exit_value
        base_value = base.exit_value
        best_value = best.exit_value

        # Effective worst (the kill-switch logic)
        effective_worst = max(worst_value, deal.hard_floor_mid)

        # Spread metrics
        absolute_spread = best_value - effective_worst
        capital = deal.capital_invested if deal.capital_invested else deal.purchase_price
        if capital <= 0:
            raise ValueError(f"Capital invested must be > 0, got {capital}")

        capital_normalized_spread = absolute_spread / capital

        # Convexity ratio: (Best - Base) / (Base - Effective Worst)
        upside = best_value - base_value
        downside = base_value - effective_worst

        if downside <= 0:
            convexity_ratio = math.inf if upside > 0 else 0.0
        elif upside <= 0:
            convexity_ratio = 0.0
        else:
            convexity_ratio = upside / downside

        # Convexity verdict using named constants
        if convexity_ratio >= CONVEXITY.high:
            cv = "HIGH"
        elif convexity_ratio >= CONVEXITY.positive:
            cv = "POSITIVE"
        elif convexity_ratio >= CONVEXITY.marginal:
            cv = "MARGINAL"
        else:
            cv = "NEGATIVE"

        worst_pct = (effective_worst / capital * 100) if capital > 0 else 100
        best_moic = best.moic if best.moic else (best_value / capital if capital > 0 else 1.0)

        # Risk/reward = best MOIC per unit of capital AT RISK (worst-case
        # loss fraction), not per unit retained. worst_pct is the % of
        # capital RETAINED, so the loss fraction is (100 - worst_pct).
        # Clamp the denominator at 1% so a zero-loss deal reports a large
        # finite ratio instead of dividing by zero.
        loss_pct = 100.0 - worst_pct
        rr_denom = loss_pct if loss_pct > 0 else 1.0
        risk_reward = best_moic / (rr_denom / 100)

        return DivergenceOutput(
            absolute_spread=absolute_spread,
            capital_normalized_spread=capital_normalized_spread,
            convexity_ratio=convexity_ratio,
            convexity_verdict=cv,
            worst_scenario_value=worst_value,
            hard_floor_mid=deal.hard_floor_mid,
            effective_worst=effective_worst,
            base_scenario_value=base_value,
            best_scenario_value=best_value,
            worst_case_pct_capital=round(worst_pct, 1),
            best_case_moic=best_moic,
            risk_reward_ratio=risk_reward,
        )

    # ── PWEV computation ────────────────────────────────────

    def compute_pwev(self, deal: DealInput) -> PWEVOutput:
        """Compute probability-weighted expected value over all scenarios."""
        total_prob = sum(s.probability for s in deal.scenarios)
        pwev = 0.0
        for s in deal.scenarios:
            if s.probability > 0:
                val = s.exit_value
                pwev += s.probability * val

        if total_prob > 0 and abs(total_prob - 1.0) > 0.01:
            pwev = pwev / total_prob

        pwev_vs_ask = ((pwev - deal.ask_price) / deal.ask_price * 100) if deal.ask_price > 0 else 0

        worst, base, best = self._get_worst_base_best(deal)
        wv = worst.exit_value
        bv = base.exit_value
        bsv = best.exit_value

        return PWEVOutput(
            pwev=pwev,
            pwev_vs_ask_pct=pwev_vs_ask,
            is_underpriced=pwev > deal.ask_price,
            worst_contribution=worst.probability * wv,
            base_contribution=base.probability * bv,
            best_contribution=best.probability * bsv,
        )

    # ── Effective Frontier ──────────────────────────────────

    def compute_effective_frontier(self, deal: DealInput) -> FrontierPoint:
        """Classify where the deal sits on the effective frontier.

        FRONTIER_ZONES thresholds are expressed as worst-case LOSS (% of
        capital that can be lost). divergence.worst_case_pct_capital is the
        % of capital RETAINED in the worst case (effective_worst / capital),
        so convert explicitly: loss_pct = 100 - retained_pct. Comparing the
        retained % against the loss thresholds inverted the classification
        (highest-loss deals were labeled 'Pursue aggressively').
        """
        div = self.compute_divergence(deal)
        loss_pct = 100.0 - div.worst_case_pct_capital
        y = div.best_case_moic

        if y >= FRONTIER_ZONES["pursue_aggressively"]["best_min_moic"]:
            zone = ("Pursue aggressively" if loss_pct < FRONTIER_ZONES["pursue_aggressively"]["worst_max_pct"]
                    else "Acceptable selectively")
        else:
            zone = ("Pass unless portfolio reason" if loss_pct < FRONTIER_ZONES["pass_portfolio"]["worst_max_pct"]
                    else "Walk away")

        return FrontierPoint(x=loss_pct, y=y, zone=zone)

    # ── Verdict generation ──────────────────────────────────

    def generate_verdict(self, deal: DealInput) -> VerdictOutput:
        """Generate final deal verdict based on convexity analysis.

        Offer recommendations use the unified OFFERS thresholds from
        constants.py — same source as OfferAnalyzer.ladder().
        """
        div = self.compute_divergence(deal)
        frontier = self.compute_effective_frontier(deal)
        pwev = self.compute_pwev(deal)

        reasoning = []
        target_offer = None
        walk_away = None
        verdict = "PASS"

        # Gate 1: Negative convexity → PASS
        if div.convexity_ratio < CONVEXITY.marginal:
            return VerdictOutput(
                verdict="PASS", target_offer=None, walk_away=None,
                convexity_ratio=div.convexity_ratio, zone=frontier.zone,
                reasoning=[f"Negative convexity (ratio {div.convexity_ratio:.2f}) — "
                          f"downside exceeds upside."],
                risk_reward_summary=(
                    f"Risk: ${deal.capital_invested:,.0f} at risk, "
                    f"effective worst {div.worst_case_pct_capital:.0f}% of capital. PASS."))

        # Gate 2: Walk away zone — allow CONDITIONAL for marginal+
        if frontier.zone == "Walk away":
            if div.convexity_ratio >= CONVEXITY.marginal:
                target_offer = deal.hard_floor_mid * OFFERS.aggressive_multiplier
                walk_away = min(deal.ask_price * OFFERS.ask_cap_pct,
                               deal.hard_floor_mid * OFFERS.walk_multiplier)
                verdict = "CONDITIONAL"
                reasoning.append(f"Frontier: {frontier.zone} — "
                               f"worst-case loss {frontier.x:.0f}%, best MOIC {frontier.y:.2f}x. "
                               f"BUT convexity {div.convexity_verdict.lower()} "
                               f"(ratio {div.convexity_ratio:.2f}).")
                reasoning.append(f"CONDITIONAL — pursue at ≤${target_offer:,.0f}, "
                               f"walk above ${walk_away:,.0f}.")
                return VerdictOutput(
                    verdict=verdict, target_offer=target_offer, walk_away=walk_away,
                    convexity_ratio=div.convexity_ratio, zone=frontier.zone,
                    reasoning=reasoning,
                    risk_reward_summary=(
                        f"Risk: ${deal.capital_invested:,.0f}, "
                        f"worst-case loss {frontier.x:.0f}% of capital. "
                        f"Best MOIC {frontier.y:.2f}x. "
                        f"Convexity {div.convexity_ratio:.2f} ({div.convexity_verdict}). "
                        f"Conditional — requires price discipline."))

            return VerdictOutput(
                verdict="PASS", target_offer=None, walk_away=None,
                convexity_ratio=div.convexity_ratio, zone=frontier.zone,
                reasoning=[f"Frontier: {frontier.zone}. "
                          f"Negative convexity ({div.convexity_ratio:.2f})."],
                risk_reward_summary="Walk away — insufficient upside for the risk.")

        # Gate 3: Pursue aggressively
        if frontier.zone == "Pursue aggressively":
            target_offer = deal.hard_floor_mid * OFFERS.aggressive_multiplier
            walk_away = min(deal.ask_price * OFFERS.ask_cap_pct,
                           deal.hard_floor_mid * OFFERS.walk_multiplier)
            verdict = f"PURSUE AT ${target_offer:,.0f}"
            reasoning.append(f"Frontier: {frontier.zone}. "
                           f"Convexity {div.convexity_ratio:.2f} ({div.convexity_verdict}). "
                           f"Target ${target_offer:,.0f}.")

        # Gate 4: Conditional (marginal convexity or acceptable zone)
        elif div.convexity_verdict == "MARGINAL" or frontier.zone == "Acceptable selectively":
            target_offer = deal.hard_floor_mid * OFFERS.midpoint_multiplier
            walk_away = min(deal.ask_price * OFFERS.ask_cap_pct,
                           deal.hard_floor_mid * OFFERS.walk_multiplier)
            verdict = "CONDITIONAL"
            reasoning.append(f"Frontier: {frontier.zone}. "
                           f"Convexity {div.convexity_ratio:.2f} ({div.convexity_verdict}). "
                           f"Conditional — pursue at ≤${target_offer:,.0f}.")

        # Gate 5: High/Positive convexity
        else:
            target_offer = deal.hard_floor_mid * OFFERS.aggressive_multiplier
            walk_away = min(deal.ask_price * OFFERS.ask_cap_pct,
                           deal.hard_floor_mid * OFFERS.walk_multiplier)
            verdict = f"PURSUE AT ${target_offer:,.0f}"
            reasoning.append(f"Frontier: {frontier.zone}. "
                           f"Convexity {div.convexity_ratio:.2f} ({div.convexity_verdict}).")

        return VerdictOutput(
            verdict=verdict, target_offer=target_offer, walk_away=walk_away,
            convexity_ratio=div.convexity_ratio, zone=frontier.zone,
            reasoning=reasoning,
            risk_reward_summary=(
                f"Risk: ${deal.capital_invested:,.0f} at risk, "
                f"effective worst {div.worst_case_pct_capital:.0f}% of capital "
                f"via hard floor (${deal.hard_floor_mid:,.0f}). "
                f"Reward: best MOIC {div.best_case_moic:.2f}x. "
                f"Convexity ratio {div.convexity_ratio:.2f}. "
                f"PWEV ${pwev.pwev:,.0f} ({pwev.pwev_vs_ask_pct:+.1f}% vs ask)."))

    # ── Full analysis pipeline ──────────────────────────────

    def analyze(self, deal: DealInput) -> ConvexityResult:
        """Run the full convexity analysis pipeline."""
        return ConvexityResult(
            deal=deal,
            divergence=self.compute_divergence(deal),
            pwev=self.compute_pwev(deal),
            frontier=self.compute_effective_frontier(deal),
            verdict=self.generate_verdict(deal),
        )


# ── Convenience Functions ────────────────────────────────────

def analyze_deal(ask_price: float,
                 purchase_price: Optional[float] = None,
                 hard_floor_low: float = 0,
                 hard_floor_mid: float = 0,
                 hard_floor_high: float = 0,
                 scenarios: Optional[List[Scenario]] = None,
                 **kwargs) -> ConvexityResult:
    """Convenience: build a DealInput and run full analysis."""
    if purchase_price is None:
        purchase_price = ask_price
    deal = DealInput(
        ask_price=ask_price, purchase_price=purchase_price,
        hard_floor_low=hard_floor_low, hard_floor_mid=hard_floor_mid,
        hard_floor_high=hard_floor_high, scenarios=scenarios or [], **kwargs)
    return ConvexityEngine().analyze(deal)


def from_json(data: dict) -> ConvexityResult:
    """
    Load a deal from an analysis JSON dict and run full convexity analysis.

    Expected structure (from listing_NNNNNNNN_analysis.json):
    {
        "property": {"price": 799000, "address": "..."},
        "hard_asset_floor": {"low": 400000, "mid": 530000, "high": 650000},
        "scenarios": {"Worst Case": {"value": 292632, "moic_5yr": 0.7}, ...},
        "valuations": {"probability_weighted_ev": {"weights": {...}}}
    }
    """
    pricing = data.get("pricing", {})
    deal = data.get("deal", {})

    # Shared schema normalization (pricing.* vs hard_asset_floor/hard_floor)
    norm = extract_pricing(data)
    ask_price = norm["ask_price"]
    purchase_price = data.get("purchase_price", 0) or pricing.get("ask", 0) or ask_price
    capital_invested = data.get("capital_invested", 0) or purchase_price

    hard_mid = norm["hard_floor_mid"]
    hard_low = norm["hard_floor_low"]
    hard_high = norm["hard_floor_high"]

    prob_weighted = data.get("valuations", {}).get("probability_weighted_ev", {})
    weights = prob_weighted.get("weights", {})
    default_prob = dict(DEFAULT_PROBABILITIES)
    if weights:
        default_prob.update(weights)

    scenarios = []
    raw_scenarios = data.get("scenarios", {})

    if isinstance(raw_scenarios, dict):
        entries = [(name, s, name.lower()) for name, s in raw_scenarios.items()]

        worst_names_lower = [n.lower() for n in SCENARIO_CATEGORIES["worst"]]
        base_names_lower = [n.lower() for n in SCENARIO_CATEGORIES["base"]]
        best_names_lower = [n.lower() for n in SCENARIO_CATEGORIES["best"]]

        worst_candidates = [(n, s) for n, s, nl in entries
                           if any(wn in nl for wn in worst_names_lower)]
        base_candidates = [(n, s) for n, s, nl in entries
                          if any(bn in nl for bn in base_names_lower)]
        best_candidates = [(n, s) for n, s, nl in entries
                          if any(bn in nl for bn in best_names_lower)]

        selected_worst = min(worst_candidates, key=lambda x: x[1].get("value", 0))[0] if worst_candidates else None
        selected_base = base_candidates[0][0] if base_candidates else None
        # PWEV weighting selects the REALISTIC best candidate (lowest-value
        # match, e.g. "Phase 1 Optimize"), per docs/convexity-engine.md §3:
        # "PWEV rooted in realistic expectations (Phase 1 Optimize at 25%
        # weight) while convexity uses maximum upside (Phase 2 Expand) for
        # the tail." Divergence/convexity independently pick the max-value
        # best inside the engine, so this only affects PWEV probabilities.
        selected_best = min(best_candidates, key=lambda x: x[1].get("value", 0))[0] if best_candidates else None

        for name, s, name_lower in entries:
            if name == selected_worst:
                prob = default_prob["worst"]
            elif name == selected_base:
                prob = default_prob["base"]
            elif name == selected_best:
                prob = default_prob["best"]
            else:
                # Phase 3 / non-core scenario — split remaining probability
                prob = 0.0  # Fallback; will be normalized if non-zero values exist

            scenarios.append(Scenario(
                name=name, probability=prob,
                revenue=s.get("gross_rent", 0), cogs=0, labor=0,
                other_opex=s.get("expenses", 0), noi=s.get("noi"),
                exit_value=s.get("value", 0), moic=s.get("moic_5yr")))

        # Normalize: distribute remaining probability to all scenarios with value > 0
        total_prob = sum(s.probability for s in scenarios)
        if total_prob < 1.0:
            eligible = [s for s in scenarios if s.probability == 0.0 and s.exit_value > 0]
            if eligible:
                remaining = 1.0 - total_prob
                per_scenario = remaining / len(eligible)
                for s in eligible:
                    s.probability = per_scenario
    else:
        for s in raw_scenarios:
            scenarios.append(Scenario(
                name=s["name"], probability=s.get("probability", 0),
                revenue=s.get("revenue", 0), cogs=s.get("cogs", 0),
                labor=s.get("labor", 0), other_opex=s.get("other_opex", 0),
                exit_value=s.get("exit_value", 0), moic=s.get("moic")))

    deal = DealInput(
        ask_price=ask_price,
        purchase_price=purchase_price,
        hard_floor_low=hard_low, hard_floor_mid=hard_mid,
        hard_floor_high=hard_high,
        real_estate_value=data.get("real_estate_value", 0),
        license_value=data.get("license_value", 0),
        equipment_value=data.get("equipment_value", 0),
        scenarios=scenarios, exit_year=data.get("exit_year", 5),
        capital_invested=capital_invested)

    return ConvexityEngine().analyze(deal)


# ── CLI Entry Point ──────────────────────────────────────────

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m cre_underwriting.convexity <deal_analysis.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        data = json.load(f)
    result = from_json(data)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
