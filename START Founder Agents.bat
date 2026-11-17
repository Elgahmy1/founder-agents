@echo off
title Founder Agents
cd /d %~dp0
if not exist .venv\Scripts\activate.bat (
  echo First run: creating the Python environment...
  python -m venv .venv || (echo Python 3.12 is needed: https://www.python.org/downloads/ & pause & exit /b 1)
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
set PYTHONUTF8=1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*uvicorn app.main:app*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
start "" "%~dp0Founder Agents.html"
echo Founder Agents is starting at http://localhost:8000  (close this window to stop it)
python -m uvicorn app.main:app --port 8000
