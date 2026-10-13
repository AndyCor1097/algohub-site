@echo off
REM Runs the MLB game algo + HR model for today, then pushes everything to the site.
echo [1/3] MLB game algo...
cd /d "%~dp0..\algohub\game_algo"
python picks.py
echo.
echo [2/3] HR model (pulls Statcast, takes a few minutes)...
cd /d "%~dp0..\HR_Model"
python daily_run.py
echo.
echo [3/3] Pushing to the site...
cd /d "%~dp0"
python sync.py
git add -A
git commit -m "mlb update"
git push
echo.
echo Done. Site updates in about a minute.
pause
