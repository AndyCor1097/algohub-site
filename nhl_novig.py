"""
nhl_novig.py: puts Novig's exchange prices next to your NHL model for the latest slate.

Moneyline (model = home_wp), puck line +-1.5 (model = p_h_m15 / p_a_m15), and the total at the book's
main line (model = Poisson around pred_total). Same columns as nfl_novig.py:
  Model %, Novig fair %, Buy at (cheapest on Novig now), Edge = Model - Buy at, ask_qty = $ payout available.

Reads data/nhl/ (the copy sync.py makes of your NHL picks) and ../novig/novig.py (public routes, no key).
Writes data/nhl_novig/nhl_<date>.csv. sync.py runs it automatically.
"""
import csv
import math
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "novig"))
SRC = HERE / "data" / "nhl"
OUT = HERE / "data" / "nhl_novig"

ALIAS = {"TB": "TBL", "NJ": "NJD", "LA": "LAK", "SJ": "SJS", "WAS": "WSH", "MON": "MTL", "CLB": "CBJ",
         "UTA": "UTA", "ARI": "UTA", "VGS": "VGK", "NAS": "NSH", "CAL": "CGY", "WIN": "WPG"}


def team(s):
    t = (s or "").strip().split()[0].upper() if s else ""
    return ALIAS.get(t, t)


def line_of(name):
    m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*$", name or "")
    return float(m.group(1)) if m else None


def p_over(lam, line):
    """Chance the total goes over `line` with a Poisson(lam) total. Whole-number lines: push removed."""
    pmf = lambda k: math.exp(-lam) * lam ** k / math.factorial(k)
    under = sum(pmf(k) for k in range(int(math.floor(line)) + 1))
    if float(line).is_integer():
        push = pmf(int(line))
        return (1 - under) / max(1 - push, 1e-9)
    return 1 - under


def latest():
    files = sorted(SRC.glob("nhl_*.csv")) if SRC.exists() else []
    return files[-1] if files else None


def main():
    import novig
    f = latest()
    if f is None:
        print("  novig nhl  no NHL slate yet")
        return
    g_all = pd.read_csv(f)
    evs = novig.events("NHL")
    by_game = {}
    for m in novig.markets("NHL"):
        a, h = novig.split_teams(evs.get(m["eventId"], {}).get("description", ""))
        if a and h:
            by_game.setdefault((team(a), team(h)), []).append(m)

    rows, missing = [], []
    for _, g in g_all.iterrows():
        a, h = team(g.away_team), team(g.home_team)
        ms = by_game.get((a, h), [])
        if not ms:
            missing.append(f"{a}@{h}")
            continue
        for m in ms:
            t, outs = m["marketType"], m.get("outcomes", [])
            if len(outs) != 2:
                continue
            if t == "SPREAD" and not all(abs(line_of(o["name"]) or 0) == 1.5 for o in outs):
                continue
            if t == "TOTAL" and not (pd.notna(g.total_line) and any(line_of(o["name"]) == float(g.total_line) for o in outs)):
                continue
            if t not in ("MONEY", "SPREAD", "TOTAL"):
                continue
            b = novig.book(m["marketId"]).get("orders", {})
            o1, o2 = outs
            for me, other in ((o1, o2), (o2, o1)):
                bid, _ = novig._side(b.get(me["outcomeId"], []))
                obid, ask_qty = novig._side(b.get(other["outcomeId"], []))
                ask = round(1 - obid, 4) if obid is not None else None
                fair = round((bid + ask) / 2, 4) if bid is not None and ask is not None else None
                name = me["name"]
                if t == "MONEY":
                    side = team(name)
                    model, label, market = (g.home_wp if side == h else 1 - g.home_wp), f"{side} ML", "Moneyline"
                elif t == "SPREAD":
                    side, ln = team(name), line_of(name)
                    if side == h:
                        model = g.p_h_m15 if ln < 0 else 1 - g.p_a_m15
                    else:
                        model = g.p_a_m15 if ln < 0 else 1 - g.p_h_m15
                    label, market = f"{side} {ln:+g}", "Puck line"
                else:
                    ln = line_of(name)
                    over = name.lower().startswith("over")
                    po = p_over(float(g.pred_total), ln)
                    model, label, market = (po if over else 1 - po), f"{'Over' if over else 'Under'} {ln:g}", "Total"
                rows.append({"matchup": f"{a} @ {h}", "day": g.date, "time": g.start_et, "market": market,
                             "side": label, "model": round(float(model), 4), "novig_fair": fair, "novig_ask": ask,
                             "edge": round(float(model) - ask, 4) if ask is not None else None,
                             "ask_qty": ask_qty, "bid": bid, "market_id": m["marketId"], "outcome_id": me["outcomeId"]})
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f.name
    if rows:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"  novig nhl  {len(rows)} sides priced"
          + (f", no Novig market for: {', '.join(missing)}" if missing else "") + f" -> {out.name}")


if __name__ == "__main__":
    main()
