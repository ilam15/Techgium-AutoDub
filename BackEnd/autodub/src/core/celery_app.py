from celery import Celery
import os
from src.core.config import settings

# Force OpenMP to allows multiple library initializations (prevents OMP Error #15 on Windows)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Initialize Celery
# Defaulting to Redis, but can be configured via environment variables
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "autodub",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.tasks"]
)

# Celery Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Define Queues
    task_queues={
        "default": {
            "routing_key": "default",
        },
        "tts": {
            "routing_key": "tts",
        },
    },
    task_default_queue="default",
    
    # Route TTS tasks to the dedicated queue
    task_routes={
        "src.tasks.tts_segment_task": {"queue": "tts"},
    },
    
    # Visibility timeout for long tasks (1 hour)
    broker_transport_options={
        'visibility_timeout': 3600,
    },
    
    # Max memory per child to prevent leaks during heavy model usage
    worker_max_memory_per_child=2500000, # 2.5GB (KiB)
    worker_max_tasks_per_child=50,       # Restart worker after 50 tasks to clear leaks
    
    # Result Backend Settings
    result_expires=3600,                 # Expire results after 1 hour to keep Redis clean
    
    # Production Robustness
    worker_prefetch_multiplier=1, # One task at a time per worker process
    task_acks_late=True,          # Tasks acknowledged after completion
    task_reject_on_worker_lost=True, # Re-queue if worker crashes
    worker_send_task_events=True,    # Enable events for Flower monitoring
    
    # Timeouts
    task_time_limit=3600,         # Hard limit: 1 hour
    task_soft_time_limit=3300,    # Soft limit: 55 mins
)

# Windows Compatibility: Overwrite pool if running on Windows
if os.name == 'nt':
    celery_app.conf.update(
        worker_pool='solo',
        worker_concurrency=1
    )

