import time
from core.models import model_manager
from core.context import RequestContext
from core.exceptions import ASRError, DiarizationError
from core.logger import logger

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

        # Optimization: Sequential execution to prevent CPU thrashing
        # Running large-v3 and pyannote simultaneously on CPU is detrimental to performance.
        
        # 1. ASR Pass (CPU Intensive)
        try:
            model = model_manager.get_whisper()
            logger.info(f"Starting Whisper transcription [Lang: {whisper_lang or 'auto'}]")
            # Beam size 1 (Greedy) is significantly faster for similar accuracy on clear audio
            segments, info = model.transcribe(
                audio_data, 
                beam_size=1, 
                best_of=1,
                temperature=0,
                word_timestamps=True, 
                language=whisper_lang
            )
        except Exception as e:
            raise ASRError(f"Whisper transcription failed: {e}")

        # 2. Diarization Pass (RAM/CPU Intensive)
        speaker_turns = []
        speaker_genders = {}
        
        # Optimization: Skip diarization for short audio (< 60s) if implied by user constraints,
        # otherwise run it sequentially.
        try:
            analyzer = model_manager.get_diarization()
            if analyzer:
                speaker_turns, speaker_genders = analyzer.analyze_audio(audio_data)
            else:
                logger.warning("Diarization model not loaded. Skipping.")
        except Exception as e:
            logger.warning(f"Diarization failed: {e}. Falling back to single speaker.")

        self.context.add_metric("asr_diarization", time.time() - st)
        return segments, info, speaker_turns, speaker_genders
