"""Test suite for CRE Underwriting enhanced analysis (moats, offers)."""

import json
import pytest
from pathlib import Path

from cre_underwriting.enhanced import MoatScorer, OfferAnalyzer, EnhancedAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


class TestMoatScorer:
    """8-moat scoring tests."""

    @pytest.fixture
    def fords_deal(self):
        with open(FIXTURES / "fords_34554176.json") as f:
            return json.load(f)

    @pytest.fixture
    def succasunna_deal(self):
        with open(FIXTURES / "succasunna_35674774.json") as f:
            return json.load(f)

    def test_fords_moats_known(self, fords_deal):
        """Fords: 15/24 NARROW MOAT."""
        moats = MoatScorer.score(fords_deal)
        assert moats.total_score == 15
        assert moats.classification == "NARROW MOAT"
        assert len(moats.dimensions) == 8

    def test_succasunna_moats_known(self, succasunna_deal):
        """Succasunna: 14/24 NARROW MOAT."""
        moats = MoatScorer.score(succasunna_deal)
        assert moats.total_score == 14
        assert moats.classification == "NARROW MOAT"

    def test_all_dimensions_present(self, fords_deal):
        """All 8 dimensions must be scored."""
        moats = MoatScorer.score(fords_deal)
        names = {d.name for d in moats.dimensions}
        expected = {
            "Scarce Transferable License", "Tourism Corridor Position",
            "Multi-Revenue-Stream Parcel", "Zoning Optionality",
            "Rent-to-Market Gap", "Brand Longevity & Goodwill",
            "Asset Stack Coverage", "Seller Asymmetry",
        }
        assert names == expected

    def test_scores_in_range(self, fords_deal):
        """Each dimension score must be 0-3."""
        moats = MoatScorer.score(fords_deal)
        for d in moats.dimensions:
            assert 0 <= d.score <= 3, f"{d.name}: {d.score}"

    def test_empty_deal_handled(self):
        """Empty deal dict should not crash."""
        moats = MoatScorer.score({})
        assert moats.total_score >= 0
        assert len(moats.dimensions) == 8

    def test_to_dict_output(self, fords_deal):
        """to_dict() should produce valid JSON-serializable output."""
        moats = MoatScorer.score(fords_deal)
        d = moats.to_dict()
        json.dumps(d)  # Should not raise
        assert "dimensions" in d
        assert "total_score" in d
        assert len(d["dimensions"]) == 8


class TestOfferAnalyzer:
    """Offer ladder tests."""

    def test_fords_ladder(self):
        """Fords: $799K ask, $57.4K NOI, $530K floor → 5 points."""
        offers = OfferAnalyzer.ladder(
            ask_price=799000, noi=57368, hard_floor_mid=530000,
            sf=4000, gross_rent=64000)
        assert len(offers.points) == 5
        assert offers.target_low > 0
        assert offers.target_high > offers.target_low
        assert offers.walk_away <= 799000

    def test_succasunna_ladder(self):
        """Succasunna: $699K ask, $58.3K NOI, $329K floor."""
        offers = OfferAnalyzer.ladder(
            ask_price=699000, noi=58300, hard_floor_mid=329000,
            sf=3645, gross_rent=65600)
        assert offers.target_low < offers.target_high
        assert offers.walk_away > offers.target_high

    def test_zero_inputs(self):
        """Zero inputs should not crash."""
        offers = OfferAnalyzer.ladder(ask_price=0, noi=0, hard_floor_mid=0)
        assert len(offers.points) == 5

    def test_cap_rates_decreasing(self):
        """Cap rates should decrease as price increases."""
        offers = OfferAnalyzer.ladder(
            ask_price=800000, noi=60000, hard_floor_mid=400000)
        caps = [p.cap_rate_pct for p in offers.points]
        for i in range(len(caps) - 1):
            assert caps[i] >= caps[i + 1], f"Cap at {i}: {caps[i]} < {caps[i+1]}"

    def test_to_dict_output(self):
        """to_dict() should produce valid JSON."""
        offers = OfferAnalyzer.ladder(
            ask_price=799000, noi=57368, hard_floor_mid=530000)
        d = offers.to_dict()
        json.dumps(d)
        assert len(d["points"]) == 5


class TestEnhancedAnalyzer:
    """Full enhanced analyzer orchestration."""

    def test_fords_analysis(self):
        with open(FIXTURES / "fords_34554176.json") as f:
            deal = json.load(f)
        analyzer = EnhancedAnalyzer(deal)
        result = analyzer.analyze()

        assert "moats" in result
        assert "offers" in result
        assert "demographics" in result
        assert "environmental" in result

    def test_with_env_data(self):
        """EnhancedAnalyzer with environmental data."""
        with open(FIXTURES / "fords_34554176.json") as f:
            deal = json.load(f)
        env = {
            "economic": {"population": 863000, "median_household_income": 98500},
            "environmental": {"flood_risk_level": "low", "ust_risk": "medium"},
        }
        analyzer = EnhancedAnalyzer(deal, env)
        result = analyzer.analyze()
        assert result["demographics"]["population"] == 863000
        assert result["environmental"]["ust_risk"] == "medium"


class TestPricingSchemaOffers:
    """H20: pricing-schema deals (pricing.ask + pricing.hard_floor_*) must not
    silently produce $0 offer ladders and 0-scored asset-stack moats."""

    @pytest.fixture
    def boonton_deal(self):
        with open(FIXTURES / "boonton_40453341_analysis.json") as f:
            return json.load(f)

    def test_offer_ladder_nonzero_for_pricing_schema(self, boonton_deal):
        """Every offer point must be priced from pricing.ask / pricing.hard_floor_mid."""
        result = EnhancedAnalyzer(boonton_deal).analyze()
        offers = result["offers"]

        assert offers["ask_price"] == 289_000
        assert offers["target_low"] > 0
        assert offers["walk_away"] > 0
        assert len(offers["points"]) > 0
        for point in offers["points"]:
            assert point["price"] > 0, f"Zero-dollar offer point: {point}"

    def test_asset_stack_moat_sees_pricing_schema_floor(self, boonton_deal):
        """Hard floor $168K vs ask $289K (58%) must register in the asset-stack moat."""
        moats = MoatScorer.score(boonton_deal)
        asset = next(d for d in moats.dimensions if d.name == "Asset Stack Coverage")
        assert asset.score > 0
