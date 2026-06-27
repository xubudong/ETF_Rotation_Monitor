$ErrorActionPreference = "Stop"

$HostAddress = if ($env:WEB_HOST) { $env:WEB_HOST } else { "127.0.0.1" }
$StartPort = if ($env:WEB_PORT) { [int]$env:WEB_PORT } else { 8001 }
$PortScanLimit = if ($env:WEB_PORT_SCAN_LIMIT) { [int]$env:WEB_PORT_SCAN_LIMIT } else { 30 }
$Python = if (Test-Path ".venv\Scripts\python.exe") {
    ".venv\Scripts\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    "py"
} else {
    throw "Python was not found. Install Python 3.10+ or create .venv first."
}

function Test-PortAvailable {
    param(
        [string]$Address,
        [int]$Port
    )

    $listener = $null
    try {
        $ip = if ($Address -eq "0.0.0.0") {
            [System.Net.IPAddress]::Any
        } else {
            [System.Net.IPAddress]::Parse($Address)
        }
        $listener = [System.Net.Sockets.TcpListener]::new($ip, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

$Port = $null
for ($candidate = $StartPort; $candidate -lt ($StartPort + $PortScanLimit); $candidate++) {
    if (Test-PortAvailable -Address $HostAddress -Port $candidate) {
        $Port = $candidate
        break
    }
}

if ($null -eq $Port) {
    throw "No available TCP port found from $StartPort to $($StartPort + $PortScanLimit - 1). Set WEB_PORT to another port and retry."
}

if ($Port -ne $StartPort) {
    Write-Host "Port $StartPort is unavailable; using $Port instead." -ForegroundColor Yellow
}

Write-Host "Starting ETF market rotation monitor at http://$HostAddress`:$Port"
& $Python -m uvicorn web_app.server:app --host $HostAddress --port $Port
