import os
import shutil
import time
import json
import uuid
import soundfile as sf
import torch
import numpy as np
import redis
from typing import List, Dict, Any
from celery import group, chain, chord
from src.core.celery_app import celery_app
from src.core.logger import logger
from src.core.context import RequestContext
from src.core.config import settings

# Redis connection for bookkeeping
REDIS_CLIENT = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

# ==============================================================================
# 3-TERMINAL PARALLEL STREAMING PIPELINE
# ==============================================================================

def trigger_autodub_pipeline(input_file, src_lang, dst_lang, gender, recover_bg, user_known_languages, trace_id):
    """
    Kicks off the 3-terminal streaming pipeline.
    """
    logger.info(f"[{trace_id}] Launching 3-Terminal Pipeline...")
    
    # Store initial data in Redis for terminal access
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "input_file", input_file)
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "original_video_path", input_file)
    REDIS_CLIENT.expire(f"pipeline:{trace_id}", 3600)
    
    # Start Terminal 1: Separation & Segmentation
    result = separation_task.apply_async(
        args=[input_file, src_lang, dst_lang, gender, recover_bg, user_known_languages, trace_id],
        queue='separation'
    )
    return result.id

# ------------------------------------------------------------------------------
# TERMINAL 1: SEPARATION & SEGMENTATION (Queue: separation)
# ------------------------------------------------------------------------------

@celery_app.task(bind=True, name="src.tasks.separation_task")
def separation_task(self, input_file: str, src_lang: str, dst_lang: str, gender: str, recover_bg: bool, user_known_languages: List[str], trace_id: str):
    """
    T1: Extract, Separate, and Stream Segments to T2.
    """
    self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': 'Audio Separation'})
    logger.info(f"[{trace_id}] terminal_1: START - Extraction & Separation")
    from src.engines.audio.processor import AudioProcessor
    context = RequestContext(trace_id)
    
    # Store the master video path for T3 access
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "input_file", input_file)
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "segments_done", 0)
    audio_proc = AudioProcessor()
    
    # 1. Extraction (Mono)
    audio_data = audio_proc.extract_to_numpy(input_file)
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)
    
    temp_audio_path = context.get_path("extracted_audio.wav")
    sf.write(temp_audio_path, audio_data, 16000)
    
    # 2. Vocal Separation (Optional)
    vocal_path = None
    bg_path = None
    if recover_bg:
        try:
            vocal_path, bg_path = audio_proc.extract_vocal_and_bg(input_file, context.sandbox_path)
            # Store paths in Redis for T3 access later
            REDIS_CLIENT.hset(f"pipeline:{trace_id}", "bg_audio_path", bg_path or "")
            REDIS_CLIENT.hset(f"pipeline:{trace_id}", "source_audio_path", vocal_path or temp_audio_path)
        except Exception as e:
            logger.warning(f"Vocal separation failed: {e}")
            REDIS_CLIENT.hset(f"pipeline:{trace_id}", "source_audio_path", temp_audio_path)
    else:
        REDIS_CLIENT.hset(f"pipeline:{trace_id}", "source_audio_path", temp_audio_path)

    # 3. Speech-Unit Segmentation (MANDATORY FIX)
    self.update_state(state='PROGRESS', meta={'progress': 30, 'stage': 'Speech-Unit Segmentation'})
    logger.info(f"[{trace_id}] terminal_1: START - Speech-Unit Analysis")
    
    source_audio = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "source_audio_path").decode()
    import librosa
    audio_data, sr = librosa.load(source_audio, sr=16000)
    
    from src.app import model_manager
    whisper_model = model_manager.get_whisper()
    
    from src.utils.utils import get_language_code
    whisper_lang = None
    if src_lang != "Automatic":
        whisper_lang = get_language_code(src_lang)
    
    # Enable word-level timestamps for precision grouping
    segments_iter, info = whisper_model.transcribe(
        audio_data, 
        word_timestamps=True,
        vad_filter=True, 
        language=whisper_lang
    )
    
    segment_counter = 0
    current_words = []
    current_start = None
    MAX_SENTENCE_DURATION = 6.0 
    MIN_PAUSE_MS = 400 

    def dispatch_unit(words, start, end):
        nonlocal segment_counter
        unit_text = " ".join([word.word.strip() for word in words])
        if not unit_text.strip(): return
        
        seg_data = {
            "id": segment_counter,
            "start": start,
            "end": end,
            "duration": end - start,
            "text": unit_text,
            "hint_lang": info.language,
            "trace_id": trace_id,
            "source_audio_path": source_audio
        }
        
        # IMMEDIATE DISPATCH TO TERMINAL 2 (Analysis) - Parallel Win
        analysis_task.apply_async(
            args=[seg_data, dst_lang, user_known_languages],
            queue='analysis'
        )
        logger.info(f"[{trace_id}] -> T1 STREAM-DISPATCH Speech-Unit {segment_counter} ('{unit_text[:20]}...')")
        segment_counter += 1

    for seg in segments_iter:
        # Fallback: If no word timestamps, treat the whole segment as one block
        if not seg.words:
            logger.warning(f"[{trace_id}] Segment {seg.id} has no word-level timestamps. Falling back to segment-level markers.")
            unit_text = seg.text.strip()
            if unit_text:
                seg_data = {
                    "id": segment_counter,
                    "start": seg.start,
                    "end": seg.end,
                    "duration": seg.end - seg.start,
                    "text": unit_text,
                    "hint_lang": info.language,
                    "trace_id": trace_id,
                    "source_audio_path": source_audio
                }
                analysis_task.apply_async(
                    args=[seg_data, dst_lang, user_known_languages],
                    queue='analysis'
                )
                segment_counter += 1
            continue
        
        for w in seg.words:
            if current_start is None:
                current_start = w.start
            
            # Check for gap between current word and last word
            if current_words:
                last_end = current_words[-1].end
                pause_duration = (w.start - last_end) * 1000
                
                # Split if pause is long OR if current unit is getting too long
                if pause_duration > MIN_PAUSE_MS or (w.end - current_start) > MAX_SENTENCE_DURATION:
                    dispatch_unit(current_words, current_start, last_end)
                    current_words = []
                    current_start = w.start
            
            current_words.append(w)
            
            # Split on punctuation (Sentence boundary)
            clean_word = w.word.strip()
            if clean_word.endswith(('.', '?', '!')):
                dispatch_unit(current_words, current_start, w.end)
                current_words = []
                current_start = None

    # Final tail unit dispatch
    if current_words:
        dispatch_unit(current_words, current_start, current_words[-1].end)

    # Finalize T1
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "total_segments", segment_counter)
    REDIS_CLIENT.expire(f"pipeline:{trace_id}", 3600)
    
    logger.info(f"[{trace_id}] terminal_1: COMPLETE - Generated {segment_counter} speech-units")
    
    # Check if T3 already finished everything before we set the total
    num_done = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "segments_done")
    if num_done is not None and int(num_done) >= segment_counter:
        logger.info(f"[{trace_id}] All segments already completed by T3. Triggering merge from T1.")
        merge_final_video_task.apply_async(args=[trace_id], queue='merge')
    elif segment_counter == 0:
        logger.info(f"[{trace_id}] No segments found. Triggering empty merge.")
        merge_final_video_task.apply_async(args=[trace_id], queue='merge')
        
    return {"total_segments": segment_counter}

# ------------------------------------------------------------------------------
# TERMINAL 2: ANALYSIS & TRANSLATION (Queue: analysis)
# ------------------------------------------------------------------------------

@celery_app.task(name="src.tasks.analysis_task")
def analysis_task(segment: Dict[str, Any], dst_lang: str, user_known_languages: List[str]):
    """
    T2: Gender Identification, Language Support, and Translation.
    """
    trace_id = segment["trace_id"]
    logger.info(f"[{trace_id}] terminal_2: START Analysis Seg {segment['id']}")
    
    from src.app import model_manager
    from src.utils.utils import get_language_name
    
    # 1. Gender Recognition
    analyzer = model_manager.get_diarization()
    gender = analyzer.identify_gender_for_segment(segment["source_audio_path"], segment["start"], segment["end"])
    segment["gender"] = gender
    
    # 2. Language Detection & Translation
    detected_lang = segment.get("hint_lang", "English")
    src_lang_name = get_language_name(detected_lang)
    target_lang_name = get_language_name(dst_lang) if len(dst_lang) <= 3 else dst_lang
    
    # Priority Logic: If target is different from global source, FORCE translation
    global_src_lang = get_language_name(segment.get("hint_lang", "en"))
    segment["src_lang_name"] = global_src_lang
    segment["dst_lang_name"] = target_lang_name
    
    if global_src_lang.lower() == target_lang_name.lower():
        segment["action"] = "KEEP"
    else:
        # ABSOLUTE FORCE: If target != source, we MUST translate.
        segment["action"] = "TRANSLATE"
        from src.engines.translation.translator import TranslationService
        context = RequestContext(trace_id)
        translator = TranslationService(context)
        try:
            # Clean text before translation to prevent engine hangs
            clean_text = segment["text"].strip()
            if not clean_text:
                segment["action"] = "KEEP" # Skip empty
            else:
                translated_text = translator.translate_text(clean_text, global_src_lang, target_lang_name)
                segment["translated_text"] = translated_text
        except Exception as e:
            logger.error(f"[{trace_id}] CRITICAL: Translation failed for segment {segment['id']}: {e}")
            # Fallback to original text if translation literally crashes, but keep action as TRANSLATE
            # so TTS still attempts to speak the original text in the new voice (better than nothing)
            segment["translated_text"] = segment["text"]

    # IMMEDIATE DISPATCH TO TERMINAL 3 (Synthesis)
    synthesis_task.apply_async(
        args=[segment],
        queue='merge'
    )
    logger.info(f"[{trace_id}] -> T2 dispatched Seg {segment['id']}")

# ------------------------------------------------------------------------------
# TERMINAL 3: SYNTHESIS & MERGE (Queue: merge)
# ------------------------------------------------------------------------------

@celery_app.task(name="src.tasks.synthesis_task")
def synthesis_task(segment: Dict[str, Any]):
    """
    T3: Voice Synthesis (TTS) and Individual Prep.
    """
    trace_id = segment["trace_id"]
    logger.info(f"[{trace_id}] terminal_3: START Synthesis Seg {segment['id']}")
    
    if segment.get("action") == "TRANSLATE":
        from src.engines.tts.dubbing_engine import your_tts
        context = RequestContext(trace_id)
        tts_path = context.get_path(f"tts_seg_{segment['id']}.wav")
        
        try:
            final_file = your_tts(
                segment["translated_text"],
                segment["dst_lang_name"],
                segment["gender"],
                tts_path,
                actual_duration=segment["end"] - segment["start"]
            )
            segment["tts_path"] = final_file
        except Exception as e:
            logger.error(f"TTS failed for {segment['id']}: {e}")
            segment["action"] = "KEEP"

    # 📖 Bookkeeping: Save processed segment to Redis
    REDIS_CLIENT.hset(f"pipeline:{trace_id}:results", segment["id"], json.dumps(segment))
    
    # Check if we are done
    num_done = REDIS_CLIENT.hincrby(f"pipeline:{trace_id}", "segments_done", 1)
    total = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "total_segments")
    
    if total is not None:
        total = int(total)
        logger.info(f"[{trace_id}] Progress: {num_done}/{total}")
        if num_done >= total:
            # All segments processed! Trigger Merge.
            source_video = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "input_file")
            if source_video: source_video = source_video.decode()
            
            merge_final_video_task.apply_async(
                args=[trace_id],
                queue='merge'
            )

def check_and_trigger_merge(trace_id, input_file):
    """Helper for zero-segment videos"""
    merge_final_video_task.apply_async(args=[trace_id], queue='merge')

@celery_app.task(name="src.tasks.merge_final_video_task")
def merge_final_video_task(trace_id: str):
    """
    T3 Final Step: Assembles all segments using the master-clock Overlay Mix.
    """
    try:
        logger.info(f"[{trace_id}] terminal_3: START Final Overlay Merge")
        
        # 1. Retrieve all data from Redis
        pipeline_data = REDIS_CLIENT.hgetall(f"pipeline:{trace_id}")
        if not pipeline_data:
            logger.error(f"[{trace_id}] No pipeline data found in Redis. Merge aborted.")
            return None
            
        source_audio = pipeline_data.get(b"source_audio_path")
        if not source_audio:
            logger.error(f"[{trace_id}] source_audio_path missing in Redis.")
            return None
        source_audio = source_audio.decode()
        
        background_audio = pipeline_data.get(b"bg_audio_path")
        if background_audio: background_audio = background_audio.decode()
        
        results_raw = REDIS_CLIENT.hgetall(f"pipeline:{trace_id}:results")
        segments_data = []
        for val in results_raw.values():
            segments_data.append(json.loads(val.decode()))
        
        logger.info(f"[{trace_id}] Merging {len(segments_data)} segments...")
        segments_data.sort(key=lambda x: x['start'])
        
        # 2. Prepare Overlay Manifest
        from src.utils.media_engine import MediaEngine
        context = RequestContext(trace_id)
        overlay_manifest = []
        
        for i, seg in enumerate(segments_data):
            if seg.get("action") == "TRANSLATE" and seg.get("tts_path") and os.path.exists(seg["tts_path"]):
                overlay_manifest.append({
                    "path": seg["tts_path"],
                    "start": seg["start"]
                })
            else:
                # For KEEP segments, we slice the original audio
                keep_path = context.get_path(f"keep_{i}.wav")
                MediaEngine.slice_audio(source_audio, seg["start"], seg["end"], keep_path)
                overlay_manifest.append({
                    "path": keep_path,
                    "start": seg["start"]
                })
                
        # 3. Execution
        input_file_bytes = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "input_file")
        if not input_file_bytes:
            logger.error(f"[{trace_id}] input_file missing in Redis.")
            return None
        input_file = input_file_bytes.decode()
        
        from src.core.config import settings
        static_processed_dir = os.path.join(settings.BASE_DIR, "static", "processed")
        os.makedirs(static_processed_dir, exist_ok=True)
        
        out_video_name = f"output_{trace_id}.mp4"
        out_video = os.path.join(static_processed_dir, out_video_name)
        
        # Run the high-performance master-clock overlay mix
        MediaEngine.overlay_segments(input_file, background_audio, overlay_manifest, out_video)
        
        # Cleanup and Return
        logger.info(f"[{trace_id}] terminal_3: COMPLETE - Video ready at {out_video}")
        
        # Clear Redis data after successful merge
        REDIS_CLIENT.delete(f"pipeline:{trace_id}", f"pipeline:{trace_id}:results")
        
        return {
            "video_url": f"processed/{out_video_name}",
            "trace_id": trace_id
        }
    except Exception as e:
        import traceback
        logger.error(f"[{trace_id}] CRITICAL: Final merge failed: {e}")
        logger.error(traceback.format_exc())
        return None
