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

    # 3. Streaming Segmentation
    self.update_state(state='PROGRESS', meta={'progress': 30, 'stage': 'Streaming Segmentation'})
    logger.info(f"[{trace_id}] terminal_1: START - Segmentation Streaming")
    
    source_audio = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "source_audio_path").decode()
    import librosa
    audio_data, sr = librosa.load(source_audio, sr=16000)
    
    from src.app import model_manager
    whisper_model = model_manager.get_whisper()
    
    total_samples = len(audio_data)
    chunk_samples = settings.PROBE_WINDOW_LONG * 16000
    segment_counter = 0
    
    for start_sample in range(0, total_samples, chunk_samples):
        end_sample = min(start_sample + chunk_samples, total_samples)
        chunk = audio_data[start_sample:end_sample]
        if len(chunk) < 8000: continue
        
        offset = start_sample / 16000
        try:
            segments_iter, info = whisper_model.transcribe(
                chunk, vad_filter=True, language=None if src_lang=="Automatic" else src_lang
            )
            
            for seg in segments_iter:
                seg_data = {
                    "id": segment_counter,
                    "start": seg.start + offset,
                    "end": seg.end + offset,
                    "duration": seg.end - seg.start,
                    "text": seg.text,
                    "hint_lang": info.language,
                    "trace_id": trace_id,
                    "source_audio_path": source_audio
                }
                
                # IMMEDIATE DISPATCH TO TERMINAL 2 (Analysis)
                analysis_task.apply_async(
                    args=[seg_data, dst_lang, user_known_languages],
                    queue='analysis'
                )
                segment_counter += 1
                logger.info(f"[{trace_id}] -> T1 dispatched Seg {segment_counter-1}")
        except Exception as e:
            logger.error(f"Segmentation error at {offset}s: {e}")

    # Finalize T1: Store total count
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "total_segments", segment_counter)
    REDIS_CLIENT.expire(f"pipeline:{trace_id}", 3600)  # Auto-clean in 1 hour
    
    logger.info(f"[{trace_id}] terminal_1: COMPLETE - Found {segment_counter} segments")
    
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
    
    segment["src_lang_name"] = src_lang_name
    segment["dst_lang_name"] = target_lang_name

    if src_lang_name.lower() == target_lang_name.lower():
        segment["action"] = "KEEP"
    else:
        from src.engines.translation.translator import TranslationService
        context = RequestContext(trace_id)
        translator = TranslationService(context)
        try:
            translated_text = translator.translate_text(segment["text"], src_lang_name, target_lang_name)
            segment["translated_text"] = translated_text
            segment["action"] = "TRANSLATE"
        except Exception as e:
            logger.error(f"Translation failed for {segment['id']}: {e}")
            segment["action"] = "KEEP"

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
            # We pass the input file info which should be stored in Redis too
            source_video = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "original_video_path")
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
    T3 Final Step: Assembles all segments into the final video.
    """
    logger.info(f"[{trace_id}] terminal_3: START Final Merge")
    
    # 1. Retrieve all data from Redis
    pipeline_data = REDIS_CLIENT.hgetall(f"pipeline:{trace_id}")
    source_audio = pipeline_data[b"source_audio_path"].decode()
    bg_audio = pipeline_data.get(b"bg_audio_path")
    if bg_audio: bg_audio = bg_audio.decode()
    
    results_raw = REDIS_CLIENT.hgetall(f"pipeline:{trace_id}:results")
    segments = []
    for val in results_raw.values():
        segments.append(json.loads(val.decode()))
    
    segments.sort(key=lambda x: x['start'])
    
    # 2. Reconstruct Timeline
    from src.utils.media_engine import MediaEngine
    context = RequestContext(trace_id)
    audio_chunks = []
    current_time = 0.0
    
    for i, seg in enumerate(segments):
        # Precise Time-Alignment logic (MANDATORY FIX)
        # Fill gaps with original audio sliced to EXACT dimensions
        if seg["start"] > current_time + 0.005: # 5ms tolerance
            gap_duration = seg["start"] - current_time
            gap = context.get_path(f"gap_{i}.wav")
            # We slice EXACTLY up to the next start time to prevent lead/drift
            MediaEngine.slice_audio(source_audio, current_time, seg["start"], gap)
            audio_chunks.append(gap)
            
        # Add translated or original segment
        if seg.get("action") == "TRANSLATE" and seg.get("tts_path") and os.path.exists(seg["tts_path"]):
            # TTS is already duration-locked to seg["duration"] by your_tts update
            audio_chunks.append(seg["tts_path"])
        else:
            keep = context.get_path(f"keep_{i}.wav")
            MediaEngine.slice_audio(source_audio, seg["start"], seg["end"], keep)
            audio_chunks.append(keep)
            
        current_time = seg["end"]
        
    # Final tail
    probe = MediaEngine.get_probe_info(source_audio)
    total_dur = float(probe['format']['duration'])
    if current_time < total_dur:
        tail = context.get_path("tail.wav")
        MediaEngine.slice_audio(source_audio, current_time, total_dur, tail)
        audio_chunks.append(tail)
        
    # 3. Media Assembly
    voice_path = context.get_path("final_vocal.wav")
    MediaEngine.concat_audio_files(audio_chunks, voice_path)
    
    # Get original video path (stored during API call or T1)
    input_file = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "input_file").decode()
    
    from src.core.config import settings
    static_processed_dir = os.path.join(settings.BASE_DIR, "static", "processed")
    os.makedirs(static_processed_dir, exist_ok=True)
    
    out_video_name = f"output_{trace_id}.mp4"
    out_video = os.path.join(static_processed_dir, out_video_name)
    
    if bg_audio and os.path.exists(bg_audio):
        MediaEngine.merge_complex(input_file, voice_path, bg_audio, out_video)
    else:
        MediaEngine.merge_audio_video(input_file, voice_path, out_video)
    
    # Cleanup and Return
    logger.info(f"[{trace_id}] terminal_3: COMPLETE - Video ready at {out_video}")
    
    # Clear Redis data (optional, auto-expiry also exists)
    REDIS_CLIENT.delete(f"pipeline:{trace_id}", f"pipeline:{trace_id}:results")
    
    return {
        "video_url": f"processed/{out_video_name}",
        "trace_id": trace_id
    }
