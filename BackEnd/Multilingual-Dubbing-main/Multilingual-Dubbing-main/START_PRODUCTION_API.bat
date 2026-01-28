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
.\venv311\Scripts\python.exe -m pip install pydantic-settings fastapi uvicorn python-multipart --quiet
echo Done.

echo.
echo [2/3] Cleaning up stale Python processes...
taskkill /F /IM python.exe 2>nul
echo Done.

echo.
echo [3/3] Starting Production API Gateway...
echo --------------------------------------------------------
echo API ENDPOINT: http://localhost:8000
echo DOCUMENTATION: http://localhost:8000/docs
echo --------------------------------------------------------
echo.

cd /d "%~dp0"
set PYTHONPATH=%CD%
.\venv311\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 --timeout-keep-alive 300

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] CRITICAL: Server crashed or failed to start.
    echo Attempting single-worker fallback for debugging...
    .\venv311\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
)

pause
