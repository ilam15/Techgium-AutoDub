@echo off
echo ========================================================
echo   Download Age-Restricted YouTube Video
echo ========================================================
echo.

if "%~1"=="" (
    echo ERROR: No URL provided!
    echo.
    echo Usage: download_age_restricted.bat "YOUTUBE_URL"
    echo Example: download_age_restricted.bat "https://youtu.be/WkieoHmxJXo"
    echo.
    pause
    exit /b 1
)

set VIDEO_URL=%~1

echo Video URL: %VIDEO_URL%
echo.
echo IMPORTANT: Please close Google Chrome completely before continuing!
echo Press any key when Chrome is closed...
pause >nul

echo.
echo Downloading video with age verification...
echo This will use your Chrome cookies for authentication.
echo.

.\venv311\Scripts\python.exe -m yt_dlp --cookies-from-browser chrome --merge-output-format mp4 -o "temp_uploads\%%(title)s.%%(ext)s" "%VIDEO_URL%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ========================================================
    echo   DOWNLOAD FAILED
    echo ========================================================
    echo.
    echo Possible solutions:
    echo 1. Make sure Chrome is completely closed
    echo 2. Sign in to YouTube in Chrome
    echo 3. Try the video in Chrome to verify you can access it
    echo 4. Update yt-dlp: pip install --upgrade yt-dlp
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   DOWNLOAD SUCCESSFUL!
echo ========================================================
echo.
echo The video has been downloaded to the temp_uploads folder.
echo You can now upload it using the file upload option in the app.
echo.
pause
