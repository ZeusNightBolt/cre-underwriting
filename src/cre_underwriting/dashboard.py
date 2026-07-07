#!/usr/bin/env python3
"""
cre_underwriting.dashboard — Claude Analytical Dashboard Generator.

Generates a data-dense, mono-forward, border-left-accented static HTML
underwriting dashboard from pipeline output.

Design System: Claude Opus Reference (cre-dashboard-claude skill)
  - DM Mono + Source Serif 4
  - Dark: #0a0c0e bg, #101214 card, #1a1e24 border
  - Border-left accent mechanism (no gradients, no rounded corners)
  - Tabular nums on all financial values
  - No glassmorphism, no animations, no emoji
"""

from datetime import date
from typing import Optional


def _num(val, fmt="{:,.0f}", fallback="—"):
    """Safely format a number."""
    if val is None:
        return fallback
    try:
        return fmt.format(float(val))
    except (ValueError, TypeError):
        return fallback


def _pct(val, fallback="—"):
    """Safely format a percentage."""
    if val is None:
        return fallback
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return fallback


def _money(val, fallback="—"):
    """Safely format a dollar amount."""
    if val is None:
        return fallback
    try:
        return f"${float(val):,.0f}"
    except (ValueError, TypeError):
        return fallback


def generate_dashboard(data: dict, title: str = None) -> str:
    """
    Generate a complete analytical HTML dashboard from pipeline output.

    Args:
        data: Output from PipelineOrchestrator.run() or run_dict()
        title: Optional override for page title

    Returns:
        Complete HTML string ready for deployment
    """
    # ── Extract with safe defaults ──
    address = data.get("address") or data.get("property", {}).get("address", "Unknown Property")
    city = data.get("city") or data.get("property", {}).get("municipality", "")
    state = data.get("state") or data.get("property", {}).get("state", "NJ")
    listing_id = data.get("listing_id") or data.get("property", {}).get("listing_id", "")
    ask_price = data.get("ask_price") or data.get("property", {}).get("price", 0) or 0
    property_type = data.get("property_type") or data.get("property", {}).get("property_type", "")
    analysis_date = data.get("analysis_date", str(date.today()))

    # Convexity
    convexity = data.get("convexity", {})
    if isinstance(convexity, dict):
        divergence = convexity.get("divergence", {})
        verdict = convexity.get("verdict", {})
        pwev = convexity.get("pwev", {})
        frontier = convexity.get("frontier", {})
    else:
        divergence = verdict = pwev = frontier = {}

    # Enhanced
    enhanced = data.get("enhanced", {})
    moats = enhanced.get("moats", {})
    offers = enhanced.get("offers", {})
    demographics = enhanced.get("demographics", {})
    environmental = enhanced.get("environmental", {})
    comps_data = enhanced.get("comps", {})
    legal_risk = enhanced.get("legal_risk", {})

    # Also check top-level for fixture compatibility
    if not moats:
        moats = data.get("moats", {})
    if not offers:
        offers = data.get("offers", data.get("offer_analysis", {}))
    if not demographics:
        demographics = data.get("demographics", {})
    if not environmental:
        environmental = data.get("environmental", {})
    if not comps_data:
        comps_data = data.get("comps", data.get("comp_summary", {}))
    if not legal_risk:
        legal_risk = data.get("lawyer_brain", {})

    # Verdict text
    verdict_raw = data.get("verdict", {})
    if isinstance(verdict_raw, str):
        verdict_text = verdict_raw
    elif isinstance(verdict_raw, dict):
        verdict_text = verdict_raw.get("verdict", "ANALYZE")
    else:
        verdict_text = "ANALYZE"
    # Also check convexity.verdict which might be a string in some fixtures
    cv_verdict = convexity.get("verdict", {}) if isinstance(convexity, dict) else {}
    if isinstance(cv_verdict, str):
        verdict_text = cv_verdict
    elif isinstance(cv_verdict, dict):
        verdict_text = cv_verdict.get("verdict", verdict_text)
    verdict_class = "pass" if "PASS" in verdict_text else "pursue" if "PURSUE" in verdict_text else "conditional"

    # Hard floor
    hard_floor_mid = data.get("hard_floor_mid", 0)

    # Build tabs
    tabs = []
    tabs.append(("overview", "OVERVIEW", _build_overview(data, ask_price, hard_floor_mid, verdict_text, verdict_class, divergence, pwev, frontier, moats)))
    tabs.append(("valuation", "VALUATION", _build_valuation(data)))
    tabs.append(("scenarios", "SCENARIOS", _build_scenarios(data)))
    tabs.append(("divergence", "DIVERGENCE", _build_divergence(divergence, data)))
    tabs.append(("offers", "OFFERS", _build_offers(offers, ask_price)))
    tabs.append(("moats", "MOATS", _build_moats(moats)))
    tabs.append(("legal", "LEGAL", _build_legal(legal_risk)))
    tabs.append(("demographics", "DEMOGRAPHICS", _build_demographics(demographics)))
    tabs.append(("environmental", "ENVIRONMENTAL", _build_environmental(environmental)))
    tabs.append(("comps", "COMPS", _build_comps(comps_data, ask_price)))
    tabs.append(("recommendation", "RECOMMENDATION", _build_recommendation(data, verdict)))

    tab_buttons = "\n".join(
        f'<button class="tab-btn{f" active" if i==0 else ""}" onclick="showTab(\'{tid}\')">{label}</button>'
        for i, (tid, label, _) in enumerate(tabs)
    )
    tab_contents = "\n".join(
        f'<div class="tab-content{f" active" if i==0 else ""}" id="{tid}">{content}</div>'
        for i, (tid, _, content) in enumerate(tabs)
    )

    # KPI strip (top-level)
    kpi_strip = _build_kpi_strip(data, ask_price, hard_floor_mid, divergence, pwev, moats)
    # Verdict block
    v_summary = ""
    if isinstance(verdict, dict):
        v_summary = verdict.get("risk_reward_summary", "")
    if not v_summary:
        v_summary = data.get("recommendation", {}).get("risk_reward_summary", "")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{title or address} — CRE Underwriting</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Source+Serif+4:ital,opsz,wght@0,8..60,300..700;1,8..60,300..700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #0a0c0e;
  --card: #101214;
  --border: #1a1e24;
  --text: #b8c8d8;
  --sub: #6a7a8a;
  --muted: #3a4a5a;
  --green: #6aba8a;
  --greenS: #8bc98b;
  --red: #ba6a5a;
  --redS: #c88888;
  --blue: #4a6a8a;
  --blueL: #8ab8da;
  --gold: #a88a6a;
  --olive: #8aaa8a;
  --yellow: #d4a843;
  --orange: #c8864a;
  --purple: #8a6aaa;
  --mono: 'DM Mono', 'IBM Plex Mono', 'JetBrains Mono', 'Fira Code', monospace;
  --serif: 'Source Serif 4', 'Cormorant Garamond', 'Crimson Pro', Georgia, serif;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ scrollbar-gutter: stable; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: var(--serif);
  line-height: 1.6;
  min-height: 100dvh;
  -webkit-font-smoothing: antialiased;
}}
.container {{ max-width: 960px; margin: auto; padding: 24px 20px 48px; }}

/* Header */
.header {{
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}}
.header-top {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--muted);
  text-transform: uppercase;
  margin-bottom: 8px;
}}
.header h1 {{
  font-family: var(--serif);
  font-size: 24px;
  font-weight: 400;
  color: var(--text);
  line-height: 1.25;
  margin-bottom: 6px;
}}
.header-meta {{
  font-family: var(--mono);
  font-size: 10px;
  color: var(--sub);
  letter-spacing: 0.5px;
}}
.header-price {{
  font-family: var(--mono);
  font-size: 28px;
  font-weight: 500;
  color: var(--gold);
  font-variant-numeric: tabular-nums;
  margin-top: 12px;
}}

/* Verdict block */
.verdict {{
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--amber);
  padding: 12px 14px;
  margin: 16px 0;
}}
.verdict.pursue {{ border-left-color: var(--green); }}
.verdict.pass {{ border-left-color: var(--red); }}
.verdict-label {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 2px;
  color: var(--muted);
  text-transform: uppercase;
  margin-bottom: 4px;
}}
.verdict-text {{
  font-family: var(--mono);
  font-size: 15px;
  font-weight: 500;
  color: var(--text);
  letter-spacing: 0.3px;
}}
.verdict-sub {{
  font-family: var(--serif);
  font-size: 12.5px;
  color: var(--sub);
  margin-top: 6px;
  line-height: 1.55;
  max-width: 780px;
}}

/* KPI strip */
.kpi-strip {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
  margin-bottom: 20px;
}}
.kpi-cell {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 10px 12px;
}}
.kpi-label {{
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 1.5px;
  color: var(--muted);
  text-transform: uppercase;
  margin-bottom: 4px;
}}
.kpi-value {{
  font-family: var(--mono);
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}}
.kpi-sub {{
  font-family: var(--mono);
  font-size: 8px;
  color: var(--sub);
  margin-top: 2px;
  letter-spacing: 0.3px;
}}

/* Tabs */
.tabs {{
  display: flex;
  flex-wrap: wrap;
  gap: 1px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
  overflow-x: auto;
}}
.tab-btn {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  padding: 10px 14px;
  background: transparent;
  color: var(--sub);
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  text-transform: uppercase;
  white-space: nowrap;
}}
.tab-btn.active {{
  color: var(--text);
  border-bottom-color: var(--green);
}}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* Section label */
.section-label {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 2px;
  color: var(--muted);
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
  padding-bottom: 4px;
  margin-bottom: 12px;
  margin-top: 24px;
}}
.section-label:first-child {{ margin-top: 0; }}

/* Cards */
.card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 12px 14px;
  margin-bottom: 8px;
}}
.card-worst {{ border-left: 3px solid var(--red); }}
.card-base {{ border-left: 3px solid var(--blue); }}
.card-best {{ border-left: 3px solid var(--green); }}
.card-moonshot {{ border-left: 3px solid var(--purple); }}
.card-header {{
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--text);
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}}
.card-metrics {{
  font-family: var(--mono);
  font-size: 10px;
  color: var(--sub);
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}}
.card-metrics span {{ font-variant-numeric: tabular-nums; }}
.card-desc {{
  font-family: var(--serif);
  font-size: 12.5px;
  color: var(--sub);
  line-height: 1.55;
  max-width: 780px;
}}

/* Metric row (label + value inline) */
.metric-row {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}}
.metric-row:last-child {{ border-bottom: none; }}
.metric-key {{
  font-family: var(--mono);
  font-size: 10px;
  color: var(--sub);
  letter-spacing: 0.5px;
}}
.metric-val {{
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 500;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}}

/* Offer table */
.offer-table {{
  width: 100%;
  border-collapse: collapse;
  font-family: var(--mono);
  font-size: 10px;
  margin-bottom: 16px;
}}
.offer-table th {{
  color: var(--muted);
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-size: 8px;
}}
.offer-table td {{
  color: var(--text);
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-variant-numeric: tabular-nums;
}}
.offer-table tr.best {{ background: rgba(106,186,138,0.05); }}
.offer-table tr.walk {{ background: rgba(186,106,90,0.05); }}

/* Moat bars */
.moat-row {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}}
.moat-row:last-child {{ border-bottom: none; }}
.moat-name {{
  font-family: var(--mono);
  font-size: 9px;
  color: var(--sub);
  width: 180px;
  flex-shrink: 0;
  letter-spacing: 0.3px;
}}
.moat-bar-bg {{
  flex: 1;
  height: 8px;
  background: var(--border);
  border-radius: 1px;
  overflow: hidden;
}}
.moat-bar-fill {{
  height: 100%;
  border-radius: 1px;
}}
.moat-score {{
  font-family: var(--mono);
  font-size: 11px;
  color: var(--text);
  width: 32px;
  text-align: right;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}}
.moat-rationale {{
  font-family: var(--serif);
  font-size: 11.5px;
  color: var(--sub);
  margin-left: 190px;
  margin-top: -4px;
  margin-bottom: 8px;
  line-height: 1.5;
  max-width: 700px;
}}

/* Flags */
.flag {{
  display: inline-block;
  padding: 3px 8px;
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 2px;
  margin: 2px 4px 2px 0;
  letter-spacing: 0.3px;
}}
.flag-red {{ background: rgba(186,106,90,0.12); color: var(--redS); border: 1px solid rgba(186,106,90,0.25); }}
.flag-amber {{ background: rgba(212,168,67,0.08); color: var(--yellow); border: 1px solid rgba(212,168,67,0.2); }}
.flag-green {{ background: rgba(106,186,138,0.08); color: var(--greenS); border: 1px solid rgba(106,186,138,0.2); }}

/* Prose */
.prose {{
  font-family: var(--serif);
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
  max-width: 780px;
}}
.prose-small {{
  font-family: var(--serif);
  font-size: 12px;
  line-height: 1.55;
  color: var(--sub);
  max-width: 780px;
}}

/* Two-column */
.two-col {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}}
@media (max-width: 720px) {{
  .two-col {{ grid-template-columns: 1fr; }}
  .moat-name {{ width: 140px; }}
  .moat-rationale {{ margin-left: 150px; }}
}}

/* Footer */
.footer {{
  font-family: var(--mono);
  font-size: 8px;
  color: var(--muted);
  text-align: center;
  padding: 24px 0 16px;
  border-top: 1px solid var(--border);
  margin-top: 32px;
  letter-spacing: 0.5px;
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <div class="header-top">LISTING {listing_id} · {city.upper() if city else ""} · {state} · {property_type}</div>
  <h1>{address}</h1>
  <div class="header-meta">Analysis date: {analysis_date}</div>
  <div class="header-price">{_money(ask_price)}</div>
</div>

<div class="verdict {verdict_class}">
  <div class="verdict-label">VERDICT</div>
  <div class="verdict-text">{verdict_text}</div>
  <div class="verdict-sub">{v_summary}</div>
</div>

{kpi_strip}

<div class="tabs">
{tab_buttons}
</div>

{tab_contents}

<div class="footer">
  CRE Underwriting Dashboard · Generated {analysis_date}<br>
  Data sources: LoopNet, Census ACS, FEMA, NJDEP · Not investment advice
</div>

</div>
<script>
function showTab(id) {{
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  event.target.classList.add('active');
}}
</script>
</body>
</html>
'''
    return html


# ─────────────────────────────────────────────────────────────────
# Tab builders
# ─────────────────────────────────────────────────────────────────

def _build_kpi_strip(data, ask_price, hard_floor_mid, divergence, pwev, moats):
    """Build the top KPI strip."""
    cells = []

    # Hard floor
    cells.append(_kpi_cell("HARD FLOOR", _money(hard_floor_mid), f"{_pct(hard_floor_mid/ask_price*100 if ask_price else 0)} of ask"))

    # Convexity ratio
    cr = divergence.get("convexity_ratio", 0)
    cells.append(_kpi_cell("CONVEXITY", f"{cr:.2f}x", divergence.get("convexity_verdict", "")))

    # PWEV
    pwev_val = pwev.get("pwev", 0) if isinstance(pwev, dict) else (pwev or 0)
    cells.append(_kpi_cell("PWEV", _money(pwev_val), f"{_pct(pwev.get('pwev_vs_ask_pct', 0) if isinstance(pwev, dict) else 0)} vs ask"))

    # Risk/reward
    rr = divergence.get("risk_reward_ratio", 0)
    cells.append(_kpi_cell("RISK/REWARD", f"{rr:.1f}", "Ratio"))

    # Moat score
    if isinstance(moats, dict):
        mt = moats.get("total_score", moats.get("total", 0))
        mm = moats.get("max_score", moats.get("max", 24))
        cells.append(_kpi_cell("MOAT SCORE", f"{mt}/{mm}", moats.get("classification", "")))
    else:
        cells.append(_kpi_cell("MOAT SCORE", "—", ""))

    # Frontier zone
    zone = data.get("frontier", {}).get("zone", data.get("convexity", {}).get("frontier", {}).get("zone", "—"))
    cells.append(_kpi_cell("FRONTIER", zone, ""))

    return f'<div class="kpi-strip">{"".join(cells)}</div>'


def _kpi_cell(label, value, sub):
    return f'''<div class="kpi-cell">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  <div class="kpi-sub">{sub}</div>
</div>'''


def _build_overview(data, ask_price, hard_floor_mid, verdict_text, verdict_class, divergence, pwev, frontier, moats):
    """Overview tab: high-level deal summary."""
    parts = []
    parts.append('<div class="section-label">Deal Summary</div>')

    # Key metrics
    rows = []
    rows.append(("Ask Price", _money(ask_price)))
    rows.append(("Hard Floor (mid)", _money(hard_floor_mid)))
    rows.append(("Floor Coverage", _pct(hard_floor_mid/ask_price*100 if ask_price else 0)))
    rows.append(("Convexity Ratio", f"{divergence.get('convexity_ratio', 0):.2f}x"))
    rows.append(("Convexity Verdict", divergence.get("convexity_verdict", "—")))
    rows.append(("Effective Worst", _money(divergence.get("effective_worst", 0))))
    rows.append(("Best Case MOIC", f"{divergence.get('best_case_moic', 0):.2f}x"))
    rows.append(("PWEV", _money(pwev.get("pwev", 0) if isinstance(pwev, dict) else (pwev or 0))))
    rows.append(("PWEV vs Ask", _pct(pwev.get("pwev_vs_ask_pct", 0) if isinstance(pwev, dict) else 0)))
    rows.append(("Frontier Zone", frontier.get("zone", "—") if isinstance(frontier, dict) else "—"))

    table = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows)
    parts.append(f'<div class="card">{table}</div>')

    # Verdict reasoning
    cv = data.get("convexity", {})
    if isinstance(cv, dict):
        vdict = cv.get("verdict", {})
        reasoning = vdict.get("reasoning", []) if isinstance(vdict, dict) else []
    else:
        reasoning = []
    if reasoning:
        parts.append('<div class="section-label">Reasoning</div>')
        for r in reasoning:
            parts.append(f'<div class="card"><div class="prose-small">{r}</div></div>')

    # Recommendation
    rec = data.get("recommendation", {})
    if rec:
        parts.append('<div class="section-label">Recommendation</div>')
        parts.append(f'<div class="card"><div class="prose">{rec.get("rationale", "")}</div></div>')

    return "\n".join(parts)


def _build_valuation(data):
    """Valuation tab: triangulated asset value."""
    parts = []
    parts.append('<div class="section-label">Valuation Triangulation</div>')

    vt = data.get("valuation_triangulation", {})
    if not vt:
        # Check fixture-style
        vt = data.get("hard_asset_floor", {})
        if vt:
            rows = []
            for k in ["low", "mid", "high"]:
                rows.append((f"Hard Floor ({k.upper()})", _money(vt.get(k, 0))))
            rows.append(("Methodology", vt.get("methodology", "—")))
            table = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows)
            parts.append(f'<div class="card">{table}</div>')
        else:
            parts.append('<div class="card"><div class="prose-small">No valuation data available.</div></div>')
        return "\n".join(parts)

    # Full triangulation
    rows = []
    land = vt.get("land", {})
    if land:
        rows.append(("Land Value", f"{_money(land.get('value_low'))} – {_money(land.get('value_high'))}"))
    building = vt.get("building", {})
    if building:
        rows.append(("Building (depreciated)", f"{_money(building.get('depreciated_value_low'))} – {_money(building.get('depreciated_value_high'))}"))
    equipment = vt.get("equipment", {})
    if equipment:
        rows.append(("Equipment/FF&E", f"{_money(equipment.get('value_low'))} – {_money(equipment.get('value_high'))}"))
    rows.append(("Licenses", _money(vt.get("license_total_value", 0))))
    rows.append(("Hard Asset Total (low)", _money(vt.get("hard_asset_value_low", 0))))
    rows.append(("Hard Asset Total (mid)", _money(vt.get("hard_asset_value_mid", 0))))
    rows.append(("Hard Asset Total (high)", _money(vt.get("hard_asset_value_high", 0))))
    rows.append(("Asset Coverage", _pct(vt.get("asset_coverage_mid_pct", 0))))
    rows.append(("Verdict", vt.get("verdict", "—")))

    table = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows)
    parts.append(f'<div class="card">{table}</div>')

    if vt.get("narrative"):
        parts.append(f'<div class="card"><div class="prose-small">{vt["narrative"]}</div></div>')

    return "\n".join(parts)


def _build_scenarios(data):
    """Scenarios tab: 5-scenario architecture."""
    parts = []
    parts.append('<div class="section-label">Scenario Analysis</div>')

    scenarios = data.get("scenarios", {})
    if isinstance(scenarios, list):
        for s in scenarios:
            name = s.get("name", "Unnamed")
            prob = s.get("probability", 0)
            val = s.get("exit_value", s.get("value", 0))
            moic = s.get("moic", s.get("moic_5yr", 0))
            desc = s.get("description", s.get("narrative", ""))
            cls = _scenario_class(name)
            parts.append(f'''<div class="card {cls}">
  <div class="card-header">{name} · {prob*100:.0f}%</div>
  <div class="card-metrics">
    <span>Exit: {_money(val)}</span>
    <span>MOIC: {moic:.2f}x</span>
  </div>
  <div class="card-desc">{desc}</div>
</div>''')
    elif isinstance(scenarios, dict):
        for name, s in scenarios.items():
            val = s.get("value", s.get("exit_value", 0))
            moic = s.get("moic_5yr", s.get("moic", 0))
            desc = s.get("description", s.get("narrative", ""))
            cls = _scenario_class(name)
            parts.append(f'''<div class="card {cls}">
  <div class="card-header">{name}</div>
  <div class="card-metrics">
    <span>Exit: {_money(val)}</span>
    <span>MOIC: {moic:.2f}x</span>
  </div>
  <div class="card-desc">{desc}</div>
</div>''')
    else:
        parts.append('<div class="card"><div class="prose-small">No scenario data.</div></div>')

    return "\n".join(parts)


def _scenario_class(name):
    n = name.lower()
    if "worst" in n: return "card-worst"
    if "base" in n or "status quo" in n: return "card-base"
    if "phase 3" in n or "strategic" in n or "moonshot" in n: return "card-moonshot"
    if "best" in n or "optimize" in n or "phase 1" in n or "phase 2" in n: return "card-best"
    return ""


def _build_divergence(divergence, data):
    """Divergence tab: convexity metrics."""
    parts = []
    parts.append('<div class="section-label">Divergence & Convexity</div>')

    if not divergence:
        parts.append('<div class="card"><div class="prose-small">No divergence data.</div></div>')
        return "\n".join(parts)

    rows = []
    rows.append(("Absolute Spread", _money(divergence.get("absolute_spread", 0))))
    rows.append(("Capital-Normalized Spread", f"{divergence.get('capital_normalized_spread', 0):.2f}"))
    rows.append(("Convexity Ratio", f"{divergence.get('convexity_ratio', 0):.2f}x"))
    rows.append(("Convexity Verdict", divergence.get("convexity_verdict", "—")))
    rows.append(("Worst Scenario Value", _money(divergence.get("worst_scenario_value", 0))))
    rows.append(("Hard Floor (mid)", _money(divergence.get("hard_floor_mid", 0))))
    rows.append(("Effective Worst", _money(divergence.get("effective_worst", 0))))
    rows.append(("Base Scenario Value", _money(divergence.get("base_scenario_value", 0))))
    rows.append(("Best Scenario Value", _money(divergence.get("best_scenario_value", 0))))
    rows.append(("Worst-Case Recovery (% of Capital)", _pct(divergence.get("worst_case_pct_capital", 0))))
    rows.append(("Best Case MOIC", f"{divergence.get('best_case_moic', 0):.2f}x"))
    rows.append(("Risk/Reward Ratio", f"{divergence.get('risk_reward_ratio', 0):.1f}"))

    table = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows)
    parts.append(f'<div class="card">{table}</div>')

    # Also show fixture-style divergence if present
    fix_div = data.get("divergence", {})
    if fix_div and fix_div != divergence:
        parts.append('<div class="section-label">Divergence (External)</div>')
        rows2 = []
        for k, v in fix_div.items():
            if isinstance(v, (int, float)):
                rows2.append((k.replace("_", " ").title(), f"{v:,.2f}" if isinstance(v, float) else f"{v:,}"))
            else:
                rows2.append((k.replace("_", " ").title(), str(v)))
        table2 = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows2)
        parts.append(f'<div class="card">{table2}</div>')

    return "\n".join(parts)


def _build_offers(offers, ask_price):
    """Offers tab: offer ladder."""
    parts = []
    parts.append('<div class="section-label">Offer Ladder</div>')

    points = []
    if isinstance(offers, dict):
        points = offers.get("points", [])
    elif isinstance(offers, list):
        points = offers

    if not points:
        parts.append('<div class="card"><div class="prose-small">No offer analysis.</div></div>')
        return "\n".join(parts)

    rows = []
    for p in points:
        price = p.get("price", 0)
        label = p.get("label", "")
        psf = p.get("price_per_sf", p.get("price_psf", 0))
        cap = p.get("cap_rate_pct", p.get("cap_rate_implied", 0))
        grm = p.get("gross_rent_multiplier", p.get("grn_adj", 0))
        coc = p.get("cash_on_cash_pct", p.get("coc", 0))
        cls = "best" if "TARGET" in label or "AGGRESSIVE" in label else "walk" if "WALK" in label else ""
        rows.append(f'<tr class="{cls}"><td>{label or "—"}</td><td>{_money(price)}</td><td>${psf:,.0f}</td><td>{cap:.1f}%</td><td>{grm:.1f}x</td><td>{coc:.1f}%</td></tr>')

    table = f'''<table class="offer-table">
<thead><tr><th>Label</th><th>Price</th><th>$/SF</th><th>Cap Rate</th><th>GRM</th><th>CoC</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>'''
    parts.append(table)

    if isinstance(offers, dict) and offers.get("rationale"):
        parts.append(f'<div class="card"><div class="prose-small">{offers["rationale"]}</div></div>')

    return "\n".join(parts)


def _build_moats(moats):
    """Moats tab: 8-dimension scoring."""
    parts = []
    parts.append('<div class="section-label">Moat Analysis</div>')

    dimensions = []
    if isinstance(moats, dict):
        dimensions = moats.get("dimensions", [])
        if not dimensions and "scores" in moats:
            # Fixture-style moats
            for name, info in moats["scores"].items():
                dimensions.append({
                    "name": name.replace("_", " ").title(),
                    "score": info.get("score", 0),
                    "max": info.get("max", 3),
                    "rationale": info.get("rationale", "")
                })
    elif isinstance(moats, list):
        dimensions = moats

    if not dimensions:
        parts.append('<div class="card"><div class="prose-small">No moat data.</div></div>')
        return "\n".join(parts)

    total = 0
    max_total = 0
    for d in dimensions:
        score = d.get("score", 0)
        max_s = d.get("max", d.get("max_score", 3))
        total += score
        max_total += max_s
        name = d.get("name", "Unknown")
        pct = score / max_s * 100 if max_s else 0
        color = "var(--green)" if pct >= 66 else "var(--yellow)" if pct >= 33 else "var(--red)"
        rationale = d.get("rationale", "")
        parts.append(f'''<div class="moat-row">
  <div class="moat-name">{name}</div>
  <div class="moat-bar-bg"><div class="moat-bar-fill" style="width:{pct:.0f}%;background:{color}"></div></div>
  <div class="moat-score">{score}/{max_s}</div>
</div>''')
        if rationale:
            parts.append(f'<div class="moat-rationale">{rationale}</div>')

    parts.insert(1, f'<div class="card"><div class="metric-row"><span class="metric-key">TOTAL SCORE</span><span class="metric-val">{total}/{max_total}</span></div></div>')

    return "\n".join(parts)


def _build_legal(legal_risk):
    """Legal tab: lawyer-brain assessment."""
    parts = []
    parts.append('<div class="section-label">Legal & Concealment Risk</div>')

    if not legal_risk:
        parts.append('<div class="card"><div class="prose-small">No legal risk data.</div></div>')
        return "\n".join(parts)

    score = legal_risk.get("legal_risk_score", 0)
    severity = legal_risk.get("legal_risk_severity", legal_risk.get("severity", "UNKNOWN"))
    env_liab = legal_risk.get("env_liability_adjustment", 0)
    flags = legal_risk.get("concealment_flags", legal_risk.get("top_3_concealment_risks", []))
    missing = legal_risk.get("missing_data", [])

    sev_color = "var(--red)" if severity in ("CRITICAL", "HIGH") else "var(--yellow)" if severity == "MODERATE" else "var(--green)"

    rows = []
    rows.append(("Legal Risk Score", f'<span style="color:{sev_color}">{score}/10</span>'))
    rows.append(("Severity", severity))
    rows.append(("Env Liability Adj", _money(env_liab)))
    rows.append(("Missing Data Points", str(len(missing))))

    table = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows)
    parts.append(f'<div class="card">{table}</div>')

    if flags:
        parts.append('<div class="section-label">Concealment Flags</div>')
        for f in flags:
            sev = f.get("severity", f.get("risk", "MODERATE"))
            fc = "flag-red" if sev == "HIGH" or sev == "CRITICAL" else "flag-amber"
            detail = f.get("detail", "")
            parts.append(f'<span class="flag {fc}">{f.get("risk", f.get("flag", "Unknown"))}</span>')
            if detail:
                parts.append(f'<div class="card"><div class="prose-small">{detail}</div></div>')

    if missing:
        parts.append('<div class="section-label">Missing Data</div>')
        for m in missing:
            parts.append(f'<span class="flag flag-amber">{m}</span>')

    if legal_risk.get("narrative"):
        parts.append(f'<div class="card"><div class="prose-small">{legal_risk["narrative"]}</div></div>')

    return "\n".join(parts)


def _build_demographics(demographics):
    """Demographics tab."""
    parts = []
    parts.append('<div class="section-label">Demographics & Economics</div>')

    if not demographics:
        parts.append('<div class="card"><div class="prose-small">No demographic data.</div></div>')
        return "\n".join(parts)

    rows = []
    for k, v in demographics.items():
        if isinstance(v, dict):
            continue
        if isinstance(v, list):
            continue
        label = k.replace("_", " ").title()
        if isinstance(v, (int, float)) and v > 1000:
            val = f"{v:,.0f}"
        elif isinstance(v, float):
            val = f"{v:.1f}"
        else:
            val = str(v)
        rows.append((label, val))

    table = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows)
    parts.append(f'<div class="card">{table}</div>')

    # Tailwinds / headwinds
    tw = demographics.get("tailwinds", [])
    hw = demographics.get("headwinds", [])
    if tw:
        parts.append('<div class="section-label">Tailwinds</div>')
        for t in tw:
            parts.append(f'<span class="flag flag-green">{t}</span>')
    if hw:
        parts.append('<div class="section-label">Headwinds</div>')
        for h in hw:
            parts.append(f'<span class="flag flag-amber">{h}</span>')

    return "\n".join(parts)


def _build_environmental(environmental):
    """Environmental tab."""
    parts = []
    parts.append('<div class="section-label">Environmental Risk</div>')

    if not environmental:
        parts.append('<div class="card"><div class="prose-small">No environmental data.</div></div>')
        return "\n".join(parts)

    rows = []
    for k, v in environmental.items():
        if isinstance(v, (list, dict)):
            continue
        label = k.replace("_", " ").title()
        val = str(v)
        rows.append((label, val))

    table = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in rows)
    parts.append(f'<div class="card">{table}</div>')

    # Red flags
    rf = environmental.get("red_flags", [])
    if rf:
        parts.append('<div class="section-label">Red Flags</div>')
        for f in rf:
            parts.append(f'<span class="flag flag-red">{f}</span>')

    return "\n".join(parts)


def _build_comps(comps_data, ask_price):
    """Comps tab."""
    parts = []
    parts.append('<div class="section-label">Comparable Sales</div>')

    comps = []
    if isinstance(comps_data, dict):
        comps = comps_data.get("comps", [])
    elif isinstance(comps_data, list):
        comps = comps_data

    if not comps:
        parts.append('<div class="card"><div class="prose-small">No comp data.</div></div>')
        return "\n".join(parts)

    rows = []
    for c in comps:
        addr = c.get("address", c.get("source", "—"))
        price = c.get("sale_price", c.get("price", 0))
        sf = c.get("sf", c.get("building_size_sf", 0))
        psf = c.get("price_per_sf", c.get("price_psf", 0))
        if not psf and price and sf:
            psf = price / sf
        ptype = c.get("property_type", c.get("type", ""))
        rows.append(f'<tr><td>{addr}</td><td>{_money(price)}</td><td>{sf:,.0f}</td><td>${psf:,.0f}</td><td>{ptype}</td></tr>')

    table = f'''<table class="offer-table">
<thead><tr><th>Address</th><th>Price</th><th>SF</th><th>$/SF</th><th>Type</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>'''
    parts.append(table)

    # Comp summary
    summary = comps_data.get("summary", {}) if isinstance(comps_data, dict) else {}
    if isinstance(summary, dict):
        srows = []
        for k, v in summary.items():
            if isinstance(v, (list, dict)):
                continue
            srows.append((k.replace("_", " ").title(), str(v)))
        if srows:
            st = "\n".join(f'<div class="metric-row"><span class="metric-key">{k}</span><span class="metric-val">{v}</span></div>' for k, v in srows)
            parts.append(f'<div class="card">{st}</div>')

    return "\n".join(parts)


def _build_recommendation(data, verdict):
    """Recommendation tab: structured negotiation sequence."""
    parts = []
    parts.append('<div class="section-label">Recommendation & Term Sheet</div>')

    # Target / walk-away
    target = None
    walk = None
    if isinstance(verdict, dict):
        target = verdict.get("target_offer")
        walk = verdict.get("walk_away")
    elif isinstance(verdict, str):
        # Try to extract from string like "CONDITIONAL — PURSUE AT $210,000"
        import re
        m = re.search(r'\$([\d,]+)', verdict)
        if m:
            target = float(m.group(1).replace(',', ''))
    
    if target:
        parts.append(f'<div class="card card-best"><div class="card-header">TARGET OFFER</div><div class="kpi-value" style="font-size:22px">{_money(target)}</div></div>')
    if walk:
        parts.append(f'<div class="card card-worst"><div class="card-header">WALK AWAY</div><div class="kpi-value" style="font-size:22px">{_money(walk)}</div></div>')

    # Key conditions
    rec = data.get("recommendation", {})
    conditions = rec.get("key_conditions", data.get("verdict", {}).get("key_conditions", []))
    if conditions:
        parts.append('<div class="section-label">Key Conditions</div>')
        for c in conditions:
            parts.append(f'<div class="card"><div class="prose-small">{c}</div></div>')

    # What would make it pursue
    pursue = rec.get("what_would_make_it_pursue_at_ask", [])
    if pursue:
        parts.append('<div class="section-label">What Would Make It Pursue at Ask</div>')
        for p in pursue:
            parts.append(f'<div class="card"><div class="prose-small">{p}</div></div>')

    # What would make it pass
    pass_ = rec.get("what_would_make_it_pass", [])
    if pass_:
        parts.append('<div class="section-label">What Would Make It Pass</div>')
        for p in pass_:
            parts.append(f'<div class="card"><div class="prose-small">{p}</div></div>')

    # Business ideas
    ideas = data.get("business_ideas", [])
    if ideas:
        parts.append('<div class="section-label">Business Concepts</div>')
        for idea in ideas:
            name = idea.get("concept", "")
            rev = idea.get("revenue_est", 0)
            ebitda = idea.get("ebitda_est", 0)
            margin = idea.get("margin", 0)
            parts.append(f'''<div class="card">
  <div class="card-header">{name}</div>
  <div class="card-metrics">
    <span>Revenue: {_money(rev)}</span>
    <span>EBITDA: {_money(ebitda)}</span>
    <span>Margin: {margin}%</span>
  </div>
  <div class="card-desc">{idea.get("rationale", "")}</div>
</div>''')

    return "\n".join(parts)
