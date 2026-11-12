@echo off
setlocal enabledelayedexpansion
title Wi-Fi Roaming Sentinel - Setup & Run
cd /d "%~dp0"

echo ========================================================
echo        Wi-Fi Roaming Sentinel - Setup & Run
echo ========================================================
echo.

:: 1. Check if Python is installed and accessible
set "PYTHON_CMD="
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_CMD=%%i"
)

:: Check default user install location if 'where python' failed
if not defined PYTHON_CMD (
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
    )
)

:: 2. If Python is NOT found, download and install official Python 3.12 (User-level, no admin needed)
if not defined PYTHON_CMD (
    echo [1/3] Python is not detected on this system.
    echo       Downloading official Python 3.12 installer from python.org...
    
    set "PY_INSTALLER=%TEMP%\python-3.12.8-amd64.exe"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
        "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile '%PY_INSTALLER%'"
    
    if not exist "%PY_INSTALLER%" (
        echo [ERROR] Failed to download Python installer. Please check internet connection.
        pause
        exit /b 1
    )
    
    echo       Installing Python silently (User-level, no administrative elevation needed)...
    "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 Include_tcltk=0 SimpleInstall=1
    
    timeout /t 5 /nobreak >nul
    
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
        echo %LocalAppData%\Programs\Python\Python312 > ".python_installed_marker"
        echo       Python installed successfully!
    ) else (
        echo [ERROR] Python installation did not finish as expected.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Python detected: !PYTHON_CMD!
)

:: 3. Setup isolated virtual environment in venv/
echo.
echo [2/3] Setting up local isolated environment and dependencies...
if not exist "venv\Scripts\python.exe" (
    echo       Creating virtual environment in venv\...
    "!PYTHON_CMD!" -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b %ERRORLEVEL%
    )
)

echo       Verifying required packages (requirements.txt)...
call venv\Scripts\python.exe -m pip install --quiet --upgrade pip
call venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install package dependencies.
    pause
    exit /b %ERRORLEVEL%
)

:: 4. Launch application
echo.
echo [3/3] Launching Wi-Fi Roaming Sentinel...
echo ========================================================
echo.
call venv\Scripts\python.exe app.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with code %ERRORLEVEL%.
    pause
)
