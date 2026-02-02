from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
import uuid
import sys
from pydantic import BaseModel

# Ensure current directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import subtitle_maker
from clean_up import cleanup_unnecessary_files
from youtube_downloader import YouTubeDownloader

from fastapi.concurrency import run_in_threadpool

# ---------------- INIT ----------------
app = FastAPI()
youtube_dl = YouTubeDownloader()

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- STATIC ----------------
app.mount("/static", StaticFiles(directory="."), name="static")

# ---------------- MODELS ----------------
class YouTubeInfoRequest(BaseModel):
    url: str

class YouTubeDownloadRequest(BaseModel):
    url: str
    quality: str = "720p"

# ---------------- ROOT ----------------
@app.get("/")
def read_root():
    return {"message": "AutoDub API is running"}

# ---------------- YOUTUBE INFO ----------------
@app.post("/youtube/info")
async def get_youtube_info(request: YouTubeInfoRequest):
    try:
        video_info = youtube_dl.get_video_info(request.url)
        return {"status": "success", "data": video_info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------- YOUTUBE DOWNLOAD ----------------
@app.post("/youtube/download")
async def download_youtube_video(request: YouTubeDownloadRequest):
    try:
        unique_filename = f"{uuid.uuid4()}_youtube_video.mp4"

        video_path = youtube_dl.download_video(
            url=request.url,
            quality=request.quality,
            filename=unique_filename
        )

        file_size_mb = round(os.path.getsize(video_path) / (1024 * 1024), 2)

        return {
            "status": "success",
            "file_path": video_path,
            "filename": os.path.basename(video_path),
            "size": f"{file_size_mb} MB"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------- DUB VIDEO ----------------
@app.post("/dub_video")
async def dub_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    youtube_video_path: str = Form(None),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    gender: str = Form("Male"),
    recover_background_noise: str = Form("false"),
    make_video: str = Form("true"),
    hf_token: str = Form(None)
):
    try:
        recover_bg = recover_background_noise.lower() == "true"
        do_make_video = make_video.lower() == "true"

        file_path = None

        # ---------- SOURCE DECISION ----------
        if youtube_video_path:
            if not os.path.exists(youtube_video_path):
                raise HTTPException(status_code=400, detail="YouTube file not found")
            file_path = youtube_video_path

        elif file:
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)

            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            file_path = os.path.join(temp_dir, unique_filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either file upload or youtube_video_path"
            )

        # ---------- PROCESS ----------
        results = await run_in_threadpool(
            subtitle_maker,
            Audio_or_Video_File=file_path,
            Source_Language=source_lang,
            Destination_Language=target_lang,
            Gender=gender,
            recover_music=recover_bg,
            make_video=do_make_video,
            subtitle_upload=None,
            hf_token=hf_token
        )

        dubb_voice_path = results[0]
        new_video_path = results[2] or results[7]

        if not new_video_path:
            raise Exception("Video generation failed")

        # ---------- STATIC URL HELPER ----------
        def get_static_url(path):
            if not path:
                return None
            path = path.replace("\\", "/")
            if path.startswith("./"):
                path = path[2:]
            elif path.startswith("/"):
                path = path[1:]
            return f"http://localhost:8000/static/{path}"

        # ---------- CLEANUP ----------
        keep_files = [new_video_path, dubb_voice_path, file_path]
        background_tasks.add_task(cleanup_unnecessary_files, keep_files=keep_files)

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

# ---------------- RUN ----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
