"""
nfl_td.py: our own anytime-TD % for every active QB/RB/WR/TE on the slate, built from the MATCHUP.

Not a betting model and never graded: it's the "TD odds" board on the site.

How a player's TD chance is built (all from games BEFORE this week):
  - his usage: red-zone carries + red-zone targets, total carries + targets, snap-free so backups count too
  - his actual TDs per game (shrunk, TDs are noisy)
  - the defense: TDs it has allowed to his position per game vs league average (shrunk early in the year)
  - game environment: his team's implied points from the spread + total (more points = more TDs)
  - weather (wind/cold)
  Early in the season each rate leans on last season's numbers until there are enough games.
A Poisson gradient-boosting model turns those into expected TDs (trained on 2022-to-now, every week only
seeing the past), then TD % = 1 - e^(-expected TDs).

  python nfl_td.py            -> backtest printout (how well calibrated it is on the latest full season)
Used by nfl_matchups.py, which writes the numbers into the matchups json the site reads.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
NFL = HERE.parent / "nfl_algo"
D = NFL / "data"
POS = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE"}
FIRST = 2022
K_PLAYER = 4.0      # games of last-season data mixed into this season's rates
K_DEF = 5.0         # games of league-average defense mixed in
LG_TEAM_PTS = 22.5

FEATS = ["is_qb", "is_rb", "is_wr", "is_te", "car_pg", "tgt_pg", "rz_car_pg", "rz_tgt_pg", "td_pg",
         "rush_td_pg", "gp_cur", "imp_pts", "def_td_fac", "wx"]


def _read(kind, season):
    f = D / f"{kind}_{season}.csv.gz"
    return pd.read_csv(f, low_memory=False) if f.exists() else None


def load_weeks(season):
    """One row per player-game (REG season) with the stats we need."""
    ps = _read("pstats", season)
    if ps is None:
        return None
    ps = ps[(ps.season_type == "REG") & ps.position.isin(POS)].copy()
    ps["pos"] = ps.position.map(POS)
    for c in ["carries", "targets", "rushing_tds", "receiving_tds"]:
        ps[c] = ps[c].fillna(0)
    ps["td"] = ps.rushing_tds + ps.receiving_tds
    ps.loc[ps.pos == "QB", "td"] = ps.loc[ps.pos == "QB", "rushing_tds"]   # QB passing TDs don't cash an anytime TD
    ps["scored"] = (ps.td > 0).astype(int)
    rz = _read("v2_rz", season)
    if rz is not None:
        rz = rz[rz.kind == "player"][["player_id", "week", "rz_tgt", "rz_car"]]
        ps = ps.merge(rz, on=["player_id", "week"], how="left")
    else:
        ps["rz_tgt"] = np.nan
        ps["rz_car"] = np.nan
    ps[["rz_tgt", "rz_car"]] = ps[["rz_tgt", "rz_car"]].fillna(0)
    return ps[["season", "week", "player_id", "player_display_name", "pos", "team", "opponent_team",
               "carries", "targets", "rz_car", "rz_tgt", "td", "rushing_tds", "scored"]]


def season_prior(ps):
    """Last season's per-game rates per player (the early-season prior)."""
    if ps is None or ps.empty:
        return pd.DataFrame(columns=["player_id"])
    g = ps.groupby("player_id")
    return pd.DataFrame({"p_gp": g.week.nunique(), "p_car": g.carries.mean(), "p_tgt": g.targets.mean(),
                         "p_rz_car": g.rz_car.mean(), "p_rz_tgt": g.rz_tgt.mean(), "p_td": g.td.mean(),
                         "p_rtd": g.rushing_tds.mean()}).reset_index()


POS_AVG = {  # rough per-game defaults when a player has no history at all
    "QB": dict(car=4, tgt=0, rz_car=0.6, rz_tgt=0, td=0.15, rtd=0.15),
    "RB": dict(car=6, tgt=2, rz_car=1.0, rz_tgt=0.3, td=0.25, rtd=0.2),
    "WR": dict(car=0.2, tgt=4, rz_car=0, rz_tgt=0.5, td=0.2, rtd=0),
    "TE": dict(car=0, tgt=3, rz_car=0, rz_tgt=0.4, td=0.15, rtd=0),
}


def player_rates(cur, prior, pos):
    """cur = this season's games before the target week for each player; returns shrunk per-game rates."""
    g = cur.groupby("player_id")
    r = pd.DataFrame({"gp_cur": g.week.nunique(), "s_car": g.carries.sum(), "s_tgt": g.targets.sum(),
                      "s_rz_car": g.rz_car.sum(), "s_rz_tgt": g.rz_tgt.sum(), "s_td": g.td.sum(),
                      "s_rtd": g.rushing_tds.sum()}).reset_index()
    return r


def shrink(rows, prior):
    """rows has player_id, pos, gp_cur and season sums; mixes in K_PLAYER games of last season (or a position default)."""
    rows = rows.merge(prior, on="player_id", how="left")
    for k, pk in [("car", "p_car"), ("tgt", "p_tgt"), ("rz_car", "p_rz_car"), ("rz_tgt", "p_rz_tgt"),
                  ("td", "p_td"), ("rtd", "p_rtd")]:
        default = rows.pos.map(lambda p: POS_AVG[p][k])
        pri = rows[pk].where(rows[pk].notna(), default) if pk in rows else default
        # with no prior season, lean on this season's own rate (role may be new), position default only lightly
        k_eff = np.where(rows[pk].notna() if pk in rows else False, K_PLAYER, 1.0)
        rows[f"{k}_pg" if k not in ("td", "rtd") else ("td_pg" if k == "td" else "rush_td_pg")] = (
            (rows[f"s_{k}"].fillna(0) + k_eff * pri) / (rows.gp_cur.fillna(0) + k_eff))
    return rows


def defense_factor(cur_all, week_rows):
    """TDs allowed by each defense to each position per game (before this week) vs league, shrunk to 1."""
    tds = cur_all.groupby(["opponent_team", "pos"]).td.sum()
    gp = cur_all.groupby("opponent_team").week.nunique()
    lg = cur_all.groupby("pos").td.sum() / max(cur_all.groupby(["opponent_team"]).week.nunique().sum(), 1)

    def f(r):
        g = gp.get(r.opponent_team, 0)
        a = tds.get((r.opponent_team, r.pos), 0.0)
        base = lg.get(r.pos, np.nan)
        if not base or not np.isfinite(base) or base <= 0:
            return 1.0
        return ((a + K_DEF * base) / (g + K_DEF)) / base
    return week_rows.apply(f, axis=1)


def implied_points(games):
    """team -> implied points per game_id-ish (season, week, team) from spread_line (home +) and total_line."""
    out = {}
    for g in games.itertuples():
        if pd.isna(g.total_line):
            continue
        sp = 0.0 if pd.isna(g.spread_line) else float(g.spread_line)
        out[(g.season, g.week, g.home_team)] = (g.total_line + sp) / 2
        out[(g.season, g.week, g.away_team)] = (g.total_line - sp) / 2
    return out


def wx_factor(wind, temp, dome):
    if dome or pd.isna(wind):
        return 1.0
    over = max(0.0, min(float(wind), 26.0) - 10.0)
    m = (1 - 0.012 * over) * (0.97 if (not pd.isna(temp) and float(temp) < 45) else 1.0)
    return max(m, 0.78)


REALLOC = True       # injury bot: hand a missing player's work to his healthy teammates


def reallocate(rows, gone, team_gp):
    """rows/gone: shrunk per-game rates. Each missing player's carries / targets / red-zone work / TDs go to
    healthy teammates in proportion to what they already get (carries -> RBs, targets -> WR/TE/RB, same position
    weighted 2x). Only the part NOT already in teammates' averages moves: if he missed half the season, the
    games he missed are already in their numbers, so half his work moves."""
    rows = rows.copy()
    rows["realloc"] = 0.0
    for g in gone.itertuples():
        if not g.gp_cur or g.team not in team_gp:
            continue
        f = min(g.gp_cur / max(team_gp[g.team], 1), 1.0)
        mates = rows.team == g.team
        rb = mates & (rows.pos == "RB")
        rec = mates & rows.pos.isin(["RB", "WR", "TE"])
        rec_td = max(g.td_pg - g.rush_td_pg, 0.0)
        if rb.any() and g.car_pg > 0:
            w = rows.loc[rb, "car_pg"] + 0.3
            w = w / w.sum()
            for c, v in (("car_pg", g.car_pg), ("rz_car_pg", g.rz_car_pg), ("rush_td_pg", g.rush_td_pg), ("td_pg", g.rush_td_pg)):
                rows.loc[rb, c] += f * v * w
            rows.loc[rb, "realloc"] += f * g.car_pg * w
        if rec.any() and g.tgt_pg > 0:
            w = (rows.loc[rec, "tgt_pg"] + 0.3) * np.where(rows.loc[rec, "pos"] == g.pos, 2.0, 1.0)
            w = w / w.sum()
            for c, v in (("tgt_pg", g.tgt_pg), ("rz_tgt_pg", g.rz_tgt_pg), ("td_pg", rec_td)):
                rows.loc[rec, c] += f * v * w
            rows.loc[rec, "realloc"] += f * g.tgt_pg * w
    return rows


def week_frame(season, week, cur, prior, targets, gone=None):
    """Feature rows for `targets` (player_id, pos, team, opponent_team, imp_pts, wx) using only cur (weeks < week).
    gone = players missing this game (player_id, pos, team): their work is handed out (REALLOC)."""
    before = cur[cur.week < week]
    sums = player_rates(before, prior, None)
    rows = targets.merge(sums, on="player_id", how="left")
    rows["gp_cur"] = rows.gp_cur.fillna(0)
    rows = shrink(rows, prior)
    rows["realloc"] = 0.0
    if REALLOC and gone is not None and len(gone):
        gr = gone.merge(sums, on="player_id", how="left")
        gr["gp_cur"] = gr.gp_cur.fillna(0)
        gr = shrink(gr, prior)
        team_gp = before.groupby("team").week.nunique().to_dict()
        rows = reallocate(rows, gr, team_gp)
    rows["def_td_fac"] = defense_factor(before, rows) if len(before) else 1.0
    for p in ["QB", "RB", "WR", "TE"]:
        rows[f"is_{p.lower()}"] = (rows.pos == p).astype(int)
    return rows


def training_set(last_season, last_week):
    """Every player-week from FIRST..last_season (weeks < last_week in the last season)."""
    out = []
    for s in range(FIRST, last_season + 1):
        cur = load_weeks(s)
        if cur is None:
            continue
        prior = season_prior(load_weeks(s - 1))
        gm = _read("games", s)
        imp = implied_points(gm[gm.game_type == "REG"]) if gm is not None else {}
        wxm = {}
        if gm is not None:
            for g in gm.itertuples():
                dome = str(getattr(g, "roof", "")).lower() in ("dome", "closed")
                wxm[(g.week, g.home_team)] = wxm[(g.week, g.away_team)] = wx_factor(g.wind, g.temp, dome)
        weeks = sorted(cur.week.unique())
        for w in weeks:
            if w < 2 or (s == last_season and w >= last_week):
                continue
            tgt = cur[cur.week == w][["player_id", "player_display_name", "pos", "team", "opponent_team", "td", "scored"]]
            # only players with some prior footprint (that's who the board shows)
            seen = set(cur[cur.week < w].player_id) | set(prior.player_id)
            tgt = tgt[tgt.player_id.isin(seen)].copy()
            tgt["imp_pts"] = [imp.get((s, w, t), LG_TEAM_PTS) for t in tgt.team]
            tgt["wx"] = [wxm.get((w, t), 1.0) for t in tgt.team]
            # missing this week: played for this team earlier (and it's still his latest team), not in this game
            bef = cur[cur.week < w].sort_values("week")
            lastt = bef.groupby("player_id").tail(1)
            lastt = lastt[lastt.team.isin(set(tgt.team)) & ~lastt.player_id.isin(set(cur[cur.week == w].player_id))]
            gone = lastt[["player_id", "pos", "team"]]
            fr = week_frame(s, w, cur, prior, tgt, gone)
            fr["season"], fr["week"] = s, w
            out.append(fr)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def fit(train):
    from sklearn.ensemble import HistGradientBoostingRegressor
    mono = [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1]
    m = HistGradientBoostingRegressor(loss="poisson", max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
                                      min_samples_leaf=80, l2_regularization=1.0, monotonic_cst=mono, random_state=0)
    m.fit(train[FEATS], train.td.clip(upper=3))
    return m


def prob(model, rows):
    lam = np.clip(model.predict(rows[FEATS]), 1e-4, 3)
    p = 1 - np.exp(-lam)
    # backtest: the model runs a bit hot above ~35% (2025: said 45% -> hit 38%), so pull the top end in
    return np.where(p > 0.35, 0.35 + 0.8 * (p - 0.35), p)


def backtest():
    from sklearn.metrics import log_loss, brier_score_loss
    seasons = sorted(int(p.stem.split("_")[1].split(".")[0]) for p in D.glob("pstats_*.csv.gz"))
    test_s = max(s for s in seasons if s >= FIRST + 1)
    full = training_set(test_s, 99)
    for ts in [s for s in (test_s - 1, test_s) if s > FIRST]:
        tr, te = full[full.season < ts], full[full.season == ts]
        if te.empty:
            continue
        m = fit(tr)
        p = prob(m, te)
        base = np.full(len(te), tr.scored.mean())
        print(f"\n== test {ts}: {len(te)} player-games, scored {te.scored.mean():.1%}")
        print(f"  log loss  model {log_loss(te.scored, p):.4f}   flat avg {log_loss(te.scored, base):.4f}")
        print(f"  brier     model {brier_score_loss(te.scored, p):.4f}   flat avg {brier_score_loss(te.scored, base):.4f}")
        b = pd.cut(p, [0, .05, .1, .15, .2, .3, .4, .5, .6, 1])
        print(pd.DataFrame({"pred": p, "hit": te.scored.values}).groupby(b, observed=True)
              .agg(n=("hit", "size"), pred=("pred", "mean"), actual=("hit", "mean")).round(3).to_string())


def predict_slate(season, week, targets, gone=None):
    """targets: player_id, player_display_name, pos, team, opponent_team, imp_pts, wx. Returns td_pct per row.
    gone: player_id, pos, team of players ruled out (their work gets handed out)."""
    train = training_set(season, week)
    m = fit(train)
    cur = load_weeks(season)
    prior = season_prior(load_weeks(season - 1))
    rows = week_frame(season, week, cur, prior, targets, gone)
    rows["td_pct"] = prob(m, rows)
    rows["xtd"] = -np.log(1 - rows.td_pct)
    rows["def_td_fac"] = rows.def_td_fac.astype(float)
    return rows


if __name__ == "__main__":
    import sys
    if "--compare" in sys.argv:
        REALLOC = False
        print("##### WITHOUT injury reallocation")
        backtest()
        REALLOC = True
        print("\n##### WITH injury reallocation")
    backtest()
