@echo off
echo ========================================
echo   Techgium AutoDub Backend Server
echo ========================================
echo.
echo Cleaning up old processes...
taskkill /F /IM python.exe 2>nul
echo.
echo Starting the application with Python 3.11...
echo.
echo Once started, visit: http://127.0.0.1:7860
echo.

cd /d "%~dp0"
.\venv311\Scripts\python.exe app.py

pause
