# Hook Stop do Claude Code: som + notificação do Windows quando a resposta termina.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Media.SystemSounds]::Asterisk.Play()

$icon = New-Object System.Windows.Forms.NotifyIcon
$icon.Icon = [System.Drawing.SystemIcons]::Information
$icon.BalloonTipTitle = 'Claude Code'
$icon.BalloonTipText = 'Terminei de responder.'
$icon.Visible = $true
$icon.ShowBalloonTip(5000)
Start-Sleep -Seconds 6
$icon.Dispose()
