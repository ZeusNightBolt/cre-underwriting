"""
Rebuild 6 Boonton Ave dashboard v3 — Hoboken/Irvington design language.
DM Mono typography throughout, sharp 2px borders, compact grid, mobile-safe.
"""
import json

with open("/tmp/boonton_analysis.json") as f:
    D = json.load(f)

def fm(v):
    if v is None: return "—"
    if isinstance(v, float):
        if abs(v) >= 1_000_000: return f"${v/1e6:,.2f}M"
        if abs(v) >= 1000: return f"${v:,.0f}"
        return f"${v:,.2f}"
    if v >= 1_000_000: return f"${v/1e6:,.2f}M"
    return f"${v:,.0f}"

def pct(v, d=1):
    if v is None: return "—"
    return f"{v:.{d}f}%"

# ═══════════════════════ SCENARIOS ═══════════════════════
sc_cards = ""
sc_colors = {0: "#ba6a5a", 1: "#6a7a8a", 2: "#b8c8d8", 3: "#6aba8a", 4: "#6aba8a"}
for s in D["scenarios"]:
    moic = s.get("moic", 0)
    ci = min(int(moic), 4) if moic < 2 else 3
    narr = next((n for n in D.get("scenario_narratives", []) if n["name"] == s["name"]), {})
    sc_cards += '<div class="sc"><div class="sc-top"><div class="sc-name">%s</div><div class="sc-m" style="color:%s">%.2f×</div></div><div class="sc-d">%s</div><div class="sc-t">%s</div></div>' % (
        s['name'], sc_colors.get(ci, '#6a7a8a'), moic,
        narr.get('detail', ''), ' · '.join(narr.get('drivers', [])))

# ═══════════════════════ VALUATION ═══════════════════════
val_items = [
    ("ASSET-BASED (HARD FLOOR)", fm(D['pricing']['hard_floor_low']) + ' – ' + fm(D['pricing']['hard_floor_high']),
     "Mid: " + fm(D['pricing']['hard_floor_mid']) + " · " + str(D['pricing']['floor_to_ask_pct']) + "% of ask",
     "Distressed market value of fee-simple condo unit"),
    ("INCOME (RE ONLY)", fm(D['pricing']['stabilized_re_value']),
     "@ 7.0% cap on $19K implied RE NOI",
     "Value if rented at market $14/SF NNN"),
    ("PWEV (PROBABILISTIC)", fm(D['convexity']['pwev']),
     pct(D['convexity']['pwev_vs_ask_pct']) + " above ask",
     "Weighted across all 5 scenarios"),
    ("GOING-CONCERN (OWNER-OP)", fm(D['pricing']['ask']) + " – " + fm(420000),
     "RE value + business EBITDA × multiple",
     "Range: breakeven coffee shop to multi-revenue café"),
]
val_cards = '<div class="vg">'
for h, v, m, n in val_items:
    val_cards += '<div class="vc"><div class="vc-h">' + h + '</div><div class="vc-v">' + v + '</div><div class="vc-m">' + m + '</div><div class="vc-n">' + n + '</div></div>'
val_cards += '</div>'

# ═══════════════════════ DIVERGENCE ═══════════════════════
div = D["convexity"]
div_items = [
    ("CONVEXITY RATIO", f"{div['convexity_ratio']:.1f}×", "$2.50 upside per $1 downside"),
    ("RISK / REWARD", f"{div['risk_reward_ratio']:.1f}×", "Upside-heavy asymmetry"),
    ("EFFECTIVE WORST", fm(div['effective_worst']), "Hard floor caps downside"),
    ("ABSOLUTE SPREAD", fm(div['absolute_spread']), "Best − worst gap"),
    ("FRONTIER ZONE", div['frontier_zone'] or '—', "Engine classification"),
    ("CAP NORM SPREAD", f"{div['capital_normalized_spread']:.1f}×", "Spread ÷ capital"),
]
div_html = '<div class="kg">'
for l, v, c in div_items:
    div_html += '<div class="k"><span class="kl">' + l + '</span><span class="kv">' + v + '</span><span class="kc">' + c + '</span></div>'
div_html += '</div>'
div_html += f'<div class="note"><strong>Convexity 2.5 → strong asymmetry.</strong> $2.50 upside per $1 downside. Hard floor at {fm(D["pricing"]["hard_floor_mid"])} (58% of ask) caps the downside. Engine PWEV conservative (+3.4%) — does not model business creation value.</div>'

# ═══════════════════════ MOATS ═══════════════════════
ml = {"license_barrier":"LICENSE BARRIER","tourism_corridor":"TOURISM CORRIDOR","multi_revenue":"MULTI-REVENUE","zoning_optionality":"ZONING OPTIONALITY","rent_gap":"RENT GAP","brand_value":"BRAND VALUE","asset_stack":"ASSET STACK","seller_asymmetry":"SELLER ASYMMETRY"}
moat_rows = ""
for k, m in D["moats"]["scores"].items():
    bar = "".join("█" if i < m['score'] else "░" for i in range(3))
    moat_rows += f'<div class="mr"><div class="ml">{ml.get(k,k.upper())}</div><div class="mb">{bar}</div><div class="mn">{m["score"]}/3</div><div class="mw">{m["rationale"]}</div></div>'

# ═══════════════════════ OFFERS ═══════════════════════
offer_rows = ""
for o in D["offers"]:
    is_tgt = "TARGET" in o["label"].upper()
    cls = ' class="ot"' if is_tgt else ''
    offer_rows += f'<div{cls}><div class="oo"><span class="ol">{o["label"]}</span><span class="op">{fm(o["price"])}</span></div><div class="om"><span>Cap {o["cap_rate_implied"]}%</span><span>CoC {o["coc"]}%</span><span>MOIC {o["moic"]}x</span></div><div class="ow">{o["rationale"]}</div></div>'

# ═══════════════════════ RISKS ═══════════════════════
rc = {"HIGH": "#ba6a5a", "MEDIUM": "#d4a843", "LOW": "#6aba8a"}
risk_rows = ""
for c in D["concealment"]:
    risk_rows += f'<div class="rk"><div class="rh"><span class="rf">{c["flag"]}</span><span class="rl" style="color:{rc.get(c["risk"],"#6a7a8a")}">{c["risk"]}</span></div><div class="rd">{c["detail"]}</div><div class="rm">→ {c["mitigant"]}</div></div>'

# ═══════════════════════ DEMOGRAPHICS ═══════════════════════
demo_rows = ""
for k, v in D["demographics"].items():
    demo_rows += f'<div class="dr"><span class="dl">{k.replace("_"," ").upper()}</span><span class="dv">{v}</span></div>'

# ═══════════════════════ ENVIRONMENTAL ═══════════════════════
env_rows = ""
for k, v in D["environmental"].items():
    env_rows += f'<div class="dr"><span class="dl">{k.replace("_"," ").upper()}</span><span class="dv">{v}</span></div>'

# ═══════════════════════ COMPS ═══════════════════════
comp_rows = ""
for c in D["comps"]:
    comp_rows += f'<tr><td>{c["address"]}</td><td class="tn">{c["sf"]:,}</td><td class="tn">{fm(c["price"])}</td><td class="tn">${c["price_psf"]}</td><td class="cn">{c["notes"]}</td></tr>'

# ═══════════════════════ RECOMMENDATION ═══════════════════════
rec = D["verdict"]
tax = D["tax"]
biz_cards = ""
for b in D["business_ideas"]:
    biz_cards += f'<div class="bz"><div class="bn">{b["concept"]}</div><div class="bm"><span>Capex {fm(b["startup_capex"])}</span><span>Rev {fm(b["revenue_est"])}</span><span>EBITDA {fm(b["ebitda_est"])}</span><span>{b["margin"]}% margin</span></div><div class="bw">{b["rationale"]}</div></div>'

rec_html = f"""
<div class="rv">{rec['verdict']}</div>
<div class="rs"><div class="rhs">KEY CONDITIONS</div><ul class="rul">{''.join(f'<li>{c}</li>' for c in rec['key_conditions'])}</ul></div>
<div class="rs"><div class="rhs">WHAT WOULD MAKE IT PURSUE AT ASK</div><ul class="rul">{''.join(f'<li>{c}</li>' for c in rec['what_would_make_it_pursue_at_ask'])}</ul></div>
<div class="rs"><div class="rhs">WHAT WOULD MAKE IT PASS</div><ul class="rul rr">{''.join(f'<li>{c}</li>' for c in rec['what_would_make_it_pass'])}</ul></div>
<div class="rs"><div class="rhs">CONVEXITY SUMMARY</div><p class="rp">{rec['convexity_summary']}</p></div>
<div class="rs"><div class="rhs">BUSINESS IDEA ANALYSIS</div><div class="bg">{biz_cards}</div></div>
"""

# ═══════════════════════ FULL HTML ═══════════════════════
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>6 Boonton Ave — CRE Underwriting</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scrollbar-gutter:stable;background:#0a0c0e}}
body{{
  font-family:'Source Serif 4','Cormorant Garamond','Crimson Pro',Georgia,serif;
  background:#0a0c0e;color:#b8c8d8;
  min-height:100dvh;overscroll-behavior:contain;
  -webkit-font-smoothing:antialiased;
  max-width:1200px;margin:0 auto;padding:12px 16px 40px;
  font-size:16px;line-height:1.5
}}

/* ── Header ── */
.hdr{{border-bottom:1px solid #1a1e24;padding-bottom:10px;margin-bottom:10px}}
.hdr-v{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:14px;letter-spacing:3px;padding:10px 20px;background:#0a1a0e;border:2px solid #d4a843;color:#d4a843;display:inline-block;margin-bottom:6px}}
.hdr-n{{font-family:'Source Serif 4','Cormorant Garamond','Crimson Pro',Georgia,serif;font-size:22px;font-weight:400;margin:4px 0}}
.hdr-s{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a;letter-spacing:1px;line-height:1.6}}
.hdr-w{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#d4a843;letter-spacing:1px;line-height:1.6}}

/* ── Tabs ── */
.tabs{{display:flex;flex-wrap:wrap;gap:1px;border-bottom:1px solid #1a1e24;margin-bottom:12px}}
.tabs button{{
  font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;
  font-size:16px;letter-spacing:1.5px;text-transform:uppercase;color:#6a7a8a;
  background:none;border:none;padding:7px 10px;cursor:pointer;white-space:nowrap;
  min-width:44px;min-height:44px;touch-action:manipulation;
  -webkit-tap-highlight-color:transparent;
  border-bottom:2px solid transparent
}}
.tabs button:hover{{color:#b8c8d8}}
.tabs button.active{{color:#6aba8a;border-bottom-color:#6aba8a}}
.tab{{display:none}}
.tab.active{{display:block}}

/* ── KPI Grid ── */
.kg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-bottom:12px}}
.k{{background:#101214;border:1px solid #1a1e24;padding:10px 12px;border-radius:2px;display:flex;flex-direction:column;gap:3px}}
.kl{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:8px;color:#6a7a8a;text-transform:uppercase;letter-spacing:1.5px}}
.kv{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:17px;color:#b8c8d8;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.2}}
.kc{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:8px;color:#6a7a8a}}

/* ── Section ── */
.note{{background:#101214;border:1px solid #1a1e24;padding:10px 12px;border-radius:2px;font-size:12px;color:#6a7a8a;line-height:1.6;margin-bottom:12px}}
.note strong{{color:#b8c8d8}}

/* ── Scenario Cards ── */
.sc{{background:#101214;border:1px solid #1a1e24;border-radius:2px;padding:10px 12px;margin-bottom:8px}}
.sc-top{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}}
.sc-name{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:11px;color:#d4a843;letter-spacing:1px}}
.sc-m{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:17px;font-weight:600;font-variant-numeric:tabular-nums}}
.sc-d{{font-size:12px;color:#b8c8d8;line-height:1.6;margin-bottom:4px}}
.sc-t{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a;letter-spacing:0.5px}}

/* ── Valuation ── */
.vg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:8px}}
.vc{{background:#101214;border:1px solid #1a1e24;padding:10px 12px;border-radius:2px}}
.vc-h{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:8px;color:#6a7a8a;letter-spacing:1.5px;margin-bottom:4px}}
.vc-v{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:17px;color:#b8c8d8;font-weight:600;font-variant-numeric:tabular-nums}}
.vc-m{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a;margin:3px 0 6px;font-variant-numeric:tabular-nums}}
.vc-n{{font-size:11px;color:#6a7a8a;line-height:1.6}}

/* ── Moat Rows ── */
.mr{{display:grid;grid-template-columns:140px 100px 40px 1fr;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid #1a1e24;font-size:12px}}
.ml{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#b8c8d8;letter-spacing:1px}}
.mb{{font-family:monospace;font-size:13px;letter-spacing:3px;color:#d4a843}}
.mn{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a;font-variant-numeric:tabular-nums}}
.mw{{font-size:11px;color:#6a7a8a;line-height:1.5}}

/* ── Offers ── */
.oc{{background:#101214;border:1px solid #1a1e24;border-radius:2px;padding:10px 12px;margin-bottom:8px}}
.ot{{background:#101214;border:2px solid #d4a843;border-radius:2px;padding:10px 12px;margin-bottom:8px}}
.oo{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}}
.ol{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:10px;color:#d4a843;letter-spacing:1.5px}}
.op{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:17px;color:#b8c8d8;font-weight:600;font-variant-numeric:tabular-nums}}
.om{{display:flex;gap:12px;margin-bottom:4px}}
.om span{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a}}
.ow{{font-size:11px;color:#6a7a8a;line-height:1.6}}

/* ── Risks ── */
.rk{{background:#101214;border:1px solid #1a1e24;border-radius:2px;padding:10px 12px;margin-bottom:8px}}
.rh{{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}}
.rf{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:12px;letter-spacing:0.5px;color:#b8c8d8}}
.rl{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;letter-spacing:1.5px;font-weight:600}}
.rd{{font-size:12px;color:#b8c8d8;line-height:1.6;margin-bottom:4px}}
.rm{{font-size:11px;color:#6aba8a;line-height:1.5}}

/* ── Demo / Env rows ── */
.dr{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1a1e24}}
.dl{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a;letter-spacing:1px}}
.dv{{font-size:12px;color:#b8c8d8;text-align:right;max-width:60%;line-height:1.5}}

/* ── Comps Table ── */
.ct{{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px}}
.ct th{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a;letter-spacing:1px;text-align:left;padding:6px 10px;border-bottom:1px solid #1a1e24}}
.ct td{{padding:6px 10px;border-bottom:1px solid #1a1e24;color:#b8c8d8}}
.tn{{font-variant-numeric:tabular-nums;font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:11px}}
.cn{{font-size:10px;color:#6a7a8a}}

/* ── Recommendation ── */
.rv{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:14px;letter-spacing:3px;padding:10px 20px;background:#0a1a0e;border:2px solid #d4a843;color:#d4a843;display:inline-block;margin-bottom:12px;text-align:center;width:100%}}
.rs{{background:#101214;border:1px solid #1a1e24;border-radius:2px;padding:10px 12px;margin-bottom:8px}}
.rhs{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#d4a843;letter-spacing:1.5px;margin-bottom:6px}}
.rul{{list-style:none;padding:0}}
.rul li{{padding:2px 0;font-size:12px;color:#b8c8d8;line-height:1.5}}
.rul li::before{{content:"→ ";color:#d4a843;font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:10px}}
.rr li{{color:#ba6a5a}}
.rr li::before{{color:#ba6a5a}}
.rp{{font-size:12px;color:#6a7a8a;line-height:1.6}}

/* ── Business Cards ── */
.bg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px;margin-top:6px}}
.bz{{background:#0a0c0e;border:1px solid #1a1e24;padding:10px 12px;border-radius:2px}}
.bn{{font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:11px;color:#d4a843;letter-spacing:0.5px;margin-bottom:4px}}
.bm{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:4px;font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:9px;color:#6a7a8a}}
.bw{{font-size:11px;color:#6a7a8a;line-height:1.5}}

/* ── Footer ── */
.ft{{text-align:center;padding:20px 0 8px;font-family:'DM Mono','IBM Plex Mono','JetBrains Mono','Fira Code',monospace;font-size:8px;color:#3a4a5a;letter-spacing:1px;border-top:1px solid #1a1e24;margin-top:16px}}

/* ── Mobile ── */
@media(max-width:768px){{
  .vg{{grid-template-columns:1fr}}
  .mr{{grid-template-columns:110px 70px 30px 1fr;gap:6px;font-size:11px}}
  .bg{{grid-template-columns:1fr}}
  .tabs button{{font-size:16px;padding:6px 8px}}
}}
@media(max-width:430px){{
  body{{padding:8px 8px 32px;font-size:16px}}
  .hdr-v{{font-size:12px;letter-spacing:2px;padding:8px 14px}}
  .hdr-n{{font-size:18px}}
  .hdr-s,.hdr-w{{font-size:8px}}
  .kg{{grid-template-columns:1fr 1fr;gap:6px}}
  .k{{padding:8px 10px}}
  .kl{{font-size:7px}}
  .kv{{font-size:15px}}
  .kc{{font-size:7px}}
  .mr{{grid-template-columns:1fr;gap:3px;padding:6px 0}}
  .mb{{text-align:center;font-size:12px}}
  .ml{{font-size:8px}}
  .mw{{font-size:10px}}
  .oc,.ot,.rk,.rs,.sc,.note{{padding:8px 10px}}
  .ct{{font-size:10px}}
  .ct th,.ct td{{padding:4px 6px}}
  .om{{flex-wrap:wrap;gap:6px}}
  .rv{{font-size:12px;letter-spacing:2px;padding:8px 14px}}
  .tabs button{{font-size:16px;padding:5px 6px;letter-spacing:1px}}
}}

@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:0.01ms!important;transition-duration:0.01ms!important}}}}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-v">CONDITIONAL — PURSUE AT $210,000</div>
  <div class="hdr-n">6 Boonton Ave</div>
  <div class="hdr-s">Butler, NJ 07405 · Morris County · Tier 1 · Fee Simple Condo · 1,500 SF · Class C · 1905 · ASK {fm(D['pricing']['ask'])} · ${D['pricing']['price_psf']:.0f}/SF · DOM 5 · Listing 40453341</div>
  <div class="hdr-w">⚠ TAX BOMB +{tax['increase_pct']}% · CONDO DOC REVIEW · 1905 BUILDING · SINGLE PARKING · VACANT DELIVERY</div>
</div>

<div class="tabs">
  <button class="active" onclick="tab('scenarios')">Scenarios</button>
  <button onclick="tab('valuation')">Valuation</button>
  <button onclick="tab('divergence')">Divergence</button>
  <button onclick="tab('moats')">Moats ({D['moats']['total']}/24)</button>
  <button onclick="tab('offers')">Offers</button>
  <button onclick="tab('risks')">Risks</button>
  <button onclick="tab('demographics')">Demographics</button>
  <button onclick="tab('environmental')">Environmental</button>
  <button onclick="tab('comps')">Comps</button>
  <button onclick="tab('recommendation')">Recommendation</button>
</div>

<script>
function tab(n){{
  document.querySelectorAll('.tabs button').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('t-'+n).classList.add('active');
}}
</script>

<div id="t-scenarios" class="tab active">
  <div class="kg">
    <div class="k"><span class="kl">SCENARIOS</span><span class="kv">5</span><span class="kc">Worst → Phase 3</span></div>
    <div class="k"><span class="kl">BEST MOIC</span><span class="kv" style="color:#6aba8a">1.87×</span><span class="kc">Butler revival</span></div>
    <div class="k"><span class="kl">WORST MOIC</span><span class="kv" style="color:#ba6a5a">0.58×</span><span class="kc">Distressed resale</span></div>
    <div class="k"><span class="kl">TARGET MOIC</span><span class="kv">1.11×</span><span class="kc">Phase 1 Optimize</span></div>
  </div>
  {sc_cards}
</div>

<div id="t-valuation" class="tab">
  <div class="kg">
    <div class="k"><span class="kl">ASK PRICE</span><span class="kv">{fm(D['pricing']['ask'])}</span><span class="kc">${D['pricing']['price_psf']:.0f}/SF</span></div>
    <div class="k"><span class="kl">HARD FLOOR MID</span><span class="kv">{fm(D['pricing']['hard_floor_mid'])}</span><span class="kc">{D['pricing']['floor_to_ask_pct']}% of ask</span></div>
    <div class="k"><span class="kl">STABILIZED RE</span><span class="kv">{fm(D['pricing']['stabilized_re_value'])}</span><span class="kc">{D['pricing']['stabilized_to_ask_pct']}% of ask</span></div>
    <div class="k"><span class="kl">IMPLIED RE NOI</span><span class="kv">{fm(19000)}</span><span class="kc">@ $14/SF NNN</span></div>
    <div class="k"><span class="kl">POST-SALE TAX</span><span class="kv" style="color:#d4a843">{fm(tax['post_sale_tax'])}/yr</span><span class="kc">Morris Co. {tax['effective_rate']}</span></div>
    <div class="k"><span class="kl">TAX INCREASE</span><span class="kv" style="color:#ba6a5a">+{tax['increase_pct']}%</span><span class="kc">+{fm(tax['increase'])}/yr</span></div>
  </div>
  {val_cards}
</div>

<div id="t-divergence" class="tab">
  {div_html}
</div>

<div id="t-moats" class="tab">
  <div class="kg">
    <div class="k"><span class="kl">TOTAL SCORE</span><span class="kv">{D['moats']['total']}/24</span><span class="kc">{D['moats']['rating']}</span></div>
    <div class="k"><span class="kl">STRONGEST</span><span class="kv">ASSET STACK</span><span class="kc">Fee simple + buildout</span></div>
    <div class="k"><span class="kl">WEAKEST</span><span class="kv">BRAND / RENT</span><span class="kc">0/3 each — greenfield</span></div>
    <div class="k"><span class="kl">MARKET TIER</span><span class="kv">Morris Co.</span><span class="kc">Tier 1 NJ</span></div>
  </div>
  {moat_rows}
</div>

<div id="t-offers" class="tab">
  {offer_rows}
</div>

<div id="t-risks" class="tab">
  {risk_rows}
</div>

<div id="t-demographics" class="tab">
  {demo_rows}
</div>

<div id="t-environmental" class="tab">
  {env_rows}
</div>

<div id="t-comps" class="tab">
  <div class="kg">
    <div class="k"><span class="kl">AVG COMP $/SF</span><span class="kv">${D['comp_summary']['avg_psf']}</span><span class="kc">5 Morris Co. retail</span></div>
    <div class="k"><span class="kl">SUBJECT $/SF</span><span class="kv">${D['comp_summary']['subject_psf']:.0f}</span><span class="kc">{D['comp_summary']['premium_to_comps']}% premium</span></div>
    <div class="k"><span class="kl">RANGE</span><span class="kv">${D['comp_summary']['min_psf']}–${D['comp_summary']['max_psf']}</span><span class="kc">$/SF across comps</span></div>
  </div>
  <table class="ct">
    <thead><tr><th>ADDRESS</th><th>SF</th><th>PRICE</th><th>$/SF</th><th>NOTES</th></tr></thead>
    <tbody>{comp_rows}</tbody>
  </table>
</div>

<div id="t-recommendation" class="tab">
  {rec_html}
</div>

<div class="ft">
  CRE Underwriting · 5-Scenario Architecture · 4-Method Triangulation · 8-Moat Scoring · Convexity Engine v1.0<br>
  Sources: LoopNet (Firefox BiDi) · Morris County Tax Records · Census ACS 2023 · BLS QCEW<br>
  Not financial advice · Analysis date: {D['deal']['analysis_date']} · All NOI estimates marked where not provided
</div>

</body>
</html>"""

with open("/tmp/boonton_dashboard_v3.html", "w") as f:
    f.write(html)

print(f"Dashboard v3: {len(html):,} chars")
print("Design: Hoboken/Irvington — DM Mono typography, 2px borders, compact grid")
