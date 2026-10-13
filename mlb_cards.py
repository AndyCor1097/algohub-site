"""AlgoHub MLB cards - same dark, edge-first look as the NFL / NHL cards.
render_game_cards(df)  -> html for an all_games_YYYY-MM-DD.csv (game algo)
render_hr_cards(data)  -> html for an hr_YYYY-MM-DD.json (HR model / HIT scores)
Edge = model prob x decimal odds - 1 (same formula as the game algo). LEAN 4 / SOLID 7 / STRONG 10."""
import html
import math

import pandas as pd

COLORS = {
    "ARI": ("#A71930", "#fff"), "ATL": ("#13274F", "#fff"), "BAL": ("#DF4601", "#000"),
    "BOS": ("#BD3039", "#fff"), "CHC": ("#0E3386", "#fff"), "CWS": ("#27251F", "#C4CED4"),
    "CIN": ("#C6011F", "#fff"), "CLE": ("#00385D", "#fff"), "COL": ("#33006F", "#C4CED4"),
    "DET": ("#0C2340", "#FA4616"), "HOU": ("#002D62", "#EB6E1F"), "KC": ("#004687", "#BD9B60"),
    "KCR": ("#004687", "#BD9B60"), "LAA": ("#BA0021", "#fff"), "LAD": ("#005A9C", "#fff"),
    "MIA": ("#00A3E0", "#000"), "MIL": ("#12284B", "#FFC52F"), "MIN": ("#002B5C", "#fff"),
    "NYM": ("#002D72", "#FF5910"), "NYY": ("#0C2340", "#fff"), "OAK": ("#003831", "#EFB21E"),
    "ATH": ("#003831", "#EFB21E"), "PHI": ("#E81828", "#fff"), "PIT": ("#FDB827", "#000"),
    "SD": ("#2F241D", "#FFC425"), "SDP": ("#2F241D", "#FFC425"), "SF": ("#FD5A1E", "#000"),
    "SFG": ("#FD5A1E", "#000"), "SEA": ("#0C2C56", "#005C5C"), "STL": ("#C41E3A", "#fff"),
    "TB": ("#092C5C", "#8FBCE6"), "TBR": ("#092C5C", "#8FBCE6"), "TEX": ("#003278", "#fff"),
    "TOR": ("#134A8E", "#fff"), "WSH": ("#AB0003", "#fff"), "WSN": ("#AB0003", "#fff"),
}
TIERS = [(10, "STRONG"), (7, "SOLID"), (4, "LEAN")]
RANK = {"STRONG": 3, "SOLID": 2, "LEAN": 1, "": 0}
GRADE_CLS = {"ELITE": "ham", "STRONG": "play", "GOOD": "lean"}
e = lambda s: html.escape(str(s)) if s is not None and not (isinstance(s, float) and math.isnan(s)) else ""


def _na(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or v == ""


def _o(v):
    return "-" if _na(v) else f"{int(float(v)):+d}"


def _dec(o):
    o = float(o)
    return 1 + (o / 100 if o > 0 else 100 / -o)


def _ev(p, o):
    return None if _na(p) or _na(o) else (float(p) * _dec(o) - 1) * 100


def _tier(ev):
    if ev is None:
        return ""
    for t, n in TIERS:
        if ev >= t:
            return n
    return ""


def _badge(t):
    bg, fg = COLORS.get(t, ("#30363d", "#fff"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{e(t)}</span>'


CSS = """
:root{--bg:#0b0e13;--card:#12161d;--card2:#171c25;--line:#222a35;--tx:#e6edf3;--mu:#7d8590;
--lean:#58a6ff;--play:#3fb950;--ham:#f2b134;--neg:#f85149}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font:14px/1.4 Inter,system-ui,sans-serif;padding:28px 16px 60px}
.wrap{max-width:1180px;margin:0 auto}
.proj,.cols span,.top h1,.stats b,.wplab,.pick,.score,.big{font-family:"Barlow Condensed",sans-serif}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:18px}
.top .k{color:var(--mu);font-size:12px;letter-spacing:.18em;font-weight:600}
.top h1{font-size:44px;font-weight:800;letter-spacing:.02em;line-height:1}
.stats{display:flex;gap:22px} .stats div{text-align:right} .stats small{display:block;color:var(--mu);font-size:11px;letter-spacing:.14em}
.stats b{font-size:30px} .stats .h b{color:var(--ham)} .stats .p b{color:var(--play)}
.tabs{display:flex;gap:6px;margin:18px 0;flex-wrap:wrap}
.tabs button{background:transparent;border:1px solid var(--line);color:var(--mu);padding:7px 14px;border-radius:999px;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.08em;cursor:pointer}
.tabs button.on{background:var(--tx);color:var(--bg);border-color:var(--tx)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;align-items:start}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;border-top:3px solid var(--line)}
.card.b-lean{border-top-color:var(--lean)} .card.b-solid{border-top-color:var(--play)}
.card.b-strong{border-top-color:var(--ham);box-shadow:0 0 0 1px rgba(242,177,52,.25),0 8px 30px rgba(242,177,52,.08)}
.meta{display:flex;justify-content:space-between;gap:10px;padding:11px 16px;color:var(--mu);font-size:11px;letter-spacing:.08em;border-bottom:1px solid var(--line)}
.team{display:flex;align-items:center;gap:12px;padding:10px 16px}
.badge{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;font:800 13px "Barlow Condensed";letter-spacing:.04em;flex:none}
.tname{flex:1;min-width:0} .tname b{display:block;font-size:16px;font-weight:600} .tname small{color:var(--mu);font-size:12px}
.proj{font-size:32px;font-weight:700;color:var(--mu)} .team.fav .proj{color:var(--tx)}
.wp{padding:6px 16px 14px} .wplab{display:flex;justify-content:space-between;font-size:15px;font-weight:700;margin-bottom:6px}
.wplab .cap{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.16em;align-self:center}
.wpbar{display:flex;height:8px;border-radius:99px;overflow:hidden;gap:2px;background:var(--line)} .wpbar i{display:block;height:100%}
.mkt{border-top:1px solid var(--line);padding:12px 16px;background:var(--card2)}
.mlabel{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.18em;margin-bottom:8px}
.cols{display:grid;grid-template-columns:1.2fr 1.2fr .8fr;gap:8px} .cols small{display:block;color:var(--mu);font-size:10px;letter-spacing:.14em}
.cols span{font-size:17px;font-weight:700} .edge span{color:var(--mu)} .edge.hot span{color:var(--tx);font-size:24px}
.pick{margin-top:10px;display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700}
.pick small{color:var(--mu);font-size:16px}
.pick .tier{font:800 11px Inter,system-ui,sans-serif;letter-spacing:.14em;padding:4px 8px;border-radius:6px;color:#0b0e13}
.t-lean .tier{background:var(--lean)} .t-solid .tier{background:var(--play)} .t-strong .tier{background:var(--ham)}
.t-strong{color:var(--ham)} .pick.none{color:#4b535d;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.16em}
.chips{display:flex;flex-wrap:wrap;gap:6px;padding:12px 16px 14px;border-top:1px solid var(--line)}
.chip{font:600 10px Inter,system-ui,sans-serif;letter-spacing:.1em;color:#c9d1d9;border:1px solid var(--line);background:#0f1319;padding:4px 8px;border-radius:6px}
.chip.hot{color:#ffd58a;border-color:#5a4520;background:#1d1810} .chip.cold{color:#9ecbff;border-color:#1f3a5a;background:#0f1620}
.foot{color:var(--mu);font-size:11px;margin-top:30px;letter-spacing:.06em}
.hide{display:none}
/* HR board */
.hr{display:grid;grid-template-columns:44px 44px minmax(0,1fr) 92px;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--line)}
.hr:first-child{border-top:0}
.rk{font:800 22px "Barlow Condensed";color:var(--mu);text-align:center}
.hr.top3 .rk{color:var(--ham)}
.who b{font-size:15px;font-weight:600} .who small{display:block;color:var(--mu);font-size:11px;letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bars{display:flex;gap:14px;margin-top:6px;flex-wrap:wrap}
.bar{font-size:10px;color:var(--mu);letter-spacing:.08em;min-width:84px}
.bar i{display:block;height:4px;border-radius:9px;background:var(--line);margin-top:3px;position:relative;overflow:hidden}
.bar i em{position:absolute;inset:0 auto 0 0;background:var(--play);border-radius:9px}
.bar b{color:var(--tx);font:700 13px "Barlow Condensed"}
.sc{text-align:right} .sc .big{display:block;font-size:30px;font-weight:800;line-height:1}
.gr{display:inline-block;margin-top:4px;font:800 9px Inter,system-ui,sans-serif;letter-spacing:.12em;padding:3px 6px;border-radius:5px;color:#0b0e13;background:var(--mu)}
.gr.ham{background:var(--ham)} .gr.play{background:var(--play)} .gr.lean{background:var(--lean)}
.board{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.wx{font-size:11px;color:var(--mu);margin-left:6px}
@media(max-width:560px){.hr{grid-template-columns:30px 36px minmax(0,1fr) 64px;gap:8px}.badge{width:34px;height:34px}.sc .big{font-size:24px}}
"""

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}</style></head><body><div class="wrap">"""

TABS_JS = """<script>
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
  const f=b.dataset.f;
  document.querySelectorAll('[data-g]').forEach(c=>c.classList.toggle('hide',
    f==='plays'?c.dataset.play!=='1':(f!=='all'&&c.dataset.g!==f)));
});
</script>"""


def _title(day):
    d = pd.Timestamp(day)
    return f"{d.strftime('%A, %B').upper()} {d.day}"


# ----------------------------------------------------------------- game cards
def _market(label, mkt, model, ev, pick, odds):
    t = _tier(ev)
    ev_txt = "-" if ev is None else f"{ev:+.1f}"
    pick_html = (f'<div class="pick t-{t.lower()}"><span class="tier">{t}</span>{e(pick)} <small>{_o(odds)}</small></div>'
                 if t else '<div class="pick none">NO PLAY</div>')
    return t, f"""
      <div class="mkt"><div class="mlabel">{label}</div>
        <div class="cols"><div><small>MARKET</small><span>{mkt}</span></div>
          <div><small>MODEL</small><span>{model}</span></div>
          <div class="edge {'hot' if t else ''}"><small>EDGE %</small><span>{ev_txt}</span></div></div>
        {pick_html}</div>"""


def _best(pairs):
    """pairs = [(ev, pick, odds), ...] -> the one with the biggest EV."""
    pairs = [p for p in pairs if p[0] is not None]
    return max(pairs, key=lambda p: p[0]) if pairs else (None, "", None)


def _game_card(r):
    h, a = r["home_abb"], r["away_abb"]
    hw = float(r["home_win_prob"])
    fav = "h" if hw >= .5 else "a"
    ca, ch = COLORS.get(a, ("#555",))[0], COLORS.get(h, ("#777",))[0]
    time_ = ""
    try:
        if "commence_time" in r and not _na(r.get("commence_time")):
            time_ = pd.Timestamp(r["commence_time"]).tz_convert("America/New_York").strftime("%I:%M %p ET").lstrip("0")
    except Exception:
        time_ = ""

    def team(s):
        t, nm, sp, pr = ((a, r["away_team"], r.get("away_starter_name"), r["away_proj_runs"]) if s == "a"
                         else (h, r["home_team"], r.get("home_starter_name"), r["home_proj_runs"]))
        return f"""<div class="team {'fav' if fav == s else ''}">{_badge(t)}
          <div class="tname"><b>{e(nm)}</b><small>SP {e(sp if not _na(sp) else 'TBD')}</small></div>
          <div class="proj">{float(pr):.1f}</div></div>"""

    # moneyline
    ml_ev, ml_pick, ml_odds = _best([(_ev(hw, r.get("home_ml")), f"{h} ML", r.get("home_ml")),
                                     (_ev(1 - hw, r.get("away_ml")), f"{a} ML", r.get("away_ml"))])
    t1, m1 = _market("MONEYLINE", f"{a} {_o(r.get('away_ml'))}<br>{h} {_o(r.get('home_ml'))}",
                     f"{a} {1 - hw:.0%}<br>{h} {hw:.0%}", ml_ev, ml_pick, ml_odds)
    # run line: the RL model is P(home wins by 2+), so it only prices games where home is -1.5
    hp = r.get("home_rl")
    priced = not _na(hp) and float(hp) < 0 and not _na(r.get("home_covers_rl_prob"))
    ph15 = float(r["home_covers_rl_prob"]) if priced else None
    if priced:
        rl_ev, rl_pick, rl_odds = _best([(_ev(ph15, r.get("home_rl_odds")), f"{h} -1.5", r.get("home_rl_odds")),
                                         (_ev(1 - ph15, r.get("away_rl_odds")), f"{a} +1.5", r.get("away_rl_odds"))])
        rl_mod = f"{a} +1.5 {1 - ph15:.0%}<br>{h} -1.5 {ph15:.0%}"
    else:
        rl_ev, rl_pick, rl_odds, rl_mod = None, "", None, "home dog:<br>not priced"
    rl_mkt = ("-" if _na(hp) else
              f"{a} {-float(hp):+g} {_o(r.get('away_rl_odds'))}<br>{h} {float(hp):+g} {_o(r.get('home_rl_odds'))}")
    t2, m2 = _market("RUN LINE", rl_mkt, rl_mod, rl_ev, rl_pick, rl_odds)
    # first 5 (only when real F5 odds exist)
    t3, m3 = "", ""
    if not _na(r.get("home_f5_ml")) and not _na(r.get("away_f5_ml")):
        f5h = float(r["home_f5_win_prob"])
        f5_ev, f5_pick, f5_odds = _best([(_ev(f5h, r["home_f5_ml"]), f"{h} F5", r["home_f5_ml"]),
                                         (_ev(1 - f5h, r["away_f5_ml"]), f"{a} F5", r["away_f5_ml"])])
        t3, m3 = _market("FIRST 5", f"{a} {_o(r['away_f5_ml'])}<br>{h} {_o(r['home_f5_ml'])}",
                         f"{a} {1 - f5h:.0%}<br>{h} {f5h:.0%}", f5_ev, f5_pick, f5_odds)
    best = max((t1, t2, t3), key=lambda t: RANK[t])
    chips = []
    if not _na(r.get("total_line")):
        chips.append(f'<span class="chip">O/U {float(r["total_line"]):g}</span>')
    if not _na(r.get("park_factor")):
        pf = float(r["park_factor"])
        chips.append(f'<span class="chip {"hot" if pf >= 1.05 else "cold" if pf <= .95 else ""}">PARK {pf:.2f}</span>')
    if not _na(r.get("temp_f")):
        chips.append(f'<span class="chip">{float(r["temp_f"]):.0f}°F</span>')
    if not _na(r.get("wind_mph")):
        wb = float(r.get("wind_boost") or 0)
        chips.append(f'<span class="chip {"hot" if wb > .05 else "cold" if wb < -.05 else ""}">WIND {float(r["wind_mph"]):.0f} MPH</span>')
    return RANK[best], f"""
    <article class="card b-{best.lower() or 'none'}" data-g="all" data-play="{1 if best else 0}">
      <header class="meta"><span>{e(time_) or e(r.get('game_date'))}</span><span>PROJ {float(r['proj_total']):.1f} RUNS</span></header>
      {team('a')}{team('h')}
      <div class="wp"><div class="wplab"><span>{e(a)} {1 - hw:.0%}</span><span class="cap">WIN PROB</span><span>{e(h)} {hw:.0%}</span></div>
        <div class="wpbar"><i style="width:{(1 - hw) * 100:.1f}%;background:{ca}"></i><i style="width:{hw * 100:.1f}%;background:{ch}"></i></div></div>
      {m1}{m2}{m3}
      <div class="chips">{''.join(chips)}</div>
    </article>"""


def render_game_cards(df):
    day = str(df.game_date.iloc[0])
    cards = [_game_card(r) for r in df.to_dict("records")]
    n_play = sum(1 for rk, _ in cards if rk)
    n_strong = sum(1 for rk, _ in cards if rk == 3)
    body = "".join(c for _, c in cards)
    return (HEAD.format(title=f"AlgoHub MLB {day}", css=CSS) + f"""
  <div class="top"><div><div class="k">THE ALGOHUB · MLB GAME ALGO</div><h1>{_title(day)}</h1></div>
    <div class="stats"><div><small>GAMES</small><b>{len(df)}</b></div>
      <div class="p"><small>GAMES W/ PLAY</small><b>{n_play}</b></div><div class="h"><small>STRONG</small><b>{n_strong}</b></div></div></div>
  <div class="tabs"><button class="on" data-f="all">ALL</button><button data-f="plays">PLAYS ONLY</button></div>
  <div class="grid">{body}</div>
  <p class="foot">Edge = model win prob × payout − 1. LEAN 4%+ / SOLID 7%+ / STRONG 10%+. Not betting advice.</p>
</div>{TABS_JS}</body></html>""")


# ----------------------------------------------------------------- HR board
def _bar(label, v, cap):
    if _na(v):
        return ""
    w = max(0, min(float(v) / cap, 1)) * 100
    return f'<span class="bar">{label} <b>{float(v):.1f}%</b><i><em style="width:{w:.0f}%"></em></i></span>'


def render_hr_cards(data, top=30):
    day = data.get("date", "")
    rows = []
    for g in data.get("games", []):
        gkey = f"{g.get('away_team')} @ {g.get('home_team')}"
        for side, opp in (("home", "away"), ("away", "home")):
            for b in g.get(f"{side}_batters", []):
                rows.append(dict(b=b, team=g.get(f"{side}_team"), game=gkey, time=g.get("game_time", ""),
                                 vs=g.get(f"{opp}_pitcher"), vs_hand=g.get(f"{opp}_pitcher_hand", ""),
                                 park=g.get("park_factor"), wx=(g.get("weather") or {}).get("wind_label", "")))
    rows.sort(key=lambda x: (x["b"].get("hit_score") or 0, x["b"].get("proj_hr_pct") or 0), reverse=True)
    rows = rows[:top]
    games = list(dict.fromkeys(r["game"] for r in rows))
    items = []
    for i, r in enumerate(rows, 1):
        b = r["b"]
        g = str(b.get("grade", "")).upper()
        items.append(f"""
      <div class="hr {'top3' if i <= 3 else ''}" data-g="{e(r['game'])}" data-play="1">
        <div class="rk">{i}</div>{_badge(r['team'])}
        <div class="who"><b>{e(b.get('player_name'))}</b>
          <small>{e(b.get('position', ''))} · vs {e(r['vs'])} ({e(r['vs_hand'])}HP) · {e(r['game'])} · {e(r['time'])}<span class="wx">{e(r['wx'])}</span></small>
          <div class="bars">{_bar('HR', b.get('proj_hr_pct'), 35)}{_bar('BARREL', b.get('barrel_rate'), 30)}{_bar('HARD HIT', b.get('hard_hit_pct'), 70)}</div></div>
        <div class="sc"><span class="big">{float(b.get('hit_score') or 0):.1f}</span><span class="gr {GRADE_CLS.get(g, '')}">{e(g)}</span></div>
      </div>""")
    n_elite = sum(1 for r in rows if str(r["b"].get("grade", "")).upper() == "ELITE")
    tabs = "".join(f'<button data-f="{e(gm)}">{e(gm)}</button>' for gm in games)
    return (HEAD.format(title=f"AlgoHub HR {day}", css=CSS) + f"""
  <div class="top"><div><div class="k">THE ALGOHUB · HOME RUN MODEL</div><h1>{_title(day) if day else 'TODAY'}</h1></div>
    <div class="stats"><div><small>GAMES</small><b>{len(data.get('games', []))}</b></div>
      <div class="h"><small>ELITE</small><b>{n_elite}</b></div></div></div>
  <div class="tabs"><button class="on" data-f="all">TOP {len(rows)}</button>{tabs}</div>
  <div class="board">{''.join(items)}</div>
  <p class="foot">HIT score blends barrel %, hard-hit %, xwOBA, launch angle, pitch-type matchup, platoon, park and weather. HR % = projected chance to homer. Not betting advice.</p>
</div>{TABS_JS.replace("c.dataset.g!==f", "c.dataset.g!==f")}</body></html>""")
