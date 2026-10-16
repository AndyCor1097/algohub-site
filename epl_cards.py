"""AlgoHub Premier League cards - same dark, edge-first look as the NHL/NFL cards.
render_cards(df, day) -> html str (df = a picks/epl_YYYY-MM-DD.csv)."""
import html
import math

import pandas as pd

# football-data.co.uk team names -> (short code, nickname, primary color, text color)
TEAMS = {
    "Arsenal": ("ARS", "Arsenal", "#EF0107", "#fff"), "Aston Villa": ("AVL", "Aston Villa", "#670E36", "#95BFE5"),
    "Bournemouth": ("BOU", "Bournemouth", "#DA291C", "#000"), "Brentford": ("BRE", "Brentford", "#E30613", "#fff"),
    "Brighton": ("BHA", "Brighton", "#0057B8", "#fff"), "Burnley": ("BUR", "Burnley", "#6C1D45", "#99D6EA"),
    "Chelsea": ("CHE", "Chelsea", "#034694", "#fff"), "Crystal Palace": ("CRY", "Crystal Palace", "#1B458F", "#C4122E"),
    "Everton": ("EVE", "Everton", "#003399", "#fff"), "Fulham": ("FUL", "Fulham", "#FFFFFF", "#000"),
    "Ipswich": ("IPS", "Ipswich", "#3A64A3", "#fff"), "Leeds": ("LEE", "Leeds", "#FFCD00", "#1D428A"),
    "Leicester": ("LEI", "Leicester", "#003090", "#FDBE11"), "Liverpool": ("LIV", "Liverpool", "#C8102E", "#fff"),
    "Luton": ("LUT", "Luton", "#F78F1E", "#002D62"), "Man City": ("MCI", "Man City", "#6CABDD", "#1C2C5B"),
    "Man United": ("MUN", "Man United", "#DA291C", "#FBE122"), "Newcastle": ("NEW", "Newcastle", "#241F20", "#fff"),
    "Nott'm Forest": ("NFO", "Nott'm Forest", "#DD0000", "#fff"), "Sheffield United": ("SHU", "Sheffield Utd", "#EE2737", "#000"),
    "Southampton": ("SOU", "Southampton", "#D71920", "#fff"), "Sunderland": ("SUN", "Sunderland", "#EB172B", "#fff"),
    "Tottenham": ("TOT", "Tottenham", "#132257", "#fff"), "West Ham": ("WHU", "West Ham", "#7A263A", "#1BB1E7"),
    "Wolves": ("WOL", "Wolves", "#FDB913", "#231F20"), "Norwich": ("NOR", "Norwich", "#00A650", "#FFF200"),
    "Watford": ("WAT", "Watford", "#FBEE23", "#ED2127"), "West Brom": ("WBA", "West Brom", "#122F67", "#fff"),
    "Middlesbrough": ("MID", "Middlesbrough", "#E11B22", "#fff"), "Coventry": ("COV", "Coventry", "#59CBE8", "#000"),
    "Hull": ("HUL", "Hull", "#F5A12D", "#000"), "Stoke": ("STK", "Stoke", "#E03A3E", "#fff"),
    "Swansea": ("SWA", "Swansea", "#FFFFFF", "#000"), "Cardiff": ("CAR", "Cardiff", "#0070B5", "#fff"),
    "Bristol City": ("BRC", "Bristol City", "#E21A23", "#fff"), "Millwall": ("MIL", "Millwall", "#001D5E", "#fff"),
    "Preston": ("PNE", "Preston", "#FFFFFF", "#002A5C"), "Blackburn": ("BLB", "Blackburn", "#009EE0", "#fff"),
    "Derby": ("DER", "Derby", "#FFFFFF", "#000"), "QPR": ("QPR", "QPR", "#1D5BA4", "#fff"),
    "Portsmouth": ("POR", "Portsmouth", "#001489", "#fff"), "Wrexham": ("WRE", "Wrexham", "#D71920", "#fff"),
}
TIER_RANK = {"HAMMER": 3, "PLAY": 2, "LEAN": 1, "": 0}
e = lambda s: html.escape(str(s)) if s is not None and not (isinstance(s, float) and math.isnan(s)) else ""


def _na(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def _s(v):
    return "" if _na(v) else str(v)


def _o(v):
    return "-" if _na(v) else f"{int(v):+d}"


def info(t):
    return TEAMS.get(t, (t[:3].upper(), t, "#30363d", "#fff"))


def _badge(t):
    code, _, bg, fg = info(t)
    return f'<span class="badge" style="background:{bg};color:{fg}">{e(code)}</span>'


def _form(f):
    f = _s(f)
    return '<span class="form">' + "".join(f'<span class="{c}">{c}</span>' for c in f) + "</span>" if f else ""


def _team_row(r, s, fav):
    t = r["home_team" if s == "h" else "away_team"]
    xg = r["xg_home" if s == "h" else "xg_away"]
    pos, pts, gp = r.get(f"{s}_pos"), r.get(f"{s}_pts"), r.get(f"{s}_gp")
    sub = f"{int(pos)}{'st' if pos == 1 else 'nd' if pos == 2 else 'rd' if pos == 3 else 'th'} · {int(pts)} pts" if not _na(pos) else "New this season"
    return f"""
      <div class="team {'fav' if fav == s else ''}">
        {_badge(t)}
        <div class="tname"><b>{e(info(t)[1])}</b><small>{e(sub)} &nbsp;{_form(r.get(f'{s}_form'))}</small></div>
        <div class="proj">{xg:.1f}</div>
      </div>"""


def _wp(r):
    a, h = r["away_team"], r["home_team"]
    ph, pd_, pa = float(r["p_home"]), float(r["p_draw"]), float(r["p_away"])
    ca, ch = info(a)[2], info(h)[2]
    return f"""
      <div class="wp">
        <div class="wplab"><span>{e(info(h)[0])} {ph:.0%}</span><span class="cap">DRAW {pd_:.0%}</span><span>{e(info(a)[0])} {pa:.0%}</span></div>
        <div class="wpbar"><i style="width:{ph * 100:.1f}%;background:{ch}"></i><i style="width:{pd_ * 100:.1f}%;background:#4b535d"></i><i style="width:{pa * 100:.1f}%;background:{ca}"></i></div>
      </div>"""


def _pick(tier_, pick, odds):
    if isinstance(tier_, str) and tier_:
        return f'<div class="pick t-{tier_.lower()}"><span class="tier">{e(tier_)}</span>{e(pick)} <small>{e(_o(odds))}</small></div>'
    return '<div class="pick none">NO PLAY</div>'


def _result_mkt(r):
    h, a = info(r["home_team"])[0], info(r["away_team"])[0]
    cells = []
    for k, lab in (("home", h), ("draw", "DRAW"), ("away", a)):
        mk, fin, od = r.get(f"mk_{k}"), r.get(f"p_{k}"), r.get(f"odds_{k}")
        pk = _s(r.get("res_pick"))
        chosen = (k == "draw" and pk == "Draw") or (k == "home" and pk == f"{r['home_team']} ML") or \
                 (k == "away" and pk == f"{r['away_team']} ML")
        mk_txt = "" if _na(mk) else f"mkt {mk:.0%}"
        cells.append(f'<div class="{"pk" if chosen and _s(r.get("res_tier")) else ""}"><small>{e(lab)} {e(_o(od))}</small>'
                     f'<b>{fin:.0%}</b><em>{e(mk_txt)}</em></div>')
    edge = r.get("res_edge")
    return f"""
      <div class="mkt">
        <div class="mlabel">MATCH RESULT <em>· ours vs sharp market · edge {('-' if _na(edge) else f'{edge:+.1f}')} pts</em></div>
        <div class="res3">{''.join(cells)}</div>
        {_pick(r.get('res_tier'), _s(r.get('res_pick')), r.get('res_odds'))}
      </div>"""


def _ou_mkt(r):
    mk, fin = r.get("mk_over25"), r.get("p_over25")
    edge = r.get("ou_edge")
    return f"""
      <div class="mkt">
        <div class="mlabel">TOTAL GOALS 2.5</div>
        <div class="cols">
          <div><small>MARKET OVER</small><span>{'-' if _na(mk) else f'{mk:.0%}'}</span></div>
          <div><small>OURS OVER</small><span>{fin:.0%}</span></div>
          <div class="edge {'hot' if _s(r.get('ou_tier')) else ''}"><small>EDGE</small><span>{'-' if _na(edge) else f'{edge:.1f}'}</span></div>
        </div>
        {_pick(r.get('ou_tier'), _s(r.get('ou_pick')), r.get('ou_odds'))}
      </div>"""


def _strip(r):
    h, a = info(r["home_team"])[0], info(r["away_team"])[0]
    return f"""
      <div class="strip"><div class="mlabel">MODEL <em>(big numbers up top = model's projected goals; win % = model blended with market) · (attack / defense: 1.00 = league average, lower defense = better)</em></div>
        <div class="frow"><b>{e(h)}</b><span>ATT <i>{r['h_att']:.2f}</i></span><span>DEF <i>{r['h_def']:.2f}</i></span></div>
        <div class="frow"><b>{e(a)}</b><span>ATT <i>{r['a_att']:.2f}</i></span><span>DEF <i>{r['a_def']:.2f}</i></span></div>
        <div class="frow"><span>MOST LIKELY <i>{e(r['top_score'])}</i> ({r['p_top_score']:.0%})</span><span>BOTH SCORE <i>{r['p_btts']:.0%}</i></span></div>
      </div>"""


def _card(r):
    tiers = [_s(r.get(k)) for k in ("res_tier", "ou_tier")]
    best = max(tiers, key=lambda x: TIER_RANK.get(x, 0))
    # highlight follows the projected score (the big numbers): that's what the model itself says.
    # The win % bar is model + market blended, so the two can point different ways on close games.
    fav = "h" if r["xg_home"] >= r["xg_away"] else "a"
    d = pd.Timestamp(r["date"])
    return f"""
    <article class="card b-{best.lower() or 'none'}" data-day="{e(r['date'])}" data-play="{1 if best else 0}">
      <header class="meta"><span>{d.strftime('%a').upper()} · {e(r['start_et'])} ET</span><span>{e(r['home_team'])} vs {e(r['away_team'])}</span></header>
      {_team_row(r, 'h', fav)}
      {_team_row(r, 'a', fav)}
      {_wp(r)}
      {_result_mkt(r)}
      {_ou_mkt(r)}
      {_strip(r)}
    </article>"""


def render_cards(df, day):
    df = df.copy()
    df["_t"] = pd.to_datetime(df.date + " " + df.start_et, format="%Y-%m-%d %I:%M %p", errors="coerce")
    df = df.sort_values(["_t", "game_id"])
    tiers = [t for k in ("res_tier", "ou_tier") for t in df[k].fillna("")]
    n_play = sum(1 for t in tiers if t)
    n_ham = sum(1 for t in tiers if t == "HAMMER")
    days = list(dict.fromkeys(df.date))
    tabs = "".join(f'<button data-f="{e(x)}">{pd.Timestamp(x).strftime("%a %b %d").upper()}</button>' for x in days) if len(days) > 1 else ""
    d = pd.Timestamp(day)
    cards = "".join(_card(r) for r in df.to_dict("records"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlgoHub EPL {e(day)}</title>
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
.res3{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:2px}}
.res3 div{{background:#0f1319;border:1px solid var(--line);border-radius:8px;padding:6px 8px}}
.res3 small{{display:block;color:var(--mu);font-size:10px;letter-spacing:.12em}} .res3 b{{font-family:"Barlow Condensed",sans-serif;font-size:18px}} .res3 em{{font-style:normal;color:var(--mu);font-size:12px;margin-left:4px}}
.res3 .pk{{border-color:var(--play)}}
.form{{font-family:"Barlow Condensed",sans-serif;letter-spacing:.12em}} .form .W{{color:#3fb950}} .form .L{{color:#f85149}} .form .D{{color:#7d8590}}
.foot{{color:var(--mu);font-size:11px;margin-top:30px;letter-spacing:.06em}}
.hide{{display:none}}
</style></head><body><div class="wrap">
  <div class="top">
    <div><div class="k">THE ALGOHUB · PREMIER LEAGUE ALGO</div><h1>MATCHES FROM {e(d.strftime('%b').upper())} {d.day}</h1></div>
    <div class="stats">
      <div><small>MATCHES</small><b>{len(df)}</b></div>
      <div class="p"><small>PLAYS</small><b>{n_play}</b></div>
      <div class="h"><small>HAMMERS</small><b>{n_ham}</b></div>
    </div>
  </div>
  <div class="tabs"><button class="on" data-f="all">ALL</button><button data-f="plays">PLAYS ONLY</button>{tabs}</div>
  <div class="grid">{cards}</div>
  <p class="foot">Dixon-Coles goals model (attack/defense per team, recent matches weighted more), blended with the sharp no-vig market: we keep 35% of the model's disagreement. Big number = projected goals. Edges in win-prob points. LEAN / PLAY / HAMMER. Not betting advice.</p>
</div>
<script>
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
  const f=b.dataset.f;
  document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hide',
    f==='plays'?c.dataset.play!=='1':(f!=='all'&&c.dataset.day!==f)));
}});
</script></body></html>"""
