@echo off
REM Builds the website and opens it on your PC at http://localhost:8000 (close this window to stop).
cd /d "%~dp0"
python build_site.py
if errorlevel 1 (
  echo.
  echo Build failed - copy the error above and send it to Claude.
  pause
  exit /b 1
)
start "" http://localhost:8000/
cd public
python -m http.server 8000
