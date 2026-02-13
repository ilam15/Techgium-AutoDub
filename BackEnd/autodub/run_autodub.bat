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
set "REDIS_DIR=C:\Redis"

:: 2. Verify Venv
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found at: %PYTHON_EXE%
    echo Please check if your virtual environment folder is named 'venv311' 
    echo and is located in: %BASE_DIR%..
    pause
    exit /b 1
)

:: 3. Start Redis Server (only if not already running)
echo [REDIS] Checking if Redis is already active...
netstat -ano | findstr :6379 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo [REDIS] Redis is already running. Skipping startup.
) else (
    echo [REDIS] Launching Redis...
    if exist "%REDIS_DIR%\redis-server.exe" (
        start "AutoDub_Redis" cmd /k "title REDIS_SERVER && cd /d %REDIS_DIR% && redis-server.exe --bind 127.0.0.1"
    ) else (
        echo [WARNING] Redis not found in %REDIS_DIR%. Trying system PATH...
        start "AutoDub_Redis" cmd /k "title REDIS_SERVER && redis-server --bind 127.0.0.1"
    )
    timeout /t 5
)

:: 4. Clear old tasks & Verify
echo [REDIS] Flushing old tasks to ensure fresh start...
redis-cli -h 127.0.0.1 FLUSHALL
echo [REDIS] Verifying Redis connection...
netstat -ano | findstr :6379 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    echo [ERROR] Redis failed to start or is not accessible.
    pause
    exit /b 1
)

:: 5. Start API Server
echo [API] Launching FastAPI...
start "AutoDub_API" cmd /k "title API_SERVER && cd /d "%BASE_DIR%" && "%PYTHON_EXE%" -m src.main"

:: 6. Launch Terminal 1: Separation & Segmentation
echo [TERMINAL 1] Launching Separation Worker...
:: T1 stays 'solo' for process isolation
start "AutoDub_Separation_Worker" cmd /k "title SEPARATION_WORKER && cd /d "%BASE_DIR%" && "%CELERY_EXE%" -A src.core.celery_app worker --loglevel=info -Q separation -P threads --concurrency=1 -Ofair --prefetch-multiplier=1"

:: Launch Terminal 2: Analysis & Translation
echo [TERMINAL 2] Launching Analysis Worker (Single Threaded for NLLB Stability)...
:: -Ofair + prefetch=1 ensures tasks are not hogged by one thread
start "AutoDub_Analysis_Worker" cmd /k "title ANALYSIS_WORKER && cd /d "%BASE_DIR%" && "%CELERY_EXE%" -A src.core.celery_app worker --loglevel=info -Q analysis -P threads --concurrency=1 -Ofair --prefetch-multiplier=1"

:: Launch Terminal 3: Synthesis & Merge
echo [TERMINAL 3] Launching Merge Worker (Single Threaded for TTS Stability)...
start "AutoDub_Merge_Worker" cmd /k "title MERGE_WORKER && cd /d "%BASE_DIR%" && "%CELERY_EXE%" -A src.core.celery_app worker --loglevel=info -Q merge -P threads --concurrency=1 -Ofair --prefetch-multiplier=1"

echo ======================================================
echo [OK] 3-Terminal Parallel Pipeline Launched!
echo Terminal 1: Separation (ASR/VAD)
echo Terminal 2: Analysis (Lang/Trans)
echo Terminal 3: Merge (TTS/Final)
echo ======================================================
pause
