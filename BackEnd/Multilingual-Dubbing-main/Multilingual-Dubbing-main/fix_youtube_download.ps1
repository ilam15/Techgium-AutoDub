# Script to fix YouTube download issues
Write-Host "=== Fixing YouTube Download Issues ===" -ForegroundColor Cyan

# Activate virtual environment
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& ".\venv311\Scripts\Activate.ps1"

# Update yt-dlp to latest version
Write-Host "`nUpdating yt-dlp to latest version..." -ForegroundColor Yellow
pip install --upgrade yt-dlp

# Check if Node.js is installed (for JavaScript runtime)
Write-Host "`nChecking for JavaScript runtime..." -ForegroundColor Yellow
$nodeInstalled = Get-Command node -ErrorAction SilentlyContinue
if ($nodeInstalled) {
    Write-Host "Node.js is installed: $($nodeInstalled.Version)" -ForegroundColor Green
} else {
    Write-Host "Node.js is NOT installed. Installing via Chocolatey or download manually from https://nodejs.org/" -ForegroundColor Red
    Write-Host "You can install it with: choco install nodejs" -ForegroundColor Yellow
    Write-Host "Or download from: https://nodejs.org/en/download/" -ForegroundColor Yellow
}

# Check ffmpeg
Write-Host "`nChecking for ffmpeg..." -ForegroundColor Yellow
$ffmpegInstalled = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegInstalled) {
    Write-Host "ffmpeg is installed" -ForegroundColor Green
} else {
    Write-Host "ffmpeg is NOT installed. This is required for video processing." -ForegroundColor Red
    Write-Host "Install with: choco install ffmpeg" -ForegroundColor Yellow
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "If Node.js or ffmpeg were missing, please install them and restart your API server." -ForegroundColor Yellow
