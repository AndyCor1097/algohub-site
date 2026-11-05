@echo off
REM Removes old per-sport scheduled tasks. Everything now runs from "AlgoHub - Daily 11AM" (run_all) + "AlgoHub - Closing lines".
for %%T in ("AlgoHub CBB - Morning" "AlgoHub NBA - Morning" "AlgoHub NHL - Morning" "AlgoHub NHL - Evening" "AlgoHub NFL - Friday" "AlgoHub NFL - Sunday" "AlgoHub NFL - Tuesday") do schtasks /Delete /TN %%T /F >nul 2>&1
echo Old tasks removed. AlgoHub tasks still scheduled:
schtasks /Query /FO LIST | findstr /I "AlgoHub"
echo.
echo You should see only: AlgoHub - Daily 11AM  and  AlgoHub - Closing lines
pause
