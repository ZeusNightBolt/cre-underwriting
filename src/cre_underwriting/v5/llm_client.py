"""
v5 Structured LLM Client — Parallel triple-LLM with JSON schema enforcement.

Architecture:
  1. Fire DeepSeek, OpenRouter, Mistral in PARALLEL (async threads)
  2. Buffer responses — wait for ALL to complete (or timeout)
  3. Validate each response parses to JSON matching expected schema
  4. Retry any failed model with error context appended
  5. DeepSeek synthesis of all 3 validated responses
  6. Return structured output (Pydantic model)

No unstructured text parsing. No markdown fence extraction as first resort.
Models are PROMPTED to return clean JSON. Extraction is fallback only.
"""

import json
import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Callable, Any, Dict, List

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


# Load .env at import time
_load_env()


# ═══════════════════════════════════════════════════════════
# JSON Schema templates — injected into every LLM prompt
# ═══════════════════════════════════════════════════════════

SCHEMA_INSTRUCTION = """
CRITICAL: Respond with ONLY the JSON object below. No markdown fences, no explanatory text, no preamble.
The JSON must validate against the schema exactly. Invalid JSON or missing fields will cause a retry.

Return ONLY:
"""


def _wrap_prompt(prompt: str, schema_json: str) -> str:
    """Wrap prompt with schema enforcement instructions."""
    return f"""{prompt}

{SCHEMA_INSTRUCTION}
{schema_json}"""


# ═══════════════════════════════════════════════════════════
# Low-level LLM callers
# ═══════════════════════════════════════════════════════════

def _call_deepseek(prompt: str, timeout: int = 120) -> str:
    """Call DeepSeek via model_router. Returns raw text."""
    _load_env()
    cmd = [str(VENV_PYTHON), str(ROUTER), prompt]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        output = result.stdout.strip()
        if output and "usage: model_router.py" not in output:
            return output
        return "" if not result.stderr else f"[ERROR] {result.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        return "[ERROR] Timeout"
    except Exception as e:
        return f"[ERROR] {e}"


def _call_openrouter(prompt: str, timeout: int = 120) -> str:
    """Call OpenRouter API with Nemotron 3 Super → fallback chain."""
    import urllib.request
    import urllib.error

    _load_env()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return "[ERROR] OPENROUTER_API_KEY not set"

    models = [
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemini-2.5-flash-lite",
        "mistralai/mistral-small-3.1-24b",
    ]

    for model in models:
        try:
            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a CRE underwriting analyst. Return ONLY valid JSON. No markdown fences."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 4096,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://cre-underwriting.vercel.app",
                    "X-Title": "CRE Underwriting v5",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())
                content = result["choices"][0]["message"]["content"]
                return content.strip()
        except Exception:
            continue

    return "[ERROR] All OpenRouter models exhausted"


def _call_mistral(prompt: str, timeout: int = 120) -> str:
    """Call Mistral via model_router."""
    _load_env()
    cmd = [str(VENV_PYTHON), str(ROUTER), "--free2c", prompt]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        output = result.stdout.strip()
        if output and "usage: model_router.py" not in output:
            return output
        return "" if not result.stderr else f"[ERROR] {result.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        return "[ERROR] Timeout"
    except Exception as e:
        return f"[ERROR] {e}"


# ═══════════════════════════════════════════════════════════
# JSON extraction (fallback when LLM wraps in fences)
# ═══════════════════════════════════════════════════════════

def extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response. Tries multiple strategies."""
    if not text:
        return None

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block (```json ... ```)
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find outermost JSON object
    idx = text.find("{")
    if idx >= 0:
        depth = 0
        for i in range(idx, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[idx:i+1])
                    except json.JSONDecodeError:
                        break

    return None


# ═══════════════════════════════════════════════════════════
# Parallel triple-LLM call with buffered response collection
# ═══════════════════════════════════════════════════════════

def call_triple_llm(
    prompt: str,
    schema_json: str,
    validate_fn: Callable[[dict], List[str]],
    max_retries: int = 3,
    timeout_per_model: int = 300,
) -> Dict[str, Any]:
    """
    Call 3 LLMs in parallel with structured JSON enforcement.

    Flow:
      1. Fire DeepSeek, OpenRouter, Mistral simultaneously (threads)
      2. Buffer: collect ALL responses (wait for slowest)
      3. Each response: extract JSON → validate against schema → retry if invalid
      4. DeepSeek synthesis: all 3 responses → final integrated output
      5. Return: {deepseek: dict, openrouter: dict, mistral: dict, synthesis: dict, errors: [...]}

    Args:
        prompt: The analysis prompt (without schema enforcement — added internally)
        schema_json: JSON schema string to append to prompt and validate against
        validate_fn: Function that validates extracted dict, returns list of error strings
        max_retries: Max retries per failed model
        timeout_per_model: Timeout in seconds per call
    """
    full_prompt = _wrap_prompt(prompt, schema_json)
    errors = []

    # ── Step 1: Parallel fire all 3 models ──
    results = {"deepseek": None, "openrouter": None, "mistral": None}
    parsed = {"deepseek": None, "openrouter": None, "mistral": None}

    def _call_with_retry(model_name, call_fn):
        current_prompt = full_prompt
        for attempt in range(max_retries + 1):
            try:
                raw = call_fn(current_prompt, timeout=timeout_per_model)
                if raw.startswith("[ERROR]"):
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    return raw

                js = extract_json(raw)
                if js is None:
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    return "[ERROR] Could not extract JSON"

                # Validate
                validation_errors = validate_fn(js)
                if validation_errors:
                    if attempt < max_retries:
                        error_ctx = "\n\nPREVIOUS ATTEMPT FAILED VALIDATION:\n" + "\n".join(validation_errors)
                        current_prompt = full_prompt + error_ctx
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        return f"[ERROR] Validation failed after {max_retries} retries: {'; '.join(validation_errors[:3])}"

                return raw  # raw text (JSON preserved for synthesis)
            except Exception as e:
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                else:
                    return f"[ERROR] {e}"
        return "[ERROR] Max retries exhausted"

    deadline = timeout_per_model * 4  # Allow 4x per-model timeout for retries
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_call_with_retry, "deepseek", _call_deepseek): "deepseek",
            executor.submit(_call_with_retry, "openrouter", _call_openrouter): "openrouter",
            executor.submit(_call_with_retry, "mistral", _call_mistral): "mistral",
        }

        try:
            for future in as_completed(futures, timeout=deadline):
                model = futures[future]
                try:
                    results[model] = future.result()
                except Exception as e:
                    errors.append(f"{model}: {e}")
                    results[model] = f"[ERROR] {e}"
        except TimeoutError:
            # as_completed timed out — collect whatever got results
            for model, future in {v: k for k, v in futures.items()}.items():
                if not future.done():
                    future.cancel()
                    errors.append(f"{model}: timed out after {deadline}s")
                    results[model] = f"[ERROR] Timeout after {deadline}s"
                elif results.get(model) is None:
                    try:
                        results[model] = future.result()
                    except Exception as e:
                        errors.append(f"{model}: {e}")
                        results[model] = f"[ERROR] {e}"

    # Parse all results
    for model in ["deepseek", "openrouter", "mistral"]:
        raw = results.get(model, "")
        if raw and not raw.startswith("[ERROR]"):
            parsed[model] = extract_json(raw)

    # ── Step 2: DeepSeek synthesis (AUTHORITY — reviews all perspectives) ──
    synthesis = None
    valid_responses = {k: v for k, v in parsed.items() if v is not None}
    if len(valid_responses) >= 1:
        # Build synthesis prompt emphasizing DeepSeek as authority
        deepseek_part = json.dumps(parsed.get("deepseek", {}), indent=2)[:4000]
        openrouter_part = json.dumps(parsed.get("openrouter", {}), indent=2)[:2000]
        mistral_part = json.dumps(parsed.get("mistral", {}), indent=2)[:2000]

        synthesis_prompt = f"""You are the lead CRE underwriter synthesizing analysis. You are the AUTHORITY.

ORIGINAL TASK: {prompt[:500]}

=== YOUR ANALYSIS (DeepSeek — AUTHORITATIVE, PRIMARY) ===
{deepseek_part}

=== PERSPECTIVE 2 (OpenRouter — sanity check, flag disagreements) ===
{openrouter_part}

=== PERSPECTIVE 3 (Mistral — additional context, flag blind spots) ===
{mistral_part}

Your job:
1. Your DeepSeek analysis is the PRIMARY authority. The other perspectives are sanity checks.
2. Identify where OpenRouter or Mistral caught something you missed — flag these as "supplemental observations"
3. Identify where OpenRouter or Mistral disagrees with your analysis — if their reasoning is stronger, adopt it. If not, explain why your analysis stands.
4. Produce the FINAL INTEGRATED JSON output. This is the single source of truth.
5. Flag any remaining uncertainty that needs human judgment.

Return ONLY the JSON object, no markdown fences.
{schema_json}"""
        try:
            synth_raw = _call_deepseek(synthesis_prompt, timeout=timeout_per_model * 3)
            synthesis = extract_json(synth_raw)
        except Exception as e:
            errors.append(f"synthesis: {e}")

    # Fallback: if synthesis failed, use best available parsed response
    if synthesis is None:
        for model in ["deepseek", "openrouter", "mistral"]:
            if parsed.get(model):
                synthesis = parsed[model]
                break

    return {
        "deepseek": results.get("deepseek", ""),
        "openrouter": results.get("openrouter", ""),
        "mistral": results.get("mistral", ""),
        "parsed_deepseek": parsed.get("deepseek"),
        "parsed_openrouter": parsed.get("openrouter"),
        "parsed_mistral": parsed.get("mistral"),
        "synthesis": synthesis or {},
        "errors": errors,
    }
