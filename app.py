"""
The AlgoHub: every algo, one site.
Each tab reads the files that sync.py copied into data/.
NFL + CFB cards use your own card designs (nfl_cards.py / cfb_cards.py, copied from your algo folders).
"""
import json
import math
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="The AlgoHub", page_icon="🎯", layout="wide")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# ---- flip a sport back on by deleting it from this list ----
ON_HOLD = {
    "NBA": "NBA picks start when the season tips off.",
}

CFB_CODE = None   # put a code in quotes here (like "Algohubfan1") to lock CFB again

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; max-width: 1240px;}
      [data-testid="stMetricValue"] {font-size: 1.9rem;}
      .stTabs [data-baseweb="tab"] {font-size: 1.05rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎯 The AlgoHub")
st.caption("Algorithmic predictions across every sport · @TheAlgoHub")


# ---------- helpers ----------
def files_for(sport, pattern="*"):
    folder = DATA / sport
    if not folder.exists():
        return []
    def key(p):
        digits = "".join(c for c in p.stem if c.isdigit())
        return (len(digits), digits)
    return sorted(folder.glob(pattern), key=key, reverse=True)


def label_from(path):
    s = path.stem
    m = re.search(r"wk(\d+)", s) or re.search(r"week(\d+)", s)
    if m:
        return f"Week {int(m.group(1))}"
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    return pd.to_datetime(m.group(0)).strftime("%a %b %d, %Y") if m else s


def pick_file(sport, pattern="*"):
    files = files_for(sport, pattern)
    if not files:
        return None
    labels = [label_from(f) for f in files]
    c1, _ = st.columns([1, 3])
    choice = c1.selectbox("Slate", labels, key=f"sel_{sport}", label_visibility="collapsed")
    return files[labels.index(choice)]


def stale_note(path, days=3):
    m = re.search(r"\d{4}-\d{2}-\d{2}", path.stem)
    if m and (date.today() - date.fromisoformat(m.group(0))).days > days:
        st.info(f"No new slate yet. Showing the last run ({label_from(path)}).")


def odds(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return ""
    if pd.isna(x):
        return ""
    return f"+{x:.0f}" if x > 0 else f"{x:.0f}"


def show(df):
    st.dataframe(df, use_container_width=True, hide_index=True)


def safe(render, name):
    """If one sport's files break, only that tab shows a warning, not the whole site."""
    try:
        render()
    except Exception as e:
        st.warning(f"Couldn't load {name} right now ({e.__class__.__name__}: {e}).")


def record_metrics(w, l, p, units=None):
    cols = st.columns(4 if units is not None else 2)
    cols[0].metric("Record", f"{w}-{l}-{p}")
    cols[1].metric("Win %", f"{w / max(w + l, 1):.1%}")
    if units is not None:
        cols[2].metric("Units", f"{units:+.2f}")
        cols[3].metric("ROI", f"{units / max(w + l, 1):+.1%}")


# ================= NFL =================
TIER_RANK = {"HAMMER": 3, "STRONG": 3, "PLAY": 2, "EDGE": 2, "LEAN": 1}


def render_nfl():
    f = pick_file("nfl")
    if not f:
        return st.info("NFL picks coming soon.")
    picks = pd.read_csv(f)
    season, week = int(picks.season.iloc[0]), int(picks.week.iloc[0])
    pf = DATA / "nfl_props" / f"props_{season}_wk{week:02d}.csv"
    props = pd.read_csv(pf) if pf.exists() else None

    t_cards, t_bets, t_posts, t_rec = st.tabs(["Cards", "Best Bets", "Posts", "Record"])

    with t_cards:
        from nfl_cards import render_cards
        height = 330 + picks.gameday.nunique() * 70 + math.ceil(len(picks) / 3) * 960
        st.caption("Tap **PLAYER PROPS** on any game to open its props.")
        components.html(render_cards(picks, season, week, props), height=height, scrolling=True)

    with t_bets:
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
                rows.append(dict(Matchup=mu, Day=g.gameday.iloc[0] if len(g) else "", Market=f"Prop · {p.label}",
                                 Pick=f"{p.player} {'TD' if is_td else p.pick} ({odds(p.price)})",
                                 Tier=p.tier, Edge=round(p.edge * 100, 1),
                                 Vegas=odds(p.over_price) if is_td else f"{p.line:g}",
                                 Model=f"{p.proj:.0%}" if is_td else f"{p.proj:.1f}"))
        if rows:
            bets = pd.DataFrame(rows)
            bets["_r"] = bets.Tier.map(TIER_RANK).fillna(0)
            bets = bets.sort_values(["_r", "Edge"], ascending=False).drop(columns="_r")
            m1, m2, m3 = st.columns(3)
            m1.metric("Hammers", int((bets.Tier == "HAMMER").sum()))
            m2.metric("Plays", int((bets.Tier == "PLAY").sum()))
            m3.metric("Leans", int((bets.Tier == "LEAN").sum()))
            show(bets)
        else:
            st.info("No plays clear the thresholds this week.")

    with t_posts:
        imgs = sorted((DATA / "nfl_posts").glob(f"{season}_wk{week:02d}_*.png"))
        if not imgs:
            st.info("No post graphics for this week.")
        else:
            cols = st.columns(min(len(imgs), 3))
            for i, img in enumerate(imgs):
                with cols[i % len(cols)]:
                    st.image(str(img), use_container_width=True)
                    st.download_button(f"Download {img.stem.split('_')[-1]}", img.read_bytes(),
                                       file_name=img.name, mime="image/png", key=img.name,
                                       use_container_width=True)

    with t_rec:
        tp = DATA / "nfl_tracker.csv"
        if not tp.exists():
            st.info("Nothing graded yet.")
        else:
            t = pd.read_csv(tp)
            t = t[t.season == t.season.max()]
            w, l, p = (t.result == "W").sum(), (t.result == "L").sum(), (t.result == "P").sum()
            record_metrics(w, l, p, t.units.sum())
            st.line_chart(t.groupby("week").units.sum().cumsum().rename("Cumulative units"))
            agg = (t.groupby(["market", "tier"])
                   .agg(W=("result", lambda x: (x == "W").sum()), L=("result", lambda x: (x == "L").sum()),
                        P=("result", lambda x: (x == "P").sum()), Units=("units", "sum")).reset_index())
            agg["Win %"] = (agg.W / (agg.W + agg.L).clip(lower=1)).map("{:.1%}".format)
            agg["Units"] = agg.Units.round(2)
            show(agg.rename(columns={"market": "Market", "tier": "Tier"}))


# ================= CFB =================
def render_cfb():
    if CFB_CODE and not st.session_state.get("cfb_ok"):
        st.markdown("**Members only.** Enter your access code to see CFB picks.")
        c1, _ = st.columns([1, 2])
        code = c1.text_input("Access code", type="password", key="cfb_code", label_visibility="collapsed",
                             placeholder="Access code")
        if c1.button("Unlock CFB →", type="primary", use_container_width=True):
            if code == CFB_CODE:
                st.session_state.cfb_ok = True
                st.rerun()
            else:
                st.error("Invalid access code")
        return

    f = pick_file("cfb")
    if not f:
        return st.info("CFB picks coming soon.")
    data = json.loads(f.read_text(encoding="utf-8"))
    games, week = data.get("games", []), data.get("week")
    from cfb_cards import render_cards, _spread_tier, _total_tier

    t_cards, t_bets, t_rec = st.tabs(["Cards", "Best Bets", "Record"])

    with t_cards:
        n_days = len({g.get("start_date", "")[:10] for g in games})
        height = 340 + n_days * 70 + math.ceil(len(games) / 3) * 820
        components.html(render_cards(games, week, data.get("generated", "")), height=height, scrolling=True)

    with t_bets:
        rows = []
        for g in games:
            mu = f"{g['away_team']} @ {g['home_team']}"
            se, te = g.get("spread_edge"), g.get("total_edge")
            st_, tt_ = _spread_tier(se), _total_tier(te)
            if st_:
                rows.append(dict(Matchup=mu, Market="Spread", Pick=f"{'HOME' if se > 0 else 'AWAY'} {abs(se):.1f} pts",
                                 Tier=st_, Edge=round(se, 1),
                                 Book=f"{g['book_spread']:+.1f}" if g.get("book_spread") is not None else "-",
                                 Model=f"{g['pred_margin']:+.1f}" if g.get("pred_margin") is not None else "-"))
            if tt_:
                rows.append(dict(Matchup=mu, Market="Total", Pick=f"{'OVER' if te > 0 else 'UNDER'} {abs(te):.1f}",
                                 Tier=tt_, Edge=round(te, 1),
                                 Book=f"{g['book_total']:.1f}" if g.get("book_total") is not None else "-",
                                 Model=f"{g['pred_total']:.1f}" if g.get("pred_total") is not None else "-"))
        if rows:
            bets = pd.DataFrame(rows)
            bets["_r"] = bets.Tier.map(TIER_RANK).fillna(0)
            bets = bets.sort_values(["_r", "Edge"], ascending=False).drop(columns="_r")
            m1, m2, m3 = st.columns(3)
            m1.metric("Strong", int((bets.Tier == "STRONG").sum()))
            m2.metric("Edge", int((bets.Tier == "EDGE").sum()))
            m3.metric("Lean", int((bets.Tier == "LEAN").sum()))
            show(bets)
        else:
            st.info("No plays clear the thresholds this week.")

    with t_rec:
        tp = DATA / "cfb_tracker.json"
        tr = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
        sp = tr.get("overall", {}).get("spread", {})
        if not sp.get("W", 0) + sp.get("L", 0):
            st.info("Nothing graded yet.")
        else:
            record_metrics(sp.get("W", 0), sp.get("L", 0), sp.get("P", 0))
            rows = [{"Market": m.upper(), "W": v.get("W", 0), "L": v.get("L", 0), "P": v.get("P", 0),
                     "Win %": f"{v.get('pct', 0):.1f}%"} for m, v in tr.get("overall", {}).items()]
            show(pd.DataFrame(rows))
            bw = tr.get("by_week", [])
            if isinstance(bw, list) and bw:
                show(pd.DataFrame([{"Week": e.get("week"), "W": (e.get("spread") or {}).get("W", 0),
                                    "L": (e.get("spread") or {}).get("L", 0),
                                    "Win %": f"{(e.get('spread') or {}).get('pct', 0):.1f}%"}
                                   for e in sorted(bw, key=lambda x: x.get("week", 0))]))


# ================= MLB (on hold) =================
def render_mlb():
    f = pick_file("mlb")
    if not f:
        return st.info("MLB picks coming soon.")
    stale_note(f)
    g = pd.read_csv(f)
    fav = g.home_win_prob >= 0.5
    show(pd.DataFrame({
        "Matchup": g.away_abb + " @ " + g.home_abb,
        "Starters": g.away_starter_name.fillna("TBD") + " vs " + g.home_starter_name.fillna("TBD"),
        "Proj Score": g.proj_score, "Proj Total": g.proj_total.round(1), "O/U Line": g.total_line,
        "Model Side": g.home_abb.where(fav, g.away_abb),
        "Win %": (g[["home_win_prob", "away_win_prob"]].max(axis=1) * 100).round(1),
        "Home ML": g.home_ml.map(odds), "Away ML": g.away_ml.map(odds),
    }))


def render_hr():
    f = pick_file("mlb_hr", "hr_*.json")
    if not f:
        return st.info("HR picks coming soon.")
    stale_note(f, days=1)
    d = json.loads(f.read_text(encoding="utf-8"))
    rows = []
    for g in d.get("games", []):
        for side, opp_p in (("home", "away_pitcher"), ("away", "home_pitcher")):
            team = g.get(f"{side}_team")
            for b in g.get(f"{side}_batters", []):
                rows.append({"Player": b.get("player_name"), "Team": team,
                             "Game": f"{g.get('away_team')} @ {g.get('home_team')}", "Time": g.get("game_time"),
                             "Vs Pitcher": g.get(opp_p), "HIT Score": b.get("hit_score"), "Grade": b.get("grade"),
                             "HR %": b.get("proj_hr_pct"), "Barrel %": b.get("barrel_rate"),
                             "Hard Hit %": b.get("hard_hit_pct"), "Park": g.get("park_factor"),
                             "Weather": (g.get("weather") or {}).get("wind_label", "")})
    if not rows:
        return st.info("No HR slate today.")
    h = pd.DataFrame(rows).sort_values(["HIT Score", "HR %"], ascending=False).head(30)
    h.insert(0, "Rank", range(1, len(h) + 1))
    show(h)


# ================= NHL =================
def render_nhl():
    f = pick_file("nhl", "nhl_*.csv")
    if not f:
        return st.info("NHL picks coming soon.")
    stale_note(f, days=1)
    g = pd.read_csv(f)
    t_cards, t_bets, t_rec = st.tabs(["Cards", "Best Bets", "Record"])

    with t_cards:
        from nhl_cards import render_cards
        height = 300 + math.ceil(len(g) / 3) * 760
        components.html(render_cards(g, str(g.date.iloc[0])), height=height, scrolling=True)

    with t_bets:
        rows = []
        for _, r in g.iterrows():
            mu = f"{r.away_team} @ {r.home_team}"
            if isinstance(r.ml_tier, str) and r.ml_tier:
                rows.append(dict(Time=r.start_et, Matchup=mu, Market="ML", Pick=f"{r.ml_pick} ML",
                                 Odds=odds(r.ml_odds), Tier=r.ml_tier, Edge=round(r.ml_edge, 1),
                                 Model=f"{r.ml_model:.0%}"))
            if isinstance(r.pl_tier, str) and r.pl_tier:
                rows.append(dict(Time=r.start_et, Matchup=mu, Market="Puck Line", Pick=r.pl_pick,
                                 Odds=odds(r.pl_odds), Tier=r.pl_tier, Edge=round(r.pl_edge, 1),
                                 Model=f"{r.pl_model:.0%}"))
            if isinstance(r.tot_tier, str) and r.tot_tier:
                rows.append(dict(Time=r.start_et, Matchup=mu, Market="Total", Pick=r.tot_pick,
                                 Odds=odds(r.tot_odds), Tier=r.tot_tier, Edge=round(r.tot_edge, 1),
                                 Model=f"{r.tot_model:.0%} · proj {r.pred_total:.1f}"))
        if rows:
            bets = pd.DataFrame(rows)
            bets["_r"] = bets.Tier.map(TIER_RANK).fillna(0)
            bets = bets.sort_values(["_r", "Edge"], ascending=False).drop(columns="_r")
            m1, m2, m3 = st.columns(3)
            m1.metric("Hammers", int((bets.Tier == "HAMMER").sum()))
            m2.metric("Plays", int((bets.Tier == "PLAY").sum()))
            m3.metric("Leans", int((bets.Tier == "LEAN").sum()))
            show(bets.rename(columns={"Edge": "Edge %"}))
        else:
            st.info("No plays clear the thresholds today.")
        st.caption("All games")
        show(pd.DataFrame({
            "Time": g.start_et, "Matchup": g.away_team + " @ " + g.home_team,
            "Proj Score": g.away_team + " " + g.proj_away.round(1).astype(str) + " - "
                          + g.home_team + " " + g.proj_home.round(1).astype(str),
            "Home Win %": (g.home_wp * 100).round(1), "OT %": (g.p_ot * 100).round(1),
            "Proj Total": g.pred_total.round(2), "O/U": g.total_line,
            "Fair ML (A/H)": g.fair_ml_away.map(odds) + " / " + g.fair_ml_home.map(odds),
        }))

    with t_rec:
        tp = DATA / "nhl_tracker.csv"
        if not tp.exists():
            st.info("Nothing graded yet.")
        else:
            t = pd.read_csv(tp)
            w, l, p = (t.result == "W").sum(), (t.result == "L").sum(), (t.result == "P").sum()
            record_metrics(w, l, p, t.units.sum())
            st.line_chart(t.groupby("date").units.sum().cumsum().rename("Cumulative units"))
            agg = (t.groupby(["market", "tier"])
                   .agg(W=("result", lambda x: (x == "W").sum()), L=("result", lambda x: (x == "L").sum()),
                        P=("result", lambda x: (x == "P").sum()), Units=("units", "sum")).reset_index())
            agg["Win %"] = (agg.W / (agg.W + agg.L).clip(lower=1)).map("{:.1%}".format)
            agg["Units"] = agg.Units.round(2)
            show(agg.rename(columns={"market": "Market", "tier": "Tier"}))


# ================= NBA (on hold) =================
def render_nba():
    f = pick_file("nba")
    if not f:
        return st.info("NBA picks coming soon.")
    t = pd.DataFrame(json.loads(f.read_text(encoding="utf-8")).get("top_overlays", []))
    if not t.empty:
        show(pd.DataFrame({"Player": t.player_name, "Game": t.game, "Stat": t.stat,
                           "Proj": t.projection.round(1), "Line": t.line, "Pick": t.direction,
                           "Edge %": t.edge_pct, "Odds": t.over_odds}))


# ================= CBB =================
def render_cbb():
    f = pick_file("cbb")
    if not f:
        return st.info("CBB picks coming soon.")
    show(pd.read_csv(f))


TABS = [
    ("🏈 NFL", "NFL", render_nfl), ("🏈 CFB", "CFB", render_cfb), ("🏒 NHL", "NHL", render_nhl),
    ("🏀 CBB", "CBB", render_cbb), ("🏀 NBA", "NBA", render_nba),
    ("⚾ MLB", "MLB", render_mlb), ("💣 MLB HR", "MLB HR", render_hr),
]

for tab, (label, name, fn) in zip(st.tabs([t[0] for t in TABS]), TABS):
    with tab:
        if name in ON_HOLD:
            st.info(ON_HOLD[name])
        else:
            safe(fn, name)

st.caption("For entertainment. Not betting advice. © 2026 TheAlgoHub")
