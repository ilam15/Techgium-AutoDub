# YouTube Download Feature - Quick Reference Card

## 🚀 Quick Start (3 Steps)

### 1️⃣ Paste URL
```
Paste YouTube URL → Click "Fetch"
```

### 2️⃣ Select Quality
```
Choose quality → 144p | 240p | 360p | 480p | 720p | 1080p | 1440p | 2160p
```

### 3️⃣ Generate Dubbed Video
```
Wait for download → Configure settings → Click "Generate Dubbed Video"
```

---

## 📡 API Endpoints

### Fetch Video Info
```http
POST http://localhost:8000/youtube/info
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

### Download Video
```http
POST http://localhost:8000/youtube/download
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "quality": "720p"
}
```

### Dub Video (with YouTube)
```http
POST http://localhost:8000/dub_video
Content-Type: multipart/form-data

youtube_video_path: "temp_downloads/[uuid]_youtube_video.mp4"
source_lang: "English"
target_lang: "Spanish"
gender: "Male"
```

---

## 🎯 Quality Options

| Quality | Resolution | Use Case | File Size (5 min) |
|---------|-----------|----------|-------------------|
| 144p | 256x144 | Preview | ~5 MB |
| 240p | 426x240 | Mobile | ~10 MB |
| 360p | 640x360 | Standard | ~20 MB |
| 480p | 854x480 | Enhanced | ~30 MB |
| **720p** | 1280x720 | **HD (Recommended)** | **~50 MB** |
| 1080p | 1920x1080 | Full HD | ~100 MB |
| 1440p | 2560x1440 | 2K | ~200 MB |
| 2160p | 3840x2160 | 4K | ~400 MB |

---

## 🔧 Files Modified

```
✅ BackEnd/youtube_downloader.py          (NEW)
✅ BackEnd/api_deprecated.py              (UPDATED)
✅ BackEnd/requirements.txt               (UPDATED)
✅ FrontEnd/src/components/InputPage/InputPage.jsx  (UPDATED)
```

---

## 🎨 UI Components Added

```jsx
// State
const [youtubeVideoInfo, setYoutubeVideoInfo] = useState(null);
const [selectedQuality, setSelectedQuality] = useState(null);
const [downloadedVideoPath, setDownloadedVideoPath] = useState(null);
const [isDownloading, setIsDownloading] = useState(false);
const [downloadProgress, setDownloadProgress] = useState(0);

// Functions
processUrl()                    // Fetch video info
downloadYoutubeVideo(quality)   // Download video
handleGenerateVideo()           // Updated for YouTube support
```

---

## 🐛 Common Issues & Fixes

| Issue | Solution |
|-------|----------|
| "Failed to fetch video info" | Check internet, verify URL is valid |
| "Download failed" | Try lower quality, check disk space |
| Quality buttons not showing | Check browser console, verify API response |
| "Video file not found" | Re-download video, check temp_downloads/ |

---

## 📊 Workflow Diagram

```
User → Paste URL → Fetch → Video Info
                              ↓
                    Quality Selection
                              ↓
                         Download
                              ↓
                      Video Ready
                              ↓
                    Configure Dubbing
                              ↓
                    Generate Output
```

---

## 🧪 Test Commands

### Test Backend Directly
```bash
# Test video info
curl -X POST http://localhost:8000/youtube/info \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Test download
curl -X POST http://localhost:8000/youtube/download \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","quality":"720p"}'
```

### Test Python Module
```bash
cd BackEnd/Multilingual-Dubbing-main/Multilingual-Dubbing-main
python youtube_downloader.py
```

---

## 📁 Directory Structure

```
BackEnd/
├── youtube_downloader.py       # YouTube download module
├── api_deprecated.py           # API with YouTube endpoints
├── temp_downloads/             # Downloaded videos
│   └── [uuid]_youtube_video.mp4
└── requirements.txt            # Dependencies (includes yt-dlp)

FrontEnd/
└── src/components/InputPage/
    └── InputPage.jsx           # UI with quality selector
```

---

## ⚡ Performance Tips

- **Recommended Quality**: 720p (best balance)
- **Fastest Download**: 144p or 240p
- **Best Quality**: 1080p or higher
- **Average Download Time**: 1-2 minutes for 720p

---

## 🎯 Success Checklist

- [ ] Backend server running
- [ ] Frontend server running
- [ ] yt-dlp installed
- [ ] Paste YouTube URL
- [ ] Click "Fetch"
- [ ] Video info appears
- [ ] Quality buttons visible
- [ ] Click quality button
- [ ] Download progress shows
- [ ] "Download Complete!" appears
- [ ] Video card shows in upload section
- [ ] "Generate Dubbed Video" works

---

## 📚 Documentation Files

1. **IMPLEMENTATION_SUMMARY.md** - Complete overview
2. **YOUTUBE_INTEGRATION_GUIDE.md** - Technical documentation
3. **YOUTUBE_TESTING_GUIDE.md** - Testing instructions
4. **QUICK_REFERENCE.md** - This file

---

## 🎉 Key Features

✅ Fetch YouTube video info
✅ Display video thumbnail & metadata
✅ 8 quality options (144p to 2160p)
✅ Real-time download progress
✅ Seamless dubbing integration
✅ Error handling
✅ Professional UI/UX

---

## 🔗 Quick Links

- **Test URL**: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- **Backend**: `http://localhost:8000`
- **Frontend**: Check your running dev server
- **API Docs**: `http://localhost:8000/docs`

---

**Version**: 1.0 | **Status**: ✅ Production Ready | **Date**: Jan 2026
