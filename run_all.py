"""
run_all.py: runs every active algo, then rebuilds + pushes the site. This is what the 11 AM task runs.

  python run_all.py            run everything now
  python run_all.py nhl cfb    run just those (then the site)

Turn a sport on/off in ACTIVE below (MLB/NBA are on hold, CBB starts in November).
Log for each day: AlgoHub_Site\\logs\\run_all_<date>.log
"""
import os
import subprocess
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESK = HERE.parent
LOGS = HERE / "logs"
PY = sys.executable

ACTIVE = ["nfl", "cfb", "nhl", "epl"]          # add "cbb", "nba", "mlb" when their seasons are live


def log(msg):
    LOGS.mkdir(exist_ok=True)
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOGS / f"run_all_{date.today()}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cwd, *args, timeout=1800):
    """Run one command in an algo folder; log its output; never stop the whole run on an error."""
    log(f"  > {Path(cwd).name}: python {' '.join(args)}")
    try:
        # force UTF-8 output: when output is captured, Windows defaults to cp1252 and any emoji
        # in an algo's print() (CFB's edge labels, weather arrows) crashes the script
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        r = subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", env=env)
        out = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
        for ln in out.splitlines()[-25:]:
            log("    " + ln)
        if r.returncode != 0:
            log(f"    !! exited with code {r.returncode}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"    !! timed out after {timeout // 60} min")
    except Exception:
        log("    !! " + traceback.format_exc().splitlines()[-1])
    return False


# ------------------------------------------------------------------ sports
def nfl():
    # nfl_algo's own autopilot: grades last week, retrains weekly, makes picks/props/cards, pushes its repo
    run(DESK / "nfl_algo", "nfl_algo.py", "auto", timeout=3600)


def cfb_week():
    """Current CFB week from CollegeFootballData's calendar (falls back to a date guess)."""
    try:
        import re
        import requests
        key = re.search(r'CFBD_KEY\s*=\s*"([^"]+)"', (DESK / "cfb_algo" / "predict.py").read_text(encoding="utf-8")).group(1)
        r = requests.get("https://api.collegefootballdata.com/calendar", params={"year": date.today().year},
                         headers={"Authorization": f"Bearer {key}"}, timeout=20)
        today = date.today().isoformat()
        for w in sorted(r.json(), key=lambda w: int(w.get("week", 0))):
            if w.get("seasonType", "regular") != "regular":
                continue
            # a week is over once its last game has kicked off (CFBD's endDate runs into Monday/Tuesday,
            # which kept us on last week after Saturday)
            end = str(w.get("lastGameStart") or w.get("endDate") or "")[:10]
            if end and end >= today:
                wk = int(w["week"])
                break
        else:
            wk = None
        if wk is not None:
            # if you've already dropped in next week's data, go to next week
            if date.today().weekday() in (6, 0, 1, 2) and \
                    (DESK / "cfb_algo" / "data" / f"training_data_{date.today().year}_week{wk + 1:02d}.csv").exists():
                wk += 1
            return wk
    except Exception as ex:
        log(f"    (calendar lookup failed: {ex}; guessing week from the date)")
    return max(1, (date.today() - date(date.today().year, 8, 30)).days // 7 + 1)


def cfb():
    folder = DESK / "cfb_algo"
    wk = cfb_week()
    log(f"  CFB week {wk}")
    new_week = not (folder / f"predictions_week{wk}.json").exists()
    if new_week:                         # first run of a new week: the full weekly update
        run(folder, "fetch_inseason.py")
        run(folder, "fetch_lines.py", timeout=600)
        run(folder, "grade.py", str(wk - 1))
        # (features.py / model.py removed: picks come from the CFBD training_data CSV, not that old model,
        #  and those steps only printed "No games" / "features_all.csv not found")
    else:                                # other days: fresh lines, fresh picks
        run(folder, "fetch_lines.py", timeout=600)
    run(folder, "predict.py", str(wk), "--push")
    if new_week:
        subprocess.run(["git", "add", "tracker_summary.json"], cwd=folder, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Update tracker week {wk - 1}"], cwd=folder, capture_output=True)
        subprocess.run(["git", "push"], cwd=folder, capture_output=True)


def nhl():
    # grades the last 3 days (both trackers), retrains every 3 days, today's picks. Site push happens below.
    run(DESK / "nhl_game_algo", "nhl_algo.py", "auto", "--no-push")


def epl():
    # grades finished matches, then picks for the next 8 days (Premier League)
    run(DESK / "epl_algo", "epl_algo.py", "auto")


def site():
    log("SITE: sync + build")
    run(HERE, "sync.py")
    for cmd in (["git", "rm", "-r", "--cached", "--quiet", "__pycache__"], ["git", "add", "-A"],
                ["git", "commit", "-m", f"daily auto {datetime.now():%Y-%m-%d %H:%M}"]):
        subprocess.run(cmd, cwd=HERE, capture_output=True)
    r = subprocess.run(["git", "push"], cwd=HERE, capture_output=True, text=True)
    log("  site push: " + ("done, live in ~1 min" if r.returncode == 0 else "FAILED " + (r.stderr or r.stdout)[-300:]))


SPORTS = {"nfl": nfl, "cfb": cfb, "nhl": nhl, "epl": epl}

if __name__ == "__main__":
    pick = [a.lower() for a in sys.argv[1:]] or ACTIVE
    log(f"===== RUN ALL {datetime.now():%Y-%m-%d %H:%M} : {', '.join(pick)} =====")
    for s in pick:
        if s in SPORTS:
            log(s.upper())
            try:
                SPORTS[s]()
            except Exception:
                log("  !! " + traceback.format_exc().splitlines()[-1])
    site()
    log("===== DONE =====")
