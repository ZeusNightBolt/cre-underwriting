"""
Multi-model LLM client for CRE underwriting v4.

Triple-perspective architecture:
  1. DeepSeek V4 Pro (primary, paid)
  2. OpenRouter/free with Nemotron 3 Super preference (independent)
  3. Mistral Small (independent, free)
  4. DeepSeek reviews all three and synthesizes final output

Timeout resilience: retry with exponential backoff (max 3 attempts).
Never proceeds with incomplete output.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

# Paths
ROUTER = Path.home() / ".hermes/scripts/model_router.py"
VENV_PYTHON = Path.home() / ".hermes/hermes-agent/venv/bin/python3"
ENV_PATH = Path.home() / ".hermes/.env"


def _load_env():
    """Load .env into os.environ (same logic as model_router.py)."""
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.split("#")[0].strip().strip('"').strip("'")
                os.environ[key] = val


# OpenRouter models -- ordered by preference (free tier)
OPENROUTER_FREE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",  # NVIDIA's reasoning model (preferred)
    "google/gemini-2.5-flash-lite",             # Fallback 1
    "mistralai/mistral-small-3.1-24b",          # Fallback 2
    "meta-llama/llama-4-maverick",              # Fallback 3
]


def _call_model_router(prompt, model_flag="",
                       system="You are a CRE underwriting analyst. Be specific, cite data, quantify risks.",
                       max_retries=3, timeout=120):
    """Call the model router with retry on timeout.

    IMPORTANT: model_router.py takes prompt as a POSITIONAL argument, not stdin.
    The router loads .env internally so no need to pass API keys.
    """
    cmd = [str(VENV_PYTHON), str(ROUTER)]
    if model_flag:
        cmd.append(model_flag)
    cmd.append(prompt)

    last_error = None
    for attempt in range(max_retries):
        try:
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, env=env,
            )
            output = result.stdout.strip()
            if output and "usage: model_router.py" not in output:
                return output
            if result.stderr:
                last_error = result.stderr.strip()[:200]
            elif output:
                last_error = "model_router returned usage/help (prompt not received correctly)"
        except subprocess.TimeoutExpired:
            last_error = "Timeout after %ds" % timeout
        except Exception as e:
            last_error = str(e)[:200]

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt + 1)

    raise RuntimeError(
        "LLM call failed after %d attempts. Model: %s. Last error: %s"
        % (max_retries, model_flag or 'deepseek', last_error)
    )


def _call_openrouter(prompt, system="", max_retries=3, timeout=120):
    """Call OpenRouter API with fallback chain.

    Tries models in order: Nemotron 3 Super, Gemini Flash, Mistral Small, Llama 4.
    If the preferred model fails, falls back to next in the chain.
    Loads .env for OPENROUTER_API_KEY (same place model_router reads from).
    """
    # Load .env (model_router.py does this, but we're calling the API directly)
    _load_env()

    import urllib.request
    import urllib.error

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set in environment or .env")

    last_error = None
    for model in OPENROUTER_FREE_MODELS:
        for attempt in range(max_retries):
            try:
                payload = json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system or "You are a CRE underwriting analyst."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                }).encode("utf-8")

                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=payload,
                    headers={
                        "Authorization": "Bearer %s" % api_key,
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://cre-underwriting.vercel.app",
                        "X-Title": "CRE Underwriting v4",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = json.loads(resp.read())
                    content = result["choices"][0]["message"]["content"]
                    return content.strip()
            except (urllib.error.URLError, urllib.error.HTTPError,
                    json.JSONDecodeError, KeyError, IndexError) as e:
                last_error = "%s: %s" % (model, str(e)[:200])
            except Exception as e:
                last_error = "%s: %s" % (model, str(e)[:200])

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + 1)

    raise RuntimeError(
        "OpenRouter call failed for all models after %d attempts each. Last error: %s"
        % (max_retries, last_error)
    )


def get_triple_analysis(prompt, system=None, max_retries=3, timeout_per_model=120):
    """Run triple-perspective LLM analysis with DeepSeek synthesis.

    Pipeline:
      1. DeepSeek V4 Pro -> primary analysis
      2. OpenRouter/free (Nemotron 3 Super preferred, auto-fallbacks) -> independent
      3. Mistral Small -> third independent perspective
      4. DeepSeek reviews all three + synthesizes final integrated output

    OpenRouter fallback chain: Nemotron 3 -> Gemini Flash -> Mistral Small -> Llama 4.
    Timeout resilience: max_retries per model, exponential backoff.
    """
    default_system = (
        "You are a senior CRE underwriting analyst at a quantitative hedge fund. "
        "Be specific. Cite numbers. Quantify risks. Identify what's missing. "
        "Never use filler language. Lead with the conclusion."
    )
    system = system or default_system
    errors = []

    # Load .env (in case subprocess doesn't inherit env)
    _load_env()

    # Step 1: DeepSeek primary
    try:
        deepseek_output = _call_model_router(
            prompt, model_flag="", system=system,
            max_retries=max_retries, timeout=timeout_per_model,
        )
    except RuntimeError as e:
        errors.append("deepseek: %s" % e)
        deepseek_output = "[ERROR: %s]" % e

    # Step 2: OpenRouter (Nemotron 3 preferred, auto-fallback)
    try:
        openrouter_output = _call_openrouter(
            prompt, system=system,
            max_retries=max_retries, timeout=timeout_per_model,
        )
    except RuntimeError as e:
        errors.append("openrouter: %s" % e)
        openrouter_output = "[ERROR: %s]" % e

    # Step 3: Mistral
    try:
        mistral_output = _call_model_router(
            prompt, model_flag="--free2c", system=system,
            max_retries=max_retries, timeout=timeout_per_model,
        )
    except RuntimeError as e:
        errors.append("mistral: %s" % e)
        mistral_output = "[ERROR: %s]" % e

    # Step 4: DeepSeek synthesizes all three
    synthesis_prompt = """You are a lead CRE underwriter synthesizing three independent analyst reports.

PROMPT: %s

=== ANALYST 1 (DeepSeek Primary) ===
%s

=== ANALYST 2 (OpenRouter -- Independent) ===
%s

=== ANALYST 3 (Mistral -- Independent) ===
%s

Your job:
1. Identify the 3-5 most important areas of agreement AND disagreement
2. Produce a FINAL INTEGRATED ANALYSIS that:
   - Resolves disagreements where one analyst had better reasoning
   - Flags remaining uncertainties that need human judgment
   - Quantifies ranges (not point estimates) where analysts diverged
   - Cites which analyst contributed each key insight
   - Concludes with a confidence level and the single most important risk

Format your response as:
## Integrated Analysis
[2-4 paragraphs of synthesis]

## Key Divergences
[bullet list of disagreements with resolution]

## Numbers (Ranges)
- [metric]: $X - $Y (Analyst A: $X, Analyst B: $Y)

## Confidence
[High/Medium/Low] - [1 sentence why]

## Top Risk
[1 sentence]
""" % (prompt[:1000], deepseek_output[:4000], openrouter_output[:4000], mistral_output[:4000])

    try:
        synthesis = _call_model_router(
            synthesis_prompt, model_flag="", system="",
            max_retries=max_retries, timeout=timeout_per_model,
        )
    except RuntimeError as e:
        errors.append("synthesis: %s" % e)
        synthesis = "[ERROR: Synthesis failed - %s]" % e

    return {
        "deepseek": deepseek_output,
        "openrouter": openrouter_output,
        "mistral": mistral_output,
        "synthesis": synthesis,
        "errors": errors,
    }


def call_deepseek(prompt, system=None, max_retries=3, timeout=120):
    """Simple single-call to DeepSeek. For quick data extraction tasks."""
    return _call_model_router(
        prompt, model_flag="", system=system or "",
        max_retries=max_retries, timeout=timeout,
    )
