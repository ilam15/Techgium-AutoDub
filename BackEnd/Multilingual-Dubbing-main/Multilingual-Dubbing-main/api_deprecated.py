from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import shutil
import os
import uuid
import sys
import yt_dlp
import json

# Ensure current directory is in python path to import app.py correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import subtitle_maker
from clean_up import cleanup_all_temporary_files

# Pydantic models for request/response
class VideoURLRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str = None  # Optional: specific format ID to download

app = FastAPI()

# CORS configuration to allow requests from React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev; specify frontend URL in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory to serve generated video files
# We mount the current directory so that relative paths returned by processing logic work
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def read_root():
    return {"message": "AutoDub API is running"}

@app.post("/dub_video")
async def dub_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    file_path: str = Form(None),  # Add option to pass already downloaded file path
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    gender: str = Form("Male"),
    recover_background_noise: str = Form("false"), # FormData sends booleans as strings often
    make_video: str = Form("true"),
    hf_token: str = Form(None)
):
    try:
        # Convert string booleans
        recover_bg = recover_background_noise.lower() == "true"
        # make_video should be true to get a video output 
        do_make_video = make_video.lower() == "true"

        # Create temp directory
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Determine file path - either from upload or from already downloaded file
        if file_path and os.path.exists(file_path):
            # Use already downloaded file
            video_file_path = file_path
            print(f"Using pre-downloaded file: {video_file_path}")
        elif file:
            # Save uploaded file
            # Generate unique filename to avoid collisions
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            video_file_path = os.path.join(temp_dir, unique_filename)
            
            with open(video_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            print(f"File saved to {video_file_path}")
        else:
            raise HTTPException(status_code=400, detail="Either file or file_path must be provided")
        
        print(f"Processing: Source={source_lang}, Target={target_lang}, Gender={gender}")

        # Call the core processing logic from app.py
        # subtitle_maker returns: 
        # dubb_voice, default_srt_path, new_video, customize_srt_path, word_level_srt_path, shorts_srt_name, text_path, new_video
        # Note: the return signature in app.py line 916 is a bit cluttered, let's verify.
        # Line 916: return dubb_voice,default_srt_path, new_video,customize_srt_path, word_level_srt_path, shorts_srt_name, text_path,new_video
        # It returns new_video twice?
        
        # Let's handle the return values carefully.
        # Call the core processing logic from app.py in a threadpool to avoid blocking
        from fastapi.concurrency import run_in_threadpool
        
        results = await run_in_threadpool(
            subtitle_maker,
            Audio_or_Video_File=video_file_path,
            Source_Language=source_lang,
            Destination_Language=target_lang,
            Gender=gender,
            recover_music=recover_bg,
            make_video=do_make_video,
            subtitle_upload=None,
            hf_token=hf_token
        )

        
        # Unpack results based on inspection of app.py
        # dubb_voice (audio path), default_srt, new_video (path), ...
        dubb_voice_path = results[0]
        new_video_path = results[2]
        
        if not new_video_path and do_make_video:
             # Fallback: sometimes logic might return it in the last position if modified?
             # But looking at line 916: "new_video" is at index 2 AND index 7.
             new_video_path = results[7]

        if not new_video_path:
             raise Exception("Video generation failed or returned None")

        # Construct full URLs for the frontend
        # Assuming server runs on localhost:8000
        # The paths returned are likely relative (e.g., "./output/foo.mp4") or absolute.
        # If relative, we prepended "static" mount.
        
        def get_static_url(path):
            if not path: return None
            # Normalize path separators
            path = path.replace("\\", "/")
            # Remove leading ./ or / if present to append to static base
            if path.startswith("./"): path = path[2:]
            elif path.startswith("/"): path = path[1:]
            return f"http://localhost:8000/static/{path}"

        # Schedule cleanup task
        keep_files = [new_video_path, dubb_voice_path, video_file_path]
        background_tasks.add_task(cleanup_all_temporary_files, keep_latest_output=False, preserve_files=keep_files)


        return {
            "status": "success",
            "video_url": get_static_url(new_video_path),
            "original_video_url": get_static_url(file_path),
            "audio_url": get_static_url(dubb_voice_path)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}

    finally:
        # Optional: Clean up temp file if needed, but for preview we might want to keep it
        pass

@app.post("/fetch_video_info")
async def fetch_video_info(request: VideoURLRequest):
    """
    Fetch video information from YouTube URL including available formats
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Add headers to avoid blocking
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            
            # Extract relevant information
            formats = info.get('formats', [])
            
            # Filter and organize formats by quality
            video_formats = []
            seen_qualities = set()
            
            for f in formats:
                # Only include formats with both video and audio, or video-only with common resolutions
                # Prefer non-HLS/DASH formats for better reliability
                if f.get('vcodec') != 'none' and f.get('height'):
                    height = f.get('height')
                    quality_label = f"{height}p"
                    protocol = f.get('protocol', '')
                    
                    # Common video qualities
                    if height in [144, 240, 360, 480, 720, 1080, 1440, 2160] and quality_label not in seen_qualities:
                        seen_qualities.add(quality_label)
                        video_formats.append({
                            'format_id': f.get('format_id'),
                            'quality': quality_label,
                            'height': height,
                            'ext': f.get('ext', 'mp4'),
                            'filesize': f.get('filesize', 0),
                            'has_audio': f.get('acodec') != 'none',
                            'protocol': protocol,
                            'is_hls': 'm3u8' in protocol or 'hls' in protocol.lower(),
                        })
            
            # Sort by quality (height)
            video_formats.sort(key=lambda x: x['height'])
            
            return {
                'status': 'success',
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
                'formats': video_formats
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        
        # Check if it's an age restriction error
        if 'age' in error_msg.lower() or 'sign in' in error_msg.lower():
            raise HTTPException(
                status_code=400, 
                detail="[Age-Restricted Video] This video requires age verification. Please:\n\n" +
                       "1. Close Google Chrome completely\n" +
                       "2. Download the video manually using yt-dlp in terminal:\n" +
                       "   yt-dlp --cookies-from-browser chrome \"" + request.url + "\"\n" +
                       "3. Upload the downloaded file directly using the file upload option\n\n" +
                       "Alternatively, try a different video that doesn't require age verification."
            )
        
        raise HTTPException(status_code=400, detail=f"Failed to fetch video info: {error_msg}")

@app.post("/download_video")
async def download_video(request: DownloadRequest):
    """
    Download video from YouTube URL in specified quality
    """
    try:
        # Create downloads directory
        download_dir = "temp_uploads"
        os.makedirs(download_dir, exist_ok=True)
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(download_dir, f"{unique_id}_%(title)s.%(ext)s")
        
        # Enhanced options for yt-dlp to handle modern YouTube requirements
        ydl_opts = {
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4',
            
            # Retry and timeout settings
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': False,
            'abort_on_unavailable_fragment': False,
            'socket_timeout': 30,
            
            # Buffer size for better streaming performance
            'buffersize': 1024 * 1024 * 16,  # 16MB buffer
            
            # HTTP options to avoid rate limiting
            'http_chunk_size': 10485760,  # 10MB chunks
            'concurrent_fragment_downloads': 3,  # Reduced from 5 to avoid overwhelming
            
            # Throttle to avoid rate limiting
            'ratelimit': None,  # No rate limit, but can set if needed
            'throttledratelimit': None,
            
            # Keep video - don't delete after processing
            'keepvideo': False,
            
            # Headers to mimic browser
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            
            # FFmpeg location (optional - yt-dlp will search PATH)
            'ffmpeg_location': None,  # Let yt-dlp find it automatically
            
            # Prefer formats that don't need post-processing
            'prefer_free_formats': True,
            
            # Post-processors - make FFmpeg optional
            'postprocessors': [],  # Remove FFmpeg post-processor to avoid failures
        }
        
        # Format selection logic - AVOID HLS/DASH/m3u8 formats completely
        if request.format_id:
            # User selected a specific format - but still avoid HLS/DASH
            ydl_opts['format'] = (
                f"({request.format_id}+bestaudio[ext=m4a])[protocol!*=m3u8][protocol!*=dash]/"
                f"({request.format_id})[protocol!*=m3u8][protocol!*=dash]/"
                f"(bestvideo+bestaudio)[protocol!*=m3u8][protocol!*=dash]/"
                f"best[protocol!*=m3u8][protocol!*=dash]"
            )
        else:
            # Best quality - STRICTLY avoid HLS/DASH/m3u8 formats
            # Only use progressive HTTP downloads
            ydl_opts['format'] = (
                '(bestvideo[ext=mp4]+bestaudio[ext=m4a])[protocol^=https][protocol!*=m3u8][protocol!*=dash]/'
                'best[ext=mp4][protocol^=https][protocol!*=m3u8][protocol!*=dash]/'
                '(bestvideo+bestaudio)[protocol!*=m3u8][protocol!*=dash]/'
                'best[protocol!*=m3u8][protocol!*=dash]/'
                'best'
            )
        
        downloaded_file = None
        max_retries = 3
        retry_count = 0
        last_error = None
        
        print(f"Downloading from: {request.url}")
        print(f"Format: {ydl_opts['format']}")
        
        # Retry loop for entire download process
        while retry_count < max_retries:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(request.url, download=True)
                    # Get the actual downloaded filename
                    downloaded_file = ydl.prepare_filename(info)
                    
                    # Handle cases where extension might change after post-processing
                    if not os.path.exists(downloaded_file):
                        # Try with .mp4 extension
                        base_name = os.path.splitext(downloaded_file)[0]
                        downloaded_file = base_name + '.mp4'
                
                # Validate file exists and is not empty
                if downloaded_file and os.path.exists(downloaded_file):
                    file_size = os.path.getsize(downloaded_file)
                    if file_size > 0:
                        # Success!
                        break
                    else:
                        raise Exception("Downloaded file is empty")
                else:
                    raise Exception("Download failed - file not found after download")
                    
            except Exception as e:
                last_error = e
                retry_count += 1
                print(f"Download attempt {retry_count} failed: {str(e)}")
                
                # Clean up failed download
                if downloaded_file and os.path.exists(downloaded_file):
                    try:
                        os.remove(downloaded_file)
                    except:
                        pass
                
                if retry_count < max_retries:
                    import time
                    wait_time = 2 ** retry_count  # Exponential backoff
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    raise last_error
        
        if not downloaded_file or not os.path.exists(downloaded_file):
            raise Exception("Download failed after all retries - file not found")
        
        file_size = os.path.getsize(downloaded_file)
        if file_size == 0:
            raise Exception("Downloaded file is empty after all retries")
        
        file_name = os.path.basename(downloaded_file)
        
        print(f"Download successful: {file_name} ({file_size} bytes)")
        
        return {
            'status': 'success',
            'file_path': downloaded_file,
            'file_name': file_name,
            'file_size': file_size,
            'message': 'Video downloaded successfully'
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Failed to download video: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
