"""
build_site.py: turns data/ into a real website in public/ (no Streamlit, never sleeps).

  python build_site.py        -> rebuilds public/
  preview.bat                 -> opens it at http://localhost:8000 on your PC

sync.py runs this automatically at the end, so update_site.bat and every algo auto-run
rebuild the site before they push. Vercel serves the public/ folder.
"""
import html
import json
import math
import re
import shutil
import sys
import traceback
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "public"
sys.path.insert(0, str(ROOT))

from board import CSS as BOARD_CSS, board_html, collect  # noqa: E402
import ticker  # noqa: E402

SITE_NAME = "The AlgoHub"
SLATES_KEPT = 14          # how many past slates per sport get their own page
TIER_RANK = {"HAMMER": 3, "STRONG": 3, "PLAY": 2, "SOLID": 2, "EDGE": 2, "LEAN": 1}
ON_HOLD = {"nba": "NBA picks start when the season tips off."}

SPORTS = [  # slug, tab label, board key
    ("nfl", "NFL", "NFL"), ("cfb", "CFB", "CFB"), ("nhl", "NHL", "NHL"), ("mlb", "MLB", "MLB"),
    ("hr", "Home Runs", "HR"), ("cbb", "CBB", "CBB"), ("nba", "NBA", None),
]
e = lambda s: html.escape(str(s)) if s is not None and not (isinstance(s, float) and math.isnan(s)) else ""


# ------------------------------------------------------------------ helpers
def files_for(sport, pattern="*"):
    folder = DATA / sport
    if not folder.exists():
        return []

    def key(p):
        d = "".join(c for c in p.stem if c.isdigit())
        return (len(d), d)
    return sorted(folder.glob(pattern), key=key, reverse=True)


def label_from(path):
    s = path.stem
    m = re.search(r"wk(\d+)", s) or re.search(r"week(\d+)", s)
    if m:
        return f"Week {int(m.group(1))}"
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return pd.to_datetime(m.group(0)).strftime("%a %b %-d" if sys.platform != "win32" else "%a %b %#d") if m else s


def slug_from(path):
    s = path.stem
    m = re.search(r"wk(\d+)", s) or re.search(r"week(\d+)", s)
    if m:
        return f"week-{int(m.group(1))}"
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else s


def odds(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return ""
    return "" if pd.isna(x) else (f"+{x:.0f}" if x > 0 else f"{x:.0f}")


def table(df, tier_col="Tier"):
    if df is None or df.empty:
        return note("Nothing here yet.")
    head = "".join(f"<th>{e(c)}</th>" for c in df.columns)
    rows = []
    for r in df.itertuples(index=False):
        cells = []
        for c, v in zip(df.columns, r):
            if c == tier_col and isinstance(v, str) and v:
                cells.append(f'<td><span class="tg tg-{TIER_RANK.get(v.upper(), 0)}">{e(v.title())}</span></td>')
            else:
                cells.append(f"<td>{e(v)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f'<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def tiles(pairs):
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><small>{e(k)}</small><b>{e(v)}</b></div>' for k, v in pairs) + "</div>"


def note(msg):
    return f'<p class="note">{e(msg)}</p>'


def record_tiles(w, l, p, units=None):
    pairs = [("Record", f"{w}-{l}-{p}"), ("Win rate", f"{w / max(w + l, 1):.1%}")]
    if units is not None:
        pairs += [("Units", f"{units:+.2f}"), ("ROI", f"{units / max(w + l, 1):+.1%}")]
    return tiles(pairs)


def units_chart(series):
    """Cumulative units line as inline SVG."""
    s = list(series)
    if len(s) < 2:
        return ""
    W, H, P = 900, 220, 28
    lo, hi = min(0, min(s)), max(0, max(s))
    span = (hi - lo) or 1
    xs = [P + i * (W - 2 * P) / (len(s) - 1) for i in range(len(s))]
    ys = [H - P - (v - lo) / span * (H - 2 * P) for v in s]
    zero = H - P - (0 - lo) / span * (H - 2 * P)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    col = "#3fb950" if s[-1] >= 0 else "#f85149"
    return f"""<figure class="chart"><figcaption>Units over the season, {s[-1]:+.2f} so far</figcaption>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="Cumulative units, now {s[-1]:+.2f}">
<line x1="{P}" x2="{W - P}" y1="{zero:.1f}" y2="{zero:.1f}" stroke="#2a3443" stroke-dasharray="4 4"/>
<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3" stroke-linejoin="round"/>
<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="5" fill="{col}"/></svg></figure>"""


def cards_frame(path_rel, title):
    return (f'<iframe class="cards" src="/{path_rel}" title="{e(title)}" loading="lazy" '
            f'onload="fit(this)"></iframe>')


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def stale(path, days=1):
    m = re.search(r"\d{4}-\d{2}-\d{2}", path.stem)
    if m and (date.today() - date.fromisoformat(m.group(0))).days >= days:
        return note(f"No new slate yet. This is the last run ({label_from(path)}).")
    return ""


# ------------------------------------------------------------------ sports
# each returns: list of (pane name, html)
def nfl(f):
    from nfl_cards import render_cards
    picks = pd.read_csv(f)
    season, week = int(picks.season.iloc[0]), int(picks.week.iloc[0])
    pf = DATA / "nfl_props" / f"props_{season}_wk{week:02d}.csv"
    props = pd.read_csv(pf) if pf.exists() else None
    card_rel = f"cards/nfl_{slug_from(f)}.html"
    write(card_rel, render_cards(picks, season, week, props))

    rows = []
    for _, r in picks.iterrows():
        mu = f"{r.away_team} @ {r.home_team}"
        if isinstance(r.sp_tier, str) and r.sp_tier:
            rows.append(dict(Matchup=mu, Day=r.gameday, Market="Spread", Pick=r.sp_pick, Tier=r.sp_tier,
                             Edge=round(r.sp_edge, 1), Vegas=r.market_line, Model=r.model_line))
        if isinstance(r.tot_tier, str) and r.tot_tier:
            rows.append(dict(Matchup=mu, Day=r.gameday, Market="Total", Pick=r.tot_pick, Tier=r.tot_tier,
                             Edge=round(r.tot_edge, 1), Vegas=f"{r.total_line:g}", Model=f"{r.pred_total:.1f}"))
    if props is not None and not props.empty:
        for _, p in props[props.tier.fillna("") != ""].iterrows():
            g = picks[picks.game_id == p.game_id]
            mu = f"{g.away_team.iloc[0]} @ {g.home_team.iloc[0]}" if len(g) else p.team
            is_td = p.market == "atd"
            rows.append(dict(Matchup=mu, Day=g.gameday.iloc[0] if len(g) else "", Market=f"Prop: {p.label}",
                             Pick=f"{p.player} {'TD' if is_td else p.pick} ({odds(p.price)})", Tier=p.tier,
                             Edge=round(p.edge * 100, 1),
                             Vegas=odds(p.over_price) if is_td else f"{p.line:g}",
                             Model=f"{p.proj:.0%}" if is_td else f"{p.proj:.1f}"))
    if rows:
        bets = pd.DataFrame(rows)
        bets["_r"] = bets.Tier.map(TIER_RANK).fillna(0)
        bets = bets.sort_values(["_r", "Edge"], ascending=False).drop(columns="_r")
        best = tiles([("Hammers", int((bets.Tier == "HAMMER").sum())), ("Plays", int((bets.Tier == "PLAY").sum())),
                      ("Leans", int((bets.Tier == "LEAN").sum()))]) + table(bets)
    else:
        best = note("No plays clear the thresholds this week.")

    imgs = sorted((DATA / "nfl_posts").glob(f"{season}_wk{week:02d}_*.png"))
    if imgs:
        (OUT / "img").mkdir(parents=True, exist_ok=True)
        figs = []
        for im in imgs:
            shutil.copy2(im, OUT / "img" / im.name)
            figs.append(f'<figure class="post"><img src="/img/{im.name}" alt="Week {week} {im.stem.split("_")[-1]} graphic" loading="lazy">'
                        f'<a class="btn" href="/img/{im.name}" download>Download {e(im.stem.split("_")[-1])}</a></figure>')
        posts = f'<div class="posts">{"".join(figs)}</div>'
    else:
        posts = note("No post graphics for this week.")

    tp = DATA / "nfl_tracker.csv"
    if tp.exists():
        t = pd.read_csv(tp)
        t = t[t.season == t.season.max()]
        w, l, p = (t.result == "W").sum(), (t.result == "L").sum(), (t.result == "P").sum()
        agg = (t.groupby(["market", "tier"]).agg(W=("result", lambda x: (x == "W").sum()),
                                                  L=("result", lambda x: (x == "L").sum()),
                                                  P=("result", lambda x: (x == "P").sum()),
                                                  Units=("units", "sum")).reset_index())
        agg["Win %"] = (agg.W / (agg.W + agg.L).clip(lower=1)).map("{:.1%}".format)
        agg["Units"] = agg.Units.map("{:+.2f}".format)
        rec = (record_tiles(w, l, p, t.units.sum()) + units_chart(t.groupby("week").units.sum().cumsum())
               + table(agg.rename(columns={"market": "Market", "tier": "Tier"})))
    else:
        rec = note("Nothing graded yet.")
    return [("Cards", '<p class="hint">Tap Player Props on any game to open its props.</p>' + cards_frame(card_rel, f"NFL week {week}")),
            ("Best bets", best), ("Vs Novig", nfl_novig_html(season, week)),
            ("Matchups", nfl_matchups_html(season, week)), ("Posts", posts), ("Record", rec)]


def nfl_novig_html(season, week):
    return novig_html(DATA / "nfl_novig" / f"{season}_wk{week:02d}.csv")


def novig_html(f, min_edge=0.03):
    """Model vs Novig's exchange price for every main line (made by nfl_novig.py / nhl_novig.py)."""
    if not f.exists():
        return note("Novig prices for this slate aren't pulled yet. Run update_site.bat.")
    d = pd.read_csv(f)
    pct = lambda s: s.map(lambda v: "" if pd.isna(v) else f"{v:.1%}")
    view = lambda x: pd.DataFrame({
        "Matchup": x.matchup, "Market": x.market, "Side": x.side, "Model": pct(x.model),
        "Novig fair": pct(x.novig_fair), "Buy at": pct(x.novig_ask),
        "Edge": x.edge.map(lambda v: "" if pd.isna(v) else f"{v * 100:+.1f}"),
        "Available": x.ask_qty.map(lambda q: f"${q:,.0f}" if q else "")})
    plays = d[d.edge >= min_edge].sort_values("edge", ascending=False)
    intro = ('<p class="hint">Novig is a betting exchange with no vig, so its price is the sharp number. '
             '<b>Buy at</b> is the cheapest price on Novig right now; <b>Edge</b> = your model minus that, in points. '
             '<b>Available</b> = max payout sitting at that price. Spread and total model % come from the projected '
             'margin/total.</p>')
    top = (tiles([("Sides beating Novig", len(plays)), ("Best edge", f"{plays.edge.max() * 100:+.1f}" if len(plays) else "-")])
           + table(view(plays)) if len(plays) else note(f"No side beats Novig by {min_edge:.0%} or more right now."))
    return intro + top + '<h3 class="sub">Every main line</h3>' + table(view(d.sort_values(["matchup", "market", "side"])))


# ---- NFL matchups: what each defense allows to WR1/WR2/TE1/RB1..., ranked 1-32 (made by nfl_matchups.py)
MU_STATS = [("tgt", "Tgt"), ("rec", "Rec"), ("rec_yds", "Rec yds"), ("rush_yds", "Rush yds"), ("td", "TD"), ("ppr", "PPR")]


def _mu_cell(val, rk, show_rank=False):
    """Cell shaded by rank: 1 = defense gives up the most (green), 32 = shuts it down (red)."""
    if rk is None or (isinstance(rk, float) and math.isnan(rk)):
        return f"<td>{val:.1f}</td>"
    t = (float(rk) - 1) / 31
    bg = (f"rgba(63,185,80,{0.5 * (1 - t / .5):.2f})" if t <= .5 else f"rgba(248,81,73,{0.5 * ((t - .5) / .5):.2f})")
    txt = f"{val:.1f}" + (f' <small class="rk">{int(rk)}</small>' if show_rank else "")
    return f'<td style="background:{bg}" title="Rank {int(rk)} of 32">{txt}</td>'


def nfl_matchups_html(season, week):
    f = DATA / "nfl_matchups" / f"{season}_wk{week:02d}.json"
    if not f.exists():
        return note("Matchups for this week aren't built yet. Run update_site.bat.")
    d = json.loads(f.read_text(encoding="utf-8"))
    head = "".join(f"<th>{lab}</th>" for _, lab in MU_STATS)
    out = ['<p class="hint">What each defense allows per game to the role, ranked 1-32 (1 = gives up the most). '
           '<span class="mu-key g">soft matchup</span> <span class="mu-key r">tough matchup</span> '
           'Player rows are his season per-game line, shaded by what this defense allows to his role. Tap a game to open it.</p>']
    for i, g in enumerate(d["games"]):
        sides = []
        for s in g["sides"]:
            al = "".join(f'<tr><td><b>{e(a["group"])}</b></td>'
                         + "".join(_mu_cell(a[k], a.get(f"{k}_rk"), True) for k, _ in MU_STATS) + "</tr>"
                         for a in s["allowed"])
            pl = "".join(f'<tr><td class="mu-role">{e(p["role"])}</td><td>{e(p["player"])}'
                         + (f' <span class="mu-tag">{e(p["tag"])}</span>' if p["tag"] else "")
                         + f'</td><td>{p["gp"]}</td>'
                         + "".join(_mu_cell(p[k], p.get(f"{k}_rk")) for k, _ in MU_STATS) + "</tr>"
                         for p in s["players"])
            sides.append(
                f'<h4 class="mu-h">{e(s["offense"])} offense vs {e(s["defense"])} defense</h4>'
                f'<p class="hint">{e(s["defense"])} allows per game ({s["def_gp"]} GP), rank in small print</p>'
                f'<div class="tbl"><table><thead><tr><th>Vs</th>{head}</tr></thead><tbody>{al}</tbody></table></div>'
                f'<p class="hint">{e(s["offense"])} players, season per game</p>'
                f'<div class="tbl"><table><thead><tr><th>Role</th><th>Player</th><th>GP</th>{head}</tr></thead>'
                f'<tbody>{pl}</tbody></table></div>')
        when = " ".join(x for x in (str(g.get("day") or ""), str(g.get("time") or "")) if x)
        out.append(f'<details class="mu"{" open" if i == 0 else ""}><summary><b>{e(g["matchup"])}</b>'
                   f'<span>{e(when)}</span></summary>{"".join(sides)}</details>')
    return "".join(out)


def cfb(f):
    from cfb_cards import render_cards, _spread_tier, _total_tier
    data = json.loads(f.read_text(encoding="utf-8"))
    games, week = data.get("games", []), data.get("week")
    card_rel = f"cards/cfb_{slug_from(f)}.html"
    write(card_rel, render_cards(games, week, data.get("generated", "")))
    rows = []
    for g in games:
        mu = f"{g['away_team']} @ {g['home_team']}"
        se, te = g.get("spread_edge"), g.get("total_edge")
        s_t, t_t = _spread_tier(se), _total_tier(te)
        if s_t:
            rows.append(dict(Matchup=mu, Market="Spread", Pick=f"{'Home' if se > 0 else 'Away'} {abs(se):.1f} pts",
                             Tier=s_t, Edge=round(se, 1),
                             Book=f"{g['book_spread']:+.1f}" if g.get("book_spread") is not None else "-",
                             Model=f"{g['pred_margin']:+.1f}" if g.get("pred_margin") is not None else "-"))
        if t_t:
            rows.append(dict(Matchup=mu, Market="Total", Pick=f"{'Over' if te > 0 else 'Under'} {abs(te):.1f}",
                             Tier=t_t, Edge=round(te, 1),
                             Book=f"{g['book_total']:.1f}" if g.get("book_total") is not None else "-",
                             Model=f"{g['pred_total']:.1f}" if g.get("pred_total") is not None else "-"))
    if rows:
        bets = pd.DataFrame(rows)
        bets["_r"] = bets.Tier.map(TIER_RANK).fillna(0)
        bets = bets.sort_values(["_r", "Edge"], ascending=False).drop(columns="_r")
        best = tiles([("Strong", int((bets.Tier == "STRONG").sum())), ("Edge", int((bets.Tier == "EDGE").sum())),
                      ("Lean", int((bets.Tier == "LEAN").sum()))]) + table(bets)
    else:
        best = note("No plays clear the thresholds this week.")
    tp = DATA / "cfb_tracker.json"
    tr = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
    sp = tr.get("overall", {}).get("spread", {})
    if sp.get("W", 0) + sp.get("L", 0):
        rec = record_tiles(sp.get("W", 0), sp.get("L", 0), sp.get("P", 0))
        rec += table(pd.DataFrame([{"Market": m.upper(), "W": v.get("W", 0), "L": v.get("L", 0), "P": v.get("P", 0),
                                    "Win %": f"{v.get('pct', 0):.1f}%"} for m, v in tr.get("overall", {}).items()]))
        bw = tr.get("by_week", [])
        if isinstance(bw, list) and bw:
            rec += table(pd.DataFrame([{"Week": x.get("week"), "W": (x.get("spread") or {}).get("W", 0),
                                        "L": (x.get("spread") or {}).get("L", 0),
                                        "Win %": f"{(x.get('spread') or {}).get('pct', 0):.1f}%"}
                                       for x in sorted(bw, key=lambda x: x.get("week", 0))]))
    else:
        rec = note("Nothing graded yet.")
    return [("Cards", cards_frame(card_rel, f"CFB week {week}")), ("Best bets", best),
            ("Vs Novig", novig_html(DATA / "cfb_novig" / f"cfb_week{week}.csv")), ("Record", rec)]


def nhl(f):
    from nhl_cards import render_cards
    g = pd.read_csv(f)
    card_rel = f"cards/nhl_{slug_from(f)}.html"
    write(card_rel, render_cards(g, str(g.date.iloc[0])))
    rows = []
    for _, r in g.iterrows():
        mu = f"{r.away_team} @ {r.home_team}"
        for k, mk in (("ml", "Moneyline"), ("pl", "Puck line"), ("tot", "Total")):
            t = r.get(f"{k}_tier")
            if isinstance(t, str) and t:
                pick = f"{r.ml_pick} ML" if k == "ml" else r[f"{k}_pick"]
                model = f"{r[f'{k}_model']:.0%}" + (f", proj {r.pred_total:.1f}" if k == "tot" else "")
                rows.append(dict(Time=r.start_et, Matchup=mu, Market=mk, Pick=pick, Odds=odds(r[f"{k}_odds"]),
                                 Tier=t, **{"Edge %": round(r[f"{k}_edge"], 1)}, Model=model))
    if rows:
        bets = pd.DataFrame(rows)
        bets["_r"] = bets.Tier.map(TIER_RANK).fillna(0)
        bets = bets.sort_values(["_r", "Edge %"], ascending=False).drop(columns="_r")
        best = tiles([("Hammers", int((bets.Tier == "HAMMER").sum())), ("Plays", int((bets.Tier == "PLAY").sum())),
                      ("Leans", int((bets.Tier == "LEAN").sum()))]) + table(bets)
    else:
        best = note("No plays clear the thresholds today.")
    allg = pd.DataFrame({
        "Time": g.start_et, "Matchup": g.away_team + " @ " + g.home_team,
        "Proj score": g.away_team + " " + g.proj_away.round(1).astype(str) + ", " + g.home_team + " " + g.proj_home.round(1).astype(str),
        "Home win %": (g.home_wp * 100).round(1), "OT %": (g.p_ot * 100).round(1),
        "Proj total": g.pred_total.round(2), "O/U": g.total_line,
        "Fair ML": g.away_team + " " + g.fair_ml_away.map(odds) + " / " + g.home_team + " " + g.fair_ml_home.map(odds)})
    best += '<h3 class="sub">Every game</h3>' + table(allg)
    tp = DATA / "nhl_tracker.csv"
    if tp.exists():
        t = pd.read_csv(tp)
        w, l, p = (t.result == "W").sum(), (t.result == "L").sum(), (t.result == "P").sum()
        agg = (t.groupby(["market", "tier"]).agg(W=("result", lambda x: (x == "W").sum()),
                                                  L=("result", lambda x: (x == "L").sum()),
                                                  P=("result", lambda x: (x == "P").sum()),
                                                  Units=("units", "sum")).reset_index())
        agg["Win %"] = (agg.W / (agg.W + agg.L).clip(lower=1)).map("{:.1%}".format)
        agg["Units"] = agg.Units.map("{:+.2f}".format)
        rec = (record_tiles(w, l, p, t.units.sum()) + units_chart(t.groupby("date").units.sum().cumsum())
               + table(agg.rename(columns={"market": "Market", "tier": "Tier"})))
    else:
        rec = note("Nothing graded yet. Results show up the morning after the first slate.")
    return [("Cards", stale(f) + cards_frame(card_rel, "NHL cards")), ("Best bets", best),
            ("Vs Novig", novig_html(DATA / "nhl_novig" / f.name)), ("Record", rec)]


def mlb(f):
    from mlb_cards import render_game_cards
    g = pd.read_csv(f)
    card_rel = f"cards/mlb_{slug_from(f)}.html"
    write(card_rel, render_game_cards(g))
    fav = g.home_win_prob >= 0.5
    tab = pd.DataFrame({
        "Matchup": g.away_abb + " @ " + g.home_abb,
        "Starters": g.away_starter_name.fillna("TBD") + " vs " + g.home_starter_name.fillna("TBD"),
        "Proj score": g.proj_score, "O/U": g.total_line, "Model side": g.home_abb.where(fav, g.away_abb),
        "Win %": (g[["home_win_prob", "away_win_prob"]].max(axis=1) * 100).round(1),
        "Home ML": g.home_ml.map(odds), "Away ML": g.away_ml.map(odds)})
    return [("Cards", stale(f) + cards_frame(card_rel, "MLB cards")), ("Table", table(tab))]


def hr(f):
    from mlb_cards import render_hr_cards
    d = json.loads(f.read_text(encoding="utf-8"))
    card_rel = f"cards/hr_{slug_from(f)}.html"
    write(card_rel, render_hr_cards(d, top=30))
    return [("Top bats", stale(f) + cards_frame(card_rel, "Home run board"))]


def cbb(f):
    from cbb_cards import render_cards
    g = pd.read_csv(f)
    card_rel = f"cards/cbb_{slug_from(f)}.html"
    write(card_rel, render_cards(g, str(g.day.iloc[0])))
    rows = []
    for _, r in g.iterrows():
        mu = f"{r.away_name} @ {r.home_name}"
        if isinstance(r.sp_tier, str) and r.sp_tier:
            rows.append(dict(Time=r.start_et, Matchup=mu, Market="Spread", Pick=r.sp_pick, Tier=r.sp_tier,
                             Edge=round(abs(r.sp_edge), 1), Book=f"{r.spread:+g}", Model=f"{-r.pred_margin:+.1f}"))
        if isinstance(r.tot_tier, str) and r.tot_tier:
            rows.append(dict(Time=r.start_et, Matchup=mu, Market="Total", Pick=r.tot_pick, Tier=r.tot_tier,
                             Edge=round(abs(r.tot_edge), 1), Book=f"{r.total:g}", Model=f"{r.pred_total:.1f}"))
        if isinstance(r.ml_pick, str) and r.ml_pick:
            rows.append(dict(Time=r.start_et, Matchup=mu, Market="Moneyline", Pick=f"{r.ml_pick} {odds(r.ml_odds)}",
                             Tier="VALUE", Edge=round(r.ml_edge * 100, 1), Book=odds(r.ml_odds), Model=f"{max(r.home_wp, 1 - r.home_wp):.0%}"))
    if rows:
        bets = pd.DataFrame(rows)
        bets["_r"] = bets.Tier.map(TIER_RANK).fillna(0)
        bets = bets.sort_values(["_r", "Edge"], ascending=False).drop(columns="_r")
        best = tiles([("Hammers", int((bets.Tier == "HAMMER").sum())), ("Plays", int((bets.Tier == "PLAY").sum())),
                      ("Leans", int((bets.Tier == "LEAN").sum()))]) + table(bets)
    else:
        best = note("No plays clear the thresholds today.")
    tp = DATA / "cbb_tracker.csv"
    if tp.exists():
        t = pd.read_csv(tp)
        w, l, p = (t.result == "W").sum(), (t.result == "L").sum(), (t.result == "P").sum()
        agg = (t.groupby(["market", "tier"]).agg(W=("result", lambda x: (x == "W").sum()),
                                                  L=("result", lambda x: (x == "L").sum()),
                                                  P=("result", lambda x: (x == "P").sum()),
                                                  Units=("units", "sum")).reset_index())
        agg["Win %"] = (agg.W / (agg.W + agg.L).clip(lower=1)).map("{:.1%}".format)
        agg["Units"] = agg.Units.map("{:+.2f}".format)
        rec = (record_tiles(w, l, p, t.units.sum()) + units_chart(t.groupby("date").units.sum().cumsum())
               + table(agg.rename(columns={"market": "Market", "tier": "Tier"})))
    else:
        rec = note("Nothing graded yet. Results show up the morning after the first slate.")
    return [("Cards", stale(f) + cards_frame(card_rel, "CBB cards")), ("Best bets", best), ("Record", rec)]


def nba(f):
    t = pd.DataFrame(json.loads(f.read_text(encoding="utf-8")).get("top_overlays", []))
    if t.empty:
        return [("Props", note("No NBA props today."))]
    return [("Props", table(pd.DataFrame({"Player": t.player_name, "Game": t.game, "Stat": t.stat,
                                          "Proj": t.projection.round(1), "Line": t.line, "Pick": t.direction,
                                          "Edge %": t.edge_pct, "Odds": t.over_odds})))]


SOURCES = {  # slug -> (data folder, file pattern, builder, empty message)
    "nfl": ("nfl", "2026_wk*.csv", nfl, "NFL picks coming soon."),
    "cfb": ("cfb", "predictions_week*.json", cfb, "CFB picks coming soon."),
    "nhl": ("nhl", "nhl_*.csv", nhl, "NHL picks coming soon."),
    "mlb": ("mlb", "all_games_*.csv", mlb, "MLB picks coming soon."),
    "hr": ("mlb_hr", "hr_*.json", hr, "Home run picks coming soon."),
    "cbb": ("cbb", "cbb_*.csv", cbb, "College basketball picks start on opening day in early November."),
    "nba": ("nba", "nba_*.json", nba, "NBA picks start when the season tips off."),
}


# ------------------------------------------------------------------ page shell
SITE_CSS = """
<style>
body{margin:0;background:var(--ink);color:var(--chalk);font:15px/1.5 Archivo,system-ui,sans-serif}
.page{max-width:1240px;margin:0 auto;padding:22px 16px 40px}
a{color:inherit}
:focus-visible{outline:2px solid var(--amber);outline-offset:2px;border-radius:6px}
.sports{display:flex;gap:4px;border-bottom:1px solid var(--rule);overflow-x:auto;scrollbar-width:none;margin-top:6px}
.sports a{position:relative;font:800 22px "Big Shoulders Display",sans-serif;color:var(--dim);text-decoration:none;
  padding:10px 16px 9px;white-space:nowrap;border-radius:8px 8px 0 0}
.sports a:hover{color:var(--chalk);background:rgba(255,255,255,.03)}
.sports a[aria-current="page"]{color:var(--chalk)}
.sports a[aria-current="page"]::before{content:"";position:absolute;left:12px;right:12px;bottom:-1px;height:3px;background:var(--amber);border-radius:3px}
.sports a.live::after{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--amber);
  margin-left:7px;vertical-align:5px;animation:ahlive 2.4s ease-out infinite}
@keyframes ahlive{0%{box-shadow:0 0 0 0 rgba(242,177,52,.55)}70%,100%{box-shadow:0 0 0 7px rgba(242,177,52,0)}}
.bar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:14px 0 6px}
.panes{display:flex;gap:4px;border-bottom:1px solid var(--rule)}
.panes button{background:none;border:0;color:var(--dim);font:600 14px Archivo,sans-serif;padding:8px 12px;cursor:pointer;
  border-bottom:2px solid transparent;margin-bottom:-1px}
.panes button[aria-selected="true"]{color:var(--chalk);border-color:var(--chalk)}
.slate select{background:var(--panel);color:var(--chalk);border:1px solid var(--rule);border-radius:10px;
  padding:8px 34px 8px 12px;font:600 14px Archivo,sans-serif;appearance:none;cursor:pointer;
  background-image:linear-gradient(45deg,transparent 50%,var(--dim) 50%),linear-gradient(135deg,var(--dim) 50%,transparent 50%);
  background-position:calc(100% - 17px) 55%,calc(100% - 12px) 55%;background-size:5px 5px;background-repeat:no-repeat}
.pane{padding-top:14px} .pane[hidden]{display:none}
iframe.cards{width:100%;border:0;border-radius:14px;min-height:600px;display:block;background:var(--ink)}
.hint{color:var(--dim);font-size:13px;margin:0 0 8px}
.note{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:12px 16px;color:var(--dim);margin:0 0 12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}
.tile{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:12px 16px}
.tile small{display:block;color:var(--dim);font-size:13px}
.tile b{font:800 34px/1.1 "Big Shoulders Display",sans-serif}
.tbl{overflow-x:auto;border:1px solid var(--rule);border-radius:12px;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--dim);font-weight:600;font-size:12px;padding:10px 12px;background:var(--panel);
  position:sticky;top:0;white-space:nowrap}
td{padding:9px 12px;border-top:1px solid var(--rule);white-space:nowrap}
tbody tr:hover{background:rgba(255,255,255,.025)}
.tg{font-weight:700;font-size:12px;padding:3px 8px;border-radius:6px;color:#0b0e13}
.tg-3{background:var(--amber)} .tg-2{background:var(--turf)} .tg-1{background:var(--ice)} .tg-0{background:var(--dim)}
h3.sub{font:800 24px "Big Shoulders Display",sans-serif;margin:22px 0 10px}
.chart{margin:0 0 16px;background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:12px 14px}
.chart figcaption{color:var(--dim);font-size:13px;margin-bottom:6px} .chart svg{width:100%;height:auto;display:block}
.posts{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.post{margin:0;background:var(--panel);border:1px solid var(--rule);border-radius:12px;overflow:hidden}
.post img{width:100%;display:block}
.btn{display:block;text-align:center;padding:10px;font-weight:600;text-decoration:none;color:var(--ink);background:var(--amber)}
.ah-hero a{text-decoration:none}
details.mu{background:var(--panel);border:1px solid var(--rule);border-radius:12px;margin-bottom:10px;padding:0 14px}
details.mu summary{cursor:pointer;padding:12px 0;display:flex;justify-content:space-between;gap:10px;font-size:16px}
details.mu summary span{color:var(--dim);font-size:13px} details.mu[open] summary{border-bottom:1px solid var(--rule);margin-bottom:6px}
details.mu .tbl{background:var(--ink)} h4.mu-h{font:800 20px "Big Shoulders Display",sans-serif;margin:14px 0 2px}
.mu-role{font-weight:700;color:var(--dim)} .mu-tag{font-size:11px;font-weight:700;color:var(--ink);background:var(--dim);border-radius:4px;padding:1px 5px}
td small.rk{color:var(--dim);font-size:11px;margin-left:3px}
.mu-key{font-size:12px;font-weight:600;padding:1px 6px;border-radius:4px} .mu-key.g{background:rgba(63,185,80,.45)} .mu-key.r{background:rgba(248,81,73,.45)}
@media (prefers-reduced-motion:reduce){.sports a.live::after{animation:none}}
</style>"""

JS = """<script>
function fit(f){try{const d=f.contentDocument,set=()=>{f.style.height=(d.documentElement.scrollHeight+4)+'px'};
 set();new ResizeObserver(set).observe(d.body);}catch(e){f.style.height='2400px'}}
document.querySelectorAll('.panes button').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.panes button').forEach(x=>x.setAttribute('aria-selected',x===b));
 document.querySelectorAll('.pane').forEach(p=>p.hidden=p.id!==b.dataset.p);
 const fr=document.querySelector('#'+b.dataset.p+' iframe.cards'); if(fr) fit(fr);
 history.replaceState(null,'','#'+b.dataset.p);});
const h=location.hash.slice(1); const hb=h&&document.querySelector('.panes button[data-p="'+h+'"]'); if(hb) hb.click();
</script>"""


def _live_picks(plays):
    return [{"sport": p["sport"], "pick": p["pick"], "game": p["game"]} for p in plays if p["sport"] != "HR"]


def shell(current, body, plays, counts, live, title):
    nav = "".join(
        f'<a href="/{"" if s == "home" else s + "/"}" class="{"live" if s in live else ""}"'
        f'{" aria-current=page" if s == current else ""}>{e(lab)}</a>'
        for s, lab, _ in SPORTS)
    hero = board_html(plays, counts).replace(
        '<div class="ah-mark"><span>The</span>AlgoHub</div>',
        '<a href="/" class="ah-mark" aria-label="The AlgoHub home"><span>The</span>AlgoHub</a>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="Algorithmic picks for NFL, college football, NHL, MLB and home run props. Updated every morning.">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="Today's model picks across every sport.">
<meta name="theme-color" content="#0b0e13">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='14' fill='%230b0e13'/><text x='32' y='45' font-family='Arial Black,sans-serif' font-size='34' font-weight='900' text-anchor='middle' fill='%23f2b134'>A</text></svg>">
{BOARD_CSS}{SITE_CSS}{ticker.CSS}</head>
<body><div class="page">{ticker.HTML}{hero}
<nav class="sports" aria-label="Sports">{nav}</nav>
<main>{body}</main>
<footer class="ah-foot"><span>Model picks for entertainment. Not betting advice.</span><span>@TheAlgoHub</span></footer>
</div>{JS}{ticker.js(_live_picks(plays), sorted({k for k in counts if not k.endswith("_today") and k != "HR"}))}</body></html>"""


def sport_body(slug, f, others):
    panes = SOURCES[slug][2](f)
    pane_ids = [f"p-{re.sub(r'[^a-z]', '', n.lower())}" for n, _ in panes]
    btns = "".join(f'<button role="tab" data-p="{pid}" aria-selected="{"true" if i == 0 else "false"}">{e(n)}</button>'
                   for i, ((n, _), pid) in enumerate(zip(panes, pane_ids)))
    divs = "".join(f'<section class="pane" id="{pid}"{"" if i == 0 else " hidden"}>{h}</section>'
                   for i, ((_, h), pid) in enumerate(zip(panes, pane_ids)))
    opts = "".join(f'<option value="/{slug}/{slug_from(o)}.html"{" selected" if o == f else ""}>{e(label_from(o))}</option>'
                   for o in others)
    slate = (f'<label class="slate">Slate <select onchange="location=this.value" aria-label="Pick a slate">{opts}</select></label>'
             if len(others) > 1 else "")
    return f'<div class="bar"><div class="panes" role="tablist">{btns}</div>{slate}</div>{divs}'


def build():
    # clear old files one by one (OneDrive can lock a folder and break a full delete)
    OUT.mkdir(exist_ok=True)
    for f in sorted(OUT.rglob("*"), reverse=True):
        try:
            f.unlink() if f.is_file() else f.rmdir()
        except OSError:
            pass
    plays, counts = collect(DATA)
    live = {s for s, _, k in SPORTS if k and (
        (k in ("NFL", "CFB") and f"{k}_today" in counts) or (k not in ("NFL", "CFB") and k in counts))}
    for slug, label, _ in SPORTS:
        folder, pattern, _, empty = SOURCES[slug]
        files = files_for(folder, pattern)[:SLATES_KEPT]
        if slug in ON_HOLD or not files:
            body = note(ON_HOLD.get(slug, empty))
            write(f"{slug}/index.html", shell(slug, body, plays, counts, live, f"{label} picks | {SITE_NAME}"))
            continue
        for i, f in enumerate(files):
            try:
                body = sport_body(slug, f, files)
            except Exception as ex:
                traceback.print_exc()
                with open(ROOT / "build_error.txt", "a", encoding="utf-8") as lf:
                    lf.write(f"--- {slug} {f.name}\n{traceback.format_exc()}\n")
                body = note(f"Couldn't load {label} right now ({ex.__class__.__name__}).")
            page = shell(slug, body, plays, counts, live, f"{label} picks, {label_from(f)} | {SITE_NAME}")
            write(f"{slug}/{slug_from(f)}.html", page)
            if i == 0:
                write(f"{slug}/index.html", page)
    # home = the first sport with games today (else NFL), with the board on top
    first = next((s for s in ("cbb", "nhl", "mlb", "nfl", "cfb", "hr") if s in live), "nfl")
    home = (OUT / first / "index.html").read_text(encoding="utf-8")
    home = re.sub(r"<title>.*?</title>", f"<title>{SITE_NAME}: today's picks</title>", home, count=1)
    write("index.html", home)
    write("404.html", shell("", note("That page doesn't exist. Pick a sport above."), plays, counts, live,
                            f"Not found | {SITE_NAME}"))
    print(f"site built -> {OUT}  ({sum(1 for _ in OUT.rglob('*.html'))} pages)")


if __name__ == "__main__":
    try:
        build()
    except Exception:
        traceback.print_exc()
        (ROOT / "build_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        sys.exit(1)
