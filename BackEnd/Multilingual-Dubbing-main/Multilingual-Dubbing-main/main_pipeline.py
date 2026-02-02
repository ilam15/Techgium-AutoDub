import os
import time
import re
import urllib.request
from typing import Dict, Any, Optional
from collections import Counter
from pydub import AudioSegment
import numpy as np
import fasttext

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

    def run(self, input_file: str, src_lang: str, dst_lang: str, gender: str = "Male", recover_music: bool = False, user_known_languages: list = []) -> Dict[str, Any]:
        """
        Main end-to-end execution path with selective translation and multilingual support.
        """
        try:
            logger.info(f"Pipeline started for: {input_file} (Req: {self.context.request_id})")
            logger.info(f"Known languages: {user_known_languages}, Target: {dst_lang}")
            
            # 1. Extraction (Direct to Memory)
            audio_data = self.audio.extract_to_numpy(input_file)
            
            # 2. Parallel Background Separator
            bg_audio_path = None
            vocal_audio_path = None
            if recover_music:
                try:
                    vocal_audio_path, bg_audio_path = self.audio.extract_vocal_and_bg(input_file, self.context.sandbox_path)
                except Exception as e:
                    logger.warning(f"Background separation failed: {e}. Degrading to voice-only.")

            # 3. ASR & Diarization (Multi-language aware)
            segments, info, turns, speaker_genders = self.asr.process_file(audio_data, src_lang)
            from app import get_language_name, format_segments, generate_srt_from_sentences
            from speaker_detection import get_speaker_for_segment
            
            # Normalize language names
            src_lang = src_lang.title() if src_lang != "Automatic" else src_lang
            dst_lang = dst_lang.title()
            
            detected_src = get_language_name(info.language) if src_lang == "Automatic" else src_lang
            logger.info(f"Pipeline Context: Source={detected_src} (Detected: {info.language}), Target={dst_lang}")
            
            # 4. Alignment & Language Decision Engine
            sentence_ts, word_ts, full_text = format_segments(segments)
            
            # DECISION ENGINE PREP
            from utils import language_dict
            known_codes = []
            for l in user_known_languages:
                # normalize to code
                l_lower = l.lower()
                matched = False
                for k, v in language_dict.items():
                    if k.lower() == l_lower:
                        known_codes.append(v["lang_code"].lower())
                        matched = True
                        break
                if not matched: known_codes.append(l_lower)
            
            target_code = ""
            for k, v in language_dict.items():
                if k.lower() == dst_lang.lower():
                    target_code = v["lang_code"].lower()
                    break
            if not target_code: target_code = dst_lang.lower()
            
            logger.info(f"DUB DECISION: Target={target_code} ({dst_lang}), Known={known_codes}")

            # Enrich sentence_ts with speaker and language info
            import langid
            # Fast-track common Indian languages, English, and the Target language
            prioritized_codes = ['hi', 'te', 'en', 'mr', 'ta', 'kn', 'ml']
            if target_code and target_code not in prioritized_codes:
                prioritized_codes.append(target_code)
            langid.set_languages(prioritized_codes) 

            for sentence in sentence_ts:
                # Default translated_text to original in case Translation Engine is skipped or fails
                sentence['translated_text'] = sentence['text']
                
                # Speaker Assignment
                if turns:
                    s_words = [w for w in word_ts if w['start'] >= sentence['start'] and w['end'] <= sentence['end']]
                    if s_words:
                        speakers = [w['speaker'] for w in s_words if 'speaker' in w]
                        if speakers:
                            sentence['speaker'] = Counter(speakers).most_common(1)[0][0]
                        else:
                            sentence['speaker'] = get_speaker_for_segment(sentence['start'], sentence['end'], turns)
                    else:
                        sentence['speaker'] = get_speaker_for_segment(sentence['start'], sentence['end'], turns)
                else:
                    sentence['speaker'] = "SPEAKER_00"
                
            # 4. TEXT-BASED LANGUAGE IDENTIFICATION (Correct Architecture)
            # Use fastText for accurate multilingual text-based LID
            fasttext_model_dir = os.path.join(settings.BASE_DIR, "engine", "lid")
            os.makedirs(fasttext_model_dir, exist_ok=True)
            fasttext_model_path = os.path.join(fasttext_model_dir, "lid.176.bin")
            
            if not os.path.exists(fasttext_model_path):
                logger.info("Initializing fastText download at shared location...")
                try:
                    urllib.request.urlretrieve(
                        "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin",
                        fasttext_model_path
                    )
                    logger.info("Shared fastText model downloaded successfully")
                except Exception as e:
                    logger.warning(f"Failed to download fastText model: {e}. Falling back to langid.")
                    fasttext_model_path = None
            
            # Load fastText model
            fasttext_model = None
            if fasttext_model_path and os.path.exists(fasttext_model_path):
                try:
                    fasttext_model = fasttext.load_model(fasttext_model_path)
                    logger.info("✅ fastText LID model ready")
                except Exception as e:
                    logger.warning(f"Failed to load fastText model: {e}. Falling back to langid.")
            
            # Fallback to langid if fastText unavailable
            if not fasttext_model:
                import langid
                langid.set_languages([target_code, 'en', 'hi', 'te', 'ta', 'kn', 'ml', 'mr', 'gu', 'bn', 'pa', 'de', 'fr', 'es', 'pt', 'it', 'ru', 'ja', 'ko', 'zh', 'ar'])
                logger.info("Using langid as fallback for language identification")
            
            # Process each segment with HYBRID per-segment language detection
            for sentence in sentence_ts:
                sentence['speaker'] = get_speaker_for_segment(sentence['start'], sentence['end'], turns) if turns else "SPEAKER_00"
                sentence['gender'] = speaker_genders.get(sentence['speaker'], gender)
                
                # CRITICAL FIX: HYBRID PER-SEGMENT LANGUAGE DETECTION
                # Strategy: Combine Whisper's per-segment language with text-based validation
                text = sentence['text'].strip()
                
                # Step 1: Get Whisper's per-segment language hint (NOT global!)
                # Find the corresponding segment from ASR output
                whisper_segment_lang = None
                whisper_segment_prob = None
                for seg in segments:
                    if abs(seg.start - sentence['start']) < 0.1:  # Match by timestamp
                        whisper_segment_lang = getattr(seg, 'segment_language', None)
                        whisper_segment_prob = getattr(seg, 'segment_language_prob', None)
                        break
                
                # Fallback to global hint only if per-segment not available
                if not whisper_segment_lang:
                    whisper_segment_lang = info.language
                    whisper_segment_prob = info.language_probability
                
                # DIAGNOSTIC: Log Whisper's audio-based detection
                logger.info(
                    f"🎤 Audio Probe - Seg[{sentence['id']:03d}]: "
                    f"lang={whisper_segment_lang} (prob={whisper_segment_prob:.2f}) | "
                    f"text='{text[:150]}'"
                )
                
                # Step 2: Text-based validation (fastText/langid)
                # ENHANCED: More aggressive detection for code-switching scenarios
                if len(text) < 3:
                    # Too short for reliable text-based detection, trust Whisper's audio-based detection
                    detected_lang = whisper_segment_lang
                    confidence = 0.7
                    method = "audio_probe_short"
                    logger.debug(f"Seg {sentence['id']}: Text too short, using audio probe: {whisper_segment_lang}")
                else:
                    try:
                        if fasttext_model:
                            # Use fastText for text-based validation
                            predictions = fasttext_model.predict(text.replace('\n', ' '), k=1)
                            text_detected_lang = predictions[0][0].replace('__label__', '')
                            text_confidence = float(predictions[1][0])
                            
                            # Normalize fastText 3-letter codes to 2-letter
                            if len(text_detected_lang) > 2:
                                lang_map = {'eng': 'en', 'hin': 'hi', 'tel': 'te', 'tam': 'ta', 'kan': 'kn', 
                                           'mal': 'ml', 'mar': 'mr', 'guj': 'gu', 'ben': 'bn', 'pan': 'pa',
                                           'deu': 'de', 'fra': 'fr', 'spa': 'es', 'por': 'pt', 'ita': 'it',
                                           'rus': 'ru', 'jpn': 'ja', 'kor': 'ko', 'zho': 'zh', 'ara': 'ar'}
                                text_detected_lang = lang_map.get(text_detected_lang, text_detected_lang[:2])
                        else:
                            # Fallback to langid
                            text_detected_lang, text_confidence = langid.classify(text)
                        
                        # DIAGNOSTIC: Log text-based detection
                        logger.info(
                            f"📝 Text-Based Detection - Seg[{sentence['id']:03d}]: "
                            f"lang={text_detected_lang} (conf={text_confidence:.2f})"
                        )
                        
                        # ENHANCED HYBRID DECISION for CODE-SWITCHING
                        # Lower threshold for text-based override to catch language switches
                        # This is critical when the same speaker switches languages
                        
                        if text_detected_lang != whisper_segment_lang:
                            # Text and audio disagree - need to decide which to trust
                            
                            # CRITICAL FIX for "English Caption Bias" & "AI Video Detection":
                            # We now trust the Granular Audio Probe (whisper_segment_lang) 
                            # if it detects a NON-ENGLISH language, because text-based LID 
                            # is often biased by English captions/subtitles.
                            
                            # If probe finds a specialized language, trust it over English text.
                            if whisper_segment_lang != 'en' and (text_detected_lang == 'en' or text_confidence < 0.7):
                                detected_lang = whisper_segment_lang
                                confidence = whisper_segment_prob or 0.8
                                method = "audio_probe_priority"
                                logger.info(
                                    f"Seg {sentence['id']}: Trusting Granular Audio Probe ({whisper_segment_lang}) "
                                    f"above Text ({text_detected_lang} {text_confidence:.2f}) due to caption bias."
                                )
                            
                            # STRATEGY 1: If text confidence is very high (>0.85), it might be legit switch
                            elif text_confidence > 0.85:
                                detected_lang = text_detected_lang
                                confidence = text_confidence
                                method = "text_override"
                                logger.info(
                                    f"Seg {sentence['id']}: High-confidence Text Override: {text_detected_lang} ({text_confidence:.2f})"
                                )
                            
                            # STRATEGY 2: Common Fallback
                            else:
                                detected_lang = whisper_segment_lang
                                confidence = whisper_segment_prob or 0.5
                                method = "whisper_audio_fallback"
                                logger.debug(f"Seg {sentence['id']}: Defaulting to Audio Probe: {whisper_segment_lang}")
                        else:
                            # Agreement
                            detected_lang = text_detected_lang
                            confidence = max(text_confidence, 0.8)
                            method = "whisper_confirmed"
                            logger.debug(f"Seg {sentence['id']}: Both probe and text agree: {detected_lang}")
                    
                    except Exception as e:
                        logger.warning(f"Text-based LID failed for segment {sentence['id']}: {e}")
                        detected_lang = whisper_segment_lang
                        confidence = 0.6
                        method = "whisper_fallback"
                
                sentence['lang'] = detected_lang
                sentence['lid_confidence'] = confidence
                sentence['lid_method'] = method
                
                # CRITICAL FIX: STRICT TRANSLATION DECISION LOGIC
                # Rule: Translate ANYTHING that is NOT the target language
                # No exceptions, no global bias, no assumptions
                
                detected_lang_code = (detected_lang or "unknown").lower()
                
                # Check for noise/silence (very strict check to avoid false positives)
                is_noise = (
                    not text.strip() or 
                    len(text.strip()) < 2 or
                    not bool(re.search(r'[a-zA-Z\u0900-\u0D7F\u0600-\u06FF\u4E00-\u9FFF]', text))
                )
                
                if is_noise:
                    action = "KEEP"
                    reason = "Non-speech/Noise"
                elif detected_lang_code == target_code.lower():
                    action = "KEEP"
                    reason = f"Already in target language ({detected_lang_code})"
                else:
                    # ANY non-target language MUST be translated
                    action = "TRANSLATE"
                    reason = f"Source: {detected_lang_code} → Target: {target_code}"
                
                sentence['action'] = action
                sentence['reason'] = reason  # Store reason for later use
                
                # COMPREHENSIVE LOGGING for debugging multilingual videos
                logger.info(
                    f"SEG[{sentence['id']:03d}] [{sentence['start']:6.1f}s] "
                    f"text='{text[:40]:40s}' | "
                    f"lang={detected_lang_code:5s} (method={method:15s}, conf={confidence:.2f}) | "
                    f"action={action:9s} | {reason}"
                )

            to_translate = [s for s in sentence_ts if s['action'] == "TRANSLATE"]
            
            # ═══════════════════════════════════════════════════════════════════
            # MULTI-LANGUAGE DETECTION & STATISTICS
            # ═══════════════════════════════════════════════════════════════════
            
            # Collect all detected languages (excluding noise)
            from app import get_language_name
            language_stats = {}
            total_video_duration = max([s['end'] for s in sentence_ts]) if sentence_ts else 0
            
            for sentence in sentence_ts:
                lang_code = sentence.get('lang', 'unknown')
                
                # Skip noise/silence segments for language statistics
                if sentence['action'] == "KEEP" and "noise" in sentence.get('reason', '').lower(): # Changed from action to reason
                    continue
                
                if lang_code not in language_stats:
                    language_stats[lang_code] = {
                        'code': lang_code,
                        'name': get_language_name(lang_code) if lang_code != 'unknown' else 'Unknown',
                        'segment_count': 0,
                        'total_duration': 0.0,
                        'segments': []
                    }
                
                duration = sentence['end'] - sentence['start']
                language_stats[lang_code]['segment_count'] += 1
                language_stats[lang_code]['total_duration'] += duration
                language_stats[lang_code]['segments'].append({
                    'id': sentence['id'],
                    'start': sentence['start'],
                    'end': sentence['end'],
                    'text': sentence['text'][:50],  # First 50 chars
                    'confidence': sentence.get('lid_confidence', 0.0),
                    'method': sentence.get('lid_method', 'unknown')
                })
            
            # Calculate percentages and sort by duration
            for lang_code, stats in language_stats.items():
                stats['percentage'] = (stats['total_duration'] / total_video_duration * 100) if total_video_duration > 0 else 0
            
            # Sort languages by duration (most spoken first)
            sorted_languages = sorted(
                language_stats.items(), 
                key=lambda x: x[1]['total_duration'], 
                reverse=True
            )
            
            # Create detected languages list for response
            detected_languages = []
            for lang_code, stats in sorted_languages:
                detected_languages.append({
                    'language_code': stats['code'],
                    'language_name': stats['name'],
                    'segment_count': stats['segment_count'],
                    'total_duration_seconds': round(stats['total_duration'], 2),
                    'percentage_of_video': round(stats['percentage'], 2),
                    'sample_segments': stats['segments'][:3]  # First 3 segments as samples
                })
            
            # ═══════════════════════════════════════════════════════════════════
            # COMPREHENSIVE LOGGING
            # ═══════════════════════════════════════════════════════════════════
            
            logger.info("=" * 80)
            logger.info("MULTI-LANGUAGE DETECTION SUMMARY")
            logger.info("=" * 80)
            logger.info(f"Total Video Duration: {total_video_duration:.2f}s")
            logger.info(f"Total Segments: {len(sentence_ts)}")
            logger.info(f"Languages Detected: {len(detected_languages)}")
            logger.info("")
            
            for i, lang_info in enumerate(detected_languages, 1):
                logger.info(
                    f"{i}. {lang_info['language_name']:15s} ({lang_info['language_code']:5s}) | "
                    f"Segments: {lang_info['segment_count']:3d} | "
                    f"Duration: {lang_info['total_duration_seconds']:6.2f}s | "
                    f"Coverage: {lang_info['percentage_of_video']:5.2f}%"
                )
            
            logger.info("")
            logger.info(f"Translation Summary: TRANSLATE={len(to_translate)}, KEEP={len(sentence_ts)-len(to_translate)}")
            logger.info("=" * 80)
            
            # Legacy language distribution for backward compatibility
            all_langs = Counter([s.get('lang', 'unknown') for s in sentence_ts])
            logger.debug(f"Language Distribution (raw): {dict(all_langs)}")
            
            # Key Engineering Insight for logs
            logger.info("ENGINEERING INSIGHT: This system overcomes Whisper’s dominant-language bias by introducing a hybrid ASR + text-based language identification pipeline, enabling accurate segment-level multilingual dubbing without audio loss.")

            if to_translate:
                from collections import defaultdict
                # Group segments by their detected language for correct multilingual translation
                lang_groups = defaultdict(list)
                for s in to_translate:
                    # Robust grouping: if lang is None (LID failed), default to 'en' for translation resolution
                    l_code = s.get('lang') or 'en'
                    lang_groups[l_code].append(s)
                
                logger.info(f"Targeting translation for {len(to_translate)} segments across {len(lang_groups)} languages...")
                
                for lang_code, group in lang_groups.items():
                    # Safely handle the string mapping for detected groups
                    src_name_for_group = get_language_name(lang_code.lower())
                    logger.info(f"Translating group: {src_name_for_group} ({lang_code}) -> {dst_lang} [{len(group)} segments]")
                    
                    # Create temp SRT for this language group
                    temp_srt = self.context.get_path(f"to_translate_{lang_code}.srt")
                    from app import generate_srt_from_sentences
                    generate_srt_from_sentences(group, srt_path=temp_srt)
                    
                    import pysrt
                    subs = pysrt.open(temp_srt)
                    translated_subs, _ = self.translator.translate_batches(subs, src_name_for_group, dst_lang)
                    
                    for i, s in enumerate(group):
                        raw_text = translated_subs[i].text
                        # Clean up any tags that might have leaked through
                        match = re.search(r'(<S:.*?\|G:.*?>)?(.*)', raw_text, re.DOTALL)
                        s['translated_text'] = (match.group(2) or raw_text).strip()
                        
                        # Log translation sample for debug
                        if i == 0 or i == len(group) - 1:
                            logger.info(f"TR [{src_name_for_group}]: '{s['text'][:30]}...' -> '{s['translated_text'][:30]}...'")
            else:
                logger.info("Decision Engine: All segments kept in original language.")

            # 6. Audio Timeline Reconstruction (Selective Dubbing Fix)
            # STRATEGY: Start with ORIGINAL VOCAL as base and surgical-replace only TRANSLATED parts.
            # This ensures anything Whisper misses or any KEEP segments are 100% preserved.
            logger.info(f"Reconstructing audio timeline (Selective: {len(to_translate)} translations, {len(sentence_ts)-len(to_translate)} kept)...")
            
            def process_segment_audio(s):
                start_s = s['start']
                end_s = s['end']
                start_ms = int(start_s * 1000)
                original_duration_ms = int((end_s - start_s) * 1000)
                
                # We save each processed chunk as a temporary file in the sandbox
                chunk_path = self.context.get_path(f"seg_{s['id']}.wav")
                
                if s['action'] == "KEEP":
                    # For KEEP, we just return the original timing; base audio already has it.
                    return (start_ms, original_duration_ms, None, "KEEP")
                else:
                    # TRANSLATE branch
                    try:
                        from app import your_tts
                        logger.info(f"Dubbing [{s['id']}] at {start_s:.1f}s -> {dst_lang}")
                        tts_file = your_tts(
                            s['translated_text'], 
                            dst_lang, 
                            s['gender'], 
                            chunk_path, 
                            actual_duration=end_s - start_s
                        )
                        if tts_file and os.path.exists(tts_file):
                            return (start_ms, original_duration_ms, tts_file, "TRANSLATE")
                        else:
                            return (start_ms, original_duration_ms, None, "KEEP")
                    except Exception as e:
                        logger.error(f"TTS Error for {s['id']}: {e}")
                        return (start_ms, original_duration_ms, None, "KEEP")

            # Parallel processing of all chunks
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=5) as executor:
                final_chunks = list(executor.map(process_segment_audio, sentence_ts))
            
            # Reconstruction via Pydub
            from pydub import AudioSegment
            # Use original vocal or original audio as the base
            if vocal_audio_path and os.path.exists(vocal_audio_path):
                final_vocal = AudioSegment.from_file(vocal_audio_path).set_frame_rate(44100)
            else:
                raw_data = (audio_data * 32767).astype(np.int16).tobytes()
                final_vocal = AudioSegment(data=raw_data, sample_width=2, frame_rate=16000, channels=1).set_frame_rate(44100)
            
            for start_ms, original_dur, chunk_path, action in final_chunks:
                if action == "TRANSLATE" and chunk_path and os.path.exists(chunk_path):
                    chunk = AudioSegment.from_file(chunk_path).set_frame_rate(44100)
                    
                    # 1. Surgical Silence: Clear EXACTLY the original segment window
                    # This prevents original voice leaking around the new TTS
                    silence = AudioSegment.silent(duration=original_dur, frame_rate=44100)
                    final_vocal = final_vocal.overlay(silence, position=start_ms, gain_during_overlay=-120)
                    
                    # 2. Overlay the new TTS (which has been elastic-speed-matched to original_dur)
                    final_vocal = final_vocal.overlay(chunk, position=start_ms)

            dubbed_vocal_path = self.context.get_path("dubbed_vocal.wav")
            final_vocal.export(dubbed_vocal_path, format="wav")
            
            # 7. Final Video Merge
            output_video_path = f"output_{self.context.request_id}.mp4"
            if bg_audio_path and os.path.exists(bg_audio_path):
                # Complex merge with ducking
                result_video = MediaEngine.merge_complex(input_file, dubbed_vocal_path, bg_audio_path, output_video_path)
            else:
                # Direct merge
                result_video = MediaEngine.merge_audio_video(input_file, dubbed_vocal_path, output_video_path)
            
            total_duration = time.time() - self.context.start_time
            self.context.add_metric("total_pipeline", total_duration)
            
            return {
                "request_id": self.context.request_id,
                "status": "success",
                "video_url": result_video,
                # Multi-language detection results
                "detected_languages": detected_languages,  # Array of all detected languages with stats
                "primary_language": detected_languages[0]['language_name'] if detected_languages else detected_src,
                "language_count": len(detected_languages),
                # Legacy field for backward compatibility
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
