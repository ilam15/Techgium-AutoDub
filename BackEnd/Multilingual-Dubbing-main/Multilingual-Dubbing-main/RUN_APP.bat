@echo off
echo ========================================
echo   Techgium AutoDub Backend Server (API)
echo ========================================
echo.
echo Cleaning up old processes...
taskkill /F /IM python.exe 2>nul
echo.
echo Installing/Updating dependencies...
cd /d "%~dp0"
.\venv311\Scripts\pip.exe install -r requirements.txt
echo.
echo Starting the REST API Server with Python 3.11...
echo API will be available at: http://127.0.0.1:8000
echo.

.\venv311\Scripts\python.exe api.py

pause
