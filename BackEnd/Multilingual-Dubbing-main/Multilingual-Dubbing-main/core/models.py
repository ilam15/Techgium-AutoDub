import torch
import gc
import time
import threading
from faster_whisper import WhisperModel
from core.config import settings
from core.logger import logger
from speaker_detection import SpeakerAnalyzer

class ModelManager:
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._models = {}
        self._last_used = {}
        self._counts = {}
        
        # Start reaper thread
        threading.Thread(target=self._cleanup_loop, daemon=True).start()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def get_whisper(self) -> WhisperModel:
        with self._lock:
            self._last_used["whisper"] = time.time()
            if "whisper" not in self._models:
                try:
                    logger.info(f"Initializing Whisper Model [{settings.DEVICE}]: {settings.WHISPER_MODEL_NAME}")
                    self._models["whisper"] = WhisperModel(
                        settings.WHISPER_MODEL_NAME, 
                        device=settings.DEVICE, 
                        compute_type=settings.COMPUTE_TYPE
                    )
                except Exception as e:
                    if "CUDA" in str(e) and settings.DEVICE == "cuda":
                        logger.warning(f"CUDA initialization failed ({e}). Falling back to CPU mode.")
                        self._models["whisper"] = WhisperModel(
                            settings.WHISPER_MODEL_NAME, 
                            device="cpu", 
                            compute_type="int8"
                        )
                    else:
                        raise e
            return self._models["whisper"]

    def get_diarization(self, hf_token: str = None) -> SpeakerAnalyzer:
        with self._lock:
            self._last_used["diarization"] = time.time()
            if "diarization" not in self._models:
                logger.info("Initializing Speaker Analyzer...")
                self._models["diarization"] = SpeakerAnalyzer(hf_token=hf_token or settings.HF_TOKEN)
            return self._models["diarization"]

    def get_translator(self):
        from transformers import pipeline
        with self._lock:
            self._last_used["translator"] = time.time()
            if "translator" not in self._models:
                device_idx = 0 if settings.DEVICE == "cuda" and torch.cuda.is_available() else -1
                try:
                    logger.info(f"Initializing NLLB-200 Translation Model [Device:{device_idx}]...")
                    self._models["translator"] = pipeline(
                        "translation",
                        model="facebook/nllb-200-distilled-600M",
                        device=device_idx
                    )
                except Exception as e:
                    if "CUDA" in str(e) and device_idx == 0:
                        logger.warning(f"Translation GPU init failed ({e}). Falling back to CPU mode.")
                        self._models["translator"] = pipeline(
                            "translation",
                            model="facebook/nllb-200-distilled-600M",
                            device=-1
                        )
                    else:
                        raise e
            return self._models["translator"]

    def _cleanup_loop(self):
        while True:
            time.sleep(30)
            now = time.time()
            with self._lock:
                to_remove = []
                for name, last_time in self._last_used.items():
                    if now - last_time > settings.MODEL_IDLE_TIMEOUT:
                        to_remove.append(name)
                
                for name in to_remove:
                    logger.info(f"Unloading idle model: {name}")
                    del self._models[name]
                    del self._last_used[name]
                    
                if to_remove:
                    self._gpu_cleanup()

    def _gpu_cleanup(self):
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

model_manager = ModelManager()
