from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import json
import torch
import shutil
import asyncio

from src.core.config import settings
from src.core.logger import logger
from src.main_pipeline import ProductionPipeline
from src.utils.clean_up import cleanup_all_temporary_files
from src.utils.media_engine import MediaEngine
from src.services.youtube_downloader import YouTubeDownloader
from src.tasks import trigger_autodub_pipeline
from src.core.celery_app import celery_app
from celery.result import AsyncResult

from src.core.context import RequestContext

router = APIRouter()

# ---------------- YouTube Setup ----------------
youtube_dl = YouTubeDownloader(download_dir=os.path.join(settings.TEMP_DIR, "downloads"))

class YouTubeInfoRequest(BaseModel):
    url: str

class YouTubeDownloadRequest(BaseModel):
    url: str
    quality: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[float] = 0
    result: Optional[dict] = None
    error: Optional[str] = None

# ---------------- Concurrency Controls ----------------
_active_requests = asyncio.Semaphore(10) # Increased for async
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
                
            local_input = context.get_path(file.filename)
            with open(local_input, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"Upload job: {trace_id} | {file.filename}")

        else:
            raise HTTPException(status_code=400, detail="Provide file or youtube_video_path")

        # ---------- Duration Check ----------
        try:
            probe = MediaEngine.get_probe_info(local_input)
            duration = float(probe.get("format", {}).get("duration", 0))
            if duration > _max_video_duration:
                raise HTTPException(status_code=413, detail="Video too long")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Duration check skipped: {e}")

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
    Check the status of a Celery task.
    """
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        response = {
            "task_id": task_id,
            "status": result.status,
            "progress": 0,
            "stage": "Queued",
            "result": None,
            "error": None
        }

        # Check for progress updates (custom state 'PROGRESS')
        if result.status == 'PROGRESS':
            response["progress"] = result.info.get('progress', 0)
            response["stage"] = result.info.get('stage', 'Processing')
        elif result.status == 'SUCCESS':
            response["progress"] = 100
            response["stage"] = "Completed"
            response["result"] = result.result
            
            # Prepend /static/ to urls
            if response["result"]:
                for key in ["video_url", "original_video_url"]:
                    if key in response["result"]:
                        fn = response["result"][key]
                        if fn and not fn.startswith(("http", "/")):
                             response["result"][key] = f"/static/{fn}"
        elif result.status == 'FAILURE':
            response["status"] = "FAILED"
            response["error"] = str(result.info)
            response["stage"] = "Error"
        
        return response
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
