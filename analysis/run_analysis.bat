@echo off
title Wi-Fi Roaming Log Analyzer
cd /d "%~dp0"
call "venv\Scripts\activate.bat"
python analyze.py %*
pause

