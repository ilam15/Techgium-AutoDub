import os
import uuid
import shutil
import time
from typing import Dict, Any
from core.config import settings
from core.logger import logger

class RequestContext:
    def __init__(self, trace_id: str = None):
        self.request_id = trace_id or str(uuid.uuid4())[:8]
        self.start_time = time.time()
        self.sandbox_path = os.path.join(settings.TEMP_DIR, "requests", self.request_id)
        self.metrics: Dict[str, float] = {}
        
        # Create unique sandbox
        os.makedirs(self.sandbox_path, exist_ok=True)
        
    def add_metric(self, stage: str, duration: float):
        self.metrics[stage] = duration
        logger.info(f"Request [{self.request_id}] - Stage [{stage}] completed in {duration:.2f}s")

    def cleanup(self):
        """Laboratory-grade sandbox cleanup"""
        if os.path.exists(self.sandbox_path):
            try:
                shutil.rmtree(self.sandbox_path)
                logger.info(f"Cleaned up sandbox for request [{self.request_id}]")
            except Exception as e:
                logger.error(f"Failed to cleanup sandbox [{self.request_id}]: {e}")

    def get_path(self, filename: str) -> str:
        """Helper to get safe path within sandbox"""
        return os.path.abspath(os.path.join(self.sandbox_path, filename))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
