param(
  [int]$Port = 5000,
  [string]$ProjectPath = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
  [string]$WeeklyRescanDay = 'Sunday',  # Sunday, Monday, ...
  [string]$WeeklyRescanTime = '03:00',  # HH:mm 24h
  [switch]$CreateFirewall
)

Write-Host "[Info] ProjectPath = $ProjectPath"
Set-Location $ProjectPath

if ($CreateFirewall) {
  try {
    Write-Host "[Info] Creating firewall rule for TCP $Port (if missing)..."
    New-NetFirewallRule -DisplayName "Vivagoal Photo Finder" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Domain -ErrorAction SilentlyContinue | Out-Null
  } catch {}
}

if (-not (Test-Path ".venv")) {
  Write-Host "[Info] Creating virtual environment (.venv)..."
  $py = "py"
  try { & $py -3.12 -m venv .venv } catch { & $py -3.14 -m venv .venv }
}

Write-Host "[Info] Installing requirements..."
& .\.venv\Scripts\python.exe -m pip install -U pip setuptools wheel | Out-Null
& .\.venv\Scripts\pip.exe install -r requirements.txt || throw "pip install failed"

$waitress = Join-Path $ProjectPath ".venv\Scripts\waitress-serve.exe"
if (-not (Test-Path $waitress)) { throw "waitress-serve.exe not found at $waitress" }

Write-Host "[Info] Creating Scheduled Task: Vivagoal Photo Finder (At logon for current user)"
$action = New-ScheduledTaskAction -Execute $waitress -Argument "--listen=0.0.0.0:$Port app:app" -WorkingDirectory $ProjectPath
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType InteractiveToken -RunLevel LeastPrivilege
try { Unregister-ScheduledTask -TaskName "Vivagoal Photo Finder" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Register-ScheduledTask -TaskName "Vivagoal Photo Finder" -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null

Write-Host "[Info] Creating Scheduled Task: Vivagoal Photo Finder Weekly Rescan ($WeeklyRescanDay $WeeklyRescanTime)"
$rescanCmd = "Invoke-WebRequest -UseBasicParsing -Method POST http://localhost:$Port/rescan | Out-Null"
$rescanAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -Command $rescanCmd"
$timeParts = $WeeklyRescanTime.Split(':')
$h = [int]$timeParts[0]
$m = [int]$timeParts[1]
$rescanTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $WeeklyRescanDay -At ([datetime]::Today.Date.AddHours($h).AddMinutes($m).TimeOfDay)
try { Unregister-ScheduledTask -TaskName "Vivagoal Photo Finder Weekly Rescan" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Register-ScheduledTask -TaskName "Vivagoal Photo Finder Weekly Rescan" -Action $rescanAction -Trigger $rescanTrigger -Settings (New-ScheduledTaskSettingsSet) | Out-Null

Write-Host "[Done] Tasks created. To start now, run:"
Write-Host "       Start-ScheduledTask -TaskName 'Vivagoal Photo Finder'"
Write-Host "       Or run start_server.bat for a foreground session"

