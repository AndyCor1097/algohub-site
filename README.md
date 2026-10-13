# The AlgoHub: one site, every algo

This folder is its own thing. It **only reads** your algo folders (nfl_algo, cfb_algo, nhl_game_algo, HR_Model,
NBA_Model, algohub/game_algo) and never changes them. Your existing per-sport
sites keep working exactly like before.

## Files
- `app.py`: the website (one tab per sport)
- `sync.py`: grabs the latest picks from each algo folder into `data/`
- `preview.bat`: double-click to see the site on your computer
- `update_site.bat`: double-click after running your algos to push fresh picks live
- `requirements.txt`, `.streamlit/config.toml`: site setup and dark theme

## 1. Preview it (on your computer)
Double-click `preview.bat`. A browser tab opens with the site.

## 2. Put it on GitHub (one time)
1. On github.com, click **New repository** and name it `algohub-site`. Don't add a README.
2. Open a terminal in this folder and run:
   ```
   git init
   git add -A
   git commit -m "first version"
   git branch -M main
   git remote add origin https://github.com/AndyCor1097/algohub-site.git
   git push -u origin main
   ```

## 3. Deploy it (one time)
Go to share.streamlit.io, click **Create app**, pick `algohub-site`, set main file `app.py`, and deploy.

## Daily routine
Run your algos like normal, then double-click `update_site.bat`. Done.

## Adding CBB later
Have the CBB algo save picks as CSVs into `CBB_Model\picks\` and the CBB tab fills in automatically.
