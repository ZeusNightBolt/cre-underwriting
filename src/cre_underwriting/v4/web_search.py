"""
Web search abstraction for CRE underwriting v4.

Primary: Brave Search API (HTTP)
Fallback: Native Hermes web_search tool
"""

import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional


def _brave_search(query: str, count: int = 10,
                  max_retries: int = 3, timeout: int = 30) -> list:
    """Search via Brave Search API. Returns list of {title, url, description}."""
    import gzip
    import io

    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return []

    params = urllib.parse.urlencode({"q": query, "count": str(count)})
    url = "https://api.search.brave.com/res/v1/web/search?%s" % params

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",  # Avoid gzip issues
                "X-Subscription-Token": api_key,
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                # Handle gzip if server ignores Accept-Encoding
                if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b'\x1f\x8b':
                    raw = gzip.decompress(raw)
                data = json.loads(raw)
                results = []
                for r in data.get("web", {}).get("results", []):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "description": r.get("description", ""),
                    })
                return results
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, gzip.BadGzipFile) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + 1)
    return []


def search_county_records(city: str, state: str,
                          property_type: str = "commercial") -> list:
    """Search for county assessor records and recent sales."""
    queries = [
        f'"{city}" {state} property tax assessment records',
        f'site:.gov {city} {state} property sales',
        f'{city} {state} {property_type} real estate recent sale price per square foot',
    ]
    all_results = []
    for q in queries:
        results = _brave_search(q, count=5)
        all_results.extend(results)
    return all_results


def search_corridor_intel(city: str, state: str) -> list:
    """Search for corridor news, development plans, zoning changes."""
    queries = [
        f'"{city}" {state} commercial development plans zoning change',
        f'"{city}" {state} retail corridor growth new construction',
        f'"{city}" {state} real estate market report 2025 2026',
    ]
    all_results = []
    for q in queries:
        results = _brave_search(q, count=3)
        all_results.extend(results)
    return all_results


def search_environmental(address: str, city: str, state: str) -> list:
    """Search for environmental records, UST, contamination."""
    queries = [
        f'"{address}" {city} {state} environmental contamination underground storage tank',
        f'site:epa.gov {city} {state} brownfield superfund',
        f'"{city}" {state} FEMA flood zone map',
    ]
    all_results = []
    for q in queries:
        results = _brave_search(q, count=3)
        all_results.extend(results)
    return all_results


def search_recent_sales(city: str, state: str,
                        property_type: str = "") -> list:
    """Search for recent CRE sales comps."""
    queries = [
        f'{city} {state} {property_type} commercial property sold recent',
        f'site:loopnet.com {city} {state} {property_type}',
        f'site:crexi.com {city} {state} {property_type}',
        f'{city} {state} commercial real estate sale price per square foot',
    ]
    all_results = []
    for q in queries:
        results = _brave_search(q, count=4)
        all_results.extend(results)
    return all_results
