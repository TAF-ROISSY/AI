@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
 echo Python 3.11+ est necessaire. Installez Python puis relancez.
 pause
 exit /b 1
)
py -m pip install -r requirements.txt
if errorlevel 1 (
 echo Installation des dependances impossible.
 pause
 exit /b 1
)
echo.
echo TAF WAREHOUSE : ouvrez http://127.0.0.1:8765
py -m uvicorn app.server:app --host 127.0.0.1 --port 8765
pause
