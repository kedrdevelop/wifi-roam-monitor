@echo off
setlocal enabledelayedexpansion
title Wi-Fi Roaming Log Analyzer
cd /d "%~dp0"

echo ========================================================
echo       Wi-Fi Roaming Sentinel - Telemetry Analyzer
echo ========================================================
echo.

:: 1. Detect Python 3.10+ (PATH, standard user install, or parent project venv)
set "PYTHON_CMD="

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    for %%D in ("%LocalAppData%\Programs\Python\Python312" "%LocalAppData%\Programs\Python\Python313" "%LocalAppData%\Programs\Python\Python311") do (
        if not defined PYTHON_CMD (
            if exist "%%~D\python.exe" (
                "%%~D\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
                if !ERRORLEVEL! EQU 0 (
                    set "PYTHON_CMD=%%~D\python.exe"
                    set "PATH=%%~D;%%~D\Scripts;!PATH!"
                )
            )
        )
    )
)

if not defined PYTHON_CMD (
    if exist "..\venv\Scripts\python.exe" (
        "..\venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            set "PYTHON_CMD=..\venv\Scripts\python.exe"
        )
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3.10+ was not found on this machine.
    echo         Please run ..\setup_and_run.bat first to install Python automatically.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('"!PYTHON_CMD!" --version 2^>^&1') do echo [1/3] Python detected: %%v

:: 2. Create isolated virtual environment in analysis/venv/ if missing
echo.
echo [2/3] Setting up analysis virtual environment and dependencies...
if not exist "venv\Scripts\pip.exe" (
    echo       Creating virtual environment in analysis\venv\...
    "!PYTHON_CMD!" -m venv --clear venv
    if !ERRORLEVEL! NEQ 0 (
        echo       First venv attempt failed [possible antivirus file lock]. Retrying in 2 seconds...
        timeout /t 2 /nobreak >nul
        "!PYTHON_CMD!" -m venv --clear venv
        if !ERRORLEVEL! NEQ 0 (
            echo [ERROR] Failed to create analysis virtual environment.
            pause
            exit /b !ERRORLEVEL!
        )
    )
    echo       Virtual environment created successfully.
)

echo.
echo       Upgrading pip and verifying analysis packages [requirements.txt]...
echo --------------------------------------------------------
"venv\Scripts\python.exe" -m pip install --upgrade pip
if !ERRORLEVEL! NEQ 0 (
    echo [WARNING] pip upgrade returned an error, continuing with package installation...
)
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Failed to install analysis dependencies.
    pause
    exit /b !ERRORLEVEL!
)
echo --------------------------------------------------------

:: 3. Launch analyzer
echo.
echo [3/3] Running telemetry log analysis...
echo ========================================================
echo.
"venv\Scripts\python.exe" analyze.py %*
echo.
pause
