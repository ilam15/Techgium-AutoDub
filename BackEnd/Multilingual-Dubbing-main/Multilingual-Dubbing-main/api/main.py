from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logger import logger
from api.routes import router as pipeline_router

import time
import os
import shutil
import subprocess
import threading

app = FastAPI(title=settings.APP_NAME)

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Static Files ----------------
app.mount("/static", StaticFiles(directory="."), name="static")

# ======================================================
#                    STARTUP WARMUP
# ======================================================
@app.on_event("startup")
async def warmup_models():
    logger.info("Starting model warmup...")
    try:
        from core.models import model_manager

        def load_models():
            try:
                logger.info("Loading Whisper...")
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

        threading.Thread(target=load_models, daemon=True).start()
        logger.info("Model warmup started in background")

    except Exception as e:
        logger.error(f"Warmup init failed: {e}")

# ======================================================
#                    HEALTH ENDPOINTS
# ======================================================

@app.get("/health")
def health():
    return {"status": "healthy", "service": settings.APP_NAME}


@app.get("/ready")
def readiness():
    try:
        from core.models import model_manager
        return {"status": "ready"}
    except:
        return {"status": "not_ready"}


@app.get("/warmup")
def manual_warmup():
    try:
        from core.models import model_manager
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
        from core.models import model_manager
        whisper = model_manager.get_whisper()
        checks["whisper"] = "loaded" if whisper else "not_loaded"
    except Exception as e:
        checks["whisper"] = f"error: {e}"

    try:
        from core.models import model_manager
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
