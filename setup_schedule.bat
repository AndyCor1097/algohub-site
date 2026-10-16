@echo off
REM Run this ONCE. Schedules run_all.bat every day at 11:00 AM.
REM  - wakes the PC from sleep to run it
REM  - if the PC was off at 11, it runs as soon as you turn it on
REM  - removes the old separate NHL / NFL schedules so nothing runs twice
cd /d "%~dp0"
set BAT=%~dp0run_all.bat

schtasks /Delete /TN "AlgoHub NHL - Morning" /F >nul 2>&1
schtasks /Delete /TN "AlgoHub NHL - Evening" /F >nul 2>&1
schtasks /Delete /TN "AlgoHub NFL - Friday"  /F >nul 2>&1
schtasks /Delete /TN "AlgoHub NFL - Sunday"  /F >nul 2>&1
schtasks /Delete /TN "AlgoHub NFL - Tuesday" /F >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute '%BAT%' -WorkingDirectory '%~dp0';" ^
  "$t = New-ScheduledTaskTrigger -Daily -At 11:00AM;" ^
  "$s = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2);" ^
  "Register-ScheduledTask -TaskName 'AlgoHub - Daily 11AM' -Action $a -Trigger $t -Settings $s -Force | Out-Null;" ^
  "Write-Host 'Scheduled: AlgoHub - Daily 11AM'"

echo.
echo All set. Every day at 11 AM your PC runs NFL, CFB, NHL and pushes the site.
echo To change the time: open Task Scheduler, find "AlgoHub - Daily 11AM".
echo To remove it: schtasks /Delete /TN "AlgoHub - Daily 11AM" /F
pause
