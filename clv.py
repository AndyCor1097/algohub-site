"""
clv.py: closing line value for every game play (NFL, CFB, CBB, NBA, NHL).

For each LEAN/PLAY/HAMMER game pick, compares the number we posted to Novig's closing line
(saved by closing.py right before the game):
  spreads / totals : points better than the close   (we took +9.5, it closed +8.5 -> +1.0)
  moneyline / puck line : closing no-vig win % minus the break-even % of our price  (+3.0% = beat it)
Beating the close over and over is the best early sign a model is actually sharp, long before
win-loss has enough games to mean anything.

Writes data/clv.csv. sync.py runs it before the site build; the Record tab shows the summary.
"""
import difflib
import glob
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CLOSE = DATA / "closing"
OUT = DATA / "clv.csv"
ALIAS = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX", "LVR": "LV", "TB": "TB", "TBL": "TB", "UTAH": "UTA",
         "NJD": "NJ", "SJS": "SJ", "LAK": "LA", "NO": "NO", "NOP": "NO", "GS": "GSW", "SA": "SAS", "NY": "NYK"}


def _n(s):
    s = str(s or "").lower().replace("&", "and").replace("state", "st").replace("saint", "st")
    return re.sub(r"[^a-z0-9]", "", s)


def _abbr(s):
    s = re.sub(r"[^A-Z0-9&]", "", str(s or "").upper())
    return ALIAS.get(s, s)


def _side_score(name, abbr, nov_name, nov_abbr):
    best = 0.0
    if abbr and nov_abbr and _abbr(abbr) == _abbr(nov_abbr):
        best = 3.0
    a, b = _n(name), _n(nov_name)
    if a and b:
        if a == b:
            best = max(best, 3.0)
        elif len(a) >= 4 and (a in b or b in a):
            best = max(best, 2.5)
        else:
            r = difflib.SequenceMatcher(None, a, b).ratio()
            if r >= 0.85:
                best = max(best, 2.0)
    return best


def _match(close, day, away, home, away_abbr=None, home_abbr=None):
    """-> (row, flipped) or (None, False)"""
    c = close[close.day_et == day]
    best, out = 0.0, (None, False)
    for _, r in c.iterrows():
        for flip in (False, True):
            na, nh, aa, ah = (r.home, r.away, r.home_abbr, r.away_abbr) if flip else (r.away, r.home, r.away_abbr, r.home_abbr)
            sa, sh = _side_score(away, away_abbr, na, aa), _side_score(home, home_abbr, nh, ah)
            if sa >= 2 and sh >= 2 and sa + sh - (0.5 if flip else 0) > best:
                best, out = sa + sh - (0.5 if flip else 0), (r, flip)
    return out


def _be(odds):
    o = float(odds)
    return -o / (-o + 100) if o < 0 else 100 / (o + 100)


def _num(x):
    try:
        v = float(x)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ picks, one adapter per sport
def _plays_nfl():
    out = []
    for f in sorted(glob.glob(str(DATA / "nfl" / "*_wk*.csv"))):
        d = pd.read_csv(f)
        for r in d.itertuples():
            day = str(r.gameday)[:10]
            base = dict(sport="nfl", day=day, away=r.away_team, home=r.home_team, away_abbr=r.away_team,
                        home_abbr=r.home_team, game=f"{r.away_team} @ {r.home_team}")
            if isinstance(r.sp_tier, str) and r.sp_tier and _num(r.spread_line) is not None:
                home = r.sp_side == r.home_team
                line = -float(r.spread_line) if home else float(r.spread_line)     # this side's handicap
                out.append({**base, "market": "SPREAD", "tier": r.sp_tier, "pick": r.sp_pick,
                            "side": "home" if home else "away", "line": line, "price": None})
            if isinstance(r.tot_tier, str) and r.tot_tier and _num(r.total_line) is not None:
                out.append({**base, "market": "TOTAL", "tier": r.tot_tier, "pick": r.tot_pick,
                            "side": "over" if str(r.tot_pick).upper().startswith("OVER") else "under",
                            "line": float(r.total_line), "price": None})
            if isinstance(r.ml_pick, str) and r.ml_pick and _num(r.ml_odds) is not None:
                out.append({**base, "market": "ML", "tier": "VALUE", "pick": f"{r.ml_pick} ML",
                            "side": "home" if r.ml_pick == r.home_team else "away", "line": None,
                            "price": float(r.ml_odds)})
    return out


def _plays_dated(sport, folder, pattern, away_c, home_c, aa_c=None, ha_c=None, day_c="day"):
    """CBB / NBA: same column layout (spread = home line, sp_edge > 0 = home)."""
    out = []
    for f in sorted(glob.glob(str(DATA / folder / pattern))):
        d = pd.read_csv(f)
        for r in d.to_dict("records"):
            day = str(r.get(day_c))[:10]
            base = dict(sport=sport, day=day, away=r[away_c], home=r[home_c],
                        away_abbr=r.get(aa_c) if aa_c else None, home_abbr=r.get(ha_c) if ha_c else None,
                        game=f"{r[away_c]} @ {r[home_c]}")
            sp = _num(r.get("spread"))
            if isinstance(r.get("sp_tier"), str) and r["sp_tier"] and sp is not None:
                home = float(r.get("sp_edge") or 0) > 0
                out.append({**base, "market": "SPREAD", "tier": r["sp_tier"], "pick": r.get("sp_pick"),
                            "side": "home" if home else "away", "line": sp if home else -sp, "price": None})
            tot = _num(r.get("total"))
            if isinstance(r.get("tot_tier"), str) and r["tot_tier"] and tot is not None:
                out.append({**base, "market": "TOTAL", "tier": r["tot_tier"], "pick": r.get("tot_pick"),
                            "side": "over" if str(r.get("tot_pick")).upper().startswith("OVER") else "under",
                            "line": tot, "price": None})
            if isinstance(r.get("ml_pick"), str) and r["ml_pick"] and _num(r.get("ml_odds")) is not None:
                out.append({**base, "market": "ML", "tier": "VALUE", "pick": f"{r['ml_pick']} ML",
                            "side": "home" if r["ml_pick"] == r[home_c] else "away", "line": None,
                            "price": float(r["ml_odds"])})
    return out


def _plays_nhl():
    out = []
    for f in sorted(glob.glob(str(DATA / "nhl" / "nhl_*.csv"))):
        d = pd.read_csv(f)
        for r in d.to_dict("records"):
            base = dict(sport="nhl", day=str(r.get("date"))[:10], away=r["away_team"], home=r["home_team"],
                        away_abbr=r["away_team"], home_abbr=r["home_team"], game=f"{r['away_team']} @ {r['home_team']}")
            if isinstance(r.get("ml_tier"), str) and r["ml_tier"] and _num(r.get("ml_odds")) is not None:
                out.append({**base, "market": "ML", "tier": r["ml_tier"], "pick": f"{r['ml_pick']} ML",
                            "side": "home" if r["ml_pick"] == r["home_team"] else "away", "line": None,
                            "price": float(r["ml_odds"])})
            if isinstance(r.get("pl_tier"), str) and r["pl_tier"] and _num(r.get("pl_odds")) is not None:
                m = re.match(r"(\S+)\s*([+-]\d+(?:\.\d+)?)", str(r.get("pl_pick")))
                if m:
                    home = m.group(1) == r["home_team"]
                    out.append({**base, "market": "PUCK LINE", "tier": r["pl_tier"], "pick": r["pl_pick"],
                                "side": "home" if home else "away", "line": float(m.group(2)),
                                "price": float(r["pl_odds"])})
            if isinstance(r.get("tot_tier"), str) and r["tot_tier"] and _num(r.get("total_line")) is not None:
                out.append({**base, "market": "TOTAL", "tier": r["tot_tier"], "pick": r.get("tot_pick"),
                            "side": "over" if str(r.get("tot_pick")).upper().startswith("OVER") else "under",
                            "line": float(r["total_line"]), "price": _num(r.get("tot_odds"))})
    return out


def _plays_cfb():
    out = []
    for f in sorted(glob.glob(str(DATA / "cfb" / "predictions_week*.json"))):
        try:
            games = json.load(open(f, encoding="utf-8")).get("games", [])
        except (OSError, ValueError):
            continue
        for g in games:
            lab, side, bs = g.get("edge_label"), g.get("edge_side"), _num(g.get("book_spread"))
            if not lab or side not in ("home", "away") or bs is None:
                continue
            ts = pd.Timestamp(g.get("commence_time") or g.get("start_date"))
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            day = (ts - pd.Timedelta(hours=5)).strftime("%Y-%m-%d")
            tier = re.sub(r"[^A-Z]", "", str(lab).upper())
            out.append(dict(sport="cfb", day=day, away=g["away_team"], home=g["home_team"], away_abbr=None,
                            home_abbr=None, game=f"{g['away_team']} @ {g['home_team']}", market="SPREAD",
                            tier=tier, pick=f"{g.get('edge_pick')} {bs if side == 'home' else -bs:+g}",
                            side=side, line=bs if side == "home" else -bs, price=None))
    return out


# ------------------------------------------------------------------ grade vs the close
def _clv(p, c, flip):
    """-> (clv value, unit, closing number as text). Everything is put in the PICK's home/away orientation
    first (flip = Novig lists the game the other way round, e.g. neutral sites)."""
    side = p["side"]
    ch, pc, ph = _num(c.spread_home), _num(c.p_home_cover), _num(c.p_home)
    if flip:
        ch = -ch if ch is not None else None
        pc = 1 - pc if pc is not None else None
        ph = 1 - ph if ph is not None else None
    if p["market"] in ("SPREAD", "PUCK LINE"):
        if ch is None:
            return None, None, None
        close_side = ch if side == "home" else -ch
        if p["market"] == "PUCK LINE":       # same +/-1.5 both times: compare prices (closing no-vig % vs ours)
            if pc is None or abs(close_side - p["line"]) > 1e-9 or p["price"] is None:
                return None, None, None
            ps = pc if side == "home" else 1 - pc
            return round((ps - _be(p["price"])) * 100, 1), "%", f"{close_side:+g}"
        return round(p["line"] - close_side, 1), "pts", f"{close_side:+g}"
    if p["market"] == "TOTAL":
        ct, po = _num(c.total), _num(c.p_over)
        if ct is None:
            return None, None, None
        if p.get("price") is not None and abs(ct - p["line"]) < 1e-9 and po is not None:
            ps = po if side == "over" else 1 - po
            return round((ps - _be(p["price"])) * 100, 1), "%", f"{ct:g}"
        d = ct - p["line"] if side == "over" else p["line"] - ct
        return round(d, 1), "pts", f"{ct:g}"
    if p["market"] == "ML":
        if ph is None or p["price"] is None:
            return None, None, None
        ps = ph if side == "home" else 1 - ph
        return round((ps - _be(p["price"])) * 100, 1), "%", f"{ps:.0%}"
    return None, None, None


def main():
    plays = (_plays_nfl() + _plays_cfb() + _plays_nhl()
             + _plays_dated("cbb", "cbb", "cbb_*.csv", "away_name", "home_name")
             + _plays_dated("nba", "nba", "nba_2*.csv", "away_name", "home_name", "away_abbr", "home_abbr"))
    rows, closes = [], {}
    for p in plays:
        sp = p["sport"]
        if sp not in closes:
            f = CLOSE / f"{sp}.csv"
            closes[sp] = pd.read_csv(f) if f.exists() else pd.DataFrame()
        c = closes[sp]
        if c.empty:
            continue
        r, flip = _match(c, p["day"], p["away"], p["home"], p.get("away_abbr"), p.get("home_abbr"))
        if r is None:
            continue
        v, unit, close_txt = _clv(p, r, flip)
        if v is None:
            continue
        rows.append(dict(sport=sp, day=p["day"], game=p["game"], market=p["market"], tier=p["tier"],
                         pick=p["pick"], close=close_txt, clv=v, unit=unit))
    df = pd.DataFrame(rows, columns=["sport", "day", "game", "market", "tier", "pick", "close", "clv", "unit"])
    if len(df):
        df = df.drop_duplicates(["sport", "day", "game", "market", "pick"], keep="last")
    df.to_csv(OUT, index=False)
    by = df.groupby("sport").size().to_dict() if len(df) else {}
    print(f"  clv        {len(df)} plays graded vs the Novig close " + (str(by) if by else "(no closing lines saved yet)"))


def summary(sport):
    """{'n', 'beat', 'pts', 'n_pts', 'pct', 'n_pct'} for the Record tab, or None."""
    if not OUT.exists():
        return None
    d = pd.read_csv(OUT)
    d = d[d.sport == sport]
    if d.empty:
        return None
    nz = d[d.clv != 0]
    pts, pct = d[d.unit == "pts"], d[d.unit == "%"]
    return dict(n=len(d), beat=(nz.clv > 0).mean() if len(nz) else None,
                pts=pts.clv.mean() if len(pts) else None, n_pts=len(pts),
                pct=pct.clv.mean() if len(pct) else None, n_pct=len(pct))


if __name__ == "__main__":
    main()
