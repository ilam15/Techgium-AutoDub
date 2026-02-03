import logging
import json
import time
from typing import Any, Dict

class StructuredLogger(logging.Logger):
    def _log_json(self, level, msg, extra=None, *args, **kwargs):
        log_record = {
            "timestamp": time.time(),
            "level": logging.getLevelName(level),
            "message": msg,
            "extra": extra or {}
        }
        super()._log(level, json.dumps(log_record), args, **kwargs)

def setup_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = setup_logger("AutoDub")
