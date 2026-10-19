"""
nfl_matchups.py: builds "defense vs. role" matchup tables for every game on the latest NFL slate.

For each defense: what it allows per game to WR1/WR2/WR3, TE1/TE2, RB1/RB2 (and position totals),
ranked 1-32 where 1 = gives up the most. For each offense: each player's season per-game line + his role.

Reads ONLY from ../nfl_algo/data and ../nfl_algo/picks (never changes them).
Writes data/nfl_matchups/<season>_wkNN.json, which the site's NFL > Matchups tab shows.
Run on its own:  python nfl_matchups.py      (sync.py also runs it automatically)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
NFL = HERE.parent / "nfl_algo"
OUT = HERE / "data" / "nfl_matchups"

POS = {"WR": "WR", "TE": "TE", "RB": "RB", "FB": "RB"}
ROLE_SLOTS = {"WR": 3, "TE": 2, "RB": 2}
STATS = {  # output name -> pstats column(s)
    "tgt": ["targets"], "rec": ["receptions"], "rec_yds": ["receiving_yards"],
    "rush_yds": ["rushing_yards"], "td": ["receiving_tds", "rushing_tds"],
    "ppr": ["fantasy_points_ppr"],
}
LABELS = {"tgt": "Tgt", "rec": "Rec", "rec_yds": "Rec Yds", "rush_yds": "Rush Yds", "td": "TD", "ppr": "PPR"}


def latest_slate():
    files = sorted((NFL / "picks").glob("*_wk*.csv"))
    files = [f for f in files if not f.name.startswith("props_")]
    if not files:
        return None
    df = pd.read_csv(files[-1])
    return df, int(df.season.iloc[0]), int(df.week.iloc[0])


def load(season, week):
    ps = pd.read_csv(NFL / "data" / f"pstats_{season}.csv.gz", low_memory=False)
    ps = ps[(ps.season_type == "REG") & (ps.week < week) & ps.position.isin(POS)].copy()
    ps["pos"] = ps.position.map(POS)
    for k, cols in STATS.items():
        ps[k] = ps[cols].fillna(0).sum(axis=1)
    sn = pd.read_csv(NFL / "data" / f"v2_snaps_{season}.csv.gz")
    ps = ps.merge(sn[["player_id", "week", "snap_pct"]], on=["player_id", "week"], how="left")
    # if snaps are missing, fall back to usage (targets + carries) so we can still rank roles
    ps["usage"] = ps.snap_pct.fillna(0) * 100 + (ps.targets.fillna(0) + ps.carries.fillna(0)) / 100
    return ps


def game_roles(ps):
    """Role each player held IN EACH GAME (WR1 = most snaps among that team's WRs that week)."""
    ps = ps.sort_values("usage", ascending=False).copy()
    ps["n"] = ps.groupby(["team", "week", "pos"]).cumcount() + 1
    ps["role"] = ps.apply(lambda r: f"{r.pos}{r.n}" if r.n <= ROLE_SLOTS[r.pos] else f"Other {r.pos}", axis=1)
    return ps


def defense_tables(ps):
    """Per-game allowed by each defense, by position and by role, plus 1-32 ranks (1 = most allowed)."""
    games = ps.groupby("opponent_team").week.nunique().rename("gp")
    out = {}
    for level in ["pos", "role"]:
        allowed = ps.groupby(["opponent_team", level])[list(STATS)].sum().reset_index()
        gp = allowed.opponent_team.map(games)
        allowed[list(STATS)] = allowed[list(STATS)].div(gp, axis=0)
        for k in STATS:
            allowed[f"{k}_rk"] = allowed.groupby(level)[k].rank(ascending=False, method="min").astype(int)
        out[level] = allowed.rename(columns={"opponent_team": "def"})
    return out, games


def depth_ranks(season):
    """Current depth-chart rank per player (WR/TE/RB). Guys buried on it (IR, inactive) can't hold a WR1-style role."""
    f = NFL / "data" / f"depth_{season}.csv.gz"
    if not f.exists():
        return {}
    d = pd.read_csv(f)
    d = d[d.pos_abb.isin(["WR", "TE", "RB", "FB"])]
    d = d[d.dt == d.dt.max()]
    return d.groupby("gsis_id").pos_rank.min().to_dict()


def current_roles(ps, injuries, team, week, depth):
    """Each player's role going into this game, by average snap share over the season so far."""
    latest_team = ps.sort_values("week").groupby("player_id").team.last()
    p = ps[ps.player_id.map(latest_team) == team]
    agg = p.groupby(["player_id", "player_display_name", "pos"]).agg(
        gp=("week", "nunique"), snap=("snap_pct", "mean"), usage=("usage", "mean"),
        **{k: (k, "mean") for k in STATS}).reset_index()
    agg["new_team"] = agg.player_id.map(ps.groupby("player_id").team.nunique()) > 1
    inj = injuries[(injuries.team == team) & (injuries.week == week)]
    status = inj.set_index("gsis_id").report_status.dropna()
    agg["status"] = agg.player_id.map(status).fillna("")
    agg["depth"] = agg.player_id.map(depth)
    buried = pd.Series(False, index=agg.index)
    if depth:
        agg.loc[agg.depth.isna() & (agg.status == ""), "status"] = "IR"          # off the depth chart entirely
        buried = agg.depth.isna() | (agg.depth > agg.pos.map(ROLE_SLOTS) + 1)    # deep backup: no WR1-style role
    agg["buried"] = buried
    agg = agg.sort_values("usage", ascending=False).reset_index(drop=True)
    healthy = ~agg.status.isin(["Out", "Doubtful", "IR"]) & ~agg.buried
    agg["n"] = 0
    agg.loc[healthy, "n"] = agg[healthy].groupby("pos").cumcount() + 1
    agg["role"] = agg.apply(
        lambda r: (f"{r.pos}{r.n}" if 0 < r.n <= ROLE_SLOTS[r.pos] else r.pos), axis=1)
    return agg[(agg.gp >= 1) & ((agg.tgt > 0) | (agg.rush_yds != 0))]   # skip guys with zero touches


def side(off, deff, ps, d, games, injuries, week, depth):
    pos_tbl = d["pos"][d["pos"]["def"] == deff]
    role_tbl = d["role"][d["role"]["def"] == deff].set_index("role")
    allowed = []
    for pos in ["WR", "TE", "RB"]:
        r = pos_tbl[pos_tbl.pos == pos]
        if r.empty:
            continue
        r = r.iloc[0]
        allowed.append({"group": f"All {pos}s", **{k: round(float(r[k]), 2) for k in STATS},
                        **{f"{k}_rk": int(r[f"{k}_rk"]) for k in STATS}})
    players = []
    for _, p in current_roles(ps, injuries, off, week, depth).iterrows():
        ref = role_tbl.loc[p.role] if p.role in role_tbl.index else None
        if ref is None:   # unnumbered depth player: compare to the position as a whole
            rr = pos_tbl[pos_tbl.pos == p.pos]
            ref = rr.iloc[0] if len(rr) else None
        players.append({
            "role": p.role, "player": p.player_display_name, "player_id": p.player_id, "pos": p.pos, "gp": int(p.gp),
            "status": p.status,
            "tag": "NEW TEAM" if p.new_team else (p.status.upper() if p.status else ""),
            **{k: round(float(p[k]), 1) for k in STATS},
            **({f"{k}_allowed": round(float(ref[k]), 1) for k in STATS} if ref is not None else {}),
            **({f"{k}_rk": int(ref[f"{k}_rk"]) for k in STATS} if ref is not None else {}),
        })
    order = {"WR1": 0, "WR2": 1, "WR3": 2, "TE1": 3, "TE2": 4, "RB1": 5, "RB2": 6}
    players.sort(key=lambda x: (order.get(x["role"], 9), -x["tgt"]))
    return {"offense": off, "defense": deff, "def_gp": int(games.get(deff, 0)), "allowed": allowed, "players": players}


def _implied(g):
    """(away pts, home pts) from the market: total + spread like 'SEA -3.0'. Falls back to our model's projection."""
    try:
        tot = float(g.total_line)
        fav, num = str(g.market_line).rsplit(" ", 1)
        num = abs(float(num))
        home_fav = fav.strip() == g.home_team
        h = tot / 2 + (num / 2 if home_fav else -num / 2)
        return tot - h, h
    except (TypeError, ValueError, AttributeError):
        pa, ph = g.get("proj_away"), g.get("proj_home")
        return (float(pa) if pd.notna(pa) else 22.5), (float(ph) if pd.notna(ph) else 22.5)


def td_board(picks, out, season, week, injuries):
    """Our matchup TD % for every active QB1/RB/WR/TE on the slate (nfl_td.py). Not graded."""
    import nfl_td
    ps = pd.read_csv(NFL / "data" / f"pstats_{season}.csv.gz", low_memory=False)
    ps = ps[(ps.season_type == "REG") & (ps.week < week)]
    qbs = ps[ps.position == "QB"]
    prev = NFL / "data" / f"pstats_{season - 1}.csv.gz"
    qid_by_name = {}
    if prev.exists():
        pq = pd.read_csv(prev, low_memory=False, usecols=["player_id", "player_display_name", "position"])
        qid_by_name.update(pq[pq.position == "QB"].drop_duplicates("player_display_name")
                           .set_index("player_display_name").player_id.to_dict())
    qid_by_name.update(qbs.drop_duplicates("player_display_name").set_index("player_display_name").player_id.to_dict())
    inj = injuries[injuries.week == week].set_index("gsis_id").report_status.dropna().to_dict()
    rows = []
    for (_, g), gj in zip(picks.iterrows(), out["games"]):
        a_pts, h_pts = _implied(g)
        dome = int(g.get("dome", 0) or 0) if "dome" in g else 0
        wx = nfl_td.wx_factor(g.get("wind", np.nan), g.get("temp", np.nan), dome)
        for side_, pts, qb_name in ((gj["sides"][0], a_pts, g.get("a_qb_name")), (gj["sides"][1], h_pts, g.get("h_qb_name"))):
            team, opp = side_["offense"], side_["defense"]
            base = dict(game_id=g.game_id, matchup=gj["matchup"], team=team, opponent_team=opp, imp_pts=pts, wx=wx)
            for p in side_["players"]:
                if p.get("status") in ("Out", "Doubtful", "IR"):
                    continue
                rows.append({**base, "player_id": p["player_id"], "player_display_name": p["player"], "pos": p["pos"],
                             "role": p["role"], "tag": p.get("tag", "")})
            # starting QB (rushing TDs only): the projected starter, else whoever started last for this team
            q = qbs[qbs.team == team]
            if len(q):
                if isinstance(qb_name, str) and qb_name:
                    # projected starter from the game model; skipped if he has no NFL history at all
                    qid, qn = qid_by_name.get(qb_name), qb_name
                else:   # no projected starter: most recent starter who isn't hurt
                    c = q.sort_values(["week", "attempts"], ascending=False)
                    c = c[~c.player_id.map(lambda k: inj.get(k) in ("Out", "Doubtful", "IR"))].head(1)
                    qid, qn = (c.player_id.iloc[0], c.player_display_name.iloc[0]) if len(c) else (None, None)
                if qid is not None and inj.get(qid) not in ("Out", "Doubtful", "IR"):
                    rows.append({**base, "player_id": qid, "player_display_name": qn,
                                 "pos": "QB", "role": "QB1", "tag": (inj.get(qid) or "").upper()})
    if not rows:
        return []
    t = pd.DataFrame(rows).drop_duplicates(["game_id", "player_id"])
    r = nfl_td.predict_slate(season, week, t)
    keep = ["game_id", "matchup", "team", "opponent_team", "player_display_name", "pos", "role", "tag",
            "td_pct", "xtd", "def_td_fac", "imp_pts"]
    r = r[keep].rename(columns={"player_display_name": "player", "opponent_team": "opp"})
    r[["td_pct", "xtd", "def_td_fac", "imp_pts"]] = r[["td_pct", "xtd", "def_td_fac", "imp_pts"]].astype(float).round(4)
    return r.to_dict("records")


def main():
    slate = latest_slate()
    if slate is None:
        print("  matchups   no NFL slate yet")
        return
    picks, season, week = slate
    ps = game_roles(load(season, week))
    if ps.empty:
        print("  matchups   no games played yet this season")
        return
    d, games = defense_tables(ps)
    injuries = pd.read_csv(NFL / "data" / f"injuries_{season}.csv.gz", low_memory=False)
    depth = depth_ranks(season)
    out = {"season": season, "week": week, "labels": LABELS, "games": []}
    for _, g in picks.iterrows():
        a, h = g.away_team, g.home_team
        out["games"].append({
            "matchup": f"{a} @ {h}", "day": g.gameday, "time": g.gametime,
            "sides": [side(a, h, ps, d, games, injuries, week, depth),
                      side(h, a, ps, d, games, injuries, week, depth)],
        })
    try:
        out["td"] = td_board(picks, out, season, week, injuries)
        print(f"  matchups   TD % for {len(out['td'])} players")
    except Exception as ex:                       # never let the TD board break the matchups tab
        print(f"  ! TD board skipped ({type(ex).__name__}: {ex})")
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{season}_wk{week:02d}.json"
    f.write_text(json.dumps(out), encoding="utf-8")
    print(f"  matchups   {len(out['games'])} games -> {f.name}")


if __name__ == "__main__":
    main()
