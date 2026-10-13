"""AlgoHub NHL cards - same dark, edge-first look as the NFL/CFB cards.
render_cards(df, day) -> html str (df = a picks/nhl_YYYY-MM-DD.csv)."""
import html
import math

import pandas as pd

COLORS = {  # primary, text-on-primary
    "ANA": ("#F47A38", "#000"), "ARI": ("#8C2633", "#fff"), "BOS": ("#FFB81C", "#000"),
    "BUF": ("#003087", "#FFB81C"), "CGY": ("#C8102E", "#F1BE48"), "CAR": ("#CC0000", "#fff"),
    "CHI": ("#CF0A2C", "#fff"), "COL": ("#6F263D", "#fff"), "CBJ": ("#002654", "#fff"),
    "DAL": ("#006847", "#fff"), "DET": ("#CE1126", "#fff"), "EDM": ("#041E42", "#FF4C00"),
    "FLA": ("#041E42", "#C8102E"), "LAK": ("#111111", "#A2AAAD"), "MIN": ("#154734", "#fff"),
    "MTL": ("#AF1E2D", "#fff"), "NSH": ("#FFB81C", "#041E42"), "NJD": ("#CE1126", "#fff"),
    "NYI": ("#00539B", "#F47D30"), "NYR": ("#0038A8", "#fff"), "OTT": ("#C52032", "#fff"),
    "PHI": ("#F74902", "#000"), "PIT": ("#FCB514", "#000"), "SJS": ("#006D75", "#fff"),
    "SEA": ("#001628", "#99D9D9"), "STL": ("#002F87", "#FCB514"), "TBL": ("#002868", "#fff"),
    "TOR": ("#00205B", "#fff"), "UTA": ("#6CACE4", "#000"), "VAN": ("#00205B", "#fff"),
    "VGK": ("#B4975A", "#000"), "WSH": ("#C8102E", "#fff"), "WPG": ("#041E42", "#fff"),
}
NAMES = {
    "ANA": "Ducks", "ARI": "Coyotes", "BOS": "Bruins", "BUF": "Sabres", "CGY": "Flames",
    "CAR": "Hurricanes", "CHI": "Blackhawks", "COL": "Avalanche", "CBJ": "Blue Jackets", "DAL": "Stars",
    "DET": "Red Wings", "EDM": "Oilers", "FLA": "Panthers", "LAK": "Kings", "MIN": "Wild",
    "MTL": "Canadiens", "NSH": "Predators", "NJD": "Devils", "NYI": "Islanders", "NYR": "Rangers",
    "OTT": "Senators", "PHI": "Flyers", "PIT": "Penguins", "SJS": "Sharks", "SEA": "Kraken",
    "STL": "Blues", "TBL": "Lightning", "TOR": "Maple Leafs", "UTA": "Mammoth", "VAN": "Canucks",
    "VGK": "Golden Knights", "WSH": "Capitals", "WPG": "Jets",
}
TIER_RANK = {"HAMMER": 3, "PLAY": 2, "LEAN": 1, "": 0}
e = lambda s: html.escape(str(s)) if s is not None and not (isinstance(s, float) and math.isnan(s)) else ""


def _s(v):
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v)


def _na(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def _o(v):
    return "-" if _na(v) else f"{int(v):+d}"


def _badge(t):
    bg, fg = COLORS.get(t, ("#30363d", "#fff"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{e(t)}</span>'


def _team_row(r, s, fav):
    t = r["away_team" if s == "a" else "home_team"]
    proj = r["proj_away" if s == "a" else "proj_home"]
    sub = " · ".join(x for x in (_s(r.get(f"{s}_rec")), "B2B" if r.get(f"{s}_b2b") else "") if x)
    return f"""
      <div class="team {'fav' if fav == s else ''}">
        {_badge(t)}
        <div class="tname"><b>{e(NAMES.get(t, t))}</b><small>{e(sub)}</small></div>
        <div class="proj">{proj:.1f}</div>
      </div>"""


def _wp(r):
    a, h = r["away_team"], r["home_team"]
    hw = float(r["home_wp"])
    ca, ch = COLORS.get(a, ("#555",))[0], COLORS.get(h, ("#777",))[0]
    return f"""
      <div class="wp">
        <div class="wplab"><span>{e(a)} {1 - hw:.0%}</span><span class="cap">WIN PROB · OT {r['p_ot']:.0%}</span><span>{e(h)} {hw:.0%}</span></div>
        <div class="wpbar"><i style="width:{(1 - hw) * 100:.1f}%;background:{ca}"></i><i style="width:{hw * 100:.1f}%;background:{ch}"></i></div>
      </div>"""


def _market(label, vegas, model, edge, tier_, pick, odds):
    has = isinstance(tier_, str) and tier_
    edge_txt = "-" if _na(edge) else f"{edge:+.1f}"
    pick_html = (f'<div class="pick t-{tier_.lower()}"><span class="tier">{e(tier_)}</span>{e(pick)} '
                 f'<small>{e(_o(odds))}</small></div>' if has else '<div class="pick none">NO PLAY</div>')
    return f"""
      <div class="mkt">
        <div class="mlabel">{label}</div>
        <div class="cols">
          <div><small>MARKET</small><span>{e(vegas).replace(chr(10), "<br>")}</span></div>
          <div><small>MODEL</small><span>{e(model).replace(chr(10), "<br>")}</span></div>
          <div class="edge {'hot' if has else ''}"><small>EDGE %</small><span>{edge_txt}</span></div>
        </div>
        {pick_html}
      </div>"""


def _strip(r):
    """Team form vs league: GF/GA per game, shots, PP/PK, save %."""
    rows = []
    for s in ("a", "h"):
        t = r["away_team" if s == "a" else "home_team"]
        rows.append(f"""
          <div class="frow"><b>{e(t)}</b>
            <span>GF <i>{r[f'{s}_gf']:.2f}</i></span><span>GA <i>{r[f'{s}_ga']:.2f}</i></span>
            <span>SF <i>{r[f'{s}_sf']:.1f}</i></span><span>SA <i>{r[f'{s}_sa']:.1f}</i></span>
            <span>PP <i>{r[f'{s}_pp']:.0%}</i></span><span>PK <i>{r[f'{s}_pk']:.0%}</i></span>
            <span>SV <i>{r[f'{s}_sv']:.3f}</i></span></div>""")
    return f'<div class="strip"><div class="mlabel">FORM <em>(per game, shrunk to last season early on)</em></div>{"".join(rows)}</div>'


def _card(r):
    tiers = [_s(r.get(k)) for k in ("ml_tier", "pl_tier", "tot_tier")]
    best = max(tiers, key=lambda x: TIER_RANK.get(x, 0))
    fav = "h" if r["home_wp"] >= .5 else "a"
    a, h = r["away_team"], r["home_team"]
    # moneyline
    ml_mkt = "-" if _na(r.get("ml_home")) else f"{a} {_o(r['ml_away'])}\n{h} {_o(r['ml_home'])}"
    ml_model = f"{a} {_o(r['fair_ml_away'])}\n{h} {_o(r['fair_ml_home'])}"
    # puck line
    pl_mkt = _s(r.get("pl_line")) or "-"
    if not _na(r.get("pl_home_pt")):
        fav_t = h if r["pl_home_pt"] < 0 else a
        p_fav = r["p_h_m15"] if fav_t == h else r["p_a_m15"]
        pl_model = f"{fav_t} -1.5 {p_fav:.0%}"
    else:
        pl_model = f"{h if fav == 'h' else a} -1.5 {(r['p_h_m15'] if fav == 'h' else r['p_a_m15']):.0%}"
    tot_mkt = "-" if _na(r.get("total_line")) else f"{r['total_line']:g}"
    flags = [f for f in _s(r.get("flags")).split("|") if f]
    chips = "".join(f'<span class="chip{" inj" if "BACKUP" in f or "B2B" in f else ""}">{e(f)}</span>' for f in flags)
    return f"""
    <article class="card b-{best.lower() or 'none'}" data-play="{1 if best else 0}" data-rank="{TIER_RANK[best]}">
      <header class="meta"><span>{e(r['start_et'])} ET</span><span>{e(_s(r.get('venue')))}</span></header>
      {_team_row(r, 'a', fav)}
      {_team_row(r, 'h', fav)}
      {_wp(r)}
      {_market("MONEYLINE", ml_mkt, ml_model, r.get("ml_edge"), r.get("ml_tier"), f"{_s(r.get('ml_pick'))} ML", r.get("ml_odds"))}
      {_market("PUCK LINE", pl_mkt, pl_model, r.get("pl_edge"), r.get("pl_tier"), _s(r.get("pl_pick")), r.get("pl_odds"))}
      {_market("TOTAL", tot_mkt, f"{r['pred_total']:.2f}", r.get("tot_edge"), r.get("tot_tier"), _s(r.get("tot_pick")), r.get("tot_odds"))}
      {_strip(r)}
      {f'<div class="chips">{chips}</div>' if chips else ''}
    </article>"""


def render_cards(df, day):
    df = df.copy()
    df["_t"] = pd.to_datetime(df.date + " " + df.start_et, format="%Y-%m-%d %I:%M %p", errors="coerce")
    df = df.sort_values(["_t", "game_id"])
    tiers = [t for k in ("ml_tier", "pl_tier", "tot_tier") for t in df[k].fillna("")]
    n_play = sum(1 for t in tiers if t)
    n_ham = sum(1 for t in tiers if t == "HAMMER")
    d = pd.Timestamp(day)
    title = f"{d.strftime('%A, %B').upper()} {d.day}"
    cards = "".join(_card(r) for r in df.to_dict("records"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlgoHub NHL {e(day)}</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0b0e13;--card:#12161d;--card2:#171c25;--line:#222a35;--tx:#e6edf3;--mu:#7d8590;
--lean:#58a6ff;--play:#3fb950;--ham:#f2b134;--neg:#f85149}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:14px/1.4 Inter,system-ui,sans-serif;padding:28px 16px 60px}}
.wrap{{max-width:1180px;margin:0 auto}}
.proj,.cols span,.top h1,.stats b,.wplab,.pick,.frow i{{font-family:"Barlow Condensed",sans-serif}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:18px}}
.top .k{{color:var(--mu);font-size:12px;letter-spacing:.18em;font-weight:600}}
.top h1{{font-size:44px;font-weight:800;letter-spacing:.02em;line-height:1}}
.stats{{display:flex;gap:22px}} .stats div{{text-align:right}} .stats small{{display:block;color:var(--mu);font-size:11px;letter-spacing:.14em}}
.stats b{{font-size:30px}} .stats .h b{{color:var(--ham)}} .stats .p b{{color:var(--play)}}
.tabs{{display:flex;gap:6px;margin:18px 0 18px;flex-wrap:wrap}}
.tabs button{{background:transparent;border:1px solid var(--line);color:var(--mu);padding:7px 14px;border-radius:999px;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.08em;cursor:pointer}}
.tabs button.on{{background:var(--tx);color:var(--bg);border-color:var(--tx)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;align-items:start}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;border-top:3px solid var(--line)}}
.card.b-lean{{border-top-color:var(--lean)}} .card.b-play{{border-top-color:var(--play)}}
.card.b-hammer{{border-top-color:var(--ham);box-shadow:0 0 0 1px rgba(242,177,52,.25),0 8px 30px rgba(242,177,52,.08)}}
.meta{{display:flex;justify-content:space-between;gap:10px;padding:11px 16px;color:var(--mu);font-size:11px;letter-spacing:.08em;border-bottom:1px solid var(--line)}}
.meta span:last-child{{text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.team{{display:flex;align-items:center;gap:12px;padding:10px 16px}}
.badge{{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;font:800 13px "Barlow Condensed";letter-spacing:.04em;flex:none}}
.tname{{flex:1;min-width:0}} .tname b{{display:block;font-size:16px;font-weight:600}} .tname small{{color:var(--mu);font-size:12px}}
.proj{{font-size:32px;font-weight:700;color:var(--mu)}} .team.fav .proj{{color:var(--tx)}}
.wp{{padding:6px 16px 14px}} .wplab{{display:flex;justify-content:space-between;font-size:15px;font-weight:700;margin-bottom:6px}}
.wplab .cap{{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.16em;align-self:center}}
.wpbar{{display:flex;height:8px;border-radius:99px;overflow:hidden;gap:2px;background:var(--line)}} .wpbar i{{display:block;height:100%}}
.mkt{{border-top:1px solid var(--line);padding:12px 16px;background:var(--card2)}}
.mlabel{{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.18em;margin-bottom:8px}} .mlabel em{{font-style:normal;letter-spacing:.04em;opacity:.7}}
.cols{{display:grid;grid-template-columns:1.3fr 1.3fr .7fr;gap:8px}} .cols small{{display:block;color:var(--mu);font-size:10px;letter-spacing:.14em}}
.cols span{{font-size:17px;font-weight:700}} .edge span{{color:var(--mu)}} .edge.hot span{{color:var(--tx);font-size:24px}}
.pick{{margin-top:10px;display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700;letter-spacing:.02em}}
.pick small{{color:var(--mu);font-size:16px}}
.pick .tier{{font:800 11px Inter,system-ui,sans-serif;letter-spacing:.14em;padding:4px 8px;border-radius:6px;color:#0b0e13}}
.t-lean .tier{{background:var(--lean)}} .t-play .tier{{background:var(--play)}} .t-hammer .tier{{background:var(--ham)}}
.t-hammer{{color:var(--ham)}} .pick.none{{color:#4b535d;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.16em}}
.strip{{border-top:1px solid var(--line);padding:12px 16px}}
.frow{{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:11px;color:var(--mu);letter-spacing:.06em;padding:3px 0;align-items:baseline}}
.frow b{{color:var(--tx);width:36px;font-size:12px}} .frow i{{font-style:normal;color:var(--tx);font-size:14px;font-weight:700}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 14px}}
.chip{{font:600 10px Inter,system-ui,sans-serif;letter-spacing:.1em;color:#c9d1d9;border:1px solid var(--line);background:#0f1319;padding:4px 8px;border-radius:6px}}
.chip.inj{{color:#ffb4ab;border-color:#5a2a27;background:#1d1212}}
.foot{{color:var(--mu);font-size:11px;margin-top:30px;letter-spacing:.06em}}
.hide{{display:none}}
</style></head><body><div class="wrap">
  <div class="top">
    <div><div class="k">THE ALGOHUB · NHL GAME ALGO</div><h1>{e(title)}</h1></div>
    <div class="stats">
      <div><small>GAMES</small><b>{len(df)}</b></div>
      <div class="p"><small>PLAYS</small><b>{n_play}</b></div>
      <div class="h"><small>HAMMERS</small><b>{n_ham}</b></div>
    </div>
  </div>
  <div class="tabs"><button class="on" data-f="all">ALL</button><button data-f="plays">PLAYS ONLY</button></div>
  <div class="grid">{cards}</div>
  <p class="foot">Poisson goal model on in-season team form, shrunk toward last season. Edges = win-prob points vs. no-vig consensus. LEAN / PLAY / HAMMER tiers. Not betting advice.</p>
</div>
<script>
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
  const f=b.dataset.f;
  document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hide',f==='plays'&&c.dataset.play!=='1'));
}});
</script></body></html>"""
