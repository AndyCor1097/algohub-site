@echo off
REM Runs every active algo (NFL, CFB, NHL), then rebuilds + pushes the site.
REM The 11 AM task runs this. Double-click to run it any time. Log: logs\run_all_<date>.log
cd /d "%~dp0"
echo Running all algos... this can take 5-15 minutes. Don't close this window.
python run_all.py %*
echo.
echo Done. Details in logs\run_all_%date:~-4%-%date:~4,2%-%date:~7,2%.log
timeout /t 20
