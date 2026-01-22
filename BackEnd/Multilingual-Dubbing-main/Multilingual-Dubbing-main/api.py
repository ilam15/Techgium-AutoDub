from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
import uuid
import sys

# Ensure current directory is in python path to import app.py correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import subtitle_maker

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
    file: UploadFile = File(...),
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
        
        # Save uploaded file
        # Generate unique filename to avoid collisions
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(temp_dir, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"File saved to {file_path}")
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
            Audio_or_Video_File=file_path,
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
