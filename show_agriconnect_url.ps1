Add-Type -AssemblyName PresentationFramework
$deadline = (Get-Date).AddSeconds(90)
$publicUrl = $null
while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $env:AGRICONNECT_TUNNEL_LOG) {
        $logText = Get-Content -LiteralPath $env:AGRICONNECT_TUNNEL_LOG -Raw -ErrorAction SilentlyContinue
        $match = [regex]::Match([string]$logText, 'https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com\b')
        if ($match.Success) { $publicUrl = $match.Value; break }
    }
    Start-Sleep -Seconds 1
}
if (-not $publicUrl) {
    [void][System.Windows.MessageBox]::Show('The local app is running, but no public URL was found within 90 seconds. Check the AgriConnect Cloudflare window.', 'AgriConnect - Tunnel pending', 'OK', 'Warning')
    exit 1
}
Write-Host ('Public URL: ' + $publicUrl)
$clipboardNote = 'Copy the URL from the launcher window to share it.'
try {
    Set-Clipboard -Value $publicUrl -ErrorAction Stop
    $clipboardNote = 'Copied to your clipboard. Paste it with Ctrl+V.'
} catch {}
$message = "Your new AgriConnect URL is:`n`n$publicUrl`n`n$clipboardNote`n`nKeep all service windows open. The public URL may take a few seconds to become reachable.`n`nOpen it in your browser now?"
$answer = [System.Windows.MessageBox]::Show($message, 'AgriConnect - Public URL', 'YesNo', 'Information')
if ($answer -eq 'Yes') { Start-Process $publicUrl }
