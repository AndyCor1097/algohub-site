@echo off
REM Run this ONCE. Saves closing lines every 30 minutes, 11:30 AM to midnight, for CLV tracking.
REM Runs hidden (no window pops up), free (Novig), never touches your picks.
cd /d "%~dp0"
if not exist logs mkdir logs
set PYF=%~dp0closing.py
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source; if (-not $pw) { $pw = (Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe') };" ^
  "$a = New-ScheduledTaskAction -Execute $pw -Argument '%PYF%' -WorkingDirectory '%~dp0';" ^
  "$t = New-ScheduledTaskTrigger -Daily -At 11:30AM;" ^
  "$t.Repetition = (New-ScheduledTaskTrigger -Once -At 11:30AM -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 12 -Minutes 30)).Repetition;" ^
  "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew;" ^
  "Register-ScheduledTask -TaskName 'AlgoHub - Closing lines' -Action $a -Trigger $t -Settings $s -Force | Out-Null;" ^
  "Write-Host 'Scheduled: AlgoHub - Closing lines (every 30 min, 11:30 AM - midnight)'"
echo.
echo Done. Log: logs\closing.log
pause
