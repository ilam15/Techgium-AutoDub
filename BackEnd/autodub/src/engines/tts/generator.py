import time
import os
from src.core.context import RequestContext
from src.core.exceptions import TTSError
from src.core.logger import logger
from src.engines.tts.dubbing_engine import dubbing

class TTSGenerator:
    def __init__(self, context: RequestContext):
        self.context = context

    def generate_dubbed_audio(self, srt_path, lang, gender, tts_model="Kokoro TTS", voice="af_heart", sandbox_dir=None):
        st = time.time()
        try:
            # We use our sandbox for the segments
            dub_audio_path = dubbing(
                srt_path, 
                lang, 
                gender, 
                tts_model=tts_model, 
                voice_name=voice, 
                sandbox_dir=sandbox_dir or self.context.sandbox_path
            )
            self.context.add_metric("tts_generation", time.time() - st)
            return dub_audio_path
        except Exception as e:
            logger.error(f"TTS Engine failed: {e}")
            raise TTSError(f"TTS generation failed: {e}")
