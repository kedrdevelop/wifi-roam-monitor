@echo off
title Wi-Fi Roaming Sentinel
cd /d "%~dp0"

:: If standalone executable exists, launch it directly
if exist "WiFiRoamingSentinel.exe" (
    start "" "WiFiRoamingSentinel.exe" %*
    exit /b
)

:: Fallback to Python script execution
python app.py %*
if %ERRORLEVEL% NEQ 0 pause
