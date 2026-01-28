import os
import time
from typing import Dict, Any, Optional
from core.context import RequestContext
from core.config import settings
from core.logger import logger
from core.exceptions import AutoDubException
from engine.asr.transcriber import ASRTranscriber
from engine.audio.processor import AudioProcessor
from engine.translation.translator import TranslationService
from engine.tts.generator import TTSGenerator
from media_engine import MediaEngine

class ProductionPipeline:
    def __init__(self, trace_id: Optional[str] = None):
        self.context = RequestContext(trace_id)
        self.asr = ASRTranscriber(self.context)
        self.translator = TranslationService(self.context)
        self.tts = TTSGenerator(self.context)
        self.audio = AudioProcessor()

    def run(self, input_file: str, src_lang: str, dst_lang: str, gender: str = "Male", recover_music: bool = False) -> Dict[str, Any]:
        """
        Main end-to-end execution path with fallback mechanisms.
        """
        try:
            logger.info(f"Pipeline started for: {input_file} (Req: {self.context.request_id})")
            
            # 1. Extraction (Direct to Memory)
            audio_data = self.audio.extract_to_numpy(input_file)
            
            # 2. Parallel Background Separator (Triggered early)
            # We use the sandbox for internal stems
            bg_audio_path = None
            if recover_music:
                try:
                    _, bg_audio_path = self.audio.extract_vocal_and_bg(input_file, self.context.sandbox_path)
                except Exception as e:
                    logger.warning(f"Background separation failed: {e}. Degrading to voice-only.")

            # 3. ASR & Diarization
            segments, info, turns, speaker_genders = self.asr.process_file(audio_data, src_lang)
            from app import get_language_name
            detected_src = get_language_name(info.language) if src_lang == "Automatic" else src_lang
            
            # 4. Generate & Format Subtitles with Speaker Alignment (Architecture P2)
            from app import format_segments, generate_srt_from_sentences
            from speaker_detection import get_speaker_for_segment
            from collections import Counter
            
            sentence_ts, word_ts, full_text = format_segments(segments)
            
            # Apply high-precision word-level speaker assignment
            if turns:
                logger.info(f"Syncing {len(sentence_ts)} segments with {len(turns)} speaker turns...")
                # Assign speakers to words
                for word in word_ts:
                    word['speaker'] = get_speaker_for_segment(word['start'], word['end'], turns)
                
                # Derive sentence speaker from word majority
                for sentence in sentence_ts:
                    # Filter words belonging to this sentence
                    s_words = [w for w in word_ts if w['start'] >= sentence['start'] and w['end'] <= sentence['end']]
                    if s_words:
                        speakers = [w['speaker'] for w in s_words]
                        sentence['speaker'] = Counter(speakers).most_common(1)[0][0]
                        sentence['gender'] = speaker_genders.get(sentence['speaker'], "Male")
                    else:
                        # Fallback to direct segment lookup
                        sentence['speaker'] = get_speaker_for_segment(sentence['start'], sentence['end'], turns)
                        sentence['gender'] = speaker_genders.get(sentence['speaker'], "Male")
            else:
                logger.warning("No diarization turns found. Single speaker fallback.")
                for s in sentence_ts:
                    s['speaker'] = "SPEAKER_00"
                    s['gender'] = gender # Use user-provided gender

            # Save original as temp for translation service
            original_srt = self.context.get_path("original.srt")
            generate_srt_from_sentences(sentence_ts, srt_path=original_srt)
            
            # 5. Translation (ID-Batched)
            import pysrt
            subs = pysrt.open(original_srt)
            translated_subs, _ = self.translator.translate_batches(subs, detected_src, dst_lang)
            
            tra_srt = self.context.get_path("translated.srt")
            translated_subs.save(tra_srt, encoding='utf-8')
            
            # 6. Final Dubbing & Muxing
            # TTS Generator uses elastic synchronization
            dubb_voice = self.tts.generate_dubbed_audio(
                tra_srt, 
                dst_lang, 
                gender, 
                sandbox_dir=self.context.sandbox_path
            )
            
            # One-pass muxing
            output_video_path = f"output_{self.context.request_id}.mp4"
            if bg_audio_path:
                result_video = MediaEngine.merge_complex(input_file, dubb_voice, bg_audio_path, output_video_path)
            else:
                result_video = MediaEngine.merge_audio_video(input_file, dubb_voice, output_video_path)
            
            total_duration = time.time() - self.context.start_time
            self.context.add_metric("total_pipeline", total_duration)
            
            return {
                "request_id": self.context.request_id,
                "status": "success",
                "video_url": result_video,
                "detected_language": detected_src,
                "metrics": self.context.metrics
            }

        except AutoDubException as e:
            logger.error(f"Pipeline failed at stage [{e.stage}]: {e}")
            return {"status": "error", "error": str(e), "stage": e.stage}
        except Exception as e:
            logger.error(f"Uncaught pipeline error: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": "Internal System Error"}
        # finally: Sandbox is cleaned up by RequestContext context manager
