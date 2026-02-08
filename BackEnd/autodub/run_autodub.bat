@echo off
setlocal enabledelayedexpansion

:: Get the directory where the batch file is located
set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

echo ======================================================
echo       AutoDub Manual Stack Launcher (Windows FIX)
echo ======================================================

:: Fix for OpenMP Conflict (OMP Error #15)
set KMP_DUPLICATE_LIB_OK=TRUE

:: 1. Define Paths (Absolute)
set "VENV_DIR=%BASE_DIR%..\venv311"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "CELERY_EXE=%VENV_DIR%\Scripts\celery.exe"

:: 2. Verify Venv
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at: %PYTHON_EXE%
    echo Please check if your virtual environment folder is named 'venv311' 
    echo and is located in: %BASE_DIR%..
    pause
    exit /b 1
)

:: 3. Check for Redis
echo [CHECK] Verifying Redis (Port 6379)...
netstat -ano | findstr :6379 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    echo [ERROR] Redis is not running! 
    echo Please start Redis before running this script.
    pause
    exit /b 1
)

:: 4. Start API Server
echo [API] Launching FastAPI...
start "AutoDub_API" cmd /k "title API_SERVER && cd /d %BASE_DIR% && %PYTHON_EXE% -m src.main"

:: 5. Start Default Worker (using -P solo for Windows stability)
echo [WORKER] Launching Default Worker...
start "AutoDub_Default_Worker" cmd /k "title DEFAULT_WORKER && cd /d %BASE_DIR% && %CELERY_EXE% -A src.core.celery_app worker --loglevel=info -Q default -P solo"

:: 6. Start TTS Worker (using -P solo for Windows stability)
echo [WORKER] Launching TTS Worker...
start "AutoDub_TTS_Worker" cmd /k "title TTS_WORKER && cd /d %BASE_DIR% && %CELERY_EXE% -A src.core.celery_app worker --loglevel=info -Q tts -P solo"

echo ======================================================
echo [OK] All windows launched with Windows-compatibility flags (-P solo).
echo ======================================================
pause
