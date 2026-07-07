"""
v5 Pipeline — Kanban-orchestrated CRE underwriting.

Architecture:
  12 Kanban cards across 4 phases:
    Phase A (K1-K5): Parallel data gathering
    Phase B (K6-K10): Parallel analysis (v3 engines + triple-LLM cross-validation)
    Phase C (K11): Synthesis + validation + learning
    Phase D (K12): Dashboard generation + Vercel deploy

Key principles:
  - LLM is the driver. v3 engines learn silently from LLM output.
  - Every output is structured (Pydantic models), validated on parse.
  - Triple-LLM calls run in parallel with buffered response collection.
  - Never produce local-only outputs. Always LLM-enriched.
  - Login-walled listings fail after 2 attempts (try alternative sources).
"""

from .models import (
    LiveContext, Range,
    MoatOutput, Scenario, ScenarioOutput,
    LegalOutput, Lever, Recommendation, LeverOutput,
    ValuationOutput, SynthesisOutput, DealInput,
    RiskLevel, Verdict, Confidence, Effort, MoatClass,
)
from .orchestrator import V5PipelineOrchestrator

__all__ = [
    "LiveContext", "Range",
    "MoatOutput", "Scenario", "ScenarioOutput",
    "LegalOutput", "Lever", "Recommendation", "LeverOutput",
    "ValuationOutput", "SynthesisOutput", "DealInput",
    "RiskLevel", "Verdict", "Confidence", "Effort", "MoatClass",
    "V5PipelineOrchestrator",
]
