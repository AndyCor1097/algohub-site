"""
nfl_novig.py: puts Novig's exchange prices next to your NFL model for the latest slate.

For every game: moneyline + the spread and total at the book's main line. For each side:
  Model %   your model's chance (ML from home_wp; spread/total from your projected margin/total)
  Novig %   Novig's fair price (middle of bid/ask) = the sharp no-vig number
  Buy at    cheapest price on Novig right now (what a sharp book is effectively charging)
  Edge      Model % minus Buy at. Positive = your model beats the sharp market.

Reads ../nfl_algo/picks (never changes it) and uses ../novig/novig.py (public Novig routes, no key).
Writes data/nfl_novig/<season>_wkNN.csv. sync.py runs it automatically.
"""
import csv
import math
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
NFL = HERE.parent / "nfl_algo"
sys.path.insert(0, str(HERE.parent / "novig"))
OUT = HERE / "data" / "nfl_novig"

SD_MARGIN, SD_TOTAL = 13.5, 13.0          # typical NFL spread of outcomes around a projection
ALIAS = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "LVR": "LV", "OAK": "LV", "SD": "LAC", "STL": "LA"}
FULL = {  # in case Novig spells team names out
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def team(s):
    s = (s or "").strip()
    if s in FULL:
        return FULL[s]
    t = s.split()[0].upper() if s else ""
    return ALIAS.get(t, t)


def line_of(name):
    """'ARI +12.5' -> 12.5 ; 'DEN -3' -> -3.0 ; 'Over 41.5' -> 41.5"""
    m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*$", name or "")
    return float(m.group(1)) if m else None


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def latest_slate():
    files = sorted(f for f in (NFL / "picks").glob("*_wk*.csv") if not f.name.startswith("props_"))
    if not files:
        return None
    df = pd.read_csv(files[-1])
    return df, int(df.season.iloc[0]), int(df.week.iloc[0])


def main():
    import novig
    slate = latest_slate()
    if slate is None:
        print("  novig      no NFL slate yet")
        return
    picks, season, week = slate
    evs = novig.events("NFL")
    mk = novig.markets("NFL")
    # index Novig markets by (away, home)
    by_game = {}
    for m in mk:
        a, h = novig.split_teams(evs.get(m["eventId"], {}).get("description", ""))
        if a and h:
            by_game.setdefault((team(a), team(h)), []).append(m)

    rows, missing = [], []
    for _, g in picks.iterrows():
        a, h = g.away_team, g.home_team
        ms = by_game.get((a, h), [])
        if not ms:
            missing.append(f"{a}@{h}")
            continue
        home_hcp = -float(g.spread_line) if pd.notna(g.spread_line) else None   # home's line, e.g. DEN +3
        wanted = []
        for m in ms:
            t, outs = m["marketType"], m.get("outcomes", [])
            if len(outs) != 2:
                continue
            if t == "MONEY":
                wanted.append(m)
            elif t == "SPREAD" and home_hcp is not None:
                if any(team(o["name"]) == h and line_of(o["name"]) == home_hcp for o in outs):
                    wanted.append(m)
            elif t == "TOTAL" and pd.notna(g.total_line):
                if any(line_of(o["name"]) == float(g.total_line) for o in outs):
                    wanted.append(m)
        for m in wanted:
            b = novig.book(m["marketId"]).get("orders", {})
            o1, o2 = m["outcomes"]
            for me, other in ((o1, o2), (o2, o1)):
                bid, bid_qty = novig._side(b.get(me["outcomeId"], []))
                obid, ask_qty = novig._side(b.get(other["outcomeId"], []))
                ask = round(1 - obid, 4) if obid is not None else None
                fair = round((bid + ask) / 2, 4) if bid is not None and ask is not None else None
                name, t = me["name"], m["marketType"]
                if t == "MONEY":
                    side = team(name)
                    model = g.home_wp if side == h else 1 - g.home_wp
                    label, market = f"{side} ML", "Moneyline"
                elif t == "SPREAD":
                    side, ln = team(name), line_of(name)
                    margin = g.pred_margin if side == h else -g.pred_margin   # projected margin for this side
                    model = phi((margin + ln) / SD_MARGIN)
                    label, market = f"{side} {ln:+g}", "Spread"
                else:
                    ln = line_of(name)
                    over = name.lower().startswith("over")
                    p_over = 1 - phi((ln - g.pred_total) / SD_TOTAL)
                    model = p_over if over else 1 - p_over
                    label, market = f"{'Over' if over else 'Under'} {ln:g}", "Total"
                rows.append({
                    "matchup": f"{a} @ {h}", "day": g.gameday, "market": market, "side": label,
                    "model": round(float(model), 4), "novig_fair": fair, "novig_ask": ask,
                    "edge": round(float(model) - ask, 4) if ask is not None else None,
                    "ask_qty": ask_qty, "bid": bid,
                })
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{season}_wk{week:02d}.csv"
    if rows:
        with open(f, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"  novig      {len(rows)} NFL sides priced"
          + (f", no Novig market for: {', '.join(missing)}" if missing else "") + f" -> {f.name}")


if __name__ == "__main__":
    main()
