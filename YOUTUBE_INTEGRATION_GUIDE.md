# YouTube Video Download Integration - Implementation Guide

## Overview
This implementation adds a YouTube video downloader with quality selection to the AutoDub project, allowing users to:
1. Paste a YouTube URL
2. Fetch video information
3. Select download quality (144p to 2160p)
4. Download the video
5. Automatically use it for dubbing conversion

## Architecture

### Backend Components

#### 1. `youtube_downloader.py`
- **Location**: `BackEnd/Multilingual-Dubbing-main/Multilingual-Dubbing-main/youtube_downloader.py`
- **Purpose**: Core YouTube download functionality using `yt-dlp`
- **Key Methods**:
  - `get_video_info(url)`: Fetches video metadata and available formats
  - `download_video(url, quality, filename)`: Downloads video at specified quality
  - `get_best_quality_available(url)`: Returns best available quality

#### 2. API Endpoints (`api_deprecated.py`)
- **POST `/youtube/info`**: Fetch video information
  - Request: `{ "url": "youtube_url" }`
  - Response: Video metadata + available quality options
  
- **POST `/youtube/download`**: Download video
  - Request: `{ "url": "youtube_url", "quality": "720p" }`
  - Response: Downloaded file path and metadata

- **POST `/dub_video`** (Updated): Now accepts `youtube_video_path` parameter
  - Supports both file uploads and YouTube downloaded videos

### Frontend Components

#### Updated `InputPage.jsx`
**New State Variables**:
```javascript
const [youtubeVideoInfo, setYoutubeVideoInfo] = useState(null);
const [selectedQuality, setSelectedQuality] = useState(null);
const [downloadedVideoPath, setDownloadedVideoPath] = useState(null);
const [isDownloading, setIsDownloading] = useState(false);
const [downloadProgress, setDownloadProgress] = useState(0);
```

**New Functions**:
- `processUrl()`: Fetches YouTube video info from backend
- `downloadYoutubeVideo(quality)`: Downloads video at selected quality
- Updated `handleGenerateVideo()`: Passes YouTube video path to backend

**New UI Components**:
- YouTube video info card with thumbnail and metadata
- Quality selector grid (144p, 240p, 360p, 480p, 720p, 1080p, 1440p, 2160p)
- Download progress indicator
- Success confirmation

## User Workflow

### Step-by-Step Process

1. **Paste YouTube URL**
   - User enters YouTube URL in the input field
   - Clicks "Fetch" button

2. **View Video Information**
   - System displays:
     - Video thumbnail
     - Title
     - Duration
     - Uploader name
     - Available quality options

3. **Select Quality**
   - User clicks on desired quality button (e.g., "720p")
   - Download starts automatically

4. **Download Progress**
   - Progress bar shows download status
   - Percentage indicator updates in real-time

5. **Video Ready**
   - Success message appears
   - Video card shows in "Uploaded Video" section
   - User can proceed with dubbing conversion

6. **Generate Dubbed Video**
   - User selects target language and voice settings
   - Clicks "Generate Dubbed Video"
   - Backend uses downloaded YouTube video for processing

## Installation & Setup

### Prerequisites
```bash
# Install yt-dlp (if not already installed)
pip install yt-dlp
```

### Backend Setup
1. Ensure `youtube_downloader.py` is in the backend directory
2. The API will automatically import and initialize the downloader
3. No additional configuration needed

### Frontend Setup
1. Frontend changes are already integrated into `InputPage.jsx`
2. No additional dependencies required
3. Restart the development server to see changes

## API Usage Examples

### Fetch Video Info
```javascript
const response = await fetch('http://localhost:8000/youtube/info', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
        url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' 
    })
});

const data = await response.json();
// Returns: { status: 'success', data: { title, thumbnail, duration, formats: [...] } }
```

### Download Video
```javascript
const response = await fetch('http://localhost:8000/youtube/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
        url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        quality: '720p'
    })
});

const data = await response.json();
// Returns: { status: 'success', file_path: '...', filename: '...', size: '...' }
```

### Submit for Dubbing
```javascript
const formData = new FormData();
formData.append('youtube_video_path', downloadedVideoPath);
formData.append('source_lang', 'English');
formData.append('target_lang', 'Spanish');
formData.append('gender', 'Male');

const response = await fetch('http://localhost:8000/dub_video', {
    method: 'POST',
    body: formData
});
```

## Features

### Quality Options
- **144p**: Low quality, smallest file size
- **240p**: Mobile-friendly
- **360p**: Standard definition
- **480p**: Enhanced definition
- **720p**: HD (Recommended)
- **1080p**: Full HD
- **1440p**: 2K
- **2160p**: 4K (if available)

### Smart Features
- Automatic format detection
- Best quality recommendation
- Progress tracking
- Error handling with user-friendly messages
- Thumbnail preview
- Duration display
- File size estimation

## Error Handling

### Common Errors & Solutions

1. **"Failed to fetch video info"**
   - Check internet connection
   - Verify YouTube URL is valid
   - Ensure video is not private/restricted

2. **"Download failed"**
   - Selected quality may not be available
   - Try a different quality option
   - Check available disk space

3. **"YouTube video file not found"**
   - Video may have been deleted from temp folder
   - Re-download the video

## File Structure

```
BackEnd/
├── youtube_downloader.py          # YouTube download module
├── api_deprecated.py              # Updated API with YouTube endpoints
└── temp_downloads/                # Downloaded videos storage

FrontEnd/
└── src/
    └── components/
        └── InputPage/
            └── InputPage.jsx      # Updated UI with quality selector
```

## Performance Considerations

- Videos are downloaded to `temp_downloads/` directory
- Files are automatically cleaned up after processing
- Download speed depends on:
  - Internet connection
  - Selected quality
  - YouTube server load

## Security Notes

- Only YouTube, Vimeo, and Bilibili URLs are accepted
- URL validation prevents malicious inputs
- Downloaded files are stored temporarily
- Automatic cleanup prevents disk space issues

## Future Enhancements

Potential improvements:
1. Resume interrupted downloads
2. Batch download multiple videos
3. Custom quality selection (bitrate control)
4. Download queue management
5. Playlist support
6. Audio-only download option

## Troubleshooting

### Backend Issues
```bash
# Check if yt-dlp is installed
pip show yt-dlp

# Update yt-dlp to latest version
pip install --upgrade yt-dlp

# Test YouTube downloader directly
python youtube_downloader.py
```

### Frontend Issues
```bash
# Clear browser cache
# Check browser console for errors
# Verify API endpoint is accessible
curl http://localhost:8000/
```

## Support

For issues or questions:
1. Check error messages in browser console
2. Review backend logs
3. Verify all dependencies are installed
4. Ensure API server is running on port 8000

---

**Implementation Date**: January 2026
**Version**: 1.0
**Status**: Production Ready
