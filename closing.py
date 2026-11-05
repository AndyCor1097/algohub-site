"""
closing.py: saves Novig's CLOSING lines (the last price before each game starts) so every pick can be
graded on closing line value (CLV): did we get a better number than the sharp market's final number?

Runs every 30 minutes from late morning to midnight (setup_closing.bat schedules it). Each run only looks
at games starting in the next ~50 minutes, so the last save for a game is 0-30 min before it starts.
Free: Novig's public prices, no Odds API credits.

Writes data/closing/<sport>.csv  (one row per game: the latest pre-game snapshot)
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "novig"))
OUT = HERE / "data" / "closing"
LEAGUES = [("NFL", "nfl", None), ("NCAAF", "cfb", None), ("NCAAB", "cbb", None), ("NBA", "nba", None),
           ("NHL", "nhl", 1.5)]
WINDOW_H = 0.85          # games starting within this many hours get snapshotted this run
KEEP_DAYS = 120


def to_et(ts):
    """UTC -> US Eastern (DST: 2nd Sun Mar 2am -> 1st Sun Nov 2am). No tz packages needed on Windows."""
    y = ts.year
    mar = datetime(y, 3, 8, tzinfo=timezone.utc)
    dst_start = mar + timedelta(days=(6 - mar.weekday()) % 7, hours=7)      # 2am EST = 7am UTC
    nov = datetime(y, 11, 1, tzinfo=timezone.utc)
    dst_end = nov + timedelta(days=(6 - nov.weekday()) % 7, hours=6)        # 2am EDT = 6am UTC
    return ts - timedelta(hours=4 if dst_start <= ts < dst_end else 5)


def snap(league, slug, fixed):
    from novig_lines import game_lines
    now = datetime.now(timezone.utc)
    try:
        games = game_lines(league, hours_ahead=WINDOW_H, fixed_spread=fixed, max_seconds=240)
    except Exception as ex:
        print(f"  {slug}: novig failed ({type(ex).__name__}: {ex})")
        return 0
    games = [g for g in games if g["start"] > now]          # pre-game only: live lines aren't a close
    if not games:
        return 0
    rows = []
    for g in games:
        rows.append(dict(day_et=to_et(g["start"]).strftime("%Y-%m-%d"), start=g["start"].isoformat(),
                         away=g["away"], home=g["home"], away_abbr=g.get("away_abbr"), home_abbr=g.get("home_abbr"),
                         spread_home=g.get("spread_home"), p_home_cover=g.get("p_home_cover"),
                         total=g.get("total"), p_over=g.get("p_over"), p_home=g.get("p_home"),
                         ml_home=g.get("ml_home"), ml_away=g.get("ml_away"), taken=now.isoformat()))
    new = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{slug}.csv"
    if f.exists():
        old = pd.read_csv(f)
        key = lambda d: d.away.astype(str) + "|" + d.home.astype(str) + "|" + d.day_et.astype(str)
        old = old[~key(old).isin(set(key(new)))]
        cut = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
        old = old[old.day_et.astype(str) >= cut]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(f, index=False)
    return len(rows)


def main():
    stamp = datetime.now().strftime("%H:%M")
    out = []
    for league, slug, fixed in LEAGUES:
        n = snap(league, slug, fixed)
        if n:
            out.append(f"{slug} {n}")
    print(f"[{stamp}] closing lines saved: " + (", ".join(out) if out else "no games starting soon"))


if __name__ == "__main__":
    # the scheduled task runs this with pythonw (no window popping up every 30 min), so log to a file
    (HERE / "logs").mkdir(exist_ok=True)
    with open(HERE / "logs" / "closing.log", "a", encoding="utf-8") as _log:
        sys.stdout = sys.stderr = _log
        try:
            main()
        except Exception as ex:
            print(f"[{datetime.now():%H:%M}] closing failed: {type(ex).__name__}: {ex}")
