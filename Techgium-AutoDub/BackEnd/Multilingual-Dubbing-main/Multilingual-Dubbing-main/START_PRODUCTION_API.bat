@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   AutoDub: Production API Server (FastAPI + Uvicorn)
echo ========================================================
echo.

echo [1/3] Checking environment and dependencies...
if not exist ".env" (
    echo [!] WARNING: .env file not found. Speaker Diarization will be disabled.
)

echo Synchronizing production dependencies...
.\venv311\Scripts\python.exe -m pip install pydantic-settings fastapi uvicorn python-multipart yt-dlp --quiet
echo Done.

echo.
echo [2/3] Cleaning up stale Python processes...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo Done.

echo.
echo [3/3] Starting Production API Gateway...
echo --------------------------------------------------------
echo API ENDPOINT: http://localhost:8000
echo DOCUMENTATION: http://localhost:8000/docs
echo YOUTUBE DOWNLOADER: ENABLED
echo --------------------------------------------------------
echo.

cd /d "%~dp0"
set PYTHONPATH=%CD%

REM Start the server using api.py directly
.\venv311\Scripts\python.exe api.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] CRITICAL: Server crashed or failed to start.
    echo Check the error messages above for details.
    echo.
)

pause
