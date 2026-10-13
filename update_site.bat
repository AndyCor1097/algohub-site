@echo off
cd /d "%~dp0"
echo Pulling latest picks from your algo folders...
python sync.py
echo.
if exist ".git" (
  git add -A
  git commit -m "update picks"
  git push
  echo Pushed. Live site updates in about a minute.
) else (
  echo Not connected to GitHub yet - see README.md step 3.
)
pause
