"""
sync.py: copies the latest picks from each of your algo folders into this site's data/ folder.

It ONLY READS your algo folders. It never changes, moves, or deletes anything in them.
Run it after your algos finish (or just double-click update_site.bat).
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESKTOP = HERE.parent                      # AlgoHub_Site sits on your Desktop next to the algo folders
DATA = HERE / "data"

# sport folder name -> (where the algo saves picks, file pattern, how many recent files to keep)
SOURCES = {
    "nfl":    (DESKTOP / "nfl_algo" / "picks",                "2026_wk*.csv",        6),
    "nfl_props": (DESKTOP / "nfl_algo" / "picks",             "props_2026_wk*.csv",  3),
    "cfb":    (DESKTOP / "cfb_algo",                          "predictions_week*.json", 6),
    "mlb":    (DESKTOP / "algohub" / "game_algo" / "output",  "all_games_*.csv",     21),
    "mlb_hr": (DESKTOP / "HR_Model" / "predictions",          "hr_predictions_*.csv", 14),
    "nhl":    (DESKTOP / "NHL_Algo" / "picks",                "nhl_picks_*.json",    21),
    "nba":    (DESKTOP / "NBA_Model" / "data",                "nba_today.json",      1),
    "cbb":    (DESKTOP / "CBB_Model" / "picks",               "*.csv",               14),
}


def sort_key(p: Path):
    # sort week files numerically (week10 after week9), everything else by name (dates sort fine)
    digits = "".join(c for c in p.stem if c.isdigit())
    return (len(digits), digits, p.name)


def main():
    DATA.mkdir(exist_ok=True)
    for sport, (src, pattern, keep) in SOURCES.items():
        out = DATA / sport
        if not src.exists():
            print(f"  {sport:10s} skipped (no folder yet)")
            continue
        files = sorted(src.glob(pattern), key=sort_key)[-keep:]
        if not files:
            print(f"  {sport:10s} no pick files yet")
            continue
        out.mkdir(parents=True, exist_ok=True)
        for f in out.iterdir():                 # clear old copies in the SITE folder only
            if f.is_file():
                f.unlink()
        for f in files:
            dest = out / f.name
            if sport == "nba":                  # NBA overwrites one file daily, so stamp it with its date
                import json
                try:
                    d = json.loads(f.read_text(encoding="utf-8")).get("date", "today")
                except Exception:
                    d = "today"
                dest = out / f"nba_{d}.json"
            shutil.copy2(f, dest)
        print(f"  {sport:10s} {len(files)} file(s), latest: {files[-1].name}")
    print("Done. Site data is up to date.")


if __name__ == "__main__":
    main()
