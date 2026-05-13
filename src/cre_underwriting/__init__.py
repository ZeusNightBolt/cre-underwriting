"""
cre_underwriting — Commercial Real Estate Underwriting Pipeline.

5-scenario convexity analysis, 8-moat scoring, 4-method valuation
triangulation, environmental risk assessment, and comparable sales.

Usage:
    from cre_underwriting.convexity import ConvexityEngine, from_json
    from cre_underwriting.enhanced import MoatScorer, OfferAnalyzer
    from cre_underwriting.environmental import assess_location
    from cre_underwriting.comps import find_comps
    from cre_underwriting.pipeline import PipelineOrchestrator
    from cre_underwriting.dashboard import generate_dashboard
    from cre_underwriting.scraping import BidiSession, detect_protection, scrape_with_cascade
"""

from .models import (
    Scenario, DealInput, ConvexityResult,
    DivergenceOutput, PWEVOutput, FrontierPoint, VerdictOutput,
    MoatDimension, MoatScorecard, OfferPoint, OfferLadder,
    EnvironmentalRisk, EconomicIndicators, Comp,
)

__version__ = "1.0.0"
__all__ = [
    "ConvexityEngine", "MoatScorer", "OfferAnalyzer", "EnhancedAnalyzer",
    "PipelineOrchestrator", "generate_dashboard",
    "from_json", "from_json_files",
    "assess_location", "find_comps",
    "Scenario", "DealInput", "ConvexityResult",
    "DivergenceOutput", "PWEVOutput", "FrontierPoint", "VerdictOutput",
    "MoatDimension", "MoatScorecard", "OfferPoint", "OfferLadder",
    "EnvironmentalRisk", "EconomicIndicators", "Comp",
]
