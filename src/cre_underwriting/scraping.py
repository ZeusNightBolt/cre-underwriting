"""
cre_underwriting.scraping — Hardened Scraping Module.

Anti-bot detection → Camoufox fallback → Firefox BiDi pivot.
Caching, retry with exponential backoff, resume support.

Architecture:
  Stage 1: curl-based protection detection (Akamai/Cloudflare/basic)
  Stage 2: Camoufox headless attempt (os=macos fingerprint)
  Stage 3: Firefox BiDi pivot (real browser, beats everything)

Usage:
    from cre_underwriting.scraping import BidiSession, detect_protection, scrape_with_cascade

    # Just BiDi (for known Akamai sites like LoopNet)
    with BidiSession(port=9222) as session:
        html = session.navigate_and_extract("https://www.loopnet.com/listing/...")
        # html contains the full page source

    # Full cascade
    html, source = scrape_with_cascade("https://example.com/listing")
"""

import hashlib
import json
import os
import random
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Tuple, List
from urllib.parse import urlparse


# ════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════

DEFAULT_BIDI_PORT = 9222
DEFAULT_LOCK_FILE = "/tmp/hermes_cre_bidi.lock"
DEFAULT_CACHE_DIR = os.path.expanduser("~/.cache/cre_underwriting/scraping")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"
)

# Anti-bot detection signatures
PROTECTION_SIGNATURES = {
    "akamai": [
        ("header", "X-Akamai-"),
        ("header", "AkamaiGHost"),
        ("body", "Reference #"),
        ("body", "akamai"),
    ],
    "cloudflare": [
        ("header", "cf-ray:"),
        ("header", "cloudflare"),
        ("body", "Checking your browser"),
        ("body", "cf-browser-verify"),
    ],
    "basic": [
        ("body", "403 Forbidden"),
        ("body", "Access Denied"),
    ],
}

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 2.0     # seconds
MAX_DELAY = 30.0     # seconds


# ════════════════════════════════════════════════════════════
# Stage 1: Anti-Bot Detection
# ════════════════════════════════════════════════════════════

def detect_protection(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Detect what anti-bot protection a site uses.

    Sends a curl request with a standard browser User-Agent and analyzes
    response headers and body for known bot-detection signatures.

    Returns:
        {
            "level": "akamai" | "cloudflare" | "basic" | "none",
            "status_code": int,
            "evidence": list[str],
            "recommended_stage": 2 | 3,
        }
    """
    import subprocess

    cmd = [
        "curl", "-s", "-i", "--connect-timeout", str(timeout),
        "-H", f"User-Agent: {DEFAULT_USER_AGENT}",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: en-US,en;q=0.9",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        output = result.stdout
    except subprocess.TimeoutExpired:
        return {"level": "unknown", "status_code": 0,
                "evidence": ["timeout"], "recommended_stage": 3}

    if not output:
        return {"level": "unknown", "status_code": 0,
                "evidence": ["empty response"], "recommended_stage": 3}

    # Parse status code
    status_line = output.split("\n")[0] if output else ""
    status_code = 0
    if "HTTP" in status_line:
        try:
            status_code = int(status_line.split()[1])
        except (IndexError, ValueError):
            pass

    headers, _, body = output.partition("\r\n\r\n")
    if not body:
        headers, body = output.split("\n\n", 1) if "\n\n" in output else (output, "")

    headers_lower = headers.lower()
    body_lower = body.lower()

    evidence = []

    # Check Akamai
    for sig_type, sig in PROTECTION_SIGNATURES["akamai"]:
        if sig_type == "header" and sig.lower() in headers_lower:
            evidence.append(f"akamai_header: {sig}")
        elif sig_type == "body" and sig.lower() in body_lower:
            evidence.append(f"akamai_body: {sig}")

    if evidence:
        return {"level": "akamai", "status_code": status_code,
                "evidence": evidence, "recommended_stage": 3}

    # Check Cloudflare
    for sig_type, sig in PROTECTION_SIGNATURES["cloudflare"]:
        if sig_type == "header" and sig.lower() in headers_lower:
            evidence.append(f"cloudflare_header: {sig}")
        elif sig_type == "body" and sig.lower() in body_lower:
            evidence.append(f"cloudflare_body: {sig}")

    if evidence:
        return {"level": "cloudflare", "status_code": status_code,
                "evidence": evidence, "recommended_stage": 3}

    # Check basic protection
    if status_code in (403, 429, 503):
        for sig_type, sig in PROTECTION_SIGNATURES["basic"]:
            if sig.lower() in body_lower:
                evidence.append(f"basic: {sig}")
        return {"level": "basic", "status_code": status_code,
                "evidence": evidence or [f"HTTP {status_code}"],
                "recommended_stage": 2}

    # No protection detected
    if status_code == 200:
        return {"level": "none", "status_code": 200,
                "evidence": [], "recommended_stage": 1}

    return {"level": "unknown", "status_code": status_code,
            "evidence": [], "recommended_stage": 3}


# ════════════════════════════════════════════════════════════
# Stage 0: curl_cffi with TLS Impersonation
# ════════════════════════════════════════════════════════════

def _attempt_curl_cffi(url: str, timeout: int = 15) -> Optional[str]:
    """
    Attempt to fetch a URL using curl_cffi with Firefox TLS impersonation.

    curl_cffi mimics browser JA4 fingerprints, HTTP/2 frame order, and header
    casing at the network layer. Bypasses basic TLS-level bot detection without
    needing a full browser. Falls back to None if library not installed.

    Works on: Zillow, basic Cloudflare, sites checking TLS only.
    Fails on: Akamai (checks JS execution), hard JS challenges.
    """
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        return None

    try:
        resp = cffi_requests.get(
            url,
            impersonate="firefox135",
            timeout=timeout,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": DEFAULT_USER_AGENT,
            },
        )
        if resp.status_code == 200 and not _is_block_page(resp.text):
            return resp.text
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════
# Block-Page Classifier
# ════════════════════════════════════════════════════════════

from enum import Enum  # noqa: E402 — intentional section-local import

class BlockReason(Enum):
    OK = "ok"
    TLS_FAIL = "tls_fail"
    JS_CHALLENGE = "js_challenge"
    RATE_LIMIT = "rate_limit"
    CAPTCHA = "captcha"
    UNKNOWN = "unknown"


def classify_block(html: str, status_code: int = 200,
                   headers: Optional[dict] = None) -> BlockReason:
    """
    Classify WHY we were blocked, not just THAT we were blocked.
    """
    if not html:
        return BlockReason.UNKNOWN

    h = html.lower()
    hdrs = str(headers or {}).lower()

    # Check specific reasons BEFORE the generic OK check
    # JS challenge signatures
    if any(s in h for s in ["cf-browser-verify", "_abck", "jschl-answer",
                              "challenge-platform", "managed-challenge"]):
        return BlockReason.JS_CHALLENGE

    # Rate limiting
    if status_code == 429 or any(s in h for s in ["rate limit", "too many requests"]):
        return BlockReason.RATE_LIMIT

    # Hard CAPTCHA — check before OK since CAPTCHA pages can return 200
    if any(s in h for s in ["captcha", "recaptcha", "h-captcha"]):
        return BlockReason.CAPTCHA

    # TLS-level failure
    if len(html) < 2000 and "cf-ray" in hdrs:
        return BlockReason.TLS_FAIL

    # Akamai block page
    if "reference #" in h or "access denied" in h:
        return BlockReason.JS_CHALLENGE

    # If we got here and it looks clean, it's OK
    if status_code == 200 and not _is_block_page(html):
        return BlockReason.OK

    return BlockReason.UNKNOWN


# ════════════════════════════════════════════════════════════
# Per-Domain Tier Cache (sqlite)
# ════════════════════════════════════════════════════════════

import sqlite3  # noqa: E402 — intentional section-local import
import threading  # noqa: E402 — intentional section-local import

_tier_cache_lock = threading.Lock()
TIER_CACHE_DB = os.path.expanduser("~/.cache/cre_underwriting/tier_cache.db")


def _init_tier_cache():
    os.makedirs(os.path.dirname(TIER_CACHE_DB), exist_ok=True)
    with sqlite3.connect(TIER_CACHE_DB) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS tiers (
            domain TEXT PRIMARY KEY,
            tier TEXT NOT NULL,
            cached_at TEXT NOT NULL
        )""")
        db.execute("PRAGMA journal_mode=WAL")


def get_cached_tier(domain: str, max_age_days: int = 7) -> Optional[str]:
    """Get the cached scraping tier for a domain. Returns None if stale."""
    _init_tier_cache()
    with _tier_cache_lock, sqlite3.connect(TIER_CACHE_DB) as db:
        row = db.execute(
            "SELECT tier, cached_at FROM tiers WHERE domain = ?", (domain,)
        ).fetchone()
        if not row:
            return None
        tier, cached_at = row
        age = datetime.now() - datetime.fromisoformat(cached_at)
        if age > timedelta(days=max_age_days):
            db.execute("DELETE FROM tiers WHERE domain = ?", (domain,))
            return None
        return tier


def set_cached_tier(domain: str, tier: str):
    """Cache the successful scraping tier for a domain."""
    _init_tier_cache()
    with _tier_cache_lock, sqlite3.connect(TIER_CACHE_DB) as db:
        db.execute(
            "INSERT OR REPLACE INTO tiers (domain, tier, cached_at) VALUES (?, ?, ?)",
            (domain, tier, datetime.now().isoformat()),
        )

def _attempt_camoufox(url: str, timeout: int = 30) -> Optional[str]:
    """
    Attempt to fetch a URL using Camoufox with macOS fingerprint.

    Camoufox is a Firefox fork with C++-level fingerprint injection that
    can bypass basic protection and some Cloudflare instances. It CANNOT
    bypass Akamai — for that, use Stage 3 (Firefox BiDi).

    Returns page HTML string, or None if blocked/failed.
    """
    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        return None  # Camoufox not installed

    try:
        with Camoufox(
            headless=True,
            humanize=True,
            os=["macos"],
            screen={"width": 1440, "height": 900},
            locale="en-US",
            timezone="America/New_York",
            geoip=False,
        ) as browser:
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000)
            time.sleep(5)  # Let JS execute
            html = page.content()

            # Check if we got blocked
            if _is_block_page(html):
                return None

            return html
    except Exception:
        return None


def _is_block_page(html: str) -> bool:
    """Check if the page is an anti-bot block page."""
    if not html:
        return True
    html_lower = html.lower()
    block_signals = [
        "access denied", "403 forbidden", "cf-browser-verify",
        "checking your browser", "please enable javascript",
        "reference #",
    ]
    return any(sig in html_lower for sig in block_signals) and len(html) < 5000


# ════════════════════════════════════════════════════════════
# Stage 3: Firefox BiDi Pivot
# ════════════════════════════════════════════════════════════

class BidiSession:
    """
    Context manager for Firefox BiDi sessions.

    Manages the full lifecycle: ensure Firefox running → create BiDi session →
    navigate → extract → end session. Handles retry with exponential backoff.

    Usage:
        with BidiSession(port=9222, max_retries=3) as session:
            html = session.navigate_and_extract("https://www.loopnet.com/...")
    """

    def __init__(self, port: int = DEFAULT_BIDI_PORT,
                 lock_file: str = DEFAULT_LOCK_FILE,
                 max_retries: int = MAX_RETRIES,
                 base_delay: float = BASE_DELAY,
                 max_delay: float = MAX_DELAY):
        self.port = port
        self.lock_file = lock_file
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._driver = None
        self._lock_fd = None

    def __enter__(self):
        self._ensure_firefox()
        self._create_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._end_session()
        return False

    def navigate_and_extract(self, url: str, dwell_min: float = 8.0,
                             dwell_max: float = 14.0,
                             scroll_px: int = 400) -> str:
        """
        Navigate to a URL and extract the full page HTML.

        Applies human-like behavior: random dwell time, random scroll,
        10% chance of double-take (revisit).

        Retries with exponential backoff on failure.
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._navigate_inner(url, dwell_min, dwell_max, scroll_px)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = min(self.base_delay * (2 ** attempt) + random.uniform(0, 1),
                               self.max_delay)
                    time.sleep(delay)

        raise RuntimeError(
            f"Failed to navigate to {url} after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def _navigate_inner(self, url: str, dwell_min: float,
                        dwell_max: float, scroll_px: int) -> str:
        """Inner navigation with human-like behavior."""
        if not self._driver:
            raise RuntimeError("BidiSession not initialized")

        self._driver.get(url)

        # Random dwell time (Gaussian-ish)
        dwell = random.uniform(dwell_min, dwell_max)
        time.sleep(dwell)

        # Simulate scroll
        import random as rnd
        self._driver.execute_script(f"window.scrollBy(0, {rnd.randint(300, scroll_px)})")
        time.sleep(1)

        # 10% chance of double-take (revisit)
        if rnd.random() < 0.10:
            current_url = self._driver.current_url
            self._driver.get(current_url)
            time.sleep(3)

        return self._driver.page_source

    def _ensure_firefox(self):
        """Ensure exactly ONE Firefox debug instance is running."""
        import fcntl

        # Check if port is already in use
        if self._port_listening():
            return

        # Acquire lock
        self._lock_fd = open(self.lock_file, "w")
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock_fd.close()
            self._lock_fd = None
            # Another process is starting Firefox — wait for it
            for _ in range(30):
                time.sleep(1)
                if self._port_listening():
                    return
            raise RuntimeError("Firefox failed to start within 30s")

        # Kill stale processes on this port
        subprocess.run(["fuser", "-k", f"{self.port}/tcp"],
                      capture_output=True, timeout=5)

        # Start Firefox
        profile_dir = os.path.expanduser(
            "~/.mozilla/firefox/firefox-remote-scrape-enable")
        if not os.path.isdir(profile_dir):
            os.makedirs(profile_dir, exist_ok=True)

        subprocess.Popen(
            ["firefox", "--new-instance", "--profile", profile_dir,
             f"--remote-debugging-port={self.port}", "--no-remote",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
        )

        # Wait for port to become available
        for _ in range(30):
            time.sleep(1)
            if self._port_listening():
                return

        raise RuntimeError(f"Firefox did not start on port {self.port} within 30s")

    def _port_listening(self) -> bool:
        """Check if BiDi port is listening (synchronous — safe in any context)."""
        try:
            r = subprocess.run(
                ["fuser", f"{self.port}/tcp"],
                capture_output=True, timeout=3,
            )
            return r.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _create_session(self):
        """Create a Selenium WebDriver session connected to Firefox BiDi."""
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options

        options = Options()
        options.add_argument("--no-remote")
        options.debugger_address = f"127.0.0.1:{self.port}"

        self._driver = webdriver.Firefox(options=options)

    def _end_session(self):
        """Clean up the BiDi session (but leave Firefox running)."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

        if self._lock_fd:
            try:
                import fcntl
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
            except Exception:
                pass
            self._lock_fd = None


# ════════════════════════════════════════════════════════════
# Full Cascade Scraper
# ════════════════════════════════════════════════════════════

def scrape_with_cascade(url: str, bidi_port: int = DEFAULT_BIDI_PORT,
                        use_cache: bool = True) -> Tuple[str, str]:
    """
    Smart 4-tier scraping cascade with domain-tier caching.

    T0: curl_cffi with TLS impersonation (fastest, beats TLS fingerprint checks)
    T1: Camoufox headless (anti-fingerprint, beats JS checks)
    T2: Firefox BiDi (real browser, beats everything including Akamai)

    Router logic:
      - Check domain tier cache first (skip probing)
      - Try cached tier → if still works, return immediately
      - If cache miss: probe T0 → classify → T1 → classify → T2
      - RATE_LIMIT: backoff same tier, don't escalate
      - CAPTCHA: fail fast, don't retry
      - Cache successful tier per domain (7-day TTL)

    Returns:
        (html_content, source_tier) — e.g., ("<html>...", "curl_cffi")
    """
    domain = urlparse(url).netloc

    # Cache check
    if use_cache:
        cached = _cache_get(url)
        if cached:
            return cached, "cache"

    # Tier cache: try previously-successful tier first
    cached_tier = get_cached_tier(domain)
    if cached_tier:
        html = _try_tier(cached_tier, url, bidi_port)
        if html:
            if use_cache:
                _cache_set(url, html)
            return html, cached_tier
        # Cached tier failed — re-probe from scratch

    # Full probe cascade
    tiers = [
        ("curl_cffi", lambda: _attempt_curl_cffi(url)),
        ("camoufox", lambda: _attempt_camoufox(url)),
        ("bidi", lambda: _bidi_fetch(url, bidi_port)),
    ]

    for tier_name, fetcher in tiers:
        try:
            html = fetcher()
        except Exception:
            continue

        reason = classify_block(html or "", 200 if html else 403)
        if reason == BlockReason.OK:
            html = html or ""
            if use_cache:
                _cache_set(url, html)
            set_cached_tier(domain, tier_name)
            return html, tier_name
        if reason == BlockReason.RATE_LIMIT:
            time.sleep(5)  # Backoff, retry same tier once
            try:
                html = fetcher()
                if html and classify_block(html) == BlockReason.OK:
                    if use_cache:
                        _cache_set(url, html)
                    set_cached_tier(domain, tier_name)
                    return html, tier_name
            except Exception:
                pass
        if reason == BlockReason.CAPTCHA:
            raise RuntimeError(f"CAPTCHA detected at tier {tier_name} for {domain}")

    raise RuntimeError(f"All {len(tiers)} tiers exhausted for {url}")


def _try_tier(tier: str, url: str, bidi_port: int) -> Optional[str]:
    """Try a specific cached tier. Returns HTML or None."""
    try:
        if tier == "curl_cffi":
            return _attempt_curl_cffi(url)
        elif tier == "camoufox":
            return _attempt_camoufox(url)
        elif tier == "bidi":
            return _bidi_fetch(url, bidi_port)
    except Exception:
        pass
    return None


def _bidi_fetch(url: str, bidi_port: int) -> str:
    """Fetch via Firefox BiDi. Raises on failure (no graceful fallback)."""
    with BidiSession(port=bidi_port, max_retries=2) as session:
        return session.navigate_and_extract(url)


# ════════════════════════════════════════════════════════════
# Caching Layer
# ════════════════════════════════════════════════════════════

def _cache_key(url: str) -> str:
    """Generate a cache key from a URL."""
    parsed = urlparse(url)
    # Use path + query as the primary key
    key = parsed.path.rstrip("/").replace("/", "_") or "root"
    if parsed.query:
        # Hash long query strings
        query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
        key = f"{key}_{query_hash}"
    return f"{key}.html"


def _cache_path(url: str) -> Path:
    """Get the cache file path for a URL."""
    os.makedirs(DEFAULT_CACHE_DIR, exist_ok=True)
    return Path(DEFAULT_CACHE_DIR) / _cache_key(url)


def _cache_get(url: str, max_age_hours: int = 24) -> Optional[str]:
    """Get cached content for a URL, if not expired."""
    path = _cache_path(url)
    if not path.exists():
        return None

    # Check age
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    age = datetime.now() - mtime
    if age > timedelta(hours=max_age_hours):
        return None

    try:
        return path.read_text()
    except Exception:
        return None


def _cache_set(url: str, content: str):
    """Cache content for a URL."""
    path = _cache_path(url)
    try:
        path.write_text(content)
    except Exception:
        pass  # Non-critical — just skip caching


def clear_cache():
    """Clear all cached scraped content."""
    import shutil
    if os.path.isdir(DEFAULT_CACHE_DIR):
        shutil.rmtree(DEFAULT_CACHE_DIR)


def cache_stats() -> Dict:
    """Get cache statistics."""
    if not os.path.isdir(DEFAULT_CACHE_DIR):
        return {"files": 0, "total_size": 0}

    files = list(Path(DEFAULT_CACHE_DIR).glob("*.html"))
    total_size = sum(f.stat().st_size for f in files)
    return {"files": len(files), "total_size": total_size}


# ════════════════════════════════════════════════════════════
# Convenience: Batch scraping with resume
# ════════════════════════════════════════════════════════════

def scrape_batch(urls: List[str], output_dir: Optional[str] = None,
                 resume_from: int = 0, max_per_session: int = 15,
                 bidi_port: int = DEFAULT_BIDI_PORT) -> List[Dict]:
    """
    Scrape a batch of URLs with resume support and caching.

    Args:
        urls: List of URLs to scrape
        output_dir: Directory to save individual page results (None = no save)
        resume_from: Index to resume from (0-based)
        max_per_session: Max URLs per BidiSession (restart Firefox after)
        bidi_port: Firefox debug port

    Returns:
        List of {"url": str, "html": str, "source": str, "error": str|None}
    """
    results = []
    urls_to_scrape = urls[resume_from:]

    for i, url in enumerate(urls_to_scrape, start=resume_from):
        # Restart Firefox session periodically
        if i > 0 and i % max_per_session == 0:
            time.sleep(random.uniform(15, 30))  # Cool-down

        try:
            html, source = scrape_with_cascade(url, bidi_port, use_cache=True)
            result = {"url": url, "html": html, "source": source, "error": None}
        except Exception as e:
            result = {"url": url, "html": None, "source": None, "error": str(e)}

        results.append(result)

        # Save incrementally (resume-safe)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            idx = i
            save_path = os.path.join(output_dir, f"page_{idx:04d}.json")
            with open(save_path, "w") as f:
                json.dump(result, f, default=str)

    return results
