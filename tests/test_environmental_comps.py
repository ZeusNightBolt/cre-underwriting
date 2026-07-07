"""Test suite for CRE Underwriting environmental + comps modules."""

import pytest
from cre_underwriting.environmental import assess_location, parse_address
from cre_underwriting.comps import find_comps, price_per_sf
from cre_underwriting.utils import parse_city_state, city_to_county


class TestAddressParsing:
    """Shared address parsing utility."""

    def test_nj_address(self):
        city, state = parse_city_state("37-39 Main St, Succasunna, NJ 07876")
        assert city == "Succasunna"
        assert state == "NJ"

    def test_nj_address_alt(self):
        city, state = parse_city_state("566-568 New Brunswick Ave, Fords, NJ 08863")
        assert city == "Fords"
        assert state == "NJ"

    def test_city_to_county_nj(self):
        assert city_to_county("irvington", "NJ") == "Essex"
        assert city_to_county("fords", "NJ") == "Middlesex"
        assert city_to_county("succasunna", "NJ") == "Morris"

    def test_city_to_county_pa(self):
        assert city_to_county("philadelphia", "PA") == "Philadelphia"
        assert city_to_county("allentown", "PA") == "Lehigh"

    def test_unknown_city(self):
        assert city_to_county("nonexistent", "NJ") == ""

    def test_parse_address_full(self):
        result = parse_address("123 Main St, Princeton, NJ 08540")
        assert result["state"] == "NJ"
        assert result["city"] == "Princeton"


class TestEnvironmental:
    """Environmental risk assessment."""

    def test_assess_fords(self):
        result = assess_location("566-568 New Brunswick Ave, Fords, NJ 08863")
        assert result["county"] == "Middlesex"
        assert "environmental" in result
        assert "economic" in result
        assert "tailwind_score" in result

    def test_assess_succasunna(self):
        result = assess_location("37-39 Main St, Succasunna, NJ 07876")
        assert result["county"] == "Morris"
        assert result["economic"]["median_household_income"] == 118_000

    def test_assess_irvington(self):
        result = assess_location("216-218 Orange Ave, Irvington, NJ 07111")
        assert result["county"] == "Essex"

    def test_output_has_required_fields(self):
        result = assess_location("123 Main St, Princeton, NJ 08540")
        required = ["address", "county", "state", "environmental",
                    "economic", "tailwind_score", "headwind_score", "verdict"]
        for key in required:
            assert key in result, f"Missing {key}"
        # Verify no duplicate timestamp bug
        assert "timestamp" in result

    def test_economic_profile_populated(self):
        result = assess_location("Test, Fords, NJ 08863")
        econ = result["economic"]
        assert econ["population"] > 0


class TestComps:
    """Comparable sales engine."""

    def test_find_comps_returns_structure(self):
        result = find_comps("123 Main St, Princeton, NJ 08540")
        assert "comps" in result
        assert "summary" in result

    def test_summary_has_source_status(self):
        """Phase 2 bugfix: summary should include source_status and data_quality_warning."""
        result = find_comps("123 Main St, Princeton, NJ 08540")
        summary = result["summary"]
        assert "source_status" in summary
        assert "data_quality_warning" in summary
        assert isinstance(summary["source_status"], dict)

    def test_all_sources_tracked(self):
        result = find_comps("123 Main St, Princeton, NJ 08540")
        sources = result["summary"]["source_status"]
        assert set(sources.keys()) == {"loopnet", "njactb"}

    def test_no_comps_warning(self):
        """When no comps found, data_quality_warning should exist (value depends on Firefox availability)."""
        result = find_comps("123 Main St, Princeton, NJ 08540")
        warning = result["summary"]["data_quality_warning"]
        # Warning may be None if LoopNet BiDi successfully finds results
        # Structure check: the field must exist
        assert "data_quality_warning" in result["summary"]
        if warning is not None:
            assert "comps" in warning.lower() or "loopnet" in warning.lower()

    def test_price_per_sf_empty(self):
        result = price_per_sf([])
        assert result["median"] is None
        assert result["mean"] is None
