# LoopNet Scraping — BiDi + Human-Like Filter Interaction

**Last tested: May 10, 2026. Firefox 150+ uses WebDriver BiDi, NOT CDP.**

## TL;DR: The Only Working Method

LoopNet (Costar-owned) uses Akamai dual-layer protection. The only reliable bypass: connect to the user's REAL Firefox via WebDriver BiDi on port 9222. The real browser's fingerprint passes Akamai.

**Firefox 150 dropped Chrome DevTools Protocol (CDP)** — `/json/version` returns 404. The debug port now serves **WebDriver BiDi** at `ws://127.0.0.1:9222/session`.

### Quick Start

```bash
# 1. Start Firefox with debug port (from server — LarkBox IS the server)
bash ~/hermes-firefox-remote.sh start

# 2. Run the search scraper (human-like filter, outputs JSON)
~/.hermes/.venv/bin/python3 ~/.hermes/skills/finance/cre-underwriting/scripts/loopnet_search.py
```

### Architecture

```
Firefox (real browser, real fingerprint, residential IP)
    ↓ --remote-debugging-port 9222
WebDriver BiDi WebSocket: ws://127.0.0.1:9222/session
    ↓ Python websockets library
BiDi commands: session.new → browsingContext.create → browsingContext.navigate
    → script.evaluate (click "Price" button)
    → script.evaluate (type "1500000" in "Max $" input)
    → script.evaluate (press Enter to apply)
    → Wait for filtered results
    → script.evaluate (extract article.innerText)
    → session.end
```

## Human-Like Filter Interaction (CRITICAL)

**Do NOT try to use URL parameters for filtering.** LoopNet (both AngularJS and React versions) ignores `msrp=`, `max-price=`, `price=`, etc. in URLs. The filter MUST be applied via UI interaction like a human would:

1. Navigate to the base search URL (e.g., `https://www.loopnet.com/search/commercial-real-estate/nj/for-sale/`)
2. Dismiss popups (Escape key, click Close buttons)
3. Click the "Price" filter button (find by `button.innerText === 'Price'`)
4. Find the "Max $" input field (placeholder = "Max $")
5. Set value to the max price using native input setter + dispatch Event('input') + Event('change')
6. Press Enter or click Apply
7. Wait for page to reload with `?max-price=N&view=map` parameter
8. Scrape the filtered article elements

**Working URL after filter**: `https://www.loopnet.com/search/commercial-real-estate/nj/for-sale/?max-price=1500000&view=map`

## BiDi Protocol Reference

### Session Lifecycle
```
Connect:  ws://127.0.0.1:9222/session
Create:   {"id":1, "method":"session.new", "params":{"capabilities":{"alwaysMatch":{"acceptInsecureCerts":true}}}}
  → returns sessionId
Use:      All subsequent commands use this sessionId implicitly
End:      {"id":99, "method":"session.end", "params":{}}
```

### Key Commands
```python
# Create tab
{"method":"browsingContext.create", "params":{"type":"tab"}}
  → returns context ID

# Navigate
{"method":"browsingContext.navigate", "params":{"context":ctx, "url":url, "wait":"complete"}}

# Execute JavaScript (extract data, click buttons, type inputs)
{"method":"script.evaluate", "params":{"expression":"...", "target":{"context":ctx}, "awaitPromise":false}}
```

### PITFALL: Max Session Limit
Firefox has a limit on active BiDi sessions. Always call `session.end` when done. If you get "Maximum number of active sessions", kill Firefox:
```bash
fuser -k 9222/tcp
```

### BiDi Check (NOT CDP)
```bash
# Check if BiDi is alive — use WebSocket, not HTTP GET
timeout 2 python3 -c "
import asyncio, websockets
async def t():
    async with websockets.connect('ws://127.0.0.1:9222/session') as ws:
        print('READY')
asyncio.run(t())
"
```

## Scripts

| Script | Purpose |
|--------|---------|
| `~/.hermes/skills/finance/cre-underwriting/scripts/loopnet_search.py` | Search NJ LoopNet w/ human-like price filter → JSON placards |
| `~/.hermes/skills/finance/cre-underwriting/scripts/loopnet_listing.py` | Scrape single listing detail page + condo/tax/NOI detection |
| `~/.hermes/skills/finance/cre-underwriting/scripts/loopnet_batch.py` | Orchestrate search → filter → detail-scrape → merge |
| `~/hermes-firefox-remote.sh start` | Starts Firefox debug on LarkBox |
| `~/hermes-firefox-remote.sh status` | Checks BiDi availability |
| `~/hermes-firefox-remote.sh navigate <url>` | Opens URL in Firefox via BiDi |
| `~/hermes-firefox-remote.sh stop` | Kills Firefox debug instance |

## Old Selenium Approach (STILL WORKS — May 2026)

Despite Firefox 150+ dropping native CDP, Selenium's `debugger_address = "127.0.0.1:9222"` **still works** (tested May 2026 on Firefox 150+). Selenium appears to bridge to BiDi internally. The `scripts/loopnet_listing.py` script uses this approach and successfully scrapes full listing detail pages.

```python
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
options = Options()
options.debugger_address = "127.0.0.1:9222"
driver = webdriver.Firefox(options=options)
driver.get("https://www.loopnet.com/Listing/.../")
html = driver.page_source
```

**PITFALL**: The `awaitPromise` and complex BiDi script.evaluate calls still fail through Selenium. For JavaScript-heavy extraction (clicking buttons, typing filters), use raw BiDi WebSocket. For simple page loads and HTML extraction, Selenium `debugger_address` is simpler and reliable.

## Tested Methods (May 2026)

| Method | Result | Notes |
|--------|--------|-------|
| **BiDi WebSocket (real Firefox)** | **WORKS** ✅ | Complex JS execution (click, type, extract) |
| Selenium `debugger_address` | **WORKS** ✅ | Simple page loads + HTML extraction. Firefox 150+ bridges to BiDi internally. |
| `curl_cffi` Chrome 136 impersonation | 403 | TLS fingerprint blocked |
| Camoufox | 403 | IP greylisted after ~10-15 requests |
| VPN datacenter IPs | 403 | Akamai blocks known datacenter ranges |
| URL filter params (`msrp=`, `price=`) | IGNORED | LoopNet ignores URL price params |

## Default Search Filters

NJ only, under $1,500,000, property types: Retail, Restaurant, Shopping Center, Multifamily, Hospitality, Land, Residential Income

## Pagination

Format: `https://www.loopnet.com/search/commercial-real-estate/nj/for-sale/N/?max-price=1500000`
25 results per page. ~750 total results = ~30 pages.
