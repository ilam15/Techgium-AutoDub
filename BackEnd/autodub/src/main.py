from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import shutil
import sys
import time
import os
import subprocess
import threading

from src.core.config import settings
from src.core.logger import logger
from src.api.routes import router as pipeline_router

# ======================================================
#                    LIFESPAN & STARTUP
# ======================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. FFmpeg Detection (Point 1)
    from src.utils.media_engine import MediaEngine
    if not shutil.which(MediaEngine.FFMPEG_PATH):
        logger.critical(f"FFmpeg not found at '{MediaEngine.FFMPEG_PATH}'! Please install FFmpeg and add it to your PATH.")
        sys.exit(1)
    
    logger.info(f"FFmpeg check passed: {MediaEngine.FFMPEG_PATH}")

    # 2. Model Warmup (Point 2)
    logger.info("Starting model warmup...")
    try:
        from src.app import model_manager

        def load_models():
            try:
                logger.info(f"Loading Whisper ({settings.WHISPER_MODEL_SIZE})...")
                model_manager.get_whisper()
                logger.info("Whisper ready")
            except Exception as e:
                logger.error(f"Whisper warmup failed: {e}")

            try:
                logger.info("Loading Speaker Analyzer...")
                model_manager.get_analyzer()
                logger.info("Speaker Analyzer ready")
            except Exception as e:
                logger.error(f"Analyzer warmup failed: {e}")
                
            try:
                 # Point 5: NLLB Pre-load
                 logger.info("Pre-loading Translation Engine...")
                 model_manager.get_translator()
                 logger.info("Translation Engine ready")
            except Exception as e:
                 logger.error(f"Translation warmup failed: {e}")

        threading.Thread(target=load_models, daemon=True).start()
        logger.info("Model warmup started in background")

    except Exception as e:
        logger.error(f"Warmup init failed: {e}")
        
    yield
    
    # Shutdown logic
    logger.info("Shutting down...")

# ======================================================
#                    MAIN APP
# ======================================================
app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Static Files ----------------
app.mount("/static", StaticFiles(directory="static"), name="static")

# ======================================================
#                    HEALTH ENDPOINTS
# ======================================================

@app.get("/health")
def health():
    return {"status": "healthy", "service": settings.APP_NAME}

@app.get("/ready")
def readiness():
    try:
        from src.app import model_manager
        return {"status": "ready"}
    except:
        return {"status": "not_ready"}

@app.get("/warmup")
def manual_warmup():
    try:
        from src.app import model_manager
        model_manager.get_whisper()
        model_manager.get_analyzer()
        return {"status": "warmed"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

@app.get("/health/deep")
def deep_health():
    checks = {}

    # ---------- FFmpeg ----------
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
            check=False
        )
        checks["ffmpeg"] = "ok" if result.returncode == 0 else "failed"
    except Exception as e:
        checks["ffmpeg"] = f"error: {e}"

    # ---------- Models ----------
    try:
        from src.app import model_manager
        whisper = model_manager.get_whisper()
        checks["whisper"] = "loaded" if whisper else "not_loaded"
    except Exception as e:
        checks["whisper"] = f"error: {e}"

    try:
        from src.app import model_manager
        analyzer = model_manager.get_analyzer()
        checks["speaker_analyzer"] = "loaded" if analyzer else "not_loaded"
    except Exception as e:
        checks["speaker_analyzer"] = f"error: {e}"

    # ---------- Disk ----------
    try:
        stat = shutil.disk_usage(".")
        free_gb = round(stat.free / (1024**3), 2)
        checks["disk_free_gb"] = free_gb
        checks["disk_status"] = "ok" if free_gb > 5 else "low"
    except Exception as e:
        checks["disk_status"] = f"error: {e}"

    all_ok = (
        checks.get("ffmpeg") == "ok" and
        checks.get("whisper") == "loaded" and
        checks.get("disk_status") == "ok"
    )

    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
        "timestamp": time.time()
    }

# ======================================================
#                    MIDDLEWARE
# ======================================================
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start_time)
    return response

# ======================================================
#                    ROUTERS
# ======================================================
app.include_router(pipeline_router, prefix="/api/v1")  # Production
app.include_router(pipeline_router)                     # Legacy

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
