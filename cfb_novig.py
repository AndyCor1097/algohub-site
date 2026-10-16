"""
cfb_novig.py: puts Novig's exchange prices next to your CFB model for the latest week.

Moneyline (model = home_win_prob) and the spread at the book's main line, or the closest Novig line
(model = cover chance from your projected margin). Totals are skipped on purpose: the CFB model takes the
book total as its total, so it has no totals opinion to compare yet.

Reads data/cfb/ (sync.py's copy of your CFB picks) and ../novig/novig.py (public routes, no key).
Writes data/cfb_novig/cfb_weekN.csv. sync.py runs it automatically.
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "novig"))
sys.path.insert(0, str(HERE))
SRC = HERE / "data" / "cfb"
OUT = HERE / "data" / "cfb_novig"
SD_MARGIN = 15.5          # typical college football spread of outcomes around a projection


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def line_of(name):
    m = re.search(r"([+-]?\d+(?:\.\d+)?)\s*$", name or "")
    return float(m.group(1)) if m else None


def abbr_of(name):
    return re.sub(r"\s*[+-]?\d+(?:\.\d+)?\s*$", "", name or "").strip()


def latest():
    files = sorted(SRC.glob("predictions_week*.json"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0)) \
        if SRC.exists() else []
    return files[-1] if files else None


def main():
    import novig
    from cfb_names import Matcher, home_away_abbr
    f = latest()
    if f is None:
        print("  novig cfb  no CFB week yet")
        return
    data = json.loads(f.read_text(encoding="utf-8"))
    games, week = data.get("games", []), data.get("week")
    m = Matcher({g["home_team"] for g in games} | {g["away_team"] for g in games})

    evs = novig.events("NCAAF")
    mk = novig.markets("NCAAF", props=False)
    by_event = {}
    for x in mk:
        by_event.setdefault(x["eventId"], []).append(x)
    lookup = {}                                         # (algo away, algo home) -> (event desc, markets)
    for eid, e in evs.items():
        a, h = novig.split_teams(e.get("description", ""))
        ma, mh = m.find(a), m.find(h)
        if ma and mh:
            lookup[(ma, mh)] = (a, h, by_event.get(eid, []))

    rows, missing = [], []
    for g in games:
        key = (g["away_team"], g["home_team"])
        if key not in lookup:
            missing.append(f"{key[0]} @ {key[1]}")
            continue
        n_away, n_home, ms = lookup[key]
        money = [x for x in ms if x["marketType"] == "MONEY" and len(x["outcomes"]) == 2]
        if not money:
            continue
        a_ab, h_ab = home_away_abbr([o["name"] for o in money[0]["outcomes"]], n_away, n_home)
        side_of = {a_ab: "away", h_ab: "home"}
        wanted = list(money[:1])
        # spread: Novig line closest to the book's home line (book_spread is the home handicap, + = underdog)
        bs = g.get("book_spread")
        spreads = []
        for x in ms:
            if x["marketType"] == "SPREAD" and len(x["outcomes"]) == 2:
                ho = [o for o in x["outcomes"] if abbr_of(o["name"]) == h_ab]
                if ho and line_of(ho[0]["name"]) is not None:
                    spreads.append((abs(line_of(ho[0]["name"]) - bs) if bs is not None else 99, x))
        if spreads and bs is not None:
            dist, best = min(spreads, key=lambda t: t[0])
            if dist <= 1.5:
                wanted.append(best)
        hwp = (g.get("home_win_prob") or 50) / 100
        margin = g.get("pred_margin") or 0.0
        for x in wanted:
            b = novig.book(x["marketId"]).get("orders", {})
            o1, o2 = x["outcomes"]
            for me, other in ((o1, o2), (o2, o1)):
                bid, _ = novig._side(b.get(me["outcomeId"], []))
                obid, ask_qty = novig._side(b.get(other["outcomeId"], []))
                ask = round(1 - obid, 4) if obid is not None else None
                fair = round((bid + ask) / 2, 4) if bid is not None and ask is not None else None
                side = side_of.get(abbr_of(me["name"]))
                if side is None:
                    continue
                team = g["home_team"] if side == "home" else g["away_team"]
                if x["marketType"] == "MONEY":
                    model, label, market = (hwp if side == "home" else 1 - hwp), f"{team} ML", "Moneyline"
                else:
                    ln = line_of(me["name"])
                    mg = margin if side == "home" else -margin
                    model, label, market = phi((mg + ln) / SD_MARGIN), f"{team} {ln:+g}", "Spread"
                rows.append({"matchup": f"{g['away_team']} @ {g['home_team']}", "day": str(g.get("start_date", ""))[:10],
                             "market": market, "side": label, "model": round(float(model), 4),
                             "novig_fair": fair, "novig_ask": ask,
                             "edge": round(float(model) - ask, 4) if ask is not None else None,
                             "ask_qty": ask_qty, "bid": bid, "market_id": x["marketId"], "outcome_id": me["outcomeId"]})
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"cfb_week{week}.csv"
    if rows:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"  novig cfb  {len(rows)} sides priced, {len(missing)} of {len(games)} games not on Novig"
          + " (finished or not listed)" + f" -> {out.name}")


if __name__ == "__main__":
    main()
