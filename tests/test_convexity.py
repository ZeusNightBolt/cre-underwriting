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
