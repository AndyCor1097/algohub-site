@echo off
REM Saves Novig closing lines for games starting soon (for CLV). Log: logs\closing.log
cd /d "%~dp0"
python closing.py
echo Done. See logs\closing.log
timeout /t 10
