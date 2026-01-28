from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
import os
import uuid
import shutil
from core.config import settings
from core.logger import logger
from main_pipeline import ProductionPipeline

router = APIRouter()

@router.post("/dub_video")
async def dub_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_lang: str = Form("Automatic"),
    target_lang: str = Form("Hindi"),
    gender: str = Form("Male"),
    recover_bg: bool = Form(False),
    hf_token: str = Form(None)
):
    try:
        # 1. Validation
        if file.size > settings.MAX_FILE_SIZE:
             raise HTTPException(status_code=400, detail="File too large")
             
        # 2. Save Upload within a fresh sandbox
        trace_id = str(uuid.uuid4())[:8]
        pipeline = ProductionPipeline(trace_id=trace_id)
        
        # Ensure we save the file INTO the sandbox
        local_input = pipeline.context.get_path(file.filename)
        with open(local_input, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Accepted work job: {trace_id} | File: {file.filename}")

        # 3. Execute Production Pipeline
        # We run this in a threadpool to keep the API responsive
        result = await run_in_threadpool(
            pipeline.run,
            input_file=local_input,
            src_lang=source_lang,
            dst_lang=target_lang,
            gender=gender,
            recover_music=recover_bg
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

    except Exception as e:
        logger.error(f"API Error: {e}")
        return {"status": "error", "error": str(e)}
