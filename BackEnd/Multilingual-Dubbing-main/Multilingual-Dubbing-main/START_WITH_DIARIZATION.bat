@echo off
echo ========================================
echo   Techgium AutoDub with Speaker Diarization
echo ========================================
echo.
echo Setting up Hugging Face token for speaker detection...
set HF_TOKEN=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
echo Token configured successfully!
echo.
echo Cleaning up old processes...
taskkill /F /IM python.exe 2>nul
echo.
echo Starting the REST API Server with Speaker Diarization enabled...
echo API will be available at: http://127.0.0.1:8000
echo.
echo Expected startup messages:
echo   - "Pyannote loaded successfully"
echo   - "Gender classification model loaded"
echo.

cd /d "%~dp0"
.\venv311\Scripts\python.exe api.py

pause
