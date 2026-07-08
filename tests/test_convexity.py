"""Test suite for CRE Underwriting convexity engine."""

import json
import math
import pytest
from pathlib import Path

from cre_underwriting.convexity import ConvexityEngine, from_json, analyze_deal
from cre_underwriting.models import DealInput, Scenario

FIXTURES = Path(__file__).parent / "fixtures"


class TestConvexityEngine:
    """Core convexity engine tests."""

    def test_fords_known_case(self):
        """Fords 34554176: convexity 1.21 → CONDITIONAL."""
        with open(FIXTURES / "fords_34554176.json") as f:
            data = json.load(f)

        result = from_json(data)

        # Known values
        assert round(result.divergence.convexity_ratio, 2) == 1.21
        assert result.verdict.verdict == "CONDITIONAL"
        assert result.divergence.convexity_verdict == "MARGINAL"
        assert result.divergence.effective_worst == 530000  # Hard floor used
        assert result.divergence.worst_scenario_value < result.divergence.effective_worst

    def test_succasunna_case(self):
        """Succasunna 35674774: convexity 1.45 → CONDITIONAL."""
        with open(FIXTURES / "succasunna_35674774.json") as f:
            data = json.load(f)

        result = from_json(data)

        assert result.divergence.convexity_ratio >= 1.0
        assert result.verdict.verdict in ("CONDITIONAL", "PURSUE")
        assert result.divergence.effective_worst > 0

    def test_effective_worst_uses_hard_floor(self):
        """When operating worst < hard floor, effective worst = hard floor."""
        deal = DealInput(
            ask_price=800_000, purchase_price=800_000,
            hard_floor_low=400_000, hard_floor_mid=500_000, hard_floor_high=600_000,
            scenarios=[
                Scenario(name="Worst Case", probability=0.2, exit_value=300_000),
                Scenario(name="Baseline", probability=0.5, exit_value=800_000),
                Scenario(name="Phase 1 Optimize", probability=0.3, exit_value=1_200_000),
            ])

        engine = ConvexityEngine()
        div = engine.compute_divergence(deal)

        # Operating worst $300K < floor mid $500K → effective = $500K
        assert div.effective_worst == 500_000
        assert div.worst_scenario_value == 300_000

    def test_zero_capital_raises(self):
        """Zero capital invested should raise ValueError."""
        with pytest.raises(ValueError):
            analyze_deal(
                ask_price=0, hard_floor_mid=0,
                scenarios=[
                    Scenario(name="Worst Case", probability=0.2, exit_value=0),
                    Scenario(name="Baseline", probability=0.5, exit_value=0),
                    Scenario(name="Phase 1 Optimize", probability=0.3, exit_value=0),
                ])

    def test_missing_worst_scenario_raises(self):
        """Missing worst scenario should raise ValueError."""
        deal = DealInput(
            ask_price=100_000, purchase_price=100_000,
            hard_floor_low=50_000, hard_floor_mid=60_000, hard_floor_high=70_000,
            scenarios=[
                Scenario(name="Baseline", probability=0.5, exit_value=100_000),
                Scenario(name="Phase 1 Optimize", probability=0.5, exit_value=150_000),
            ])

        engine = ConvexityEngine()
        with pytest.raises(ValueError, match="No worst-case scenario"):
            engine.compute_divergence(deal)

    def test_pwev_computation(self):
        """PWEV should weight scenarios by probability."""
        deal = DealInput(
            ask_price=100_000, purchase_price=100_000,
            hard_floor_low=40_000, hard_floor_mid=50_000, hard_floor_high=60_000,
            scenarios=[
                Scenario(name="Worst Case", probability=0.2, exit_value=40_000),
                Scenario(name="Baseline", probability=0.5, exit_value=100_000),
                Scenario(name="Phase 1 Optimize", probability=0.3, exit_value=150_000),
            ])

        engine = ConvexityEngine()
        pwev = engine.compute_pwev(deal)

        # 0.2*40 + 0.5*100 + 0.3*150 = 8 + 50 + 45 = 103
        assert abs(pwev.pwev - 103_000) < 100
        assert pwev.is_underpriced  # $103K > $100K ask

    def test_high_convexity_verdict(self):
        """High convexity (>2.5) → PURSUE."""
        deal = DealInput(
            ask_price=100_000, purchase_price=100_000,
            hard_floor_low=80_000, hard_floor_mid=90_000, hard_floor_high=95_000,
            scenarios=[
                Scenario(name="Worst Case", probability=0.1, exit_value=90_000),
                Scenario(name="Baseline", probability=0.4, exit_value=100_000),
                Scenario(name="Phase 2 Expand", probability=0.5, exit_value=250_000),
            ])

        engine = ConvexityEngine()
        div = engine.compute_divergence(deal)

        assert div.convexity_ratio >= 2.5
        assert div.convexity_verdict == "HIGH"


class TestEffectiveFrontier:
    """Effective frontier zone classification (H19: was inverted)."""

    @staticmethod
    def _deal(hard_floor_mid, worst_exit, best_exit):
        return DealInput(
            ask_price=100_000, purchase_price=100_000,
            hard_floor_low=hard_floor_mid * 0.9,
            hard_floor_mid=hard_floor_mid,
            hard_floor_high=hard_floor_mid * 1.1,
            scenarios=[
                Scenario(name="Worst Case", probability=0.2, exit_value=worst_exit),
                Scenario(name="Baseline", probability=0.5, exit_value=110_000),
                Scenario(name="Phase 2 Expand", probability=0.3, exit_value=best_exit),
            ])

    def test_low_loss_deal_ranks_safer_than_high_loss_deal(self):
        """A deal that risks 10% of capital must classify better than one risking 80%."""
        engine = ConvexityEngine()

        # Safe: effective worst $90K on $100K capital → 10% worst-case loss
        safe = engine.compute_effective_frontier(
            self._deal(hard_floor_mid=90_000, worst_exit=85_000, best_exit=260_000))
        # Risky: effective worst $20K on $100K capital → 80% worst-case loss
        risky = engine.compute_effective_frontier(
            self._deal(hard_floor_mid=20_000, worst_exit=20_000, best_exit=260_000))

        # x is worst-case LOSS as % of capital — safe deal loses less
        assert safe.x == pytest.approx(10.0)
        assert risky.x == pytest.approx(80.0)
        assert safe.x < risky.x

        # Both clear the MOIC bar (2.6x); only the low-loss deal may be
        # pursued aggressively. Before the fix these were swapped.
        assert safe.zone == "Pursue aggressively"
        assert risky.zone == "Acceptable selectively"

    def test_low_moic_zones_use_loss_not_recovery(self):
        """Below the MOIC bar: small loss → 'Pass unless portfolio reason', large loss → 'Walk away'."""
        engine = ConvexityEngine()

        small_loss = engine.compute_effective_frontier(
            self._deal(hard_floor_mid=90_000, worst_exit=85_000, best_exit=150_000))
        large_loss = engine.compute_effective_frontier(
            self._deal(hard_floor_mid=20_000, worst_exit=20_000, best_exit=150_000))

        assert small_loss.zone == "Pass unless portfolio reason"
        assert large_loss.zone == "Walk away"


class TestRiskReward:
    """risk_reward_ratio direction: reward per unit of capital AT RISK."""

    @staticmethod
    def _deal(hard_floor_mid, worst_exit, best_moic):
        return DealInput(
            ask_price=100_000, purchase_price=100_000,
            hard_floor_low=hard_floor_mid * 0.9,
            hard_floor_mid=hard_floor_mid,
            hard_floor_high=hard_floor_mid * 1.1,
            scenarios=[
                Scenario(name="Worst Case", probability=0.2, exit_value=worst_exit),
                Scenario(name="Baseline", probability=0.5, exit_value=110_000),
                Scenario(name="Phase 2 Expand", probability=0.3,
                         exit_value=best_moic * 100_000, moic=best_moic),
            ])

    def test_safer_deal_scores_higher_risk_reward(self):
        """Same best MOIC: the deal risking 10% must out-score the one risking 90%."""
        engine = ConvexityEngine()

        # Retains 90% in the worst case → 10% of capital at risk
        safe = engine.compute_divergence(self._deal(90_000, 90_000, 3.0))
        # Retains 10% in the worst case → 90% of capital at risk
        risky = engine.compute_divergence(self._deal(10_000, 10_000, 3.0))

        # 3.0 MOIC / 0.10 at risk = 30x;  3.0 / 0.90 = 3.33x
        assert safe.risk_reward_ratio == pytest.approx(30.0, rel=0.01)
        assert risky.risk_reward_ratio == pytest.approx(3.33, rel=0.01)
        assert safe.risk_reward_ratio > risky.risk_reward_ratio

    def test_zero_loss_deal_finite_ratio(self):
        """A deal whose effective worst retains all capital must not divide by zero."""
        engine = ConvexityEngine()
        div = engine.compute_divergence(self._deal(100_000, 100_000, 3.0))
        assert math.isfinite(div.risk_reward_ratio)
        assert div.risk_reward_ratio > 0


class TestVerdictGates:
    """Verdict gate branching per docs/convexity-engine.md gate table."""

    @staticmethod
    def _deal(hard_floor_mid, worst_exit, base_exit, best_exit):
        return DealInput(
            ask_price=100_000, purchase_price=100_000,
            hard_floor_low=hard_floor_mid * 0.9,
            hard_floor_mid=hard_floor_mid,
            hard_floor_high=hard_floor_mid * 1.1,
            scenarios=[
                Scenario(name="Worst Case", probability=0.2, exit_value=worst_exit),
                Scenario(name="Baseline", probability=0.5, exit_value=base_exit),
                Scenario(name="Phase 2 Expand", probability=0.3, exit_value=best_exit),
            ])

    def test_gate1_negative_convexity_passes(self):
        """Gate 1: convexity ratio < 1.0 → PASS."""
        engine = ConvexityEngine()
        # Upside 10K, downside 60K → ratio ~0.17
        v = engine.generate_verdict(self._deal(30_000, 30_000, 90_000, 100_000))
        assert v.verdict == "PASS"
        assert v.target_offer is None

    def test_gate3_pursue_aggressively(self):
        """Gate 3: 'Pursue aggressively' zone → PURSUE AT $X with offer numbers."""
        engine = ConvexityEngine()
        # Loss 10%, best MOIC 2.6x+, strong convexity
        v = engine.generate_verdict(self._deal(90_000, 85_000, 110_000, 270_000))
        assert v.zone == "Pursue aggressively"
        assert v.verdict.startswith("PURSUE AT ")
        assert v.target_offer and v.target_offer > 0
        assert v.walk_away and v.walk_away > 0

    def test_gate2_walk_away_with_marginal_convexity_is_conditional(self):
        """Gate 2: 'Walk away' zone but ratio >= 1.0 → CONDITIONAL with price discipline."""
        engine = ConvexityEngine()
        # Loss 80% (fails zone), best MOIC below bar, but upside >= downside
        v = engine.generate_verdict(self._deal(20_000, 20_000, 60_000, 110_000))
        assert v.zone == "Walk away"
        assert v.verdict == "CONDITIONAL"
        assert v.target_offer and v.target_offer > 0

    def test_gate4_acceptable_selectively_is_conditional(self):
        """Gate 4: 'Acceptable selectively' zone → CONDITIONAL."""
        engine = ConvexityEngine()
        # Loss 80% but best MOIC clears the bar; positive convexity
        v = engine.generate_verdict(self._deal(20_000, 20_000, 60_000, 270_000))
        assert v.zone == "Acceptable selectively"
        assert v.verdict == "CONDITIONAL"


class TestPWEVWeighting:
    """from_json PWEV weighting: 'best' weight goes to the realistic
    (lowest-value) best candidate — Phase 1 Optimize — per
    docs/convexity-engine.md §3, not to Phase 2 Expand."""

    def test_fords_pwev_matches_validated_reference(self):
        """Fords fixture: engine PWEV must match the committed reference
        (20% worst / 55% base / 25% Phase 1 = $710,287)."""
        with open(FIXTURES / "fords_34554176.json") as f:
            data = json.load(f)

        result = from_json(data)
        reference = data["valuations"]["probability_weighted_ev"]["pwev"]

        assert result.pwev.pwev == pytest.approx(reference, rel=0.001)

    def test_phase1_gets_best_weight_not_phase2(self):
        """Phase 1 Optimize carries the 'best' probability; Phase 2 Expand
        stays at 0 for PWEV (it still drives divergence upside)."""
        with open(FIXTURES / "fords_34554176.json") as f:
            data = json.load(f)

        result = from_json(data)
        probs = {s.name: s.probability for s in result.deal.scenarios}

        assert probs["Phase 1 Optimize"] == pytest.approx(0.25)
        assert probs["Phase 2 Expand"] == 0.0
        # Divergence must still use maximum upside (Phase 2 Expand value)
        assert result.divergence.best_scenario_value == data["scenarios"]["Phase 2 Expand"]["value"]
