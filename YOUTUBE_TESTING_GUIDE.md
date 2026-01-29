# Quick Start: Testing YouTube Download Feature

## Prerequisites
- Backend server running on `http://localhost:8000`
- Frontend server running (typically `http://localhost:5173`)
- `yt-dlp` installed (already done)

## Step-by-Step Testing Guide

### 1. Start the Backend Server

```bash
cd d:\Autodub\Techgium-AutoDub\BackEnd\Multilingual-Dubbing-main\Multilingual-Dubbing-main
python api_deprecated.py
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Verify Frontend is Running

The frontend should already be running (you mentioned `npm run dev` is active).
If not:
```bash
cd d:\Autodub\Techgium-AutoDub\FrontEnd
npm run dev
```

### 3. Test the Feature

#### Step 1: Navigate to Convert Page
1. Open your browser to the frontend URL
2. Go to the convert/input page

#### Step 2: Test YouTube URL Fetch
1. Paste a YouTube URL in the input field, for example:
   ```
   https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```
2. Click the "Fetch" button
3. Wait for video information to load

**Expected Result:**
- Video thumbnail appears
- Video title, duration, and uploader name displayed
- Quality options grid shows (144p, 240p, 360p, 480p, 720p, 1080p, 1440p, 2160p)

#### Step 3: Download Video
1. Click on any quality button (e.g., "720p")
2. Watch the download progress bar

**Expected Result:**
- Progress bar animates from 0% to 100%
- "Download Complete! Ready for dubbing" message appears
- Video card shows in the "Uploaded Video" section

#### Step 4: Generate Dubbed Video
1. Select target language (e.g., Spanish)
2. Select voice gender (Male/Female)
3. Click "Generate Dubbed Video"

**Expected Result:**
- Processing starts
- Backend uses the downloaded YouTube video
- Dubbed video is generated and preview page opens

## Test URLs

### Recommended Test Videos (Short duration)

1. **Short Music Video** (~3 mins)
   ```
   https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

2. **Tech Tutorial** (~5 mins)
   ```
   https://www.youtube.com/watch?v=9bZkp7q19f0
   ```

3. **Short Documentary Clip** (~2 mins)
   ```
   https://www.youtube.com/watch?v=aqz-KE-bpKQ
   ```

## Troubleshooting

### Issue: "Failed to fetch video info"

**Solution:**
1. Check backend console for errors
2. Verify internet connection
3. Try a different YouTube URL
4. Check if video is age-restricted or private

### Issue: "Download failed"

**Solution:**
1. Try a lower quality option
2. Check available disk space
3. Verify yt-dlp is installed: `pip show yt-dlp`
4. Update yt-dlp: `pip install --upgrade yt-dlp`

### Issue: Quality buttons not appearing

**Solution:**
1. Check browser console for JavaScript errors
2. Verify API response in Network tab
3. Ensure backend returned formats array

### Issue: "YouTube video file not found" during dubbing

**Solution:**
1. Check if file exists in `temp_downloads/` folder
2. Re-download the video
3. Verify file path in backend logs

## Debugging Tips

### Check Backend Logs
```bash
# Backend should print:
# "Successfully fetched info for: [Video Title]"
# "Starting download: [URL] at [quality]"
# "Download completed: [file_path]"
# "Using YouTube downloaded video: [file_path]"
```

### Check Browser Console
```javascript
// Should see:
// "YouTube video info: { title: '...', formats: [...] }"
// "Downloaded video path: temp_downloads/..."
```

### Verify API Endpoints
```bash
# Test info endpoint
curl -X POST http://localhost:8000/youtube/info \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Test download endpoint
curl -X POST http://localhost:8000/youtube/download \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","quality":"720p"}'
```

## Expected File Structure After Download

```
BackEnd/Multilingual-Dubbing-main/Multilingual-Dubbing-main/
├── temp_downloads/
│   └── [uuid]_youtube_video.mp4  # Downloaded video
├── temp_uploads/                  # If using file upload
└── output/                        # Dubbed videos
```

## Performance Notes

- **720p** is recommended for balance between quality and speed
- Download time varies based on:
  - Video duration
  - Selected quality
  - Internet speed
  - YouTube server load

## Success Indicators

✅ Video info fetched successfully
✅ Quality options displayed
✅ Download progress shows
✅ Video card appears with thumbnail
✅ "Generate Dubbed Video" button enabled
✅ Dubbing process starts without errors

## Next Steps After Testing

1. Test with different video lengths
2. Try various quality options
3. Test error scenarios (invalid URL, restricted videos)
4. Verify cleanup of temporary files
5. Test the complete dubbing workflow

---

**Happy Testing! 🎉**

If you encounter any issues not covered here, check:
1. Backend terminal for error messages
2. Browser console for frontend errors
3. Network tab for API request/response details

