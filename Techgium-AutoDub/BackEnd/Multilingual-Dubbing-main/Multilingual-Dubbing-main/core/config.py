import os
from pydantic_settings import BaseSettings
from typing import Optional

import torch

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AutoDub Engine"
    DEBUG: bool = False
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TEMP_DIR: str = os.path.join(BASE_DIR, "temp")
    
    # ML Model Settings
    # DEVICE checks actual availability
    DEVICE: str = "cuda" if (os.environ.get("USE_GPU", "true").lower() == "true" and torch.cuda.is_available()) else "cpu"
    WHISPER_MODEL_NAME: str = "deepdml/faster-whisper-large-v3-turbo-ct2"
    
    # Use int8 on CPU to avoid float16 errors
    COMPUTE_TYPE: str = "float16" if (os.environ.get("USE_GPU", "true").lower() == "true" and torch.cuda.is_available()) else "int8"
    HF_TOKEN: Optional[str] = os.environ.get("HF_TOKEN")
    MODEL_IDLE_TIMEOUT: int = 300 # Seconds
    
    # API Limits
    MAX_FILE_SIZE: int = 500 * 1024 * 1024 # 500MB
    MAX_VIDEO_DURATION: int = 3600 # 1 hour
    
    # TTS Settings
    DEFAULT_TTS: str = "Kokoro TTS"
    KOKORO_MODEL_ID: str = "hexgrad/Kokoro-82M"
    
    # Translation Cache
    TRANSLATION_CACHE_ENABLED: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.TEMP_DIR, exist_ok=True)