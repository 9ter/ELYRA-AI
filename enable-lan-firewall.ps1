#Requires -RunAsAdministrator
param(
    [string]$LanAddress = '192.168.1.181',
    [ValidateRange(1,65535)][int]$Port = 3000
)
$ErrorActionPreference = 'Stop'
# Refuse wildcard, non-private, or non-local addresses before changing the firewall.
$ip = [System.Net.IPAddress]::Parse($LanAddress)
$bytes = $ip.GetAddressBytes()
if ($bytes.Length -ne 4 -or -not ($bytes[0] -eq 10 -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168))) {
    throw 'Use a private IPv4 address assigned to this computer.'
}
$assigned = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $LanAddress -ErrorAction Stop
if (-not $assigned) { throw 'LAN address is not assigned to this computer.' }
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$ruleName = "ELYRA-LAN-$LanAddress-$Port"
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) { $existing | Remove-NetFirewallRule }
New-NetFirewallRule -Name $ruleName -DisplayName "ELYRA LAN $LanAddress port $Port" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -LocalAddress $LanAddress -RemoteAddress LocalSubnet -Program $pythonExe -Profile Any | Out-Null
Write-Host "Allowed local-subnet devices: http://${LanAddress}:$Port"
