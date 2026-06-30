param(
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $name, $value = $trimmed.Split("=", 2)
        $name = $name.Trim()
        if (-not $name -or [Environment]::GetEnvironmentVariable($name, "Process")) { continue }
        $value = $value.Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Import-DotEnv -Path (Join-Path $Root ".env")

$HostAddress = if ($env:WEB_HOST) { $env:WEB_HOST } else { "127.0.0.1" }
$StartPort = if ($env:WEB_PORT) { [int]$env:WEB_PORT } else { 8000 }
$PortScanLimit = if ($env:WEB_PORT_SCAN_LIMIT) { [int]$env:WEB_PORT_SCAN_LIMIT } else { 30 }
$RuntimeDir = Join-Path $Root "runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$PidFile = Join-Path $RuntimeDir "web.pid"
New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir | Out-Null

$Python = if (Test-Path ".venv\Scripts\python.exe") {
    (Resolve-Path ".venv\Scripts\python.exe").Path
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    (Get-Command python).Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    (Get-Command py).Source
} else {
    throw "Python was not found. Install Python 3.10+ or create .venv first."
}

function Test-PortAvailable {
    param([string]$Address, [int]$Port)
    $listener = $null
    try {
        $ip = if ($Address -eq "0.0.0.0") { [System.Net.IPAddress]::Any } else { [System.Net.IPAddress]::Parse($Address) }
        $listener = [System.Net.Sockets.TcpListener]::new($ip, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

$Port = $null
for ($candidate = $StartPort; $candidate -lt ($StartPort + $PortScanLimit); $candidate++) {
    if (Test-PortAvailable -Address $HostAddress -Port $candidate) { $Port = $candidate; break }
}
if ($null -eq $Port) { throw "No available TCP port found from $StartPort to $($StartPort + $PortScanLimit - 1). Set WEB_PORT to another port and retry." }
if ($Port -ne $StartPort) { Write-Host "Port $StartPort is unavailable; using $Port instead." -ForegroundColor Yellow }

$Url = "http://$HostAddress`:$Port"
$Args = @("-m", "uvicorn", "web_app.server:app", "--host", $HostAddress, "--port", $Port)

if ($Foreground) {
    Write-Host "Starting ETF market rotation monitor in foreground at $Url"
    & $Python @Args
    exit $LASTEXITCODE
}

if (Test-Path -LiteralPath $PidFile) {
    $OldPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($OldPid -and (Get-Process -Id ([int]$OldPid) -ErrorAction SilentlyContinue)) {
        Write-Host "ETF market rotation monitor is already running: PID $OldPid, $Url" -ForegroundColor Yellow
        exit 0
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$StdoutLog = Join-Path $LogDir "web_$Timestamp.out.log"
$StderrLog = Join-Path $LogDir "web_$Timestamp.err.log"
$Process = Start-Process -FilePath $Python -ArgumentList $Args -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
Set-Content -LiteralPath $PidFile -Value $Process.Id -Encoding ASCII

Write-Host "ETF market rotation monitor started."
Write-Host "URL: $Url"
Write-Host "PID: $($Process.Id)"
Write-Host "PID file: $PidFile"
Write-Host "Logs: $StdoutLog ; $StderrLog"
Write-Host "Stop: .\stop_web.ps1"
