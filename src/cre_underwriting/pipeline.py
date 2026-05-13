"""
cre_underwriting.pipeline — Pipeline Orchestrator.

Composes all engines (convexity, enhanced, environmental, comps) into a
single pipeline that produces a complete analysis dict.

Usage:
    from cre_underwriting.pipeline import PipelineOrchestrator

    orch = PipelineOrchestrator()
    result = orch.run("listing_34554176_analysis.json")
    # result contains convexity + moats + offers + demographics + environmental + comps
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

from .convexity import ConvexityEngine, from_json
from .enhanced import EnhancedAnalyzer
from .environmental import assess_location


class PipelineOrchestrator:
    """
    Compose all CRE underwriting engines into a unified pipeline.

    Takes a deal analysis JSON file, runs convexity analysis, enhanced
    scoring, environmental assessment, and returns a complete analysis dict
    ready for dashboard generation or pipeline storage.
    """

    def __init__(self):
        self.convexity = ConvexityEngine()

    def run(self, deal_path: str, env_path: str = None,
            comps_path: str = None) -> dict:
        """
        Run the full pipeline on a deal JSON file.

        Args:
            deal_path: Path to listing analysis JSON
            env_path: Optional path to environmental assessment JSON
            comps_path: Optional path to comps summary JSON

        Returns:
            Complete analysis dict with convexity, enhanced, environmental sections
        """
        with open(deal_path) as f:
            deal_data = json.load(f)

        prop = deal_data.get("property", {})

        # ── Convexity Analysis ──
        convexity_result = from_json(deal_data)
        convexity = convexity_result.to_dict()

        # ── Enhanced Analysis (moats, offers, demographics, comps) ──
        env_data = {}
        if env_path:
            try:
                with open(env_path) as f:
                    env_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        else:
            # Auto-run environmental assessment from property address
            address = prop.get("address", "")
            if address:
                try:
                    env_data = assess_location(address)
                except Exception:
                    pass

        comps_data = {}
        if comps_path:
            try:
                with open(comps_path) as f:
                    comps_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        enh = EnhancedAnalyzer(deal_data, env_data, comps_data)
        enhanced = enh.analyze()

        # ── Pipeline Output ──
        return {
            "listing_id": prop.get("listing_id", ""),
            "address": prop.get("address", ""),
            "city": prop.get("municipality", prop.get("city", "")),
            "state": prop.get("state", "NJ"),
            "property_type": prop.get("property_type", ""),
            "ask_price": prop.get("price", 0),
            "hard_floor_mid": deal_data.get("hard_asset_floor", {}).get("mid", 0),
            "analysis_date": str(date.today()),
            "convexity": convexity,
            "enhanced": enhanced,
        }

    def run_dict(self, deal_data: dict, env_data: dict = None,
                 comps_data: dict = None) -> dict:
        """Run pipeline from in-memory dicts (no file I/O)."""
        convexity_result = from_json(deal_data)
        convexity = convexity_result.to_dict()
        enh = EnhancedAnalyzer(deal_data, env_data or {}, comps_data or {})
        enhanced = enh.analyze()
        prop = deal_data.get("property", {})

        return {
            "listing_id": prop.get("listing_id", ""),
            "address": prop.get("address", ""),
            "city": prop.get("municipality", prop.get("city", "")),
            "state": prop.get("state", "NJ"),
            "property_type": prop.get("property_type", ""),
            "ask_price": prop.get("price", 0),
            "hard_floor_mid": deal_data.get("hard_asset_floor", {}).get("mid", 0),
            "analysis_date": str(date.today()),
            "convexity": convexity,
            "enhanced": enhanced,
        }


def main():
    """CLI entry point: cre-pipeline <deal.json> [env.json] [comps.json]."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: cre-pipeline <deal_analysis.json> [env.json] [comps.json]")
        sys.exit(1)

    orch = PipelineOrchestrator()
    result = orch.run(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else None,
        sys.argv[3] if len(sys.argv) > 3 else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
