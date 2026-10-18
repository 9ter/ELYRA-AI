param(
    [ValidateRange(1, 65535)]
    [int]$Port = 3000
)

$ErrorActionPreference = 'Stop'
$failed = $false
$dataDirectory = Join-Path $PSScriptRoot '.data'

function Remove-MatchingPidFile {
    param([string]$Name, [int]$StoppedId)
    $file = Join-Path $dataDirectory $Name
    $saved = (Get-Content -LiteralPath $file -ErrorAction SilentlyContinue) -as [int]
    if ($saved -eq $StoppedId) {
        Remove-Item -LiteralPath $file -ErrorAction Stop
    }
}

# Inspect the command target, not just a saved PID (which Windows can reuse).
# Both `ngrok http 3000` and `ngrok http http://127.0.0.1:3000` are supported.
$targetPattern = '^(?:' + $Port + '|(?:https?://)?(?:localhost|127\.0\.0\.1|\[::1\]):' + $Port + '/?)$'
$tunnels = @(Get-CimInstance Win32_Process -Filter "Name='ngrok.exe'" | Where-Object {
    $arguments = @([regex]::Matches($_.CommandLine, '"[^"]*"|[^\s"]+') | ForEach-Object { $_.Value.Trim('"') })
    for ($index = 1; $index -lt $arguments.Count - 1; $index++) {
        if ($arguments[$index] -eq 'http' -and $arguments[$index + 1] -match $targetPattern) {
            return $true
        }
    }
    return $false
})

if (-not $tunnels) {
    Write-Host "ngrok is not running for local port $Port."
}
foreach ($tunnel in $tunnels) {
    try {
        Stop-Process -Id $tunnel.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped ngrok (PID $($tunnel.ProcessId), local port $Port)."
        Remove-MatchingPidFile 'ngrok.pid' $tunnel.ProcessId
    } catch {
        $failed = $true
        Write-Warning "Could not stop/clean up ngrok PID $($tunnel.ProcessId): $($_.Exception.Message)"
    }
}

# Keep the original server guard: only Python running app.py and listening here.
$ids = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique)
$servers = @($ids | ForEach-Object {
    Get-CimInstance Win32_Process -Filter "ProcessId=$_"
} | Where-Object {
    $_.Name -like 'python*' -and
    $_.CommandLine -match '(?:^|\s)(?:"[^"]*[\\/]app\.py"|"app\.py"|[^\s"]*[\\/]app\.py|app\.py)(?=\s|$)'
})
if (-not $servers) {
    Write-Host "ELYRA is not running on port $Port."
}
foreach ($server in $servers) {
    try {
        Stop-Process -Id $server.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped ELYRA (PID $($server.ProcessId))."
        Remove-MatchingPidFile 'server.pid' $server.ProcessId
    } catch {
        $failed = $true
        Write-Warning "Could not stop/clean up ELYRA PID $($server.ProcessId): $($_.Exception.Message)"
    }
}

if ($failed) { exit 1 }
exit 0
