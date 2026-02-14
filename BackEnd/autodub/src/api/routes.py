from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import json
import torch
import shutil

from src.core.config import settings
from src.core.logger import logger
from src.utils.clean_up import cleanup_all_temporary_files
from src.utils.media_engine import MediaEngine
from src.services.youtube_downloader import YouTubeDownloader
from src.tasks import trigger_autodub_pipeline
from src.core.celery_app import celery_app
from celery.result import AsyncResult

from src.core.context import RequestContext

router = APIRouter()

# ---------------- YouTube Setup ----------------
# Use a static location for downloads so they can be served or inspected easily
DOWNLOAD_DIR = os.path.join(settings.BASE_DIR, "static", "downloads")
UPLOAD_DIR = os.path.join(settings.BASE_DIR, "static", "uploads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

youtube_dl = YouTubeDownloader(download_dir=DOWNLOAD_DIR)

class YouTubeInfoRequest(BaseModel):
    url: str

class YouTubeDownloadRequest(BaseModel):
    url: str
    quality: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[float] = 0
    stage: Optional[str] = "Pending"
    result: Optional[dict] = None
    error: Optional[str] = None

# ---------------- Concurrency Controls ----------------
_max_video_duration = 3600 # 1 hour

# ======================================================
#                    DUB VIDEO
# ======================================================
@router.post("/dub_video")
async def dub_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    youtube_video_path: str = Form(None),
    youtube_url: str = Form(None),
    source_lang: str = Form("Automatic"),
    target_lang: str = Form("Hindi"),
    gender: str = Form("Male"),
    recover_bg: bool = Form(False),
    user_known_languages: str = Form("[]"),
    hf_token: str = Form(None)
):
    try:
        trace_id = str(uuid.uuid4())[:8]
        context = RequestContext(trace_id)

        # ---------- Parse Languages ----------
        try:
            known_langs = json.loads(user_known_languages)
        except:
            known_langs = []

        # ---------- Input Source ----------
        local_input = None

        if youtube_url:
            try:
                logger.info(f"Downloading YouTube video: {youtube_url} (Trace: {trace_id})")
                dl_filename = f"yt_{trace_id}.mp4"
                local_input = youtube_dl.download_video(youtube_url, filename=dl_filename)
                logger.info(f"YouTube download complete: {local_input}")
            except Exception as e:
                logger.error(f"YouTube download failed: {e}")
                raise HTTPException(status_code=400, detail=f"YouTube download failed: {str(e)}")

        elif youtube_video_path:
            if not os.path.exists(youtube_video_path):
                raise HTTPException(status_code=400, detail="YouTube file not found")
            local_input = youtube_video_path
            logger.info(f"YouTube local file job: {trace_id}")

        elif file:
            # Check for empty file
            if file.filename == "":
                raise HTTPException(status_code=400, detail="No file uploaded")
            
            # Save to static/uploads for persistence/accessibility
            safe_filename = f"upload_{trace_id}_{file.filename}"
            local_input = os.path.join(UPLOAD_DIR, safe_filename)
            
            with open(local_input, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"Upload job: {trace_id} | {file.filename}")

        else:
            raise HTTPException(status_code=400, detail="Provide file or youtube_video_path")

        # ---------- Duration Check ----------
        try:
            probe = MediaEngine.get_probe_info(local_input)
            if not probe:
                 raise Exception("FFmpeg probe failed (no output)")
            
            duration = float(probe.get("format", {}).get("duration", 0))
            if duration > _max_video_duration:
                raise HTTPException(status_code=413, detail=f"Video too long (Max {_max_video_duration}s)")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Input verification failed: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid video file: {str(e)}")

        # ---------- Run Pipeline (Celery Async) ----------
        try:
            task_id = trigger_autodub_pipeline(
                input_file=local_input,
                src_lang=source_lang,
                dst_lang=target_lang,
                gender=gender,
                recover_bg=recover_bg,
                user_known_languages=known_langs,
                trace_id=trace_id
            )
            
            return {
                "status": "queued",
                "task_id": task_id,
                "request_id": trace_id,
                "message": "Video dubbing pipeline started in background."
            }
        except Exception as e:
            logger.error(f"Failed to start Celery pipeline: {e}")
            raise HTTPException(status_code=500, detail="Failed to start processing pipeline.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API Error: {e}")
        return {"status": "error", "error": str(e)}


# ======================================================
#                YOUTUBE ENDPOINTS
# ======================================================

@router.post("/youtube/info")
async def get_youtube_info(request: YouTubeInfoRequest):
    try:
        data = youtube_dl.get_video_info(request.url)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/youtube/download")
async def download_youtube_video(request: YouTubeDownloadRequest):
    try:
        filename = f"{uuid.uuid4()}_youtube.mp4"
        path = youtube_dl.download_video(request.url, request.quality, filename)
        size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)

        return {
            "status": "success",
            "file_path": path,
            "filename": os.path.basename(path),
            "size": f"{size_mb} MB"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Check the status of a Celery task with distributed pipeline awareness.
    """
    from src.tasks import REDIS_CLIENT
    try:
        # 1. Base status from Celery (AsyncResult is fast)
        result = AsyncResult(task_id, app=celery_app)
        
        response = {
            "task_id": task_id,
            "status": result.status,
            "progress": 0,
            "stage": "Initializing",
            "result": None,
            "error": None
        }

        # 2. Pipeline-Aware Progress (Redis)
        trace_id_bytes = REDIS_CLIENT.get(f"task:{task_id}:trace")
        if trace_id_bytes:
            trace_id = trace_id_bytes.decode()
            pipeline_data = REDIS_CLIENT.hgetall(f"pipeline:{trace_id}")
            
            if pipeline_data:
                # Progress Math
                done = int(pipeline_data.get(b"segments_done", 0))
                total = int(pipeline_data.get(b"total_segments", 0))
                
                if total > 0:
                    # Logic: T1 takes ~30% for separation. T3 takes remaining 70%
                    p = (done / total) * 100
                    response["progress"] = min(99, p)
                    response["stage"] = f"Dubbing Segments ({done}/{total})"
                
                # Check for input file to serve original URL if needed (optional)
                input_file = pipeline_data.get(b"input_file", b"").decode()
                
        # 3. Handle Lifecycle
        if result.status == 'PROGRESS':
            # Use T1 status if available
            if isinstance(result.info, dict):
                response["progress"] = max(response["progress"], result.info.get('progress', 0))
                response["stage"] = result.info.get('stage', 'Segmenting Audio')
            
        elif result.status == 'SUCCESS':
            # Even if T1 (Celery) is SUCCESS, wait for T3 (Final Merge)
            if trace_id_bytes:
                trace_id = trace_id_bytes.decode()
                # Check if output file exists
                out_name = f"output_{trace_id}.mp4"
                processed_path = os.path.join(settings.BASE_DIR, "static", "processed", out_name)
                
                if os.path.exists(processed_path):
                    response["status"] = "SUCCESS"
                    response["progress"] = 100
                    response["stage"] = "Completed"
                    
                    # Original Video URL
                    # Input is typically in "static/downloads" or "static/uploads" now.
                    # We can construct proper URL if we know the filename.
                    original_url = ""
                    if pipeline_data:
                         input_file = pipeline_data.get(b"input_file", b"").decode()
                         if "static" in input_file:
                             # Extract relative path from static
                             rel_path = input_file.split("static")[-1].replace("\\", "/")
                             original_url = f"/static{rel_path}"

                    response["result"] = {
                        "video_url": f"/static/processed/{out_name}",
                        "original_video_url": original_url,
                        "trace_id": trace_id
                    }
                else:
                    # Still merging...
                    response["status"] = "PROGRESS"
                    response["stage"] = "Finalizing Video Merge"
                    response["progress"] = 99
            else:
                # Fallback for old tasks
                response["progress"] = 100
                response["stage"] = "Completed"
                response["result"] = result.result

        elif result.status == 'FAILURE':
            response["status"] = "FAILED"
            response["error"] = str(result.info)
            response["stage"] = "Error"
        
        return response
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
