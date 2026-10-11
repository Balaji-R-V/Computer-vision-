@echo off
REM Starts Aegis-OS with the Python that has the project's packages installed.
REM Optional settings (uncomment and edit):
REM   set AEGIS_PASSWORD=change-me          (turns on the login)
REM   set AEGIS_RETENTION_DAYS=30
REM   set PORT=5050
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PY%" set PY=python
"%PY%" -u server.py >> logs\server.log 2>&1
