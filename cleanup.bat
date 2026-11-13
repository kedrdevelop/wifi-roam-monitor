@echo off
setlocal enabledelayedexpansion
title Wi-Fi Roaming Sentinel - Cleanup and Uninstall
cd /d "%~dp0"

echo ========================================================
echo       Wi-Fi Roaming Sentinel - Cleanup and Uninstall
echo ========================================================
echo.
echo This script will remove:
echo   - Local virtual environment [venv/] and all installed packages
echo   - Analysis virtual environment [analysis/venv/] if present
echo   - Temporary Python cache files [__pycache__]
if exist ".python_installed_marker" (
    echo   - Standalone Python 3.12 installation [installed by setup_and_run.bat]
)
echo.
set /p CONFIRM="Are you sure you want to proceed with cleanup? (Y/N): "
if /i not "!CONFIRM!"=="Y" (
    echo Cleanup cancelled.
    exit /b 0
)

echo.
:: 1. Remove local virtual environments and package caches
echo [1/3] Removing local virtual environments [venv/ and analysis/venv/]...
if exist "venv" (
    rmdir /s /q "venv" 2>nul
    if exist "venv" (
        timeout /t 2 /nobreak >nul
        rmdir /s /q "venv" 2>nul
    )
    if exist "venv" (
        echo       [WARNING] Could not fully remove venv/. Close any open Python windows and retry.
    ) else (
        echo       venv/ successfully removed.
    )
) else (
    echo       No root venv/ found.
)

if exist "analysis\venv" (
    rmdir /s /q "analysis\venv" 2>nul
    if exist "analysis\venv" (
        timeout /t 2 /nobreak >nul
        rmdir /s /q "analysis\venv" 2>nul
    )
    if exist "analysis\venv" (
        echo       [WARNING] Could not fully remove analysis\venv\. Close any open Python windows and retry.
    ) else (
        echo       analysis\venv\ successfully removed.
    )
) else (
    echo       No analysis\venv\ found.
)

:: 2. Remove __pycache__ and bytecode
echo [2/3] Cleaning bytecode caches [__pycache__]...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul

:: 3. Check if Python was installed by setup_and_run.bat
echo [3/3] Checking if Python was installed by the setup script...
if exist ".python_installed_marker" (
    echo       Marker found: Python was installed by setup_and_run.bat.
    echo       Uninstalling Python 3.12 from this machine...

    set "PY_INSTALLER=%TEMP%\python-3.12.8-amd64.exe"
    if not exist "!PY_INSTALLER!" (
        echo       Downloading uninstaller helper from python.org...
        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
            "$url = 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe'; " ^
            "$out = Join-Path $env:TEMP 'python-3.12.8-amd64.exe'; " ^
            "if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) { " ^
            "  Start-BitsTransfer -Source $url -Destination $out -DisplayName 'Downloading Python Uninstaller'; " ^
            "} else { " ^
            "  Invoke-WebRequest -Uri $url -OutFile $out; " ^
            "}"
    )

    if exist "!PY_INSTALLER!" (
        "!PY_INSTALLER!" /uninstall /passive
        timeout /t 3 /nobreak >nul
        del /f /q "!PY_INSTALLER!" 2>nul
    )

    set /p PY_DIR=<".python_installed_marker"
    if exist "!PY_DIR!" (
        rmdir /s /q "!PY_DIR!" 2>nul
    )
    del /f /q ".python_installed_marker" 2>nul
    echo       Python 3.12 has been uninstalled from this computer.
) else (
    echo       System Python was pre-existing and has been preserved untouched.
)

echo.
echo ========================================================
echo [SUCCESS] Cleanup finished!
echo All installed dependencies and temporary files removed.
echo ========================================================
echo.
pause
