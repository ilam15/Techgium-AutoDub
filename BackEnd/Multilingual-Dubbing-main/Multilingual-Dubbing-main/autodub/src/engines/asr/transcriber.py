import time
from src.app import model_manager
from src.core.context import RequestContext
from src.core.exceptions import ASRError, DiarizationError
from src.core.logger import logger
from concurrent.futures import ThreadPoolExecutor

class ASRTranscriber:
    def __init__(self, context: RequestContext):
        self.context = context

    def process_file(self, audio_data, source_lang: str):
        from src.utils.utils import language_dict
        import numpy as np
        st = time.time()
        
        # Normalize language to ISO code
        whisper_lang = None
        if source_lang != "Automatic":
            # Search for the lang_code in language_dict
            if source_lang in language_dict:
                whisper_lang = language_dict[source_lang]["lang_code"]
            else:
                whisper_lang = source_lang if len(source_lang) <= 3 else None

        with ThreadPoolExecutor(max_workers=2) as executor:
            # 1. ASR Pass
            def run_whisper():
                model = model_manager.get_whisper()
                from types import SimpleNamespace
                
                # CRITICAL ARCHITECTURE CHANGE: Granular Audio Language Probing
                # To defeat English caption bias and rapid code-switching, we:
                # 1. Use small 10s windows for transcription
                # 2. For EVERY segment found, we perform a dedicated audio-only 
                #    language detection pass on that specific segment's audio.
                
                chunk_duration = 10 # seconds (Increased frequency of resets)
                chunk_samples = chunk_duration * 16000
                total_samples = len(audio_data)
                
                segments_list = []
                global_info_list = []
                
                logger.info(f"🌍 ASR Engine: Ultra-Granular Multilingual Transcription ({chunk_duration}s windows + Segment Probing)")
                logger.info("   Each segment will undergo a dedicated audio-only language verification pass.")
                
                for start_sample in range(0, total_samples, chunk_samples):
                    # HEARTBEAT: Keep the model alive during long CPU runs
                    model_manager.heartbeat("whisper")
                    
                    end_sample = min(start_sample + chunk_samples, total_samples)
                    chunk = audio_data[start_sample:end_sample]
                    
                    if len(chunk) < 8000: # Less than 0.5s, skip
                        continue
                        
                    offset = start_sample / 16000
                    
                    # 1. Transcribe the chunk
                    chunk_segments_iter, chunk_info = model.transcribe(
                        chunk,
                        vad_filter=True,
                        language=None if source_lang == "Automatic" else whisper_lang,
                        task="transcribe",
                        beam_size=5,
                        word_timestamps=True
                    )
                    
                    global_info_list.append(chunk_info)
                    
                    # 2. Process segments and PROBE each one's audio for language
                    for seg in chunk_segments_iter:
                        seg_start = seg.start + offset
                        seg_end = seg.end + offset
                        
                        # Calculate exact audio indices for this segment within the current chunk
                        audio_start = int(seg.start * 16000)
                        audio_end = int(seg.end * 16000)
                        segment_audio = chunk[audio_start:audio_end]
                        
                        # Skip probe for very short segments (< 0.5s) as detection is unreliable
                        if len(segment_audio) < 8000:
                            actual_lang = chunk_info.language
                            actual_prob = chunk_info.language_probability
                        else:
                            # DEDICATED AUDIO PROBE: Detect language of just this segment's audio
                            # Using a lightweight transcribe call to get language info only
                            _, probe_info = model.transcribe(
                                segment_audio,
                                language=None,
                                beam_size=1  # Fast detection
                            )
                            actual_lang = probe_info.language
                            actual_prob = probe_info.language_probability
                        
                        logger.info(
                            f"🎤 Segment Probe [{seg_start:5.2f}s]: Audio-Detected='{actual_lang}' "
                            f"(conf={actual_prob:.2f}) | Text='{seg.text[:30]}...'"
                        )
                        
                        wrapper = SimpleNamespace(
                            start=seg_start,
                            end=seg_end,
                            text=seg.text,
                            words=seg.words,
                            segment_language=actual_lang,
                            segment_language_prob=actual_prob,
                            whisper_hint=chunk_info.language,
                            whisper_hint_prob=chunk_info.language_probability
                        )
                        segments_list.append(wrapper)

                # Summary logic
                if global_info_list:
                    from collections import Counter
                    most_common_lang = Counter([i.language for i in global_info_list]).most_common(1)[0][0]
                    global_info = next(i for i in global_info_list if i.language == most_common_lang)
                else:
                    global_info = SimpleNamespace(language="en", language_probability=0.0)
                
                logger.info(f"ASR complete: {len(segments_list)} segments probed. Dominant: {global_info.language}")
                return segments_list, global_info

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
