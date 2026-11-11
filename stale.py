"""
stale.py: the stale-line board. Spots where DraftKings is slow to move and is offering a better number
than the sharp market. That's a +EV bet on its own, before our model even weighs in. When our model
ALSO likes that side, it's the best bet on the board.

Sharp numbers we compare DK to:
  NFL, CFB : Novig's no-vig price AT DK's line (from nfl_novig.py / cfb_novig.py)  -> real EV %
  CBB, CFB : Pinnacle's line vs DK's line (from the algos)                         -> points better + rough EV %
Writes data/stale.csv. sync.py runs it before the site build; each sport gets a "Stale lines" tab.
"""
import glob
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = DATA / "stale.csv"
MIN_EV = 0.02              # +2% expected value or better to make the board (Novig-priced sides)
MAX_EV = 0.12              # more than this is almost always a live/in-game or stale-feed price, not a real bet
PTS_K = {"cbb": 0.030, "cfb": 0.025}     # ~cover % per point of line, near the middle of the distribution
TOT_K = 0.020


def _dec(o):
    o = float(o)
    return 1 + (100 / -o if o < 0 else o / 100)


def _num(x):
    try:
        v = float(x)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _latest(pattern):
    fs = sorted(glob.glob(str(DATA / pattern)), key=lambda p: [int(x) for x in re.findall(r"\d+", Path(p).stem)])
    return Path(fs[-1]) if fs else None


def _novig_rows(sport, f, ml_lookup):
    """Novig fair % for each side at DK's line. Spreads/totals priced at the standard -110."""
    rows = []
    if f is None or not f.exists():
        return rows
    d = pd.read_csv(f)
    for r in d.itertuples():
        fair = _num(r.novig_fair)
        if fair is None:
            continue
        if r.market in ("Spread", "Total"):
            price = -110.0
        else:
            price = ml_lookup.get((r.matchup, r.side))
            if price is None:
                continue
        ev = fair * _dec(price) - 1
        if MIN_EV <= ev <= MAX_EV:
            model = _num(r.model)
            rows.append(dict(sport=sport, day=str(r.day)[:10], game=r.matchup, market=r.market, bet=r.side,
                             dk=f"{price:+.0f}" if r.market not in ("Spread", "Total") else "-110 (assumed)", sharp=f"Novig {fair:.0%}", ev=round(ev * 100, 1),
                             model_agrees=bool(model is not None and model > fair)))
    return rows


def _nfl():
    f = _latest("nfl_novig/*_wk*.csv")
    picks = _latest("nfl/*_wk*.csv")
    ml = {}
    if picks is not None:
        p = pd.read_csv(picks)
        for r in p.itertuples():
            mu = f"{r.away_team} @ {r.home_team}"
            if _num(r.ml_home) is not None:
                ml[(mu, f"{r.home_team} ML")] = float(r.ml_home)
            if _num(r.ml_away) is not None:
                ml[(mu, f"{r.away_team} ML")] = float(r.ml_away)
    return _novig_rows("nfl", f, ml)


def _cfb():
    rows = []
    pf = _latest("cfb/predictions_week*.json")
    games = json.loads(pf.read_text(encoding="utf-8")).get("games", []) if pf else []
    ml = {}
    for g in games:
        mu = f"{g['away_team']} @ {g['home_team']}"
        for side, k in ((g["home_team"], "home_moneyline_book"), (g["away_team"], "away_moneyline_book")):
            if _num(g.get(k)) is not None:
                ml[(mu, f"{side} ML")] = float(g[k])
    rows += _novig_rows("cfb", _latest("cfb_novig/cfb_week*.csv"), ml)
    for g in games:                                   # Pinnacle point gaps on spreads
        bs, ps = _num(g.get("book_spread")), _num(g.get("pinnacle_spread"))
        if bs is None or ps is None or abs(bs - ps) < 1:
            continue
        home_better = bs > ps          # DK gives the home side more points than Pinnacle does
        side = g["home_team"] if home_better else g["away_team"]
        line = bs if home_better else -bs
        gap = abs(bs - ps)
        ev = (0.5 + gap * PTS_K["cfb"]) * _dec(-110) - 1
        if not MIN_EV <= ev <= MAX_EV:
            continue
        me = _num(g.get("spread_edge"))
        rows.append(dict(sport="cfb", day=str(g.get("commence_time") or g.get("start_date") or "")[:10],
                         game=f"{g['away_team']} @ {g['home_team']}", market="Spread", bet=f"{side} {line:+g}",
                         dk=f"{line:+g} (-110)", sharp=f"Pinnacle {(ps if home_better else -ps):+g}", ev=round(ev * 100, 1),
                         model_agrees=bool(me is not None and ((me > 0) == home_better))))
    return rows


def _cbb():
    rows = []
    f = _latest("cbb/cbb_*.csv")
    if f is None:
        return rows
    for f in sorted(glob.glob(str(DATA / "cbb" / "cbb_*.csv")))[-2:]:          # today + tomorrow
        d = pd.read_csv(f)
        if "pin_spread" not in d:
            continue
        for r in d.itertuples():
            day = str(r.day)[:10]
            mu = f"{r.away_name} @ {r.home_name}"
            bs, ps = _num(r.spread), _num(r.pin_spread)
            if bs is not None and ps is not None and abs(bs - ps) >= 1:
                home_better = bs > ps
                side, line, gap = (r.home_name, bs, bs - ps) if home_better else (r.away_name, -bs, ps - bs)
                ev = (0.5 + gap * PTS_K["cbb"]) * _dec(-110) - 1
                if not MIN_EV <= ev <= MAX_EV:
                    continue
                rows.append(dict(sport="cbb", day=day, game=mu, market="Spread", bet=f"{side} {line:+g}",
                                 dk=f"{line:+g} (-110)", sharp=f"Pinnacle {(ps if home_better else -ps):+g}",
                                 ev=round(ev * 100, 1),
                                 model_agrees=bool((_num(r.sp_edge) or 0) > 0) == home_better))
            bt, pt = _num(r.total), _num(getattr(r, "pin_total", None))
            if bt is not None and pt is not None and abs(bt - pt) >= 1.5:
                over = bt < pt                 # DK total lower than Pinnacle -> over is the better number at DK
                ev = (0.5 + abs(bt - pt) * TOT_K) * _dec(-110) - 1
                if not MIN_EV <= ev <= MAX_EV:
                    continue
                mt = _num(r.pred_total)
                rows.append(dict(sport="cbb", day=day, game=mu, market="Total",
                                 bet=f"{'Over' if over else 'Under'} {bt:g}", dk=f"{bt:g} (-110)", sharp=f"Pinnacle {pt:g}",
                                 ev=round(ev * 100, 1),
                                 model_agrees=bool(mt is not None and ((mt > bt) == over))))
    return rows


def main():
    rows = []
    for fn in (_nfl, _cfb, _cbb):
        try:
            rows += fn()
        except Exception as ex:
            print(f"  ! stale {fn.__name__}: {type(ex).__name__}: {ex}")
    df = pd.DataFrame(rows, columns=["sport", "day", "game", "market", "bet", "dk", "sharp", "ev", "model_agrees"])
    from datetime import datetime, timedelta, timezone
    today = (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d")
    df = df[df.day.astype(str) >= today]                 # upcoming games only
    if len(df):
        df = df.sort_values(["sport", "model_agrees", "ev"], ascending=[True, False, False])
    df.to_csv(OUT, index=False)
    by = df.groupby("sport").size().to_dict() if len(df) else {}
    both = int(df.model_agrees.sum()) if len(df) else 0
    print(f"  stale      {len(df)} stale DK lines {by}, {both} where our model agrees too")


if __name__ == "__main__":
    main()
