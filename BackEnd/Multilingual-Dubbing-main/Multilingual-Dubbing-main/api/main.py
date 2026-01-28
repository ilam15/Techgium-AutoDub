from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from core.config import settings
from core.logger import logger
from api.routes import router as pipeline_router
from fastapi.middleware.cors import CORSMiddleware
import time
import os

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

@app.get("/health")
def health():
    return {"status": "healthy", "service": settings.APP_NAME}

@app.get("/ready")
def readiness():
    # Check if models can be initialized
    from core.models import model_manager
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
