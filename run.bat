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

echo Installing builder dependencies ^(first run only^)...
python -m pip install -r requirements.txt
echo Starting DIMS Dashboard Builder...
python builder.py
pause
