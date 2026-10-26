@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (echo Python 3 kurulu olmali.& pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo Panel: http://127.0.0.1:8000/
echo OBS: http://127.0.0.1:8000/overlay
echo.
start "" http://127.0.0.1:8000/
".venv\Scripts\python.exe" app.py
pause
