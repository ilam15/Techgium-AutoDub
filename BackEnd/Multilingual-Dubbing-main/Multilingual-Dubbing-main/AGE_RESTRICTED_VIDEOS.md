# YouTube Age-Restricted Video Support

## What Changed

The API has been updated to support age-restricted YouTube videos by using browser cookies for authentication.

## How It Works

The system now uses `cookiesfrombrowser` feature in yt-dlp to automatically extract cookies from your Chrome browser. This allows the API to:
- Download age-restricted videos
- Access videos requiring sign-in
- Bypass YouTube's authentication requirements

## Requirements

1. **Google Chrome** must be installed on your system
2. You must be **signed in to YouTube** in Chrome
3. Your Chrome profile should have access to the videos you want to download

## Setup Instructions

### Option 1: Use Chrome (Recommended - Already Configured)
The API is already configured to use Chrome cookies. Just make sure:
1. Chrome is installed
2. You're signed in to YouTube in Chrome
3. Restart the API server

### Option 2: Use a Different Browser
If you prefer Firefox, Edge, or another browser, edit `api_deprecated.py`:

**For Firefox:**
```python
'cookiesfrombrowser': ('firefox',),
```

**For Edge:**
```python
'cookiesfrombrowser': ('edge',),
```

**For Brave:**
```python
'cookiesfrombrowser': ('brave',),
```

## Restart the API Server

After making changes, restart the API server:

```bash
# Stop the current server (Ctrl+C in the terminal)
# Then run:
.\START_PRODUCTION_API.bat
```

Or run directly:
```bash
.\venv311\Scripts\python.exe api_deprecated.py
```

## Troubleshooting

### Error: "Could not find Chrome cookies"
**Solution:** 
- Make sure Chrome is installed
- Sign in to YouTube in Chrome
- Close all Chrome windows and try again

### Error: "Failed to extract cookies"
**Solution:**
- Update yt-dlp: `pip install --upgrade yt-dlp`
- Make sure you're signed in to YouTube in your browser
- Try closing the browser and reopening it

### Still Getting Age Restriction Error
**Solution:**
1. Open Chrome
2. Go to YouTube.com
3. Sign in to your account
4. Try to play the age-restricted video in Chrome to confirm you can access it
5. Restart the API server
6. Try downloading again

## Alternative: Manual Cookie Export

If automatic cookie extraction doesn't work, you can manually export cookies:

1. Install a browser extension like "Get cookies.txt"
2. Export YouTube cookies to a file named `cookies.txt`
3. Update the API configuration:

```python
'cookiefile': 'cookies.txt',
```

## Testing

Try fetching an age-restricted video:
```bash
curl -X POST http://localhost:8000/fetch_video_info \
  -H "Content-Type: application/json" \
  -d '{"url": "YOUR_AGE_RESTRICTED_VIDEO_URL"}'
```

## Security Note

Cookies contain your authentication tokens. The API only reads cookies from your browser and doesn't store or transmit them anywhere. All processing happens locally on your machine.
