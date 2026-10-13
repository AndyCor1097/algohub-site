"""The top-of-site board: today's best plays across every sport, plus the site's look (CSS).
Reads the same data/ files the tabs use. Any sport that can't be read is just skipped."""
import html
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

TOP = {"HAMMER": 3, "STRONG": 3, "PLAY": 2, "SOLID": 2, "EDGE": 2, "LEAN": 1}
e = lambda s: html.escape(str(s)) if s is not None and not (isinstance(s, float) and math.isnan(s)) else ""


def _o(v):
    try:
        return f"{int(float(v)):+d}"
    except (TypeError, ValueError):
        return ""


def _latest(folder, pattern):
    fs = sorted(Path(folder).glob(pattern), key=lambda p: ("".join(c for c in p.stem if c.isdigit())))
    return fs[-1] if fs else None


def _fresh(path):
    """True when the file's date is today or later."""
    import re
    m = re.search(r"\d{4}-\d{2}-\d{2}", path.stem)
    return bool(m) and date.fromisoformat(m.group(0)) >= date.today()


def _nhl(data):
    f = _latest(data / "nhl", "nhl_*.csv")
    if not f or not _fresh(f):
        return []
    out = []
    for r in pd.read_csv(f).to_dict("records"):
        mu = f"{r['away_team']} at {r['home_team']}"
        for k, lab in (("ml", "ML"), ("pl", ""), ("tot", "")):
            t = r.get(f"{k}_tier")
            if isinstance(t, str) and t:
                pick = f"{r[k + '_pick']} {lab}".strip() if k != "ml" else f"{r['ml_pick']} ML"
                out.append(dict(sport="NHL", pick=pick, odds=_o(r.get(f"{k}_odds")), tier=t,
                                edge=float(r[f"{k}_edge"]), game=mu, when=r.get("start_et", "")))
    return out


def _nfl(data):
    f = _latest(data / "nfl", "2026_wk*.csv")
    if not f:
        return []
    out = []
    for r in pd.read_csv(f).to_dict("records"):
        if str(r.get("gameday", "")) < date.today().isoformat():
            continue
        mu = f"{r['away_team']} at {r['home_team']}"
        when = pd.Timestamp(r["gameday"]).strftime("%a")
        for k, lab in (("sp", "Spread"), ("tot", "Total")):
            t = r.get(f"{k}_tier")
            if isinstance(t, str) and t:
                out.append(dict(sport="NFL", pick=r[f"{k}_pick"], odds="-110", tier=t,
                                edge=float(r[f"{k}_edge"]), game=mu, when=when, unit="pts",
                                day=str(r.get("gameday", ""))[:10]))
    return out


def _cfb(data):
    f = _latest(data / "cfb", "predictions_week*.json")
    if not f:
        return []
    try:
        import sys
        sys.path.insert(0, str(data.parent))
        from cfb_cards import _spread_tier, _total_tier
    except Exception:
        return []
    out = []
    for g in json.loads(f.read_text(encoding="utf-8")).get("games", []):
        when_utc = g.get("commence_time") or g.get("start_date") or ""
        ct = str(when_utc)[:10]
        try:   # ET game day (kickoffs are stored in UTC)
            day = (pd.Timestamp(str(when_utc).replace("Z", "")) - pd.Timedelta(hours=4)).strftime("%Y-%m-%d")
        except Exception:
            day = "unknown"
        if ct and ct < (date.today() - timedelta(days=1)).isoformat():
            continue
        mu = f"{g['away_team']} at {g['home_team']}"
        se, te = g.get("spread_edge"), g.get("total_edge")
        if _spread_tier(se):
            side = g["home_team"] if se > 0 else g["away_team"]
            bs = g.get("book_spread")
            line = "" if bs is None else f" {(bs if se > 0 else -bs):+g}"
            out.append(dict(sport="CFB", pick=f"{side}{line}", odds="-110", tier=_spread_tier(se),
                            edge=abs(se), game=mu, when="", unit="pts", day=day))
        if _total_tier(te) and g.get("book_total") is not None:
            out.append(dict(sport="CFB", pick=f"{'Over' if te > 0 else 'Under'} {g['book_total']:g}", odds="-110",
                            tier=_total_tier(te), edge=abs(te), game=mu, when="", unit="pts", day=day))
    return out


def _mlb(data):
    f = _latest(data / "mlb", "all_games_*.csv")
    if not f or not _fresh(f):
        return []
    try:
        from mlb_cards import _ev, _tier
    except Exception:
        return []
    out = []
    for r in pd.read_csv(f).to_dict("records"):
        mu = f"{r['away_abb']} at {r['home_abb']}"
        hw = r["home_win_prob"]
        for p, o, pick in ((hw, r.get("home_ml"), f"{r['home_abb']} ML"), (1 - hw, r.get("away_ml"), f"{r['away_abb']} ML")):
            ev = _ev(p, o)
            if _tier(ev):
                out.append(dict(sport="MLB", pick=pick, odds=_o(o), tier=_tier(ev), edge=ev, game=mu, when=""))
        hp = r.get("home_rl")
        if not pd.isna(hp) and float(hp) < 0 and not pd.isna(r.get("home_covers_rl_prob")):
            ph = float(r["home_covers_rl_prob"])
            for p, o, pick in ((ph, r.get("home_rl_odds"), f"{r['home_abb']} -1.5"),
                               (1 - ph, r.get("away_rl_odds"), f"{r['away_abb']} +1.5")):
                ev = _ev(p, o)
                if _tier(ev):
                    out.append(dict(sport="MLB", pick=pick, odds=_o(o), tier=_tier(ev), edge=ev, game=mu, when=""))
    return out


def _cbb(data):
    f = _latest(data / "cbb", "cbb_*.csv")
    if not f or not _fresh(f):
        return []
    out = []
    for r in pd.read_csv(f).to_dict("records"):
        mu = f"{r['away_name']} at {r['home_name']}"
        for k in ("sp", "tot"):
            t = r.get(f"{k}_tier")
            if isinstance(t, str) and t:
                out.append(dict(sport="CBB", pick=r[f"{k}_pick"], odds="-110", tier=t, edge=abs(float(r[f"{k}_edge"])),
                                game=mu, when=r.get("start_et", ""), unit="pts"))
    return out


def _hr(data):
    f = _latest(data / "mlb_hr", "hr_*.json")
    if not f or not _fresh(f):
        return []
    d = json.loads(f.read_text(encoding="utf-8"))
    bats = [(b, g) for g in d.get("games", []) for s in ("home", "away") for b in g.get(f"{s}_batters", [])]
    bats.sort(key=lambda x: x[0].get("hit_score") or 0, reverse=True)
    return [dict(sport="HR", pick=b["player_name"], odds="", tier="HR", edge=b.get("hit_score") or 0,
                 game=f"{g['away_team']} at {g['home_team']}", when=g.get("game_time", "").replace(" ET", ""),
                 unit="hit", proj=b.get("proj_hr_pct")) for b, g in bats[:2]]


def collect(data: Path):
    plays, counts = [], {}
    for fn in (_nfl, _cfb, _cbb, _nhl, _mlb, _hr):
        try:
            p = fn(data)
        except Exception:
            p = []
        # the board is TODAY only: football plays for later in the week stay on their own tabs
        p = [x for x in p if not x.get("day") or x["day"] == date.today().isoformat()]
        if p:
            counts[p[0]["sport"]] = len(p)
            if any(x.get("day") == date.today().isoformat() for x in p):
                counts[p[0]["sport"] + "_today"] = 1
        plays += p
    return plays, counts


def board_html(plays, counts):
    games = [p for p in plays if p["sport"] != "HR"]
    # best 2 per sport, tonight's sports first, so one sport can't take over the board
    by = {}
    for p in sorted(games, key=lambda p: (TOP.get(p["tier"], 0), p["edge"]), reverse=True):
        by.setdefault(p["sport"], []).append(p)
    order = ["CBB", "NHL", "MLB", "NFL", "CFB"]
    top = [p for rnd in range(2) for sp in order for p in by.get(sp, [])[rnd:rnd + 1]]
    top += [p for p in plays if p["sport"] == "HR"][:2]
    today = date.today()
    n = len(games)
    head = f"""
<header class="ah-hero">
  <div class="ah-mark"><span>The</span>AlgoHub</div>
  <div class="ah-today"><b>{today.strftime('%A, %B')} {today.day}</b>
    <span>{n} play{'s' if n != 1 else ''} on the board across {len([s for s in counts if s != 'HR' and not s.endswith('_today')])} sports</span></div>
</header>"""
    if not top:
        return head + '<p class="ah-empty">No plays posted yet today. Picks land each morning around 11.</p>'
    slips = []
    for p in top:
        rank = TOP.get(p["tier"], 0)
        cls = {3: "s-top", 2: "s-mid", 1: "s-low"}.get(rank, "s-hr")
        if p["sport"] == "HR":
            stat = f'<em>{p["edge"]:.0f}</em><small>hit score</small>'
            tier = "Home run"
            sub = f"{e(p['game'])}" + (f", {e(p.get('proj'))}% to homer" if p.get("proj") else "")
        else:
            stat = (f'<em>+{p["edge"]:.1f}</em><small>{"pts edge" if p.get("unit") == "pts" else "% edge"}</small>')
            tier = p["tier"].title()
            sub = e(p["game"]) + (f", {e(p['when'])}" if p.get("when") else "")
        live_attrs = ("" if p["sport"] == "HR" else
                      f' data-sport="{e(p["sport"])}" data-pick="{e(p["pick"])}" data-game="{e(p["game"])}"')
        slips.append(f"""
  <div class="ah-slip {cls}"{live_attrs}>
    <div class="ah-slip-top"><span class="ah-sport">{e(p['sport'])}</span><span class="ah-tier">{e(tier)}</span></div>
    <div class="ah-pick">{e(p['pick'])}<span>{e(p['odds'])}</span></div>
    <div class="ah-sub">{sub}</div>
    <div class="ah-stat">{stat}</div>
  </div>""")
    return head + f'<section class="ah-board" aria-label="Top plays today">{"".join(slips)}</section>'


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800;900&family=Archivo:wght@400;500;600;700&display=swap');
:root{--ink:#0b0e13;--panel:#121821;--rule:#232c39;--chalk:#eef2f6;--dim:#8792a2;
      --amber:#f2b134;--turf:#3fb950;--ice:#58a6ff;--red:#f85149}
html,body,.stApp{background:var(--ink)!important}
.stApp{background:
  radial-gradient(1200px 380px at 50% -140px, rgba(242,177,52,.10), transparent 70%),
  var(--ink)!important}
[data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer,.stDeployButton,[data-testid="stDecoration"]{display:none!important}
.block-container{padding-top:1.4rem!important;max-width:1240px}
html,body,[class*="st-"],.stMarkdown,p,div,span,label{font-family:Archivo,system-ui,sans-serif}

/* hero */
.ah-hero{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;
  padding:6px 0 18px;border-bottom:1px solid var(--rule)}
.ah-mark{font:900 clamp(56px,9vw,104px)/.82 "Big Shoulders Display",sans-serif;color:var(--chalk);letter-spacing:-.01em}
.ah-mark span{display:block;font-size:.3em;font-weight:600;color:var(--amber);letter-spacing:.02em;line-height:1.1}
.ah-today{text-align:right;color:var(--dim);font-size:14px;line-height:1.5}
.ah-today b{display:block;color:var(--chalk);font:800 28px/1 "Big Shoulders Display",sans-serif;margin-bottom:4px}
.ah-empty{color:var(--dim);padding:18px 0}

/* the board: bet slips */
.ah-board{display:flex;gap:12px;overflow-x:auto;padding:18px 2px 22px;scroll-snap-type:x mandatory;scrollbar-width:thin}
.ah-slip{flex:0 0 212px;scroll-snap-align:start;position:relative;background:var(--panel);border:1px solid var(--rule);
  border-radius:12px;padding:12px 14px 12px;display:flex;flex-direction:column;gap:4px;
  -webkit-mask:radial-gradient(circle 7px at 0 62%,transparent 98%,#000) left/51% 100% no-repeat,
                radial-gradient(circle 7px at 100% 62%,transparent 98%,#000) right/51% 100% no-repeat;
          mask:radial-gradient(circle 7px at 0 62%,transparent 98%,#000) left/51% 100% no-repeat,
                radial-gradient(circle 7px at 100% 62%,transparent 98%,#000) right/51% 100% no-repeat}
.ah-slip-top{display:flex;justify-content:space-between;font-size:12px;color:var(--dim)}
.ah-sport{font-weight:700;color:var(--chalk)}
.ah-tier{font-weight:600}
.ah-pick{font:800 26px/1.05 "Big Shoulders Display",sans-serif;color:var(--chalk);margin-top:2px}
.ah-pick span{font:600 15px Archivo,sans-serif;color:var(--dim);margin-left:8px;vertical-align:3px}
.ah-sub{font-size:12px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  padding-bottom:8px;border-bottom:1px dashed var(--rule)}
.ah-stat{display:flex;align-items:baseline;gap:6px;padding-top:4px}
.ah-stat em{font:800 24px "Big Shoulders Display",sans-serif;font-style:normal}
.ah-stat small{font-size:12px;color:var(--dim)}
.s-top{background:linear-gradient(180deg,rgba(242,177,52,.16),var(--panel) 60%);border-color:rgba(242,177,52,.45)}
.s-top .ah-tier,.s-top .ah-stat em{color:var(--amber)}
.s-mid .ah-tier,.s-mid .ah-stat em{color:var(--turf)}
.s-low .ah-tier,.s-low .ah-stat em{color:var(--ice)}
.s-hr .ah-tier,.s-hr .ah-stat em{color:#ff8a5c}

/* sport tabs = scoreboard */
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--rule);background:transparent}
.stTabs [data-baseweb="tab"]{font:800 22px "Big Shoulders Display",sans-serif!important;color:var(--dim);
  padding:10px 16px 8px!important;background:transparent;border-radius:8px 8px 0 0;height:auto}
.stTabs [data-baseweb="tab"] p{font:inherit!important;letter-spacing:.02em;white-space:nowrap}
.stTabs [data-baseweb="tab-list"]{overflow-x:auto;scrollbar-width:none}
.stTabs [data-baseweb="tab"]:hover{color:var(--chalk);background:rgba(255,255,255,.03)}
.stTabs [aria-selected="true"]{color:var(--chalk)!important}
.stTabs [data-baseweb="tab-highlight"]{background:var(--amber)!important;height:3px}
.stTabs [data-baseweb="tab-border"]{display:none}
/* inner tabs (Cards / Best Bets / Record) stay small */
.stTabs .stTabs [data-baseweb="tab"]{font:600 14px Archivo,sans-serif!important;padding:6px 12px!important}
.stTabs .stTabs [data-baseweb="tab-highlight"]{background:var(--chalk)!important;height:2px}

/* metrics, tables, notes */
[data-testid="stMetric"]{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:12px 16px}
[data-testid="stMetricLabel"] p{color:var(--dim)!important;font-size:13px!important}
[data-testid="stMetricValue"]{font:800 34px "Big Shoulders Display",sans-serif!important;color:var(--chalk)}
[data-testid="stDataFrame"]{border:1px solid var(--rule);border-radius:12px;overflow:hidden}
[data-testid="stAlert"]{background:var(--panel)!important;border:1px solid var(--rule)!important;border-radius:12px;color:var(--dim)}
[data-testid="stSelectbox"] [data-baseweb="select"]>div{background:var(--panel);border-color:var(--rule);border-radius:10px}
iframe{border-radius:14px}
.ah-foot{color:var(--dim);font-size:12px;border-top:1px solid var(--rule);margin-top:28px;padding-top:14px;
  display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
.ah-foot a{color:var(--chalk);text-decoration:none;font-weight:600}
@media (max-width:640px){.ah-today{text-align:left}.stTabs [data-baseweb="tab"]{font-size:19px!important;padding:8px 10px 6px!important}}
@media (prefers-reduced-motion:reduce){.ah-board{scroll-behavior:auto}}
</style>
"""

FOOT = """<div class="ah-foot"><span>Model picks for entertainment. Not betting advice.</span>
<span>@TheAlgoHub</span></div>"""
