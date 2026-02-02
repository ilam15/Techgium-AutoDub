from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
import os
import uuid
import shutil
import asyncio
import json

from core.config import settings
from core.logger import logger
from main_pipeline import ProductionPipeline
from clean_up import cleanup_all_temporary_files
from youtube_downloader import YouTubeDownloader
from pydantic import BaseModel

router = APIRouter()

# ---------------- YouTube Setup ----------------
youtube_dl = YouTubeDownloader()

class YouTubeInfoRequest(BaseModel):
    url: str

class YouTubeDownloadRequest(BaseModel):
    url: str
    quality: str = "720p"

# ---------------- Concurrency Controls ----------------
_active_requests = asyncio.Semaphore(3)
_request_timeout = 600
_max_video_duration = 600

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
    if _active_requests.locked():
        raise HTTPException(status_code=429, detail="Server busy. Try later.")

    async with _active_requests:
        try:
            trace_id = str(uuid.uuid4())[:8]
            pipeline = ProductionPipeline(trace_id=trace_id)

            # ---------- Parse Languages ----------
            try:
                known_langs = json.loads(user_known_languages)
            except:
                known_langs = []

            # ---------- Input Source ----------
            if youtube_url:
                try:
                    logger.info(f"Downloading YouTube video: {youtube_url} (Trace: {trace_id})")
                    # Download directly to temp folder with trace_id to avoid collisions
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
                if file.size > settings.MAX_FILE_SIZE:
                    raise HTTPException(status_code=400, detail="File too large")

                local_input = pipeline.context.get_path(file.filename)
                with open(local_input, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                logger.info(f"Upload job: {trace_id} | {file.filename}")

            else:
                raise HTTPException(status_code=400, detail="Provide file or youtube_video_path")

            # ---------- Duration Check ----------
            try:
                from media_engine import MediaEngine
                probe = MediaEngine.get_probe_info(local_input)
                duration = float(probe.get("format", {}).get("duration", 0))
                if duration > _max_video_duration:
                    raise HTTPException(status_code=413, detail="Video too long")
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Duration check skipped: {e}")

            # ---------- Run Pipeline ----------
            try:
                result = await asyncio.wait_for(
                    run_in_threadpool(
                        pipeline.run,
                        input_file=local_input,
                        src_lang=source_lang,
                        dst_lang=target_lang,
                        gender=gender,
                        recover_music=recover_bg,
                        user_known_languages=known_langs
                    ),
                    timeout=_request_timeout
                )
            except asyncio.TimeoutError:
                raise HTTPException(status_code=408, detail="Processing timeout")

            if result.get("status") == "error":
                return result

            # ---------- Cleanup ----------
            background_tasks.add_task(cleanup_all_temporary_files, keep_latest_output=True)

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
