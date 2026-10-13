"""
The AlgoHub: every algo, one site.
Each tab reads the pick files that sync.py copied into data/<sport>/.
"""
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="The AlgoHub", page_icon="🎯", layout="wide")

DATA = Path(__file__).resolve().parent / "data"

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem;}
      h1 {margin-bottom: 0;}
      .stTabs [data-baseweb="tab"] {font-size: 1.05rem; padding: 0.5rem 1rem;}
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


def pick_file(sport, pattern="*", key=None):
    files = files_for(sport, pattern)
    if not files:
        return None
    labels = [label_from(f) for f in files]
    choice = st.selectbox("Slate", labels, key=key or f"sel_{sport}")
    return files[labels.index(choice)]


def coming_soon(name):
    st.info(f"{name} picks coming soon.")


def odds(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return ""
    if pd.isna(x):
        return ""
    return f"+{x:.0f}" if x > 0 else f"{x:.0f}"


def show(df, **kw):
    st.dataframe(df, use_container_width=True, hide_index=True, **kw)


def safe(render, name):
    """If one sport's file format changes, only that tab breaks, not the whole site."""
    try:
        render()
    except Exception as e:
        st.warning(f"Couldn't load {name} picks right now ({e.__class__.__name__}).")


# ---------- NFL ----------
def render_nfl():
    f = pick_file("nfl")
    if not f:
        return coming_soon("NFL")
    df = pd.read_csv(f)
    df["Matchup"] = df.away_team + " @ " + df.home_team
    df["Proj Score"] = (df.away_team + " " + df.proj_away.round(1).astype(str)
                        + " — " + df.home_team + " " + df.proj_home.round(1).astype(str))
    df["Home Win %"] = (df.home_wp * 100).round(1)
    out = pd.DataFrame({
        "Date": df.gameday, "Time": df.gametime, "Matchup": df.Matchup,
        "Proj Score": df["Proj Score"], "Model Line": df.model_line, "Market": df.market_line,
        "Spread Pick": df.sp_pick, "Spread Tier": df.sp_tier.fillna(""),
        "Total Pick": df.tot_pick, "Total Tier": df.tot_tier.fillna(""),
        "ML Pick": df.ml_pick, "ML Odds": df.ml_odds.map(odds), "Home Win %": df["Home Win %"],
    })
    tiers = df.sp_tier.fillna("").str.upper()
    c1, c2, c3 = st.columns(3)
    c1.metric("Games", len(df))
    c2.metric("🔨 Hammers", int((tiers == "HAMMER").sum()))
    c3.metric("Leans", int((tiers == "LEAN").sum()))
    only = st.toggle("Only show spread plays", key="nfl_only")
    if only:
        out = out[out["Spread Tier"] != ""]
    show(out)

    props = files_for("nfl_props")
    week = re.search(r"wk\d+", f.stem)
    match = [p for p in props if week and week.group(0) in p.stem]
    if match:
        st.subheader("Player Props")
        p = pd.read_csv(match[0])
        p = p[p.pick.notna()].copy()
        tiers = ["All"] + sorted(p.tier.dropna().unique().tolist())
        t = st.selectbox("Tier", tiers, key="nfl_prop_tier")
        if t != "All":
            p = p[p.tier == t]
        show(pd.DataFrame({
            "Player": p.player, "Team": p.team, "Opp": p.opp, "Market": p.label,
            "Proj": p.proj.round(1), "Pick": p.pick, "Odds": p.price.map(odds),
            "Edge %": (p.edge * 100).round(1), "Tier": p.tier, "Book": p.book,
        }).sort_values("Edge %", ascending=False))


# ---------- CFB ----------
def render_cfb():
    f = pick_file("cfb")
    if not f:
        return coming_soon("CFB")
    g = pd.DataFrame(json.loads(f.read_text(encoding="utf-8"))["games"])
    out = pd.DataFrame({
        "Kickoff (ET)": pd.to_datetime(g.start_date).dt.tz_localize("UTC")
                          .dt.tz_convert("America/New_York").dt.strftime("%a %m/%d %I:%M %p"),
        "Matchup": g.away_team + " @ " + g.home_team,
        "Proj Score": g.away_team + " " + g.pred_away.astype(str) + " — " + g.home_team + " " + g.pred_home.astype(str),
        "Home Win %": g.home_win_prob, "Book Spread": g.book_spread, "Book Total": g.book_total,
        "Spread Edge": g.spread_edge, "Total Edge": g.total_edge,
        "Play": g.edge_label.fillna(""), "Pick": g.edge_pick.fillna(""),
    })
    c1, c2 = st.columns(2)
    c1.metric("Games", len(out))
    c2.metric("Plays", int((out.Pick != "").sum()))
    if st.toggle("Only show plays", key="cfb_only"):
        out = out[out.Pick != ""]
    show(out)


# ---------- MLB ----------
def render_mlb():
    f = pick_file("mlb")
    if not f:
        return coming_soon("MLB")
    g = pd.read_csv(f)
    fav = g.home_win_prob >= 0.5
    show(pd.DataFrame({
        "Matchup": g.away_abb + " @ " + g.home_abb,
        "Starters": g.away_starter_name.fillna("TBD") + " vs " + g.home_starter_name.fillna("TBD"),
        "Proj Score": g.proj_score, "Proj Total": g.proj_total.round(1), "O/U Line": g.total_line,
        "Model Side": g.home_abb.where(fav, g.away_abb),
        "Win %": (g[["home_win_prob", "away_win_prob"]].max(axis=1) * 100).round(1),
        "Home ML": g.home_ml.map(odds), "Away ML": g.away_ml.map(odds),
        "Temp °F": g.temp_f, "Wind mph": g.wind_mph,
    }))


# ---------- MLB HR ----------
def render_hr():
    f = pick_file("mlb_hr")
    if not f:
        return coming_soon("MLB HR")
    h = pd.read_csv(f)
    prob = "hr_probability" if "hr_probability" in h.columns else "model_prob"
    h = h.sort_values(prob, ascending=False)
    n = st.slider("Show top", 10, min(100, len(h)), 25, key="hr_n")
    show(pd.DataFrame({
        "Rank": range(1, len(h) + 1), "Player": h.player_name, "Team": h.batting_team,
        "Vs Pitcher": h.opposing_pitcher, "HR %": (h[prob] * 100).round(1),
        "Barrel% L15": (h.barrel_rate_last15 * 100).round(1) if "barrel_rate_last15" in h else None,
        "Park": h.park_factor, "Wind": h.wind_label if "wind_label" in h else None,
    }).head(n))


# ---------- NHL ----------
def render_nhl():
    f = pick_file("nhl")
    if not f:
        return coming_soon("NHL")
    d = json.loads(f.read_text(encoding="utf-8"))
    rows = []
    for bucket, label in [("strong", "🔥 Strong"), ("value", "Value"), ("puck_line", "Puck Line"), ("totals", "Total")]:
        for p in d.get(bucket, []):
            rows.append({"Tier": label, "Matchup": p.get("matchup"), "Pick": p.get("pick"),
                         "Odds": odds(p.get("odds")), "Edge %": p.get("edge"),
                         "Proj Score": p.get("proj_score")})
    if rows:
        st.subheader("Plays")
        show(pd.DataFrame(rows))
    games = d.get("reg_ml", [])
    if games:
        st.subheader("All Games")
        g = pd.DataFrame(games)
        show(pd.DataFrame({"Matchup": g.matchup, "Proj Score": g.proj_score,
                           "Home Reg %": g.home_prob, "Away Reg %": g.away_prob, "Draw %": g.draw_prob}))
    if not rows and not games:
        st.info("No NHL games on this slate.")


# ---------- NBA ----------
def render_nba():
    f = pick_file("nba")
    if not f:
        return coming_soon("NBA")
    d = json.loads(f.read_text(encoding="utf-8"))
    st.subheader("Top Overlays")
    t = pd.DataFrame(d.get("top_overlays", []))
    if t.empty:
        st.info("No NBA games on this slate.")
        return
    show(pd.DataFrame({
        "Player": t.player_name, "Game": t.game, "Stat": t.stat, "Proj": t.projection.round(1),
        "Line": t.line, "Pick": t.direction, "Edge %": t.edge_pct, "Odds": t.over_odds, "Form": t.form,
    }))


# ---------- CBB ----------
def render_cbb():
    f = pick_file("cbb")
    if not f:
        return coming_soon("CBB")
    show(pd.read_csv(f))


TABS = [
    ("🏈 NFL", render_nfl), ("🏈 CFB", render_cfb), ("⚾ MLB", render_mlb), ("💣 MLB HR", render_hr),
    ("🏒 NHL", render_nhl), ("🏀 NBA", render_nba), ("🏀 CBB", render_cbb),
]

for tab, (name, fn) in zip(st.tabs([t[0] for t in TABS]), TABS):
    with tab:
        safe(fn, name)
