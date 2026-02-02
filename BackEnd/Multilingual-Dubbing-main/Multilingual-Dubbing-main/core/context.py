import os
import uuid
import shutil
import time
from typing import Dict
from core.config import settings
from core.logger import logger


class RequestContext:
    def __init__(self, trace_id: str = None):
        self.request_id = trace_id or str(uuid.uuid4())[:8]
        self.start_time = time.time()
        self.sandbox_path = os.path.join(settings.TEMP_DIR, "requests", self.request_id)
        self.metrics: Dict[str, float] = {}

        # ---------- Optional Disk Space Check ----------
        try:
            # optional utility – avoid hard dependency
            from app import check_disk_space
            free_gb = check_disk_space(min_gb=2)
            logger.info(f"Disk space check: {free_gb:.1f}GB free")
        except Exception as e:
            logger.warning(f"Disk space check skipped: {e}")

        # ---------- Create Sandbox ----------
        os.makedirs(self.sandbox_path, exist_ok=True)

        # ---------- Optional Cleanup Registry ----------
        try:
            from app import register_for_cleanup
            register_for_cleanup(self.sandbox_path)
        except Exception as e:
            logger.warning(f"Cleanup registry unavailable: {e}")

    # ======================================================
    #                    METRICS
    # ======================================================
    def add_metric(self, stage: str, duration: float):
        self.metrics[stage] = duration
        logger.info(
            f"Request [{self.request_id}] - Stage [{stage}] completed in {duration:.2f}s"
        )

    # ======================================================
    #                    CLEANUP
    # ======================================================
    def cleanup(self):
        """Sandbox cleanup with optional registry support"""
        if os.path.exists(self.sandbox_path):
            try:
                shutil.rmtree(self.sandbox_path)
                logger.info(f"Cleaned up sandbox for request [{self.request_id}]")

                # Optional unregister
                try:
                    from app import unregister_from_cleanup
                    unregister_from_cleanup(self.sandbox_path)
                except:
                    pass

            except Exception as e:
                logger.error(f"Failed to cleanup sandbox [{self.request_id}]: {e}")

    # ======================================================
    #                    PATH HELPER
    # ======================================================
    def get_path(self, filename: str) -> str:
        return os.path.abspath(os.path.join(self.sandbox_path, filename))

    # ======================================================
    #                    CONTEXT MANAGER
    # ======================================================
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
