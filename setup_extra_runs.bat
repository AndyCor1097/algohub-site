@echo off
REM Run this ONCE. Adds two extra daily runs on top of the 11 AM one:
REM   5:45 PM  NBA   - after the evening injury reports, before 7 PM tips (props + sides re-priced on the news)
REM   9:30 PM  CBB   - prices TOMORROW's college hoops as soon as DK posts openers (openers are the softest lines)
REM Both run hidden-ish (minimized), skip themselves if another run is going, and never touch the 11 AM run.
cd /d "%~dp0"
set BAT=%~dp0run_all.bat
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable:$false -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew;" ^
  "$a1 = New-ScheduledTaskAction -Execute '%BAT%' -Argument 'nba' -WorkingDirectory '%~dp0';" ^
  "Register-ScheduledTask -TaskName 'AlgoHub - NBA pre-tip 545PM' -Action $a1 -Trigger (New-ScheduledTaskTrigger -Daily -At 5:45PM) -Settings $s -Force | Out-Null;" ^
  "$a2 = New-ScheduledTaskAction -Execute '%BAT%' -Argument 'cbb' -WorkingDirectory '%~dp0';" ^
  "Register-ScheduledTask -TaskName 'AlgoHub - CBB openers 930PM' -Action $a2 -Trigger (New-ScheduledTaskTrigger -Daily -At 9:30PM) -Settings $s -Force | Out-Null;" ^
  "Write-Host 'Scheduled: AlgoHub - NBA pre-tip 545PM, AlgoHub - CBB openers 930PM'"
echo.
echo Done. To remove: schtasks /Delete /TN "AlgoHub - NBA pre-tip 545PM" /F  (same for "AlgoHub - CBB openers 930PM")
pause
