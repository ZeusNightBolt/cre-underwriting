"""cre_underwriting.v4 — Dynamic API-First Underwriting Pipeline.

Replaces the stale local-data v3 pipeline with live API calls,
web search, and multi-model LLM analysis for every deal.

Nodes:
  1. Valuation Triangulation (kept from v3)
  2. Comps — LoopNet BiDi + web search + LLM dedup
  3. HPA — FRED API (real MSA-level data)
  4. Financial & Business Levers — LLM-suggested
  5. Demographics — FRED + Census ACS
  6. Effective Frontier (kept from v3)
  7. Scenarios — LLM-generated, deal-specific
  8. Convexity + Enhanced — multi-LLM moats, offers, legal risk
  9. Dashboard + Deploy (kept from v3)

Architecture: Triple-LLM analysis (DeepSeek + Nemotron 3 + Mistral)
with DeepSeek synthesizing all perspectives.
"""

from .models import LiveContext, DealContext
from .orchestrator import V4PipelineOrchestrator

__all__ = ["LiveContext", "DealContext", "V4PipelineOrchestrator"]
