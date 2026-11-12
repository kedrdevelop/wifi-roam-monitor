@echo off
setlocal
title Build Wi-Fi Roaming Sentinel (.exe)
cd /d "%~dp0"

echo ========================================================
echo    Building Standalone Wi-Fi Roaming Sentinel (.exe)
echo ========================================================
echo.

:: 1. Ensure required build dependencies are installed
echo [1/4] Checking Python build tools (PyInstaller, Pillow)...
python -m pip install --quiet --upgrade pyinstaller pillow pywebview

:: 2. Ensure multi-resolution application icon is generated
echo [2/4] Verifying application icon...
if not exist "assets\icon.ico" (
    python generate_icon.py
)

:: 3. Run PyInstaller using spec file
echo [3/4] Compiling standalone executable with PyInstaller...
python -m PyInstaller --clean --noconfirm WiFiRoamingSentinel.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PyInstaller compilation failed!
    pause
    exit /b %ERRORLEVEL%
)

:: 4. Deploy executable to root directory for easy access
echo [4/4] Deploying WiFiRoamingSentinel.exe...
copy /y "dist\WiFiRoamingSentinel.exe" "WiFiRoamingSentinel.exe" >nul

echo.
echo ========================================================
echo [SUCCESS] Build completed successfully!
echo Standalone executable: WiFiRoamingSentinel.exe
echo You can run it on any Windows 10/11 machine without Python.
echo ========================================================
echo.
pause
