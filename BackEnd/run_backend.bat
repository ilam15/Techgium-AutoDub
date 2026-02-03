@echo off
REM Navigate to the script's directory
cd /d "%~dp0"

REM Activate virtual environment (CMD version)
call venv311\Scripts\activate.bat

REM Go to autodub folder


REM Run module
cd autodub  
python -m src.main

pause