$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root "runtime\web.pid"

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "No PID file found. ETF market rotation monitor does not appear to be running."
    exit 0
}

$PidText = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $PidText) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "PID file was empty and has been removed."
    exit 0
}

$Process = Get-Process -Id ([int]$PidText) -ErrorAction SilentlyContinue
if (-not $Process) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Process $PidText is not running. PID file removed."
    exit 0
}

Stop-Process -Id $Process.Id -ErrorAction Stop
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "Stopped ETF market rotation monitor, PID $($Process.Id)."
