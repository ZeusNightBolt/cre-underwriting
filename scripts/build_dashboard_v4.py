#!/usr/bin/env python3
"""
build_dashboard_v4.py — Generate CRE underwriting dashboard from v4 pipeline output.

v4 design: Claude reference system — DM Mono + Source Serif 4, dark theme, border-left accents.
Data sources: FRED API, Brave Search, Triple-LLM (DeepSeek + OpenRouter + Mistral → DeepSeek synthesis).

Usage:
    python3 build_dashboard_v4.py /tmp/succasunna_v4_result.json [--output /tmp/dash.html] [--deploy vercel]
"""

import json
import sys
import os
import math
from datetime import date
from pathlib import Path
from typing import Optional, Union


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def fm(v, fallback="—"):
    """Format money."""
    if v is None: return fallback
    try:
        v = float(v)
        if abs(v) >= 1_000_000: return f"${v/1e6:,.2f}M"
        if abs(v) >= 1000: return f"${v:,.0f}"
        return f"${v:,.2f}"
    except (ValueError, TypeError):
        return fallback

def pct(v, d=1, fallback="—"):
    """Format percentage."""
    if v is None: return fallback
    try:
        return f"{float(v):.{d}f}%"
    except (ValueError, TypeError):
        return fallback

def sf(v):
    """Safely get string."""
    return str(v) if v else ""

def safe_dict(d, key, default=None):
    """Safely get from dict."""
    return d.get(key, default) if isinstance(d, dict) else default


# ═══════════════════════════════════════════════════════════
# Design system (Claude reference)
# ═══════════════════════════════════════════════════════════

CSS = """
:root {
  --bg: #0a0c0e; --card: #101214; --border: #1a1e24;
  --text: #b8c8d8; --sub: #6a7a8a; --muted: #3a4a5a;
  --green: #6aba8a; --red: #ba6a5a; --gold: #d4a843;
  --blue: #4a6a8a; --orange: #c8864a; --purple: #8a6aaa;
  --mono: 'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;
  --serif: 'Source Serif 4','Cormorant Garamond','Crimson Pro',Georgia,serif;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scrollbar-gutter:stable;background:var(--bg)}
body{
  font-family:var(--serif);background:var(--bg);color:var(--text);
  min-height:100dvh;-webkit-font-smoothing:antialiased;
  max-width:1200px;margin:0 auto;padding:12px 16px 40px;
  font-size:14px;line-height:1.55;
}
/* Header */
.hdr{border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:12px}
.hdr-v{font-family:var(--mono);font-size:13px;letter-spacing:2.5px;padding:8px 16px;background:#0a1a0e;border:2px solid var(--gold);color:var(--gold);display:inline-block;margin-bottom:8px}
.hdr-n{font-family:var(--serif);font-size:24px;font-weight:400;margin:4px 0;color:var(--text)}
.hdr-s{font-family:var(--mono);font-size:9px;color:var(--sub);letter-spacing:1px;line-height:1.7}
.hdr-w{font-family:var(--mono);font-size:9px;color:var(--orange);letter-spacing:1px;line-height:1.7}
/* Tabs */
.tabs{display:flex;flex-wrap:wrap;gap:1px;border-bottom:1px solid var(--border);margin-bottom:14px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.tabs button{
  font-family:var(--mono);font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:var(--sub);
  background:none;border:none;padding:8px 14px;cursor:pointer;white-space:nowrap;
  min-width:44px;min-height:44px;touch-action:manipulation;
  border-bottom:2px solid transparent;transition:color 0.15s
}
.tabs button:hover{color:var(--text)}
.tabs button.active{color:var(--green);border-bottom-color:var(--green)}
.tab{display:none}
.tab.active{display:block}
/* KPI Grid */
.kg{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin-bottom:14px}
.k{background:var(--card);border:1px solid var(--border);padding:10px 12px;border-radius:2px;display:flex;flex-direction:column;gap:3px}
.kl{font-family:var(--mono);font-size:7.5px;color:var(--sub);text-transform:uppercase;letter-spacing:1.5px}
.kv{font-family:var(--mono);font-size:17px;color:var(--text);font-weight:600;font-variant-numeric:tabular-nums;line-height:1.2}
.kc{font-family:var(--mono);font-size:7.5px;color:var(--sub)}
/* Section */
.sec{margin-bottom:14px}
.sec-h{font-family:var(--mono);font-size:9px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;border-bottom:1px solid var(--border);padding-bottom:5px;margin-bottom:10px}
.note{background:var(--card);border:1px solid var(--border);padding:10px 12px;border-radius:2px;font-size:12px;color:var(--sub);line-height:1.6;margin-bottom:12px}
.note strong{color:var(--text)}
/* Scenario Cards */
.sc{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--gold);border-radius:2px;padding:12px 14px;margin-bottom:8px}
.sc-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.sc-name{font-family:var(--mono);font-size:11px;color:var(--gold);letter-spacing:0.5px}
.sc-m{font-family:var(--mono);font-size:18px;font-weight:600;font-variant-numeric:tabular-nums}
.sc-kpis{display:flex;gap:16px;margin-bottom:6px;flex-wrap:wrap}
.sc-kpi{font-family:var(--mono);font-size:9px;color:var(--sub)}
.sc-kpi strong{color:var(--text)}
.sc-d{font-size:12px;color:var(--text);line-height:1.6;margin-bottom:6px}
.sc-t{font-family:var(--mono);font-size:8px;color:var(--muted);letter-spacing:0.5px}
/* Valuation */
.vg{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;margin-bottom:12px}
.vc{background:var(--card);border:1px solid var(--border);padding:12px 14px;border-radius:2px}
.vc-h{font-family:var(--mono);font-size:8px;color:var(--sub);letter-spacing:1.5px;margin-bottom:5px}
.vc-v{font-family:var(--mono);font-size:17px;color:var(--text);font-weight:600;font-variant-numeric:tabular-nums}
.vc-m{font-family:var(--mono);font-size:9px;color:var(--sub);margin:3px 0 6px}
.vc-n{font-size:11px;color:var(--sub);line-height:1.6}
/* Divergence */
.dg{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin-bottom:12px}
.dc{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--blue);padding:10px 12px;border-radius:2px}
.dc-h{font-family:var(--mono);font-size:8px;color:var(--sub);letter-spacing:1.5px;margin-bottom:4px}
.dc-v{font-family:var(--mono);font-size:17px;color:var(--text);font-weight:600;font-variant-numeric:tabular-nums}
.dc-n{font-size:11px;color:var(--sub);margin-top:3px}
/* Moats */
.mr{display:grid;grid-template-columns:140px 90px 40px 1fr;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--border);font-size:12px}
.ml{font-family:var(--mono);font-size:9px;color:var(--text);letter-spacing:0.5px}
.mb{font-family:var(--mono);font-size:13px;letter-spacing:3px;color:var(--gold)}
.mn{font-family:var(--mono);font-size:9px;color:var(--sub)}
.mw{font-size:10px;color:var(--sub);line-height:1.5}
/* Offers */
.oc{background:var(--card);border:1px solid var(--border);border-radius:2px;padding:12px 14px;margin-bottom:8px}
.ot{background:var(--card);border:2px solid var(--gold);border-radius:2px;padding:12px 14px;margin-bottom:8px}
.oo{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px}
.ol{font-family:var(--mono);font-size:10px;color:var(--gold);letter-spacing:1.5px}
.op{font-family:var(--mono);font-size:17px;color:var(--text);font-weight:600}
.om{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:4px}
.om span{font-family:var(--mono);font-size:9px;color:var(--sub)}
.ow{font-size:11px;color:var(--sub);line-height:1.6}
/* Legal Risk */
.lr{background:var(--card);border:1px solid var(--border);padding:12px 14px;border-radius:2px;margin-bottom:8px}
.lr-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.lr-score{font-family:var(--mono);font-size:22px;font-weight:600;color:var(--red)}
.lr-level{font-family:var(--mono);font-size:10px;letter-spacing:1.5px;padding:3px 8px;border:1px solid var(--red);border-radius:2px;color:var(--red)}
.lr-summary{font-size:12px;color:var(--text);line-height:1.6;margin-bottom:8px}
.lr-risks{margin:8px 0}
.lr-risk{font-size:11px;color:var(--sub);padding:3px 0;line-height:1.5}
.lr-risk::before{content:"⚠ ";color:var(--red);font-size:10px}
.lr-due{font-family:var(--mono);font-size:9px;color:var(--muted);margin-top:8px}
.lr-due span{display:inline-block;background:var(--border);padding:2px 6px;margin:2px 3px;border-radius:1px}
/* Levers */
.lv{background:var(--card);border:1px solid var(--border);border-radius:2px;padding:10px 12px;margin-bottom:6px}
.lv-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}
.lv-name{font-family:var(--mono);font-size:10px;color:var(--gold);letter-spacing:0.5px}
.lv-impact{font-family:var(--mono);font-size:9px;color:var(--green)}
.lv-meta{font-family:var(--mono);font-size:8px;color:var(--sub);margin-bottom:4px}
.lv-desc{font-size:11px;color:var(--sub);line-height:1.5}
/* Demographics & Comps */
.dr{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--border)}
.dl{font-family:var(--mono);font-size:9px;color:var(--sub);letter-spacing:0.5px}
.dv{font-size:12px;color:var(--text);text-align:right;max-width:60%;line-height:1.5}
/* Recommendation */
.re{background:var(--card);border:1px solid var(--border);padding:14px 16px;border-radius:2px;margin-bottom:10px}
.re-verdict{font-family:var(--mono);font-size:14px;letter-spacing:3px;padding:10px 20px;background:#0a1a0e;border:2px solid var(--gold);color:var(--gold);display:inline-block;margin-bottom:12px;width:100%;text-align:center}
.re-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin-bottom:10px}
.re-card{background:var(--bg);border:1px solid var(--border);padding:10px 12px;border-radius:2px}
.re-card-h{font-family:var(--mono);font-size:8px;color:var(--sub);letter-spacing:1.5px;margin-bottom:4px}
.re-card-v{font-family:var(--mono);font-size:15px;color:var(--text);font-weight:600}
.re-section{margin:10px 0}
.re-section-h{font-family:var(--mono);font-size:9px;color:var(--gold);letter-spacing:1.5px;margin-bottom:6px}
.re-list{list-style:none;padding:0}
.re-list li{padding:3px 0;font-size:12px;color:var(--text);line-height:1.5}
.re-list li::before{content:"→ ";color:var(--gold);font-family:var(--mono);font-size:10px}
/* Footer */
.ft{text-align:center;padding:20px 0 8px;font-family:var(--mono);font-size:7.5px;color:var(--muted);letter-spacing:1px;border-top:1px solid var(--border);margin-top:16px;line-height:1.8}
/* Mobile */
@media(max-width:768px){
  .vg{grid-template-columns:1fr}
  .mr{grid-template-columns:100px 70px 30px 1fr;gap:6px}
  .dg{grid-template-columns:1fr}
  .re-grid{grid-template-columns:1fr}
  .tabs button{font-size:8px;padding:6px 10px}
}
@media(max-width:430px){
  body{padding:8px 8px 32px;font-size:14px}
  .hdr-v{font-size:11px;padding:6px 12px}
  .hdr-n{font-size:18px}
  .kg{grid-template-columns:1fr 1fr;gap:6px}
  .k{padding:8px 10px}
  .kl{font-size:7px}.kv{font-size:15px}.kc{font-size:7px}
  .mr{grid-template-columns:1fr;gap:3px;padding:6px 0}
  .mb{text-align:center;font-size:12px}
  .ml{font-size:8px}.mw{font-size:10px}
  .lv,.lr,.re,.sc,.oc,.ot{padding:8px 10px}
  .sc-kpis{gap:10px}
  .tabs button{font-size:8px;padding:5px 7px;letter-spacing:1px}
}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:0.01ms!important;transition-duration:0.01ms!important}}
"""

JS = """
function showTab(tid){
  document.querySelectorAll('.tabs button').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('t-'+tid).classList.add('active');
}
"""


# ═══════════════════════════════════════════════════════════
# Section builders
# ═══════════════════════════════════════════════════════════

def build_header(D):
    """Build header section."""
    addr = D.get("address", "Unknown")
    ask = D.get("ask_price", 0)
    pricing = D.get("pricing", {})
    psf = pricing.get("price_psf", D.get("ask_price", 0) / max(pricing.get("sf", 1), 1))
    ptype = D.get("property_type", "")
    city = D.get("city", "")
    state = D.get("state", "")
    lid = D.get("listing_id", "")
    date_ = D.get("analysis_date", str(date.today()))

    # Build flags
    flags = []
    demo = D.get("demographics", {})
    if (demo.get("unemployment_rate_pct") or 99) < 5:
        flags.append("Low unemployment MSA")
    if (demo.get("median_household_income") or 0) > 80000:
        flags.append(f"${demo.get('median_household_income',0):,} MSA median HHI")
    moats = D.get("moats", {})
    if moats.get("classification") == "NO MOAT":
        flags.append("No moat — commodity CRE")

    return f"""<div class="hdr">
  <div class="hdr-v">{sf(moats.get('classification','ANALYZE'))}</div>
  <div class="hdr-n">{addr}</div>
  <div class="hdr-s">{city}, {state} · {ptype} · ASK {fm(ask)} · ${psf:,.0f}/SF · Listing {lid} · Analysis {date_}</div>
  <div class="hdr-w">{' · '.join(flags[:4])}</div>
</div>"""


def build_tabs(D):
    """Build tab navigation."""
    moats = D.get("moats", {})
    moat_total = moats.get("total", "?")
    tabs = [
        ("overview", "Overview"), ("scenarios", "Scenarios"),
        ("valuation", "Valuation"), ("divergence", "Divergence"),
        (f"moats ({moat_total}/24)", "moats"), ("offers", "Offers"),
        ("legal", "Legal Risk"), ("levers", "Levers"),
        ("demographics", "Demographics"), ("comps", "Comps"),
        ("recommendation", "Recommendation"), ("sources", "Data Sources"),
    ]
    btns = "\n".join(
        f'<button class="{"active" if i==0 else ""}" onclick="showTab(\'{tid}\')">{label}</button>'
        for i, (tid, label) in enumerate(tabs)
    )
    return f'<div class="tabs">{btns}</div>'


def _compute_convexity(D):
    """Compute convexity/divergence from v4 scenarios."""
    scenarios = D.get("scenarios", [])
    ask = max(D.get("ask_price", 1), 1)
    pricing = D.get("pricing", {})
    hf_mid = pricing.get("hard_floor_mid", D.get("hard_floor_mid", 0))

    # Find worst/best/base scenarios
    worst = base = best = None
    for s in scenarios:
        name = (s.get("name", "")).lower()
        if not worst and ("worst" in name): worst = s
        if not base and ("baseline" in name or "base" in name or "status quo" in name): base = s
        if best is None:
            best = s
        elif s.get("moic", 0) > best.get("moic", 0):
            if "worst" not in s.get("name", "").lower():
                best = s

    worst_val = worst.get("exit_value", 0) if worst else ask * 0.35
    best_val = best.get("exit_value", 0) if best else ask * 1.5
    base_val = base.get("exit_value", 0) if base else ask

    # Effective worst = max(worst scenario, hard floor mid)
    eff_worst = max(worst_val, hf_mid) if hf_mid else worst_val

    # Convexity ratio = upside / downside
    upside = best_val - ask if best_val > ask else ask * 0.5
    downside = ask - eff_worst if ask > eff_worst else 1
    conv_ratio = upside / max(downside, 1)
    absolute_spread = best_val - eff_worst

    # Risk/reward
    risk_reward = conv_ratio

    # Capital normalized spread
    cap_norm_spread = absolute_spread / ask if ask > 0 else 0

    # PWEV (probability-weighted expected value)
    pw_sum_value = sum(s.get("exit_value", 0) * s.get("probability", 0) for s in scenarios)
    pw_sum_prob = sum(s.get("probability", 0) for s in scenarios)
    pwev = pw_sum_value / max(pw_sum_prob, 0.01)
    pwev_vs_ask = (pwev / ask - 1) * 100 if ask > 0 else 0

    # Frontier zone
    if conv_ratio >= 2.0 and downside < ask * 0.5:
        zone = "Pursue aggressively"
    elif downside < ask * 0.6:
        zone = "Acceptable selectively"
    elif downside < ask * 0.8:
        zone = "Pass unless portfolio reason"
    else:
        zone = "Walk away"

    best_moic = best.get("moic", 0) if best else 0
    worst_moic = worst.get("moic", 0) if worst else 0

    return {
        "convexity_ratio": conv_ratio,
        "risk_reward_ratio": risk_reward,
        "effective_worst": eff_worst,
        "absolute_spread": absolute_spread,
        "capital_normalized_spread": cap_norm_spread,
        "frontier_zone": zone,
        "pwev": pwev,
        "pwev_vs_ask_pct": pwev_vs_ask,
        "best_moic": best_moic,
        "worst_moic": worst_moic,
        "worst_val": worst_val,
        "best_val": best_val,
        "base_val": base_val,
    }


def build_overview(D):
    """Build overview tab."""
    conv = _compute_convexity(D)
    pricing = D.get("pricing", {})
    ask = D.get("ask_price", 0)
    hf_mid = pricing.get("hard_floor_mid", D.get("hard_floor_mid", 0))
    moats = D.get("moats", {})
    rec = D.get("recommendation", {})
    lr = D.get("legal_risk", {})

    pwev = conv["pwev"]
    pwev_pct = conv["pwev_vs_ask_pct"]

    return f"""<div class="kg">
  <div class="k"><span class="kl">ASK PRICE</span><span class="kv">{fm(ask)}</span><span class="kc">${pricing.get('price_psf',0):.0f}/SF</span></div>
  <div class="k"><span class="kl">HARD FLOOR</span><span class="kv">{fm(hf_mid)}</span><span class="kc">{pricing.get('floor_to_ask_pct',0)}% of ask</span></div>
  <div class="k"><span class="kl">PWEV</span><span class="kv" style="color:{'var(--green)' if pwev>ask else 'var(--red)'}">{fm(pwev)}</span><span class="kc">{pct(pwev_pct,'+') if pwev_pct>0 else pct(pwev_pct)} vs ask</span></div>
  <div class="k"><span class="kl">CONVEXITY</span><span class="kv" style="color:{'var(--green)' if conv['convexity_ratio']>=2 else 'var(--gold)'}">{conv['convexity_ratio']:.1f}×</span><span class="kc">{conv['frontier_zone']}</span></div>
  <div class="k"><span class="kl">BEST MOIC</span><span class="kv" style="color:var(--green)">{conv['best_moic']:.2f}×</span><span class="kc">Phase 3</span></div>
  <div class="k"><span class="kl">WORST MOIC</span><span class="kv" style="color:var(--red)">{conv['worst_moic']:.2f}×</span><span class="kc">Distress scenario</span></div>
  <div class="k"><span class="kl">MOAT RATING</span><span class="kv">{moats.get('total','?')}/24</span><span class="kc">{moats.get('classification','?')}</span></div>
  <div class="k"><span class="kl">LEGAL RISK</span><span class="kv" style="color:{'var(--red)' if safe_dict(lr,'risk_score',5)>6 else 'var(--gold)'}">{safe_dict(lr,'risk_score','?')}/10</span><span class="kc">{safe_dict(lr,'risk_level','?')}</span></div>
</div>
<div class="note"><strong>Recommendation:</strong> {rec.get('verdict','ANALYZE')} · Target {fm(rec.get('target_offer'))} · Walk {fm(rec.get('walk_away'))} · {rec.get('confidence','Medium')} Confidence</div>"""


def build_scenarios(D):
    """Build scenarios tab."""
    scenarios = D.get("scenarios", [])
    narratives = {n["name"]: n for n in D.get("scenario_narratives", [])}
    ask = max(D.get("ask_price", 1), 1)

    colors = {0: "var(--red)", 1: "var(--sub)", 2: "var(--blue)", 3: "var(--green)", 4: "var(--green)"}
    cards = ""
    for i, s in enumerate(scenarios):
        moic = s.get("moic", 0)
        ci = min(int(moic * 2), 4) if moic < 1.5 else 3
        narr = narratives.get(s["name"], {})
        ev = s.get("exit_value", 0)
        noi = s.get("noi", 0)
        prob = s.get("probability", 0)
        cap_rate = s.get('exit_cap', 0.08) * 100 if s.get('exit_cap', 1) < 1 else s.get('exit_cap', 8.0)
        cards += f"""<div class="sc">
  <div class="sc-top"><div class="sc-name">{sf(s.get('name','Scenario').upper())}</div><div class="sc-m" style="color:{colors.get(ci,'var(--sub)')}">{moic:.2f}×</div></div>
  <div class="sc-kpis"><span class="sc-kpi">Exit: <strong>{fm(ev)}</strong></span><span class="sc-kpi">NOI: <strong>{fm(noi)}</strong></span><span class="sc-kpi">Cap: <strong>{pct(cap_rate,1)}</strong></span><span class="sc-kpi">Prob: <strong>{pct(prob*100,0)}</strong></span></div>
  <div class="sc-d">{sf(s.get('description','')[:300])}</div>
  <div class="sc-t">{' · '.join(s.get('triggers',s.get('drivers',[]))[:5])}</div>
</div>"""
    return f'<div class="sec"><div class="sec-h">5-Scenario Analysis</div>{cards}</div>'


def build_valuation(D):
    """Build valuation tab."""
    pricing = D.get("pricing", {})
    ask = D.get("ask_price", 0)
    conv = _compute_convexity(D)
    return f"""<div class="kg">
  <div class="k"><span class="kl">ASK PRICE</span><span class="kv">{fm(ask)}</span><span class="kc">${pricing.get('price_psf',0):.0f}/SF</span></div>
  <div class="k"><span class="kl">HARD FLOOR</span><span class="kv">{fm(pricing.get('hard_floor_mid',0))}</span><span class="kc">{pricing.get('floor_to_ask_pct',0)}% of ask</span></div>
  <div class="k"><span class="kl">STABILIZED RE</span><span class="kv">{fm(pricing.get('stabilized_re_value',0))}</span><span class="kc">Income approach</span></div>
  <div class="k"><span class="kl">PWEV</span><span class="kv">{fm(conv['pwev'])}</span><span class="kc">{pct(conv['pwev_vs_ask_pct'],'')} vs ask</span></div>
</div>
<div class="vg">
  <div class="vc"><div class="vc-h">ASSET-BASED (HARD FLOOR)</div><div class="vc-v">{fm(pricing.get('hard_floor_low',0))} – {fm(pricing.get('hard_floor_high',0))}</div><div class="vc-m">Mid: {fm(pricing.get('hard_floor_mid',0))} · {pricing.get('floor_to_ask_pct',0)}% of ask</div><div class="vc-n">Distressed market value. Land + replacement cost.</div></div>
  <div class="vc"><div class="vc-h">INCOME APPROACH</div><div class="vc-v">{fm(pricing.get('stabilized_re_value',0))}</div><div class="vc-m">Cap rate applied to stabilized NOI</div><div class="vc-n">If rented at market $/SF NNN</div></div>
  <div class="vc"><div class="vc-h">PWEV (PROBABILISTIC)</div><div class="vc-v" style="color:{'var(--green)' if conv['pwev']>ask else 'var(--red)'}">{fm(conv['pwev'])}</div><div class="vc-m">{pct(conv['pwev_vs_ask_pct'],'+' if conv['pwev_vs_ask_pct']>0 else '')} vs ask</div><div class="vc-n">Probability-weighted across 5 scenarios</div></div>
  <div class="vc"><div class="vc-h">RECOMMENDED TARGET</div><div class="vc-v">{fm(D.get('recommendation',{}).get('target_offer','?'))}</div><div class="vc-m">{pct(D.get('recommendation',{}).get('target_offer',0)/max(ask,1)*100-100,'-')} below ask</div><div class="vc-n">LLM-synthesized from all analyses</div></div>
</div>"""


def build_divergence(D):
    """Build divergence/convexity tab."""
    conv = _compute_convexity(D)
    items = [
        ("CONVEXITY RATIO", f"{conv['convexity_ratio']:.1f}×", f"${conv['convexity_ratio']:.1f} upside per $1 downside"),
        ("RISK / REWARD", f"{conv['risk_reward_ratio']:.1f}×", "Upside-heavy asymmetry"),
        ("EFFECTIVE WORST", fm(conv['effective_worst']), "Hard floor caps downside"),
        ("ABSOLUTE SPREAD", fm(conv['absolute_spread']), "Best − worst gap"),
        ("FRONTIER ZONE", conv.get('frontier_zone', '—'), "Engine classification"),
        ("CAP NORM SPREAD", f"{conv['capital_normalized_spread']:.1f}×", "Spread ÷ capital"),
        ("BEST SCENARIO", fm(conv['best_val']), f"{conv['best_moic']:.2f}× MOIC — Phase 3 moonshot"),
        ("WORST SCENARIO", fm(conv['worst_val']), f"{conv['worst_moic']:.2f}× MOIC — distress"),
    ]
    rows = "\n".join(
        f'<div class="dc"><div class="dc-h">{h}</div><div class="dc-v">{v}</div><div class="dc-n">{n}</div></div>'
        for h, v, n in items
    )

    # Add real v3⨂LLM divergence flags if present
    flag_html = ""
    flags = D.get("divergences", [])
    if flags:
        flag_rows = "\n".join(
            f'<div class="mr"><div class="ml">v3⨂LLM</div><div class="mb" style="font-size:10px;color:var(--gold)">⚠</div><div class="mn" style="font-size:10px">Δ</div><div class="mw">{f[:200]}</div></div>'
            for f in flags[:10]
        )
        flag_html = f'<div class="sec" style="margin-top:14px"><div class="sec-h">v3 ⨂ LLM DISAGREEMENTS ({len(flags)})</div>{flag_rows}</div>'

    return f'<div class="dg">{rows}</div>{flag_html}'


def build_moats(D):
    """Build moats tab."""
    moats = D.get("moats", {})
    scores = moats.get("scores", {})
    labels = {
        "license_barrier": "LICENSE BARRIER", "tourism_corridor": "TOURISM CORRIDOR",
        "multi_revenue": "MULTI-REVENUE", "zoning_optionality": "ZONING OPTIONALITY",
        "rent_gap": "RENT GAP", "brand_value": "BRAND VALUE",
        "asset_stack": "ASSET STACK", "seller_asymmetry": "SELLER ASYM",
    }
    rows = ""
    for key, label in labels.items():
        s = scores.get(key, {})
        score = s.get("score", 0)
        bar = "█" * score + "░" * (3 - score)
        rows += f'<div class="mr"><div class="ml">{label}</div><div class="mb">{bar}</div><div class="mn">{score}/3</div><div class="mw">{sf(s.get("rationale","")[:120])}</div></div>'

    return f"""<div class="kg">
  <div class="k"><span class="kl">TOTAL SCORE</span><span class="kv">{moats.get('total','?')}/24</span><span class="kc">{moats.get('classification','?')}</span></div>
  <div class="k"><span class="kl">VERDICT</span><span class="kv" style="font-size:11px">{sf(moats.get('verdict','')[:50])}</span><span class="kc">8-dimension analysis</span></div>
</div>
{rows}"""


def build_offers(D):
    """Build offers tab."""
    offers = D.get("offers", [])
    if not offers:
        return '<div class="note">Offer ladder from LLM recommendation</div>'
    rows = ""
    for o in offers:
        is_tgt = "target" in o.get("label", "").lower()
        cls = ' class="ot"' if is_tgt else ' class="oc"'
        rows += f"""<div{cls}>
  <div class="oo"><span class="ol">{sf(o.get('label',''))}</span><span class="op">{fm(o.get('price',0))}</span></div>
  <div class="om"><span>${o.get('price_per_sf',0):.0f}/SF</span><span>Cap {pct(o.get('cap_rate_pct',0),0)}%</span><span>CoC {pct(o.get('cash_on_cash_pct',0),0)}%</span><span>GRM {o.get('gross_rent_multiplier',0):.1f}×</span></div>
  <div class="ow">{sf(o.get('label',''))}</div>
</div>"""
    return rows


def build_legal(D):
    """Build legal risk tab."""
    lr = D.get("legal_risk", {})
    score = safe_dict(lr, "risk_score", 5)
    level = safe_dict(lr, "risk_level", "MODERATE")
    level_color = "var(--red)" if level == "HIGH" else "var(--gold)" if level == "MODERATE" else "var(--green)"

    risks = lr.get("top_3_risks", []) if isinstance(lr, dict) else []
    liability = lr.get("environmental_liability_estimate", 0) if isinstance(lr, dict) else 0
    due = lr.get("legal_due_diligence_required", []) if isinstance(lr, dict) else []

    risks_html = "\n".join(f'<div class="lr-risk">{r[:200]}</div>' for r in risks[:5])
    due_html = "\n".join(f'<span>{d[:80]}</span>' for d in due[:6]) if due else ""

    return f"""<div class="lr">
  <div class="lr-h"><span class="lr-score">{score:.1f}</span><span class="lr-level" style="border-color:{level_color};color:{level_color}">{level}</span></div>
  <div class="lr-summary">{sf(lr.get('summary','')[:300])}</div>
  <div class="sec-h" style="margin-top:10px">TOP RISKS</div>
  <div class="lr-risks">{risks_html}</div>
  <div class="sec-h" style="margin-top:10px">ENVIRONMENTAL LIABILITY</div>
  <div style="font-family:var(--mono);font-size:15px;color:var(--red);margin-bottom:4px">{fm(liability)}</div>
  <div class="lr-due">{due_html}</div>
</div>"""


def build_levers(D):
    """Build business levers tab."""
    levers = D.get("levers", [])
    if not levers:
        return '<div class="note">No business levers identified</div>'
    rows = ""
    for lv in levers[:6]:
        rows += f"""<div class="lv">
  <div class="lv-top"><span class="lv-name">{sf(lv.get('name',''))}</span><span class="lv-impact">+{pct(lv.get('noi_impact_pct',0))} NOI</span></div>
  <div class="lv-meta">{sf(lv.get('category',''))} · {sf(lv.get('effort',''))} effort · {sf(lv.get('timeline_months',''))}mo timeline</div>
  <div class="lv-desc">{sf(lv.get('description','')[:150])}</div>
</div>"""
    return f'<div class="sec"><div class="sec-h">Business Levers (NOI Impact)</div>{rows}</div>'


def build_demographics(D):
    """Build demographics tab."""
    demo = D.get("demographics", {})
    hpa = D.get("home_price_appreciation", {})
    rows = ""
    items = [
        ("MSA NAME", sf(hpa.get("msa_name", ""))),
        ("HPI 1YR", pct(hpa.get("hpi_1yr_pct"), 1)),
        ("HPI 5YR ANNUALIZED", pct(hpa.get("hpi_5yr_annualized_pct"), 1)),
        ("MEDIAN HHI", fm(demo.get("median_household_income", 0)) if isinstance(demo, dict) else sf(demo)),
        ("UNEMPLOYMENT", pct(demo.get("unemployment_rate_pct", 0)) if isinstance(demo, dict) else sf(demo)),
        ("POPULATION", _num(demo.get("population", 0)) if isinstance(demo, dict) else sf(demo)),
        ("DATA SOURCE", sf(demo.get("source", hpa.get("source", "")))),
    ]
    for l, v in items:
        if v and v != "—":
            rows += f'<div class="dr"><span class="dl">{l}</span><span class="dv">{v}</span></div>'
    fallback_note = '<div class="note">Live FRED data</div>'
    return f'<div class="sec"><div class="sec-h">MSA Economic Profile</div>{rows if rows else fallback_note}</div>'


def build_comps(D):
    """Build comparables tab."""
    comps = D.get("comps", [])
    if not comps:
        return '<div class="note">No comps from web search — run v4 pipeline with BRAVE_API_KEY</div>'

    header = '<thead><tr><th>ADDRESS</th><th>PRICE</th><th>SF</th><th>$/SF</th><th>SOURCE</th></tr></thead>'
    rows = ""
    for c in comps[:8]:
        price = c.get("price", 0) if isinstance(c, dict) else 0
        sf_ = c.get("sf", 0) if isinstance(c, dict) else 0
        rows += f'<tr><td>{sf(c.get("address","") if isinstance(c,dict) else str(c))[:40]}</td><td class="tn">{fm(price)}</td><td class="tn">{sf_}</td><td class="tn">${c.get("psf",0) if isinstance(c,dict) else "?"}</td><td class="cn">{sf(c.get("source","") if isinstance(c,dict) else "Brave")[:30]}</td></tr>'

    return f"""<div class="kg">
  <div class="k"><span class="kl">WEB COMPS</span><span class="kv">{len(comps)}</span><span class="kc">Brave Search</span></div>
  <div class="k"><span class="kl">ASK $/SF</span><span class="kv">${fm(D.get('pricing',{}).get('price_psf',0))}</span><span class="kc">Subject</span></div>
</div>
<table class="ct" style="width:100%;border-collapse:collapse;font-size:11px">
{header}<tbody>{rows}</tbody></table>"""


def build_recommendation(D):
    """Build recommendation tab."""
    rec = D.get("recommendation", {})
    verdict = rec.get("verdict", "ANALYZE")
    target = rec.get("target_offer", D.get("ask_price", 0))
    walk = rec.get("walk_away", D.get("ask_price", 0) * 1.05)
    conditions = rec.get("key_conditions", [])
    strategy = rec.get("negotiation_strategy", "")
    risk = rec.get("single_biggest_risk", "")
    confidence = rec.get("confidence", "Medium")

    cond_html = "\n".join(f'<li>{c[:200]}</li>' for c in conditions[:5]) if conditions else ""

    # Data sources audit
    sources = D.get("data_sources", {})
    src_rows = "\n".join(f'<div class="dr"><span class="dl">{k.upper()}</span><span class="dv">{v[:120]}</span></div>' for k, v in sources.items())

    return f"""<div class="re">
  <div class="re-verdict">{verdict}</div>
  <div class="re-grid">
    <div class="re-card"><div class="re-card-h">TARGET OFFER</div><div class="re-card-v">{fm(target)}</div></div>
    <div class="re-card"><div class="re-card-h">WALK AWAY</div><div class="re-card-v">{fm(walk)}</div></div>
    <div class="re-card"><div class="re-card-h">ASK PRICE</div><div class="re-card-v">{fm(D.get('ask_price',0))}</div></div>
    <div class="re-card"><div class="re-card-h">CONFIDENCE</div><div class="re-card-v">{confidence}</div></div>
  </div>
  <div class="re-section-h">KEY CONDITIONS</div>
  <ul class="re-list">{cond_html}</ul>
  <div class="re-section-h">NEGOTIATION STRATEGY</div>
  <div class="note">{sf(strategy[:300])}</div>
  <div class="re-section-h">BIGGEST RISK</div>
  <div class="note" style="border-left:3px solid var(--red)"><strong>{sf(risk[:200])}</strong></div>
  <div class="re-section-h">DATA SOURCES (AUDIT TRAIL)</div>
  {src_rows}
</div>"""


def build_sources(D):
    """Build data sources / methodology tab."""
    sources = D.get("data_sources", {})
    rows = "\n".join(f'<div class="dr"><span class="dl">{k.upper()}</span><span class="dv">{sf(v)[:150]}</span></div>' for k, v in sources.items())

    live = D.get("live_context", {})
    return f"""<div class="sec">
<div class="sec-h">Live Data Pipeline (v4)</div>
<div class="note"><strong>Triple-LLM Architecture:</strong> DeepSeek V4 Pro (primary) → OpenRouter Nemotron 3 Super (independent) → Mistral Small (independent) → DeepSeek synthesis</div>
{rows}
</div>
<div class="sec">
<div class="sec-h">Live Context Summary</div>
<div class="note">
  <strong>FRED Economics:</strong> {sf(live.get('msa_name',''))} · ${sf(live.get('county_median_income','?'))} HHI · {sf(live.get('county_unemployment_pct','?'))}% UE<br>
  <strong>Web Search:</strong> {sf(live.get('web_search_comps_count','?'))} comps · {sf(live.get('corridor_news_count','?'))} corridor · {sf(live.get('environmental_flags','?'))} environmental · {sf(live.get('zoning_changes_count','?'))} zoning<br>
  <strong>Warnings:</strong> {sf(', '.join(D.get('warnings',[]) or ['None']))}<br>
  <strong>Timestamp:</strong> {sf(live.get('analysis_timestamp',''))}
</div>
</div>"""


def _num(val, fmt="{:,}", fallback="—"):
    """Format a number."""
    if val is None: return fallback
    try: return fmt.format(int(val))
    except: return fallback


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def build_dashboard(D: dict, title: str = None) -> str:
    """Build complete dashboard HTML from v4 pipeline output."""

    sections = [
        ("overview", build_overview(D)),
        ("scenarios", build_scenarios(D)),
        ("valuation", build_valuation(D)),
        ("divergence", build_divergence(D)),
        ("moats", build_moats(D)),
        ("offers", build_offers(D)),
        ("legal", build_legal(D)),
        ("levers", build_levers(D)),
        ("demographics", build_demographics(D)),
        ("comps", build_comps(D)),
        ("recommendation", build_recommendation(D)),
        ("sources", build_sources(D)),
    ]

    tab_content = "\n".join(
        f'<div class="tab{" active" if i==0 else ""}" id="t-{tid}">{content}</div>'
        for i, (tid, content) in enumerate(sections)
    )

    header = build_header(D)
    tabs = build_tabs(D)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{title or D.get('address','CRE Underwriting')}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;0,600&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,500;0,8..60,600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>

{header}
{tabs}

{tab_content}

<div class="ft">
  CRE Underwriting v4 · Triple-LLM Analysis · FRED Live Data · Brave Web Search<br>
  DeepSeek V4 Pro + OpenRouter Nemotron 3 Super + Mistral Small → DeepSeek Synthesis<br>
  Sources: FRED API · Brave Search API · SEC EDGAR · Census ACS · Not financial advice · {D.get('analysis_date', str(date.today()))}
</div>

<script>{JS}</script>
</body>
</html>"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build v4 CRE dashboard")
    parser.add_argument("input", help="Path to v4 pipeline JSON output")
    parser.add_argument("--output", "-o", default=None, help="Output HTML path")
    parser.add_argument("--deploy", choices=["vercel"], help="Deploy to platform")
    args = parser.parse_args()

    with open(args.input) as f:
        D = json.load(f)

    html = build_dashboard(D)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html)
        print(f"Dashboard written: {out_path} ({len(html):,} chars)")
    else:
        # Default: name based on input
        base = Path(args.input).stem
        out_path = Path(f"/tmp/{base}_dashboard.html")
        out_path.write_text(html)
        print(f"Dashboard written: {out_path} ({len(html):,} chars)")

    if args.deploy == "vercel":
        import subprocess
        # Deploy via vercel CLI
        result = subprocess.run(
            ["npx", "vercel", "--prod", "--yes", str(out_path)],
            capture_output=True, text=True, cwd=out_path.parent,
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)


if __name__ == "__main__":
    main()
