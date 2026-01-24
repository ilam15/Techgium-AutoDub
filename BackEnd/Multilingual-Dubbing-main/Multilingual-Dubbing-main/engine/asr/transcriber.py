import time
from core.models import model_manager
from core.context import RequestContext
from core.exceptions import ASRError, DiarizationError
from core.logger import logger
from concurrent.futures import ThreadPoolExecutor

class ASRTranscriber:
    def __init__(self, context: RequestContext):
        self.context = context

    def process_file(self, audio_data, source_lang: str):
        from utils import language_dict
        st = time.time()
        
        # Normalize language to ISO code
        whisper_lang = None
        if source_lang != "Automatic":
            # Search for the lang_code in language_dict
            if source_lang in language_dict:
                whisper_lang = language_dict[source_lang]["lang_code"]
            else:
                # Fallback: check if it's already a code
                # (Whisper codes are usually 2 chars)
                whisper_lang = source_lang if len(source_lang) <= 3 else None

        with ThreadPoolExecutor(max_workers=2) as executor:
            # 1. ASR Pass
            def run_whisper():
                model = model_manager.get_whisper()
                logger.info(f"Starting Whisper transcription [Lang: {whisper_lang or 'auto'}]")
                return model.transcribe(audio_data, word_timestamps=True, language=whisper_lang)

            # 2. Diarization Pass
            def run_diarization():
                try:
                    analyzer = model_manager.get_diarization()
                    return analyzer.analyze_audio(audio_data)
                except Exception as e:
                    logger.warning(f"Diarization failed: {e}. Falling back to single speaker.")
                    return [], {}

            whisper_future = executor.submit(run_whisper)
            diar_future = executor.submit(run_diarization)

            try:
                segments, info = whisper_future.result()
                speaker_turns, speaker_genders = diar_future.result()
            except Exception as e:
                raise ASRError(f"Speech transcription pipeline failed: {e}")

        self.context.add_metric("asr_diarization", time.time() - st)
        return segments, info, speaker_turns, speaker_genders
