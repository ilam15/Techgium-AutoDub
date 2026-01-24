import os
import subprocess
from core.exceptions import MediaError
from core.logger import logger
from media_engine import MediaEngine

class AudioProcessor:
    @staticmethod
    def extract_vocal_and_bg(input_path: str, output_dir: str):
        """Wraps separation logic with error handling"""
        from app import separate_audio
        try:
            logger.info(f"Separating audio for: {input_path}")
            vocal, background = separate_audio(input_path)
            if not vocal or not background:
                raise MediaError("Audio separation returned empty paths")
            return vocal, background
        except Exception as e:
            logger.error(f"Separation failed: {e}")
            return None, None # Force graceful degradation

    @staticmethod
    def extract_to_numpy(input_path: str):
        try:
            return MediaEngine.extract_audio_numpy(input_path)
        except Exception as e:
            raise MediaError(f"Failed to extract audio to numpy: {e}")
