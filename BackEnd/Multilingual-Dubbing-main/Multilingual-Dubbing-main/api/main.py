from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from core.config import settings
from core.logger import logger
from api.routes import router as pipeline_router
from fastapi.middleware.cors import CORSMiddleware
import time
import os
import shutil
import subprocess

app = FastAPI(title=settings.APP_NAME)

# CORS configuration for Frontend Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory for video serving
app.mount("/static", StaticFiles(directory="."), name="static")

@app.on_event("startup")
async def warmup_models():
    """
    Pre-load ML models during startup to avoid first-request delays.
    Critical for production: prevents 30-120s timeout on first API call.
    """
    logger.info("🚀 Starting model warmup...")
    try:
        from app import model_manager
        # Trigger lazy loading in background
        import threading
        
        def load_models():
            try:
                logger.info("Loading Whisper model...")
                model_manager.get_whisper()
                logger.info("✓ Whisper model ready")
            except Exception as e:
                logger.error(f"Whisper warmup failed: {e}")
            
            try:
                logger.info("Loading Speaker Analyzer...")
                model_manager.get_analyzer()
                logger.info("✓ Speaker Analyzer ready")
            except Exception as e:
                logger.error(f"Speaker Analyzer warmup failed: {e}")
        
        # Load in background thread to not block startup
        warmup_thread = threading.Thread(target=load_models, daemon=True)
        warmup_thread.start()
        logger.info("✓ Model warmup initiated in background")
    except Exception as e:
        logger.error(f"Warmup initialization failed: {e}")

@app.get("/health")
def health():
    return {"status": "healthy", "service": settings.APP_NAME}

@app.get("/warmup")
def warmup():
    """
    Manually trigger model loading. Useful for:
    - Container health checks before accepting traffic
    - Pre-warming after deployment
    - Testing model availability
    """
    from app import model_manager
    try:
        model_manager.get_whisper()
        model_manager.get_analyzer()
        return {"status": "warmed", "models": ["whisper", "speaker_analyzer"]}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

@app.get("/health/deep")
def deep_health():
    """
    Deep health check that validates all critical dependencies.
    Returns degraded status if any component fails.
    """
    checks = {}
    
    # Check FFmpeg availability
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, 
            timeout=5,
            check=False
        )
        checks["ffmpeg"] = "ok" if result.returncode == 0 else "failed"
    except Exception as e:
        checks["ffmpeg"] = f"failed: {e}"
    
    # Check ML models
    try:
        from app import model_manager
        whisper = model_manager.get_whisper()
        checks["whisper"] = "loaded" if whisper else "not_loaded"
    except Exception as e:
        checks["whisper"] = f"error: {e}"
    
    try:
        from app import model_manager
        analyzer = model_manager.get_analyzer()
        checks["speaker_analyzer"] = "loaded" if analyzer else "not_loaded"
    except Exception as e:
        checks["speaker_analyzer"] = f"error: {e}"
    
    # Check disk space
    try:
        stat = shutil.disk_usage(".")
        free_gb = round(stat.free / (1024**3), 2)
        checks["disk_free_gb"] = free_gb
        checks["disk_status"] = "ok" if free_gb > 5 else "low"
    except Exception as e:
        checks["disk_status"] = f"error: {e}"
    
    # Determine overall status
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

@app.get("/ready")
def readiness():
    # Check if models can be initialized
    from app import model_manager
    try:
        # Shallow check: model_manager is available
        return {"status": "ready"}
    except:
        return {"status": "not_ready"}

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Include Production Routes (New FAANG Standard)
app.include_router(pipeline_router, prefix="/api/v1")

# Legacy Support (Top-level fallback for existing Frontend)
app.include_router(pipeline_router)

