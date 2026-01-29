from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
import os
import uuid
import shutil
import asyncio
from core.config import settings
from core.logger import logger
from main_pipeline import ProductionPipeline
from youtube_downloader import YouTubeDownloader
from pydantic import BaseModel

# Initialize YouTube downloader
youtube_dl = YouTubeDownloader()

# Pydantic models for YouTube endpoints
class YouTubeInfoRequest(BaseModel):
    url: str

class YouTubeDownloadRequest(BaseModel):
    url: str
    quality: str = "720p"

router = APIRouter()

# Global concurrency control - max 3 parallel dubbing requests
_active_requests = asyncio.Semaphore(3)
_request_timeout = 600  # 10 minutes max per request
_max_video_duration = 600  # 10 minutes max video length

@router.post("/dub_video")
async def dub_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    youtube_video_path: str = Form(None),
    source_lang: str = Form("Automatic"),
    target_lang: str = Form("Hindi"),
    gender: str = Form("Male"),
    recover_bg: bool = Form(False),
    hf_token: str = Form(None)
):
    # Check if server is at capacity
    if _active_requests.locked():
        raise HTTPException(
            status_code=429,
            detail="Server at capacity. Maximum 3 concurrent requests allowed. Please try again in a few minutes."
        )
    
    async with _active_requests:
        try:
            # 1. Determine input source
            trace_id = str(uuid.uuid4())[:8]
            pipeline = ProductionPipeline(trace_id=trace_id)
            
            if youtube_video_path:
                # Use YouTube downloaded video
                if not os.path.exists(youtube_video_path):
                    raise HTTPException(status_code=400, detail="YouTube video file not found")
                local_input = youtube_video_path
                logger.info(f"Using YouTube video: {trace_id} | Path: {youtube_video_path}")
            elif file:
                # Validation for uploaded file
                if file.size > settings.MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail="File too large")
                
                # Save uploaded file
                local_input = pipeline.context.get_path(file.filename)
                with open(local_input, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                logger.info(f"Accepted work job: {trace_id} | File: {file.filename}")
            else:
                raise HTTPException(status_code=400, detail="Either file or youtube_video_path must be provided")

            # 2. Validate video duration to prevent resource exhaustion
            try:
                from media_engine import MediaEngine
                probe = MediaEngine.get_probe_info(local_input)
                duration = float(probe.get("format", {}).get("duration", 0))
                
                if duration > _max_video_duration:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Video too long: {duration:.0f}s (max {_max_video_duration}s / {_max_video_duration//60} minutes)"
                    )
                
                logger.info(f"Video duration: {duration:.1f}s - within limits")
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Could not validate video duration: {e}. Proceeding anyway.")

            # 3. Execute Production Pipeline with timeout protection
            try:
                result = await asyncio.wait_for(
                    run_in_threadpool(
                        pipeline.run,
                        input_file=local_input,
                        src_lang=source_lang,
                        dst_lang=target_lang,
                        gender=gender,
                        recover_music=recover_bg
                    ),
                    timeout=_request_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Request {trace_id} timed out after {_request_timeout}s")
                raise HTTPException(
                    status_code=408,
                    detail=f"Processing timeout. Request exceeded {_request_timeout//60} minute limit."
                )
            
            if result.get("status") == "error":
                return result

            # 4. Success payload
            base_url = f"{request.url.scheme}://{request.url.netloc}"
            return {
                "status": "success",
                "request_id": trace_id,
                "video_url": f"{base_url}/static/{result['video_url']}",
                "metrics": result["metrics"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API Error: {e}")
            return {"status": "error", "error": str(e)}

@router.post("/youtube/info")
async def get_youtube_info(request: YouTubeInfoRequest):
    """
    Fetch YouTube video information including available quality options
    """
    try:
        logger.info(f"Fetching YouTube info for: {request.url}")
        video_info = youtube_dl.get_video_info(request.url)
        return {
            "status": "success",
            "data": video_info
        }
    except Exception as e:
        logger.error(f"YouTube Info Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/youtube/download")
async def download_youtube_video(request: YouTubeDownloadRequest):
    """
    Download YouTube video with specified quality
    Returns the local file path that can be used for dubbing
    """
    try:
        logger.info(f"Downloading YouTube video: {request.url} at {request.quality}")
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}_youtube_video.mp4"
        
        # Download video
        video_path = youtube_dl.download_video(
            url=request.url,
            quality=request.quality,
            filename=unique_filename
        )
        
        # Get file info
        file_size = os.path.getsize(video_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        logger.info(f"Download complete: {video_path} ({file_size_mb} MB)")
        
        return {
            "status": "success",
            "file_path": video_path,
            "filename": os.path.basename(video_path),
            "size": f"{file_size_mb} MB"
        }
    except Exception as e:
        logger.error(f"YouTube Download Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
