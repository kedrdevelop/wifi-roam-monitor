@echo off
title Wi-Fi Roaming Sentinel
cd /d "%~dp0"

:: Launch Wi-Fi Roaming Sentinel via Python
python app.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)
