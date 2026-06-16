@echo off
REM Double-click launcher (Windows): install deps then start the builder.
cd /d "%~dp0"

set PY=python
echo Installing builder dependencies...
%PY% -m pip install -r requirements.txt
echo Starting DIMS Dashboard Builder...
%PY% builder.py
pause
