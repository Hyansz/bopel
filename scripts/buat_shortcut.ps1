$ErrorActionPreference = "Stop"

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "BOPEL.lnk"

if (Test-Path $shortcutPath) {
    $response = Read-Host "Shortcut 'BOPEL.lnk' sudah ada di Desktop. Timpa? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Host "Pembuatan shortcut dibatalkan."
        exit 0
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$targetPath = Join-Path $scriptDir "start.bat"
$iconPath = Join-Path $scriptDir "assets\bopel.ico"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $targetPath
$Shortcut.WorkingDirectory = $scriptDir
$Shortcut.IconLocation = "$iconPath,0"
$Shortcut.WindowStyle = 7 # Minimized
$Shortcut.Save()

Write-Host "Shortcut berhasil dibuat: $shortcutPath"
