@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   AutoDub: High-Throughput Dubbing Pipeline
echo ========================================================
echo.
echo [1/4] Checking environment...
if not exist ".env" (
    echo [!] WARNING: .env file not found. Speaker Diarization will be disabled.
    echo Please create a .env file with HF_TOKEN=your_huggingface_token
) else (
    echo [OK] .env configuration file detected.
)

echo.
echo [2/4] Optimizations Enabled:
echo   - In-Memory PCM Streaming (Zero Disk I/O)
echo   - Parallel ASR and Diarization Pipeline
echo   - Real-time Audio Stabilization (24kHz Sync)
echo   - One-Pass Complex Merging (FFmpeg Filter)
echo.

echo [3/4] Cleaning up stale Python processes...
taskkill /F /IM python.exe 2>nul
echo Done.

echo.
echo [4/4] Starting Optimized API Server...
echo --------------------------------------------------------
echo API ENDPOINT: http://localhost:8000
echo --------------------------------------------------------
echo.

cd /d "%~dp0"
.\venv311\Scripts\python.exe api.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] CRITICAL: Server crashed or failed to start.
    echo Please check if 'venv311' is properly installed and requirements are met.
)

pause
