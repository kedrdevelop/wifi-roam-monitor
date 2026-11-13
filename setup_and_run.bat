@echo off
setlocal enabledelayedexpansion
title Wi-Fi Roaming Sentinel - Setup and Run
cd /d "%~dp0"

echo ========================================================
echo        Wi-Fi Roaming Sentinel - Setup and Run
echo ========================================================
echo.

:: 1. Check if Python 3.10+ is installed and accessible (ignores Windows Store stub)
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

:: 2. If Python is NOT found, attempt installation via winget or official installer
if not defined PYTHON_CMD (
    echo [1/3] Python 3.10+ is not detected on this system.

    :: Attempt 1: Try winget (Microsoft Package Manager, often whitelisted in corporate proxies)
    where winget >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo       Installing Python 3.12 via Microsoft winget...
        echo.
        winget install --id Python.Python.3.12 --source winget --scope user --accept-source-agreements --accept-package-agreements
        timeout /t 3 /nobreak >nul
        echo.
    )

    :: Check if winget installed Python
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_CMD=python"
        echo       Python installed successfully via winget!
    )
    if not defined PYTHON_CMD (
        if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
            set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
            set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;!PATH!"
            echo %LocalAppData%\Programs\Python\Python312> ".python_installed_marker"
            echo       Python installed successfully via winget!
        )
    )

    :: Attempt 2: Direct download via PowerShell with visible progress
    if not defined PYTHON_CMD (
        echo       Downloading official Python 3.12 installer from python.org...
        set "PY_INSTALLER=%TEMP%\python-3.12.8-amd64.exe"
        if exist "!PY_INSTALLER!" del /f /q "!PY_INSTALLER!" 2>nul

        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "try { " ^
            "  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
            "  $url = 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe'; " ^
            "  $out = Join-Path $env:TEMP 'python-3.12.8-amd64.exe'; " ^
            "  if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) { " ^
            "    Start-BitsTransfer -Source $url -Destination $out -DisplayName 'Downloading Python 3.12.8'; " ^
            "  } else { " ^
            "    Invoke-WebRequest -Uri $url -OutFile $out; " ^
            "  } " ^
            "} catch { exit 1 }"

        if exist "!PY_INSTALLER!" (
            echo       Installing Python [User-level, no administrative elevation needed]...
            "!PY_INSTALLER!" /passive InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 Include_tcltk=0 SimpleInstall=1
            timeout /t 3 /nobreak >nul

            if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
                set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
                set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;!PATH!"
                echo %LocalAppData%\Programs\Python\Python312> ".python_installed_marker"
                echo       Python installed successfully!
            )
        )
    )

    :: Attempt 3: Corporate Proxy / Zscaler intervention [Open browser to click Continue]
    if not defined PYTHON_CMD (
        echo.
        echo ========================================================
        echo [NOTICE] Corporate Proxy / Zscaler blocked automated download.
        echo Opening Python download page in your browser...
        echo Please click "Continue" on the Zscaler warning in your browser,
        echo run the downloaded installer, and check "Add python.exe to PATH".
        echo ========================================================
        start https://www.python.org/downloads/release/python-3128/
        echo.
        pause

        :: Re-check after user installs
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
            echo [ERROR] Python 3.10+ was not found. Please complete the installation and run setup_and_run.bat again.
            pause
            exit /b 1
        )
    )
) else (
    for /f "tokens=*" %%v in ('"!PYTHON_CMD!" --version 2^>^&1') do echo [1/3] Python detected: %%v
)

:: 3. Setup isolated virtual environment in venv/
echo.
echo [2/3] Setting up local isolated environment and dependencies...
if not exist "venv\Scripts\pip.exe" (
    echo       Creating virtual environment in venv/...
    "!PYTHON_CMD!" -m venv --clear venv
    if !ERRORLEVEL! NEQ 0 (
        echo       First venv attempt failed [possible antivirus file lock]. Retrying in 2 seconds...
        timeout /t 2 /nobreak >nul
        "!PYTHON_CMD!" -m venv --clear venv
        if !ERRORLEVEL! NEQ 0 (
            echo [ERROR] Failed to create virtual environment.
            pause
            exit /b !ERRORLEVEL!
        )
    )
    echo       Virtual environment created successfully.
)

echo.
echo       Upgrading pip and verifying packages [requirements.txt]...
echo --------------------------------------------------------
"venv\Scripts\python.exe" -m pip install --upgrade pip
if !ERRORLEVEL! NEQ 0 (
    echo [WARNING] pip upgrade returned an error, continuing with package installation...
)
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Failed to install package dependencies.
    pause
    exit /b !ERRORLEVEL!
)
echo --------------------------------------------------------

:: 4. Launch application
echo.
echo [3/3] Launching Wi-Fi Roaming Sentinel...
echo ========================================================
echo.
"venv\Scripts\python.exe" app.py %*
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo Application exited with code !ERRORLEVEL!.
    pause
)
