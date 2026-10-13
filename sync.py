"""
sync.py: copies the latest picks (and your card designs) from each algo folder into this site.

It ONLY READS your algo folders. It never changes, moves, or deletes anything in them.
Run it after your algos finish (or just double-click update_site.bat).
"""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESKTOP = HERE.parent                      # AlgoHub_Site sits on your Desktop next to the algo folders
DATA = HERE / "data"

# folder in data/ -> (where the algo saves it, file pattern, how many recent files to keep)
SOURCES = {
    "nfl":       (DESKTOP / "nfl_algo" / "picks",               "2026_wk*.csv",           6),
    "nfl_props": (DESKTOP / "nfl_algo" / "picks",               "props_2026_wk*.csv",     3),
    "nfl_posts": (DESKTOP / "nfl_algo" / "posts",               "2026_wk*.png",           6),
    "cfb":       (DESKTOP / "cfb_algo",                         "predictions_week*.json", 6),
    "mlb":       (DESKTOP / "algohub" / "game_algo" / "output", "all_games_*.csv",        21),
    "mlb_hr":    (DESKTOP / "HR_Model" / "data",                "today.json",             1),
    "nhl":       (DESKTOP / "nhl_game_algo" / "picks",               "nhl_*.csv",              21),
    "nba":       (DESKTOP / "NBA_Model" / "data",               "nba_today.json",         1),
    "cbb":       (DESKTOP / "cbb_algo" / "picks",               "cbb_*.csv",              14),
}

# single files: (source, destination inside this site)
SINGLE = [
    (DESKTOP / "nfl_algo" / "cards.py",            HERE / "nfl_cards.py"),   # your NFL card design
    (DESKTOP / "cfb_algo" / "cards.py",            HERE / "cfb_cards.py"),   # your CFB card design
    (DESKTOP / "nfl_algo" / "tracker.csv",         DATA / "nfl_tracker.csv"),
    (DESKTOP / "cfb_algo" / "tracker_summary.json", DATA / "cfb_tracker.json"),
    (DESKTOP / "nhl_game_algo" / "cards.py",            HERE / "nhl_cards.py"),   # your NHL card design
    (DESKTOP / "nhl_game_algo" / "tracker.csv",         DATA / "nhl_tracker.csv"),
    (DESKTOP / "cbb_algo" / "cards.py",            HERE / "cbb_cards.py"),   # your CBB card design
    (DESKTOP / "cbb_algo" / "tracker.csv",         DATA / "cbb_tracker.csv"),
]


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
            print(f"  {sport:10s} no files yet")
            continue
        out.mkdir(parents=True, exist_ok=True)
        if sport not in ("nba", "mlb_hr"):      # dated folders: keep history of the stamped ones
            for f in out.iterdir():             # clear old copies in the SITE folder only
                if f.is_file():
                    f.unlink()
        for f in files:
            dest = out / f.name
            if sport in ("nba", "mlb_hr"):      # these overwrite one file daily, so stamp it with its date
                try:
                    d = json.loads(f.read_text(encoding="utf-8")).get("date", "today")
                except Exception:
                    d = "today"
                dest = out / f"{'nba' if sport == 'nba' else 'hr'}_{d}.json"
            shutil.copy2(f, dest)
        print(f"  {sport:10s} {len(files)} file(s), latest: {files[-1].name}")

    for src, dest in SINGLE:
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  copied     {src.parent.name}/{src.name}")
    print("Done. Site data is up to date.")
    try:                                         # rebuild the real website in public/
        import build_site
        build_site.build()
    except Exception as ex:
        print(f"  ! website build failed: {ex}")


if __name__ == "__main__":
    main()
