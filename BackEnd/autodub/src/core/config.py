import os
from pydantic_settings import BaseSettings
from typing import Optional

import torch

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AutoDub Engine"
    DEBUG: bool = False
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMP_DIR: str = os.path.join(BASE_DIR, "temp")
    
    # ML Model Settings
    # DEVICE checks actual availability
    DEVICE: str = "cuda" if (os.environ.get("USE_GPU", "true").lower() == "true" and torch.cuda.is_available()) else "cpu"
    
    # Point 3: Whisper Optimization & Configuration
    # Use 'small' for better accuracy on CPU while maintaining reasonable speed
    WHISPER_MODEL_SIZE: str = "small" 
    @property
    def WHISPER_MODEL_NAME(self) -> str:
        # Map size to specific model names if needed, or use directly
        if self.WHISPER_MODEL_SIZE == "large-v3":
            return "deepdml/faster-whisper-large-v3-turbo-ct2"
        return self.WHISPER_MODEL_SIZE
    
    # Feature Flags
    ENABLE_GENDER_DETECTION: bool = True

    # Use int8 on CPU to avoid float16 errors
    COMPUTE_TYPE: str = "float16" if (os.environ.get("USE_GPU", "true").lower() == "true" and torch.cuda.is_available()) else "int8"
    HF_TOKEN: Optional[str] = os.environ.get("HF_TOKEN")
    MODEL_IDLE_TIMEOUT: int = 1200 # 20 minutes (Prevent unloading during long CPU runs)
    
    # API Limits
    MAX_FILE_SIZE: int = 500 * 1024 * 1024 # 500MB
    MAX_VIDEO_DURATION: int = 3600 # 1 hour
    
    # Point 7 & 10: TTS & Audio Settings
    # Increased speed range to handle fast speakers and prevent overlaps
    TTS_SPEED_CAP: float = 1.7      # Max speedup ratio
    TTS_SLOW_DOWN_CAP: float = 0.70 # Min speed ratio
    
    # Point 6: Probing Settings
    PROBE_WINDOW_SHORT: int = 5     # For duration < 60s
    PROBE_WINDOW_LONG: int = 10     # For duration >= 60s
    
    # TTS Settings
    DEFAULT_TTS: str = "Kokoro TTS"
    KOKORO_MODEL_ID: str = "hexgrad/Kokoro-82M"
    
    # Translation Cache
    TRANSLATION_CACHE_ENABLED: bool = True

    # Celery Settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = "../.env" # Look in parent directory (because user kept it outside 'autodub')

settings = Settings()

# Ensure directories exist
os.makedirs(settings.TEMP_DIR, exist_ok=True)
