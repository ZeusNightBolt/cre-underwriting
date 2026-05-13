"""Test suite for CRE Underwriting pipeline orchestrator (end-to-end)."""

import json
import pytest
from pathlib import Path

from cre_underwriting.pipeline import PipelineOrchestrator
from cre_underwriting.convexity import from_json

FIXTURES = Path(__file__).parent / "fixtures"


class TestPipelineOrchestrator:
    """Full pipeline end-to-end tests."""

    def test_fords_full_pipeline(self):
        """Fords 34554176: full pipeline produces valid output."""
        orch = PipelineOrchestrator()
        result = orch.run(str(FIXTURES / "fords_34554176.json"))

        # Top-level fields
        assert result["listing_id"] == "34554176"
        assert result["ask_price"] == 799000
        assert result["hard_floor_mid"] == 530000

        # Convexity
        c = result["convexity"]
        assert c["verdict"]["verdict"] == "CONDITIONAL"
        assert round(c["divergence"]["convexity_ratio"], 2) == 1.21
        assert c["divergence"]["effective_worst"] == 530000

        # Enhanced
        e = result["enhanced"]
        assert e["moats"]["total_score"] == 15
        assert e["moats"]["classification"] == "NARROW MOAT"
        assert len(e["offers"]["points"]) == 5

    def test_succasunna_full_pipeline(self):
        """Succasunna 35674774: full pipeline."""
        orch = PipelineOrchestrator()
        result = orch.run(str(FIXTURES / "succasunna_35674774.json"))

        c = result["convexity"]
        assert round(c["divergence"]["convexity_ratio"], 2) == 1.45
        assert c["verdict"]["verdict"] == "CONDITIONAL"

        e = result["enhanced"]
        assert e["moats"]["total_score"] == 14

    def test_run_dict_api(self):
        """run_dict() should work with in-memory dicts."""
        with open(FIXTURES / "fords_34554176.json") as f:
            data = json.load(f)

        orch = PipelineOrchestrator()
        result = orch.run_dict(data)
        assert result["convexity"]["verdict"]["verdict"] == "CONDITIONAL"

    def test_missing_file_raises(self):
        """Non-existent file should raise FileNotFoundError."""
        orch = PipelineOrchestrator()
        with pytest.raises(FileNotFoundError):
            orch.run("nonexistent.json")

    def test_output_is_json_serializable(self):
        """Full pipeline output should be JSON-serializable."""
        orch = PipelineOrchestrator()
        result = orch.run(str(FIXTURES / "fords_34554176.json"))
        serialized = json.dumps(result)
        assert len(serialized) > 0
        # Re-parse to verify
        parsed = json.loads(serialized)
        assert parsed["listing_id"] == "34554176"


class TestDashboardGenerator:
    """Dashboard HTML generation."""

    def test_generates_html(self):
        from cre_underwriting.dashboard import generate_dashboard

        orch = PipelineOrchestrator()
        result = orch.run(str(FIXTURES / "fords_34554176.json"))
        html = generate_dashboard(result)

        assert "<!DOCTYPE html>" in html
        assert "</html>" in html
        assert len(html) > 1000

    def test_anti_slop_compliance(self):
        """Generated dashboard must pass anti-slop checks."""
        from cre_underwriting.dashboard import generate_dashboard

        orch = PipelineOrchestrator()
        result = orch.run(str(FIXTURES / "fords_34554176.json"))
        html = generate_dashboard(result)

        # Cardinal sins
        assert "backdrop-filter" not in html, "glassmorphism found"
        assert "#9333ea" not in html, "purple found"
        assert "border-left: 3px" not in html, "left-border cards found"

        # Mobile rules
        assert "min-height: 100dvh" in html, "dvh missing"
        assert "scrollbar-gutter: stable" in html
        assert "viewport-fit=cover" in html
        assert "tabular-nums" in html
        assert "prefers-reduced-motion" in html
        assert "color-mix(in oklch" in html
