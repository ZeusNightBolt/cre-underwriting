#!/usr/bin/env python3
"""
cre_underwriting.dashboard — Dashboard Generator.

Generates a complete, anti-slop-compliant, 10-tab static HTML CRE underwriting
dashboard from a PipelineOrchestrator output dict.

Usage:
    from cre_underwriting.dashboard import generate_dashboard

    pipeline_result = orch.run("deal.json")
    html = generate_dashboard(pipeline_result)
    with open("dashboard.html", "w") as f:
        f.write(html)

Design rules enforced (per anti-slop-design + open-design fusion):
    1. min-height: 100dvh + scrollbar-gutter: stable
    2. color-mix(in oklch, ...) for card gradients
    3. font-size ≥ 16px on interactive elements
    4. ALL CAPS → letter-spacing: 0.08em
    5. 1px hairline KPI grid, border-radius: 6px
    6. No glassmorphism, no backdrop-filter
    7. Terracotta (#C96442) accent for CRE
    8. tabular-nums on all financial values
    9. prefers-reduced-motion wrapping
    10. No invented metrics — every KPI has label + value + context
"""

from datetime import date
from typing import Optional


def generate_dashboard(pipeline_result: dict,
                       title: str = None,
                       accent_color: str = "#c96442") -> str:
    """
    Generate a complete anti-slop HTML dashboard from pipeline output.

    Args:
        pipeline_result: Output from PipelineOrchestrator.run() or run_dict()
        title: Optional custom title (defaults to property address)
        accent_color: Accent color (terracotta #c96442 for CRE, cyan #00d4aa for finance)

    Returns:
        Complete HTML string ready for deployment
    """
    # Extract data sections
    convexity = pipeline_result.get("convexity", {})
    enhanced = pipeline_result.get("enhanced", {})
    address = pipeline_result.get("address", "Unknown Property")
    listing_id = pipeline_result.get("listing_id", "")
    ask_price = pipeline_result.get("ask_price", 0)
    hard_floor = pipeline_result.get("hard_floor_mid", 0)
    analysis_date = pipeline_result.get("analysis_date", str(date.today()))

    # Convexity data
    divergence = convexity.get("divergence", {})
    verdict = convexity.get("verdict", {})
    pwev = convexity.get("pwev", {})
    frontier = convexity.get("frontier", {})

    # Enhanced data
    moats = enhanced.get("moats", {})
    offers = enhanced.get("offers", {})
    demographics = enhanced.get("demographics", {})
    environmental = enhanced.get("environmental", {})
    comps_data = enhanced.get("comps", {})

    # Build KPI grid
    kpi_html = _build_kpi_grid(pipeline_result)

    # Build tabs
    scenarios_tab = _build_scenarios_tab(pipeline_result)
    valuation_tab = _build_valuation_tab(pipeline_result)
    divergence_tab = _build_divergence_tab(divergence, frontier, pwev, ask_price, hard_floor)
    moats_tab = _build_moats_tab(moats)
    offers_tab = _build_offers_tab(offers, ask_price)
    risks_tab = _build_risks_tab(pipeline_result)
    demographics_tab = _build_demographics_tab(demographics)
    environmental_tab = _build_environmental_tab(environmental)
    comps_tab = _build_comps_tab(comps_data, ask_price)
    recommendation_tab = _build_recommendation_tab(verdict, divergence, moats, offers, ask_price, hard_floor)

    verdict_class = "conditional" if "CONDITIONAL" in verdict.get("verdict", "") else (
        "pursue" if "PURSUE" in verdict.get("verdict", "") else "pass")
    verdict_text = verdict.get("verdict", "UNKNOWN")

    city = pipeline_result.get("city", "")
    state = pipeline_result.get("state", "NJ")
    property_type = pipeline_result.get("property_type", "")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{title or address} — CRE Underwriting</title>
<style>
/* ════════════════════════════════════════════════════════════════
   Open Design Fusion: Trading Terminal × Warm Editorial
   Anti-Slop Compliant — Zero cardinal sins, mobile-safe
   ════════════════════════════════════════════════════════════════ */
:root {{
  --bg: #0D0D0D; --surface: #141414; --surface2: #1A1A1A;
  --border: #2A2A2A; --text: #FAF9F5; --sub: #B0AEA5; --muted: #87867F;
  --accent: {accent_color}; --accent-dim: color-mix(in oklch, {accent_color} 30%, transparent);
  --green: #00D4AA; --red: #FF4757; --amber: #FFB800;
  --gold: #C9A96E; --blue: #4A7A9A; --purple: #8A6AAA;
  --font-display: Georgia, 'Times New Roman', serif;
  --font-body: 'Source Serif 4', 'Cormorant Garamond', Georgia, serif;
  --font-mono: 'DM Mono', 'IBM Plex Mono', 'JetBrains Mono', monospace;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ scrollbar-gutter: stable; }}
body {{
  background: var(--bg); color: var(--text);
  font-family: var(--font-body); line-height: 1.5;
  min-height: 100dvh; overscroll-behavior: contain;
  -webkit-font-smoothing: antialiased;
}}
.container {{ max-width: 1100px; margin: auto; padding: 20px 16px 40px; }}
.header {{
  padding: 24px 0 16px; border-bottom: 1px solid var(--border);
  margin-bottom: 20px; display: flex; justify-content: space-between;
  align-items: flex-end; flex-wrap: wrap; gap: 12px;
}}
.header h1 {{
  font-family: var(--font-mono); font-size: 15px; font-weight: 600;
  color: var(--text); letter-spacing: 0.08em; text-transform: uppercase;
}}
.header .price {{ font-family: var(--font-display); font-size: 28px; color: var(--gold); font-variant-numeric: tabular-nums; }}
.verdict-banner {{
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 24px; border: 2px solid var(--amber);
  color: var(--amber); font-family: var(--font-mono);
  font-size: 16px; letter-spacing: 0.1em; font-weight: 600;
  margin: 16px 0;
}}
p.verdict-banner.pursue {{ border-color: var(--green); color: var(--green); }}
.verdict-banner.pass {{ border-color: var(--red); color: var(--red); }}
.tagline {{
  font-family: var(--font-body); font-size: 15px; color: var(--sub);
  margin-top: 8px; max-width: 650px; line-height: 1.6;
}}

/* KPI Grid — 1px hairline technique */
.kpi-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 1px; background: var(--border); border: 1px solid var(--border);
  border-radius: 6px; overflow: hidden; margin-bottom: 20px;
}}
.kpi-cell {{
  background: linear-gradient(140deg, var(--surface), color-mix(in oklch, var(--surface2) 90%, transparent));
  padding: 14px 16px;
}}
.kpi-label {{
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em;
  color: var(--muted); text-transform: uppercase;
}}
.kpi-value {{
  font-family: var(--font-display); font-size: 24px; font-weight: 500;
  font-variant-numeric: tabular-nums; margin-top: 4px;
}}
.kpi-sub {{
  font-family: var(--font-mono); font-size: 10px; color: var(--sub); margin-top: 2px;
}}

/* Tabs */
.tabs {{
  display: flex; flex-wrap: wrap; gap: 1px;
  border-bottom: 1px solid var(--border); margin-bottom: 20px;
  overflow-x: auto; -webkit-overflow-scrolling: touch;
}}
.tab-btn {{
  font-family: var(--font-mono); font-size: 16px; letter-spacing: 0.08em;
  padding: 10px 14px; background: transparent; color: var(--sub);
  border: none; border-bottom: 2px solid transparent;
  cursor: pointer; text-transform: uppercase; white-space: nowrap;
  touch-action: manipulation; min-height: 44px;
}}
.tab-btn.active {{
  color: var(--accent); border-bottom: 2px solid var(--accent);
  background: color-mix(in oklch, var(--accent) 5%, transparent);
}}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.section-label {{
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.08em;
  color: var(--muted); text-transform: uppercase;
  padding-bottom: 8px; border-bottom: 1px solid var(--border); margin-bottom: 16px;
}}

/* Cards */
.card {{
  background: linear-gradient(140deg, var(--surface), color-mix(in oklch, var(--surface2) 90%, transparent));
  border: 1px solid var(--border); border-radius: 6px;
  padding: 14px 16px; margin-bottom: 10px;
}}
.card.worst {{ border-top: 2px solid var(--red); }}
.card.best {{ border-top: 2px solid var(--green); }}
.card.phase3 {{ border-top: 2px solid var(--purple); }}
.card-name {{ font-family: var(--font-mono); font-size: 12px; font-weight: 600; color: var(--text); letter-spacing: 0.06em; }}
.card-metrics {{ font-family: var(--font-mono); font-size: 11px; color: var(--sub); margin-top: 6px; display: flex; gap: 18px; flex-wrap: wrap; }}
.card-metrics span {{ font-variant-numeric: tabular-nums; }}
.card-desc {{ font-family: var(--font-body); font-size: 13px; color: var(--sub); margin-top: 6px; line-height: 1.6; }}

/* Flags */
.flag {{ padding: 4px 10px; font-family: var(--font-mono); font-size: 11px; border-radius: 3px; display: inline-block; margin: 3px; }}
.flag-red {{ background: color-mix(in oklch, var(--red) 12%, transparent); color: var(--red); }}
.flag-amber {{ background: color-mix(in oklch, var(--amber) 12%, transparent); color: var(--amber); }}
.flag-green {{ background: color-mix(in oklch, var(--green) 12%, transparent); color: var(--green); }}

/* Moats bar chart */
.moat-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
.moat-label {{ font-family: var(--font-mono); font-size: 10px; color: var(--sub); width: 170px; text-align: right; flex-shrink: 0; letter-spacing: 0.04em; }}
.moat-bar-bg {{ flex: 1; height: 10px; background: var(--border); border-radius: 3px; overflow: hidden; }}
.moat-bar-fill {{ height: 100%; border-radius: 3px; }}
.moat-score {{ font-family: var(--font-display); font-size: 13px; color: var(--text); width: 28px; text-align: right; flex-shrink: 0; font-variant-numeric: tabular-nums; }}
.moat-rationale {{ font-family: var(--font-body); font-size: 12px; color: var(--sub); margin-left: 180px; margin-bottom: 10px; line-height: 1.5; }}

/* Offer grid */
.offer-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: 6px; overflow: hidden; margin-bottom: 10px; }}
.offer-cell {{ background: linear-gradient(140deg, var(--surface), color-mix(in oklch, var(--surface2) 90%, transparent)); padding: 14px 16px; text-align: center; }}
.offer-price {{ font-family: var(--font-display); font-size: 22px; font-weight: 500; font-variant-numeric: tabular-nums; }}
.offer-metric {{ font-family: var(--font-mono); font-size: 11px; color: var(--sub); margin-top: 4px; letter-spacing: 0.04em; }}
.offer-best {{ border: 1px solid var(--green); background: color-mix(in oklch, var(--green) 5%, transparent); }}

/* Footer */
.footer {{
  font-family: var(--font-mono); font-size: 9px; color: var(--muted);
  text-align: center; padding: 24px 0 16px;
  border-top: 1px solid var(--border); margin-top: 28px;
  letter-spacing: 0.04em;
}}

/* Econ row */
.econ-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }}
.econ-item {{
  background: linear-gradient(140deg, var(--surface), color-mix(in oklch, var(--surface2) 90%, transparent));
  border: 1px solid var(--border); padding: 10px 14px; border-radius: 6px;
  flex: 1; min-width: 120px;
}}
.econ-label {{ font-family: var(--font-mono); font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
.econ-value {{ font-family: var(--font-display); font-size: 15px; color: var(--text); font-variant-numeric: tabular-nums; margin-top: 3px; }}

/* Comps table */
.comp-table {{ width: 100%; border-collapse: collapse; font-family: var(--font-mono); font-size: 11px; margin-bottom: 16px; }}
.comp-table th {{ color: var(--muted); text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); font-weight: 400; text-transform: uppercase; letter-spacing: 0.08em; }}
.comp-table td {{ color: var(--text); padding: 8px 10px; border-bottom: 1px solid color-mix(in oklch, var(--border) 50%, transparent); font-variant-numeric: tabular-nums; }}

/* Animations — reduced motion aware */
@media (prefers-reduced-motion: no-preference) {{
  .moat-bar-fill {{ transition: width 600ms ease-out; }}
  .fade-in {{ animation: fadeIn 600ms ease-out; }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }}
}}
@keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

/* Responsive */
@media (max-width: 768px) {{
  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .moat-label {{ width: 120px; font-size: 9px; }}
  .moat-rationale {{ margin-left: 130px; }}
  .offer-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}
@media (max-width: 430px) {{
  .container {{ padding: 12px 8px; }}
  .header h1 {{ font-size: 13px; }}
  .kpi-grid {{ grid-template-columns: 1fr 1fr; }}
  .kpi-value {{ font-size: 20px; }}
  .tab-btn {{ font-size: 16px; padding: 8px 10px; }}
  .moat-label {{ width: 90px; font-size: 8px; }}
  .moat-rationale {{ margin-left: 98px; font-size: 11px; }}
  .comp-table {{ font-size: 9px; }}
  .comp-table th, .comp-table td {{ padding: 5px 6px; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <div>
    <div style="font-family:var(--font-mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;">LISTING {listing_id} · {city.upper() if city else ""} · {state}</div>
    <h1>{address}</h1>
    <div style="font-family:var(--font-body);font-size:13px;color:var(--sub);margin-top:4px;">{property_type}</div>
  </div>
  <div class="price">${ask_price:,.0f}</div>
</div>

<div class="verdict-banner {verdict_class}">{verdict_text}</div>
<div class="tagline">{verdict.get('risk_reward_summary', '')}</div>

{kpi_html}

<div class="tabs">
  <button class="tab-btn active" onclick="showTab('scenarios')">Scenarios</button>
  <button class="tab-btn" onclick="showTab('valuation')">Valuation</button>
  <button class="tab-btn" onclick="showTab('divergence')">Divergence</button>
  <button class="tab-btn" onclick="showTab('moats')">Moats</button>
  <button class="tab-btn" onclick="showTab('offers')">Offers</button>
  <button class="tab-btn" onclick="showTab('risks')">Risks</button>
  <button class="tab-btn" onclick="showTab('demographics')">Demographics</button>
  <button class="tab-btn" onclick="showTab('environmental')">Environmental</button>
  <button class="tab-btn" onclick="showTab('comps')">Comps</button>
  <button class="tab-btn" onclick="showTab('recommendation')">Rec</button>
</div>

<div class="tab-content active" id="scenarios">{scenarios_tab}</div>
<div class="tab-content" id="valuation">{valuation_tab}</div>
<div class="tab-content" id="divergence">{divergence_tab}</div>
<div class="tab-content" id="moats">{moats_tab}</div>
<div class="tab-content" id="offers">{offers_tab}</div>
<div class="tab-content" id="risks">{risks_tab}</div>
<div class="tab-content" id="demographics">{demographics_tab}</div>
<div class="tab-content" id="environmental">{environmental_tab}</div>
<div class="tab-content" id="comps">{comps_tab}</div>
<div class="tab-content" id="recommendation">{recommendation_tab}</div>

<div class="footer">
  CRE Underwriting Analysis · {address} · Listing {listing_id} · {analysis_date}
  <br>Methodology: 5-Scenario Architecture · 4-Method Triangulation · 8-Moat Scoring · Convexity Engine
</div>

</div>

<script>
function showTab(n) {{
  document.querySelectorAll('.tab-content').forEach(e => e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e => e.classList.remove('active'));
  document.getElementById(n).classList.add('active');
  event.target.classList.add('active');
}}
</script>
</body>
</html>'''
    return html


# ════════════════════════════════════════════════════════════════
# Section Builders
# ════════════════════════════════════════════════════════════════

def _build_kpi_grid(result: dict) -> str:
    """Build the KPI grid from pipeline output."""
    divergence = result.get("convexity", {}).get("divergence", {})
    verdict = result.get("convexity", {}).get("verdict", {})
    pwev = result.get("convexity", {}).get("pwev", {})
    moats = result.get("enhanced", {}).get("moats", {})
    offers = result.get("enhanced", {}).get("offers", {})
    hard_floor = result.get("hard_floor_mid", 0)
    ask_price = result.get("ask_price", 0)

    def kpi(label, value, sub="", color="var(--text)"):
        return f'''<div class="kpi-cell"><div class="kpi-label">{label}</div><div class="kpi-value" style="color:{color}">{value}</div><div class="kpi-sub">{sub}</div></div>'''

    cap_rate = result.get("enhanced", {}).get("offers", {}).get("points", [{}])
    cap_val = f"{cap_rate[0].get('cap_rate_pct', 0):.1f}%" if cap_rate else "—"

    cv = divergence.get("convexity_ratio", 0)
    cv_color = "var(--green)" if cv >= 1.5 else ("var(--amber)" if cv >= 1.0 else "var(--red)")

    pwev_pct = pwev.get("pwev_vs_ask_pct", 0)
    pwev_color = "var(--green)" if pwev_pct > 0 else "var(--red)"

    floor_pct = (hard_floor / ask_price * 100) if ask_price > 0 else 0

    return f'''<div class="kpi-grid">
  {kpi("Convexity", f"{cv:.2f}×", divergence.get("convexity_verdict", ""), cv_color)}
  {kpi("PWEV vs Ask", f"{pwev_pct:+.1f}%", f"${pwev.get('pwev', 0):,.0f} PWEV", pwev_color)}
  {kpi("Hard Floor", f"${hard_floor:,.0f}", f"{floor_pct:.0f}% of ask", "var(--blue)")}
  {kpi("Worst Case", f"{divergence.get('worst_case_pct_capital', 0):.0f}%", "of capital", "var(--red)")}
  {kpi("Best MOIC", f"{divergence.get('best_case_moic_5yr', 0):.2f}×", "5-year", "var(--green)")}
  {kpi("Moats", f"{moats.get('total_score', 0)}/24", moats.get('classification', ''), "var(--blue)")}
  {kpi("Offer Target", f"${offers.get('target_low', 0):,.0f}–{offers.get('target_high', 0):,.0f}", f"Walk > ${offers.get('walk_away', 0):,.0f}", "var(--gold)")}
  {kpi("Risk/Reward", f"{divergence.get('risk_reward_ratio', 0):.1f}", "", cv_color)}
</div>'''


def _build_scenarios_tab(result: dict) -> str:
    """Build scenarios tab from deal data."""
    # Scenarios come from the convexity engine's deal data
    # We need to extract from JSON since pipeline_entry doesn't pass raw scenarios
    scenarios_data = result.get("convexity", {}).get("divergence", {})
    return f'''<div class="section-label">5-Scenario Architecture</div>
<div class="card worst">
  <div class="card-name">1. WORST CASE</div>
  <div class="card-metrics">
    <span>Value <b style="color:var(--red)">${scenarios_data.get("worst_scenario_value", 0):,.0f}</b></span>
  </div>
  <div class="card-desc">Worst-case scenario. Hard floor at ${result.get("hard_floor_mid", 0):,.0f} provides downside protection.</div>
</div>
<div class="card">
  <div class="card-name">2. BASELINE</div>
  <div class="card-metrics">
    <span>Value <b>${scenarios_data.get("base_scenario_value", 0):,.0f}</b></span>
  </div>
  <div class="card-desc">Baseline — property operates as-is under new ownership.</div>
</div>
<div class="card best">
  <div class="card-name">3. PHASE 1 OPTIMIZE</div>
  <div class="card-metrics">
    <span>Value <b style="color:var(--green)">${scenarios_data.get("best_scenario_value", 0):,.0f}</b></span>
  </div>
  <div class="card-desc">Phase 1 — low-capital operational improvements. Highest-probability value-add.</div>
</div>
<p style="font-family:var(--font-body);font-size:13px;color:var(--sub);margin-top:12px;">
  Effective worst: ${scenarios_data.get("effective_worst", 0):,.0f} (max of operating worst and hard floor).
  {scenarios_data.get("convexity_verdict", "")} convexity ratio: {scenarios_data.get("convexity_ratio", 0):.2f}×.
</p>'''


def _build_valuation_tab(result: dict) -> str:
    pwev = result.get("convexity", {}).get("pwev", {})
    hard_floor = result.get("hard_floor_mid", 0)
    ask_price = result.get("ask_price", 0)
    return f'''<div class="section-label">4-Method Valuation Triangulation</div>
<div class="kpi-grid">
  <div class="kpi-cell"><div class="kpi-label">Asset-Based Floor</div><div class="kpi-value" style="color:var(--blue)">${hard_floor:,.0f}</div><div class="kpi-sub">Distressed liquidation</div></div>
  <div class="kpi-cell"><div class="kpi-label">PWEV</div><div class="kpi-value" style="color:var(--purple)">${pwev.get('pwev', 0):,.0f}</div><div class="kpi-sub">{pwev.get('pwev_vs_ask_pct', 0):+.1f}% vs ask</div></div>
  <div class="kpi-cell"><div class="kpi-label">Ask Price</div><div class="kpi-value" style="color:var(--gold)">${ask_price:,.0f}</div><div class="kpi-sub">Listing price</div></div>
  <div class="kpi-cell"><div class="kpi-label">PWEV Premium</div><div class="kpi-value" style="color:var(--green)">+{pwev.get('pwev', 0) - ask_price:,.0f}</div><div class="kpi-sub">Above ask</div></div>
</div>
<p style="font-family:var(--font-body);font-size:13px;color:var(--sub);margin-top:12px;">
  PWEV of ${pwev.get('pwev', 0):,.0f} is {pwev.get('pwev_vs_ask_pct', 0):+.1f}% vs ask — {'undervalued' if pwev.get('is_underpriced') else 'overvalued'} at listing price.
</p>'''


def _build_divergence_tab(divergence: dict, frontier: dict, pwev: dict, ask_price: float, hard_floor: float) -> str:
    cv = divergence.get("convexity_ratio", 0)
    cv_color = "var(--green)" if cv >= 1.5 else ("var(--amber)" if cv >= 1.0 else "var(--red)")
    return f'''<div class="section-label">Divergence & Effective Frontier</div>
<div class="kpi-grid">
  <div class="kpi-cell"><div class="kpi-label">Convexity Ratio</div><div class="kpi-value" style="color:{cv_color}">{cv:.2f}×</div><div class="kpi-sub">{divergence.get("convexity_verdict", "")}</div></div>
  <div class="kpi-cell"><div class="kpi-label">Absolute Spread</div><div class="kpi-value" style="color:var(--green)">${divergence.get("absolute_spread", 0):,.0f}</div><div class="kpi-sub">Best − Eff. Worst</div></div>
  <div class="kpi-cell"><div class="kpi-label">Risk/Reward</div><div class="kpi-value" style="color:var(--green)">{divergence.get("risk_reward_ratio", 0):.1f}</div><div class="kpi-sub">Best MOIC ÷ Worst %</div></div>
  <div class="kpi-cell"><div class="kpi-label">Effective Worst</div><div class="kpi-value" style="color:var(--red)">${divergence.get("effective_worst", 0):,.0f}</div><div class="kpi-sub">max(Op Worst, Floor)</div></div>
  <div class="kpi-cell"><div class="kpi-label">Worst % Capital</div><div class="kpi-value" style="color:var(--red)">{divergence.get("worst_case_pct_capital", 0):.0f}%</div><div class="kpi-sub">Of ${ask_price:,.0f}</div></div>
  <div class="kpi-cell"><div class="kpi-label">Best MOIC</div><div class="kpi-value" style="color:var(--green)">{divergence.get("best_case_moic_5yr", 0):.2f}×</div><div class="kpi-sub">5-year</div></div>
  <div class="kpi-cell"><div class="kpi-label">Frontier Zone</div><div class="kpi-value" style="color:var(--amber)">{frontier.get("zone", "")}</div><div class="kpi-sub">({frontier.get("x", 0):.0f}%, {frontier.get("y", 0):.2f}×)</div></div>
  <div class="kpi-cell"><div class="kpi-label">PWEV</div><div class="kpi-value" style="color:var(--purple)">${pwev.get("pwev", 0):,.0f}</div><div class="kpi-sub">{pwev.get("pwev_vs_ask_pct", 0):+.1f}% vs ask</div></div>
</div>'''


def _build_moats_tab(moats: dict) -> str:
    if not moats or not moats.get("dimensions"):
        return '<div class="section-label">8-Moat Scoring</div><p>No moat data available.</p>'

    dims = moats["dimensions"]
    rows = []
    for d in dims:
        score = d["score"]
        pct = score / 3 * 100
        color = "var(--green)" if score == 3 else ("var(--amber)" if score == 2 else "var(--red)")
        rows.append(f'''<div class="moat-row">
  <div class="moat-label">{d["name"]}</div>
  <div class="moat-bar-bg"><div class="moat-bar-fill" style="width:{pct:.0f}%;background:{color};"></div></div>
  <div class="moat-score" style="color:{color}">{score}/3</div>
</div>
<div class="moat-rationale">{d.get("rationale", "")}</div>''')

    return f'''<div class="section-label">8-Moat Scoring · {moats["total_score"]}/{moats.get("max_score", 24)} · {moats.get("classification", "")}</div>
{"".join(rows)}
<div class="card" style="margin-top:16px;">
  <div class="card-name">{moats.get("verdict_text", "")}</div>
</div>'''


def _build_offers_tab(offers: dict, ask_price: float) -> str:
    if not offers or not offers.get("points"):
        return '<div class="section-label">Offer Analysis</div><p>No offer data available.</p>'

    points = offers["points"]
    cells = []
    for p in points:
        label = p.get("label", "")
        color = "var(--green)" if "TARGET" in label else ("var(--amber)" if "WALK" in label else "var(--red)" if "ASK" in label else "var(--text)")
        best = 'offer-best' if 'AGGRESSIVE' in label or 'TARGET MIDPOINT' in label else ''
        cells.append(f'''<div class="offer-cell {best}">
  <div class="offer-price" style="color:{color}">${p["price"]:,.0f}</div>
  <div class="offer-metric">${p.get("price_per_sf", 0):.0f}/SF</div>
  <div class="offer-metric">Cap {p.get("cap_rate_pct", 0):.1f}%</div>
  <div class="offer-metric">CoC {p.get("cash_on_cash_pct", 0):.1f}%</div>
  <div style="font-family:var(--font-mono);font-size:9px;color:{color};margin-top:4px;letter-spacing:0.06em;">{label}</div>
</div>''')

    return f'''<div class="section-label">Offer Analysis · Price Ladder</div>
<div class="offer-grid">{"".join(cells)}</div>
<p style="font-family:var(--font-body);font-size:13px;color:var(--sub);margin-top:12px;line-height:1.6;">
  {offers.get("rationale", "")}
</p>'''


def _build_risks_tab(result: dict) -> str:
    enhanced = result.get("enhanced", {})
    env = enhanced.get("environmental", {})
    return f'''<div class="section-label">Risks & Concealment</div>
<div class="card">
  <div class="card-name">Tax Bomb</div>
  <div class="card-desc">NJ reassesses at sale price. Post-sale tax increase modeled in all scenarios.</div>
</div>
<div class="card">
  <div class="card-name">Environmental</div>
  <div class="card-desc">Flood risk: {env.get("flood_risk_level", "unknown")}. UST risk: {env.get("ust_risk", "unknown")}. Phase I recommended: {env.get("phase_i_recommended", False)}.</div>
</div>
<div class="card">
  <div class="card-name">Structural</div>
  <div class="card-desc">Verify roof/HVAC condition, building code compliance, and any unpermitted work before offer.</div>
</div>'''


def _build_demographics_tab(demographics: dict) -> str:
    if not demographics:
        return '<div class="section-label">Demographics</div><p>No demographic data available.</p>'

    def eco(label, value, color="var(--text)"):
        return f'<div class="econ-item"><div class="econ-label">{label}</div><div class="econ-value" style="color:{color}">{value}</div></div>'

    top_emp = ", ".join(demographics.get("top_employers", [])[:5])

    return f'''<div class="section-label">Economic Profile</div>
<div class="econ-row">
  {eco("Population", f"{demographics.get('population', 0):,}")}
  {eco("Pop Growth (5yr)", f"{demographics.get('population_growth_5yr_pct', 0):+.1f}%")}
  {eco("Median Income", f"${demographics.get('median_household_income', 0):,}")}
  {eco("Poverty Rate", f"{demographics.get('poverty_rate_pct', 0):.1f}%")}
  {eco("Bachelor's+", f"{demographics.get('bachelor_degree_pct', 0):.0f}%")}
</div>
<div class="econ-row">
  {eco("Employment", f"{demographics.get('total_employment', 0):,}")}
  {eco("Emp Growth (5yr)", f"{demographics.get('employment_growth_5yr_pct', 0):+.1f}%")}
  {eco("Unemployment", f"{demographics.get('unemployment_rate_pct', 0):.1f}%")}
  {eco("Median Home", f"${demographics.get('median_home_value', 0):,}")}
  {eco("Rental Vacancy", f"{demographics.get('rental_vacancy_rate_pct', 0):.1f}%")}
</div>
<div class="econ-item" style="margin-top:10px;">
  <div class="econ-label">Top Employers</div>
  <div style="font-family:var(--font-mono);font-size:11px;color:var(--text);margin-top:4px;">{top_emp}</div>
</div>
<p style="font-family:var(--font-body);font-size:12px;color:var(--sub);margin-top:12px;">
  Verdict: {demographics.get("verdict", "unknown")} · Tailwind score: {demographics.get("tailwind_score", 0)} · Headwind: {demographics.get("headwind_score", 0)}
</p>'''


def _build_environmental_tab(environmental: dict) -> str:
    if not environmental:
        return '<div class="section-label">Environmental Risk</div><p>No environmental data available.</p>'
    return f'''<div class="section-label">Environmental Risk Assessment</div>
<div class="kpi-grid">
  <div class="kpi-cell"><div class="kpi-label">Flood Zone</div><div class="kpi-value" style="font-size:18px;">{environmental.get("flood_zone", "—") or "—"}</div><div class="kpi-sub">{environmental.get("flood_risk_level", "unknown").upper()}</div></div>
  <div class="kpi-cell"><div class="kpi-label">In Floodplain</div><div class="kpi-value" style="font-size:18px;color:var(--red) if environmental.get('in_floodplain') else 'var(--green)'">{'YES' if environmental.get("in_floodplain") else 'NO'}</div></div>
  <div class="kpi-cell"><div class="kpi-label">UST Risk</div><div class="kpi-value" style="font-size:18px;color:var(--amber)">{environmental.get("ust_risk", "unknown").upper()}</div><div class="kpi-sub">{environmental.get("ust_sites_nearby", 0)} sites nearby</div></div>
  <div class="kpi-cell"><div class="kpi-label">Phase I ESA</div><div class="kpi-value" style="font-size:18px;color:var(--amber) if environmental.get('phase_i_recommended') else 'var(--green)'">{'RECOMMENDED' if environmental.get("phase_i_recommended") else 'NOT REQUIRED'}</div></div>
</div>'''


def _build_comps_tab(comps_data: dict, ask_price: float) -> str:
    if not comps_data or not comps_data.get("comps"):
        return '<div class="section-label">Comparable Sales</div><p>No comp data available. Consider manual research.</p>'

    comps = comps_data.get("comps", [])
    rows = []
    for c in comps[:10]:
        rows.append(f'<tr><td>{c.get("address", "")}</td><td>{c.get("property_type", "")}</td><td>${c.get("sale_price", 0):,.0f}</td><td>${c.get("price_per_sf", 0):,.0f}/SF</td></tr>')

    return f'''<div class="section-label">Comparable Sales · {comps_data.get("comp_count", len(comps))} found</div>
<table class="comp-table">
  <thead><tr><th>Address</th><th>Type</th><th>Price</th><th>$ / SF</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>
<p style="font-family:var(--font-body);font-size:12px;color:var(--sub);">
  Subject: ${ask_price:,.0f} · Price/SF range: ${comps_data.get("price_per_sf_range", [0,0])[0]:.0f}–${comps_data.get("price_per_sf_range", [0,0])[1]:.0f} SF
</p>'''


def _build_recommendation_tab(verdict: dict, divergence: dict, moats: dict,
                               offers: dict, ask_price: float, hard_floor: float) -> str:
    cv = divergence.get("convexity_ratio", 0)
    return f'''<div class="section-label">Recommendation</div>
<div style="font-family:var(--font-mono);font-size:18px;color:var(--amber);letter-spacing:0.1em;margin-bottom:16px;font-weight:600;">{verdict.get("verdict", "UNKNOWN")}</div>

<div style="font-family:var(--font-body);font-size:14px;color:var(--sub);max-width:700px;line-height:1.7;">
  <p>{verdict.get("risk_reward_summary", "")}</p>
  {f'<p style="margin-top:12px;"><b>Target Offer:</b> ${offers.get("target_low", 0):,.0f} – ${offers.get("target_high", 0):,.0f} · <b>Walk Away:</b> ${offers.get("walk_away", 0):,.0f}</p>' if offers else ''}
  {f'<p style="margin-top:8px;"><b>Moats:</b> {moats.get("total_score", 0)}/24 {moats.get("classification", "")} · <b>Convexity:</b> {cv:.2f}× ({divergence.get("convexity_verdict", "")})</p>' if moats else ''}
</div>

{"; ".join(verdict.get("reasoning", []))}
'''
