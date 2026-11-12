@echo off
title Create Wi-Fi Roaming Sentinel Shortcut
cd /d "%~dp0"

echo Creating application shortcut with custom icon...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%~dp0Wi-Fi Roaming Sentinel.lnk'); $py = (Get-Command pythonw -ErrorAction SilentlyContinue); if (!$py) { $py = (Get-Command python -ErrorAction SilentlyContinue) }; $s.TargetPath = $py.Source; $s.Arguments = 'app.py'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0assets\icon.ico,0'; $s.Description = 'Wi-Fi Roaming Sentinel'; $s.Save();"

if exist "%~dp0Wi-Fi Roaming Sentinel.lnk" (
    echo [SUCCESS] Created shortcut: "Wi-Fi Roaming Sentinel.lnk" with custom icon!
) else (
    echo [ERROR] Failed to create shortcut.
)
echo.
pause
