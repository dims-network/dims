@echo off
REM One-click launcher (Windows): installs dependencies, then starts the builder.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python 3 is not installed.
  echo Install it ^(free^) from https://www.python.org/downloads/ then run this again.
  pause
  exit /b 1
)

REM Create an isolated virtual environment so we don't touch the system Python.
if not exist ".venv" (
  echo Creating virtual environment ^(first run only^)...
  python -m venv .venv
)
set PY=.venv\Scripts\python.exe

echo Installing builder dependencies ^(first run only^)...
"%PY%" -m pip install --upgrade pip >nul
"%PY%" -m pip install -r requirements.txt
echo Starting DIMS Dashboard Builder...
"%PY%" builder.py
pause
