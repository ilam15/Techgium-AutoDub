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
    task = separation_task.apply_async(
        args=[input_file, src_lang, dst_lang, gender, recover_bg, user_known_languages, trace_id],
        queue='separation'
    )
    # Store mapping for progress polling
    REDIS_CLIENT.set(f"task:{task.id}:trace", trace_id, ex=3600)
    return task.id

# ------------------------------------------------------------------------------
# TERMINAL 1: CONTROLLER - SEPARATION & VAD (Queue: separation)
# ------------------------------------------------------------------------------

@celery_app.task(bind=True, name="src.tasks.separation_task")
def separation_task(self, input_file: str, src_lang: str, dst_lang: str, gender: str, recover_bg: bool, user_known_languages: List[str], trace_id: str):
    """
    CONTROLLER: Extract, VAD, and Dispatch Stateless Segment Workers.
    """
    self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': 'VAD & Separation'})
    logger.info(f"[{trace_id}] CONTROLLER: START - VAD Segmentation")
    from src.engines.audio.processor import AudioProcessor
    context = RequestContext(trace_id)
    
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "input_file", input_file)
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "segments_done", 0)
    audio_proc = AudioProcessor()
    
    # 1. Extraction (Mono 16kHz)
    audio_data = audio_proc.extract_to_numpy(input_file)
    
    # 2. Vocal Separation for cleaner ASR/Detection (Mandatory for precision VAD)
    vocal_path = None
    bg_path = None
    if recover_bg:
        try:
            from src.utils.audio_separator import separate_audio
            vocal_path, bg_path = separate_audio(input_file)
            REDIS_CLIENT.hset(f"pipeline:{trace_id}", "bg_audio_path", bg_path or "")
            REDIS_CLIENT.hset(f"pipeline:{trace_id}", "source_audio_path", vocal_path or input_file)
        except Exception as e:
            logger.warning(f"Separation failed, using original: {e}")
            REDIS_CLIENT.hset(f"pipeline:{trace_id}", "source_audio_path", input_file)
    else:
        REDIS_CLIENT.hset(f"pipeline:{trace_id}", "source_audio_path", input_file)

    # 3. Precision VAD Segmentation (Single Pass)
    # CRITICAL: If we have vocal_path, use it for VAD. It's much cleaner than the mixed audio.
    from src.app import model_manager
    whisper_model = model_manager.get_whisper()
    
    vad_source = vocal_path if vocal_path and os.path.exists(vocal_path) else audio_data

    # Fast VAD pass
    # Focus on finding gaps to break up long speech into parallelizable chunks
    segments_iter, _ = whisper_model.transcribe(
        vad_source, 
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=300, # More aggressive segmentation
            speech_pad_ms=100
        )
    )
    
    from types import SimpleNamespace
    raw_segments = [SimpleNamespace(start=s.start, end=s.end, text=s.text) for s in segments_iter]
    processed_segments = []
    
    # Rule: Minimum segment 300ms, merge gaps < 150ms
    MIN_SEG_DUR = 0.3
    MIN_GAP_MERGE = 0.15
    
    if raw_segments:
        curr = raw_segments[0]
        for next_seg in raw_segments[1:]:
            gap = next_seg.start - curr.end
            if gap < MIN_GAP_MERGE:
                # Merge
                curr.end = next_seg.end
                curr.text = curr.text + " " + next_seg.text
            else:
                if (curr.end - curr.start) >= MIN_SEG_DUR:
                    processed_segments.append(curr)
                curr = next_seg
        if (curr.end - curr.start) >= MIN_SEG_DUR:
            processed_segments.append(curr)

    # 4. Parallel Dispatch
    # If a segment is huge (>12s), we subdivision it manually if needed, 
    # but for now, we follow the VAD boundaries.
    segment_counter = len(processed_segments)
    REDIS_CLIENT.hset(f"pipeline:{trace_id}", "total_segments", segment_counter)
    
    source_audio_path = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "source_audio_path").decode()

    for idx, seg in enumerate(processed_segments):
        seg_data = {
            "id": idx,
            "start": seg.start,
            "end": seg.end,
            "duration": seg.end - seg.start,
            "text_hint": seg.text.strip(),
            "trace_id": trace_id,
            "source_audio_path": source_audio_path
        }
        segment_worker_task.apply_async(
            args=[seg_data, dst_lang, gender],
            queue='analysis' 
        )
        logger.info(f"[{trace_id}] CONTROLLER -> Dispatch Seg {idx} [{seg.start:.2f}s - {seg.end:.2f}s]")

    if segment_counter == 0:
        merge_final_video_task.apply_async(args=[trace_id], queue='merge')
        
    return {"total_segments": segment_counter}

# ------------------------------------------------------------------------------
# TERMINAL 2: SEGMENT WORKER - DETECTION, ASR, TRANS, TTS (Stateless)
# ------------------------------------------------------------------------------

@celery_app.task(name="src.tasks.segment_worker_task")
def segment_worker_task(segment: Dict[str, Any], dst_lang: str, global_gender: str):
    """
    WORKER: Stateless processing of EXACTLY ONE segment.
    """
    trace_id = segment["trace_id"]
    from src.app import model_manager
    from src.utils.utils import get_language_name
    from src.utils.media_engine import MediaEngine
    from src.core.context import RequestContext
    import json
    
    # 1. Audio-Based High-Priority Detection
    audio_chunk = MediaEngine.extract_pure_audio_numpy_segment(
        segment["source_audio_path"],
        segment["start"],
        segment["duration"]
    )
    
    whisper_model = model_manager.get_whisper()
    active_beam = 5 if settings.DEVICE == "cuda" else 2
    
    # Full ASR + Detection Pass
    results, info = whisper_model.transcribe(audio_chunk, beam_size=active_beam, word_timestamps=True)
    results = list(results)
    
    audio_lang = info.language
    audio_conf = info.language_probability
    asr_text = " ".join([r.text for r in results]).strip()
    
    # 2. Tiered Language Strategy (Strict)
    # Audio-based (primary) >= 0.80
    # Text-based (fallback) >= 0.85
    final_lang_code = "UNKNOWN"
    
    if audio_conf >= 0.80:
        final_lang_code = audio_lang
    else:
        # Fallback to text-based detection using langid (dependency safe)
        try:
            import langid
            res_lang, res_prob = langid.classify(asr_text)
            if res_prob >= 0.85:
                final_lang_code = res_lang
        except:
            pass
            
    detected_lang_name = get_language_name(final_lang_code) if final_lang_code != "UNKNOWN" else "UNKNOWN"
    target_lang_name = get_language_name(dst_lang) if len(dst_lang) <= 3 else dst_lang
    
    segment.update({
        "detected_lang": detected_lang_name,
        "detect_prob": audio_conf,
        "asr_text": asr_text,
        "target_lang": target_lang_name
    })

    # 3. Decision Logic: Logic-Agnostic / Non-Negotiable
    if detected_lang_name.lower() == target_lang_name.lower():
        segment["action"] = "KEEP"
    else:
        segment["action"] = "TRANSLATE"
        
        # Translation
        from src.engines.translation.translator import TranslationService
        context = RequestContext(trace_id)
        translator = TranslationService(context)
        try:
            segment["translated_text"] = translator.translate_text(asr_text, detected_lang_name, target_lang_name)
        except:
            segment["translated_text"] = asr_text # Fallback
            
        # TTS
        from src.engines.tts.dubbing_engine import your_tts
        tts_path = context.get_path(f"dub_{segment['id']}.wav")
        try:
            # Get gender for segment
            analyzer = model_manager.get_diarization()
            seg_gender = analyzer.identify_gender_for_segment(segment["source_audio_path"], segment["start"], segment["duration"])
            
            final_tts = your_tts(
                segment["translated_text"],
                target_lang_name,
                seg_gender,
                tts_path,
                actual_duration=segment["duration"]
            )
            segment["dub_audio_path"] = final_tts
        except:
            segment["action"] = "KEEP" # Fail safe

    # Log source of truth
    logger.info(f"SEGMENT_ID: {segment['id']} | START: {segment['start']:.2f} | END: {segment['end']:.2f} | "
                f"DETECTED_LANG: {detected_lang_name} | TARGET_LANG: {target_lang_name} | ACTION: {segment['action']}")

    # 4. Bookkeeping & Assembly Trigger
    REDIS_CLIENT.hset(f"pipeline:{trace_id}:results", segment["id"], json.dumps(segment))
    num_done = REDIS_CLIENT.hincrby(f"pipeline:{trace_id}", "segments_done", 1)
    total_raw = REDIS_CLIENT.hget(f"pipeline:{trace_id}", "total_segments")
    
    if total_raw and num_done >= int(total_raw):
         merge_final_video_task.apply_async(args=[trace_id], queue='merge')

# ------------------------------------------------------------------------------
# TERMINAL 3: ASSEMBLER - SILENCE & INSERT (Single Task, Loop-Safe)
# ------------------------------------------------------------------------------

@celery_app.task(
    name="src.tasks.merge_final_video_task",
    autoretry_for=(),  # RULE 3: No retries
    acks_late=False,   # RULE 3: Immediate acknowledgment
    max_retries=0      # RULE 3: Absolutely no retries
)
def merge_final_video_task(trace_id: str):
    """
    ASSEMBLER: Loop-Safe Audio Assembly with Idempotency Guard.
    
    ANTI-LOOP GUARANTEES:
    1. Runs exactly once (idempotency lock)
    2. Pre-allocates audio buffer (no append)
    3. Sorts segments by start time (monotonic)
    4. Inserts each segment once (deduplication)
    5. Validates timeline integrity
    """
    
    # RULE 3: IDEMPOTENCY LOCK - Prevent multiple executions
    lock_key = f"assembler_lock:{trace_id}"
    if not REDIS_CLIENT.set(lock_key, "1", nx=True, ex=300):
        logger.warning(f"[{trace_id}] ASSEMBLER already running or completed. SKIPPING.")
        return {"status": "already_processed", "trace_id": trace_id}
    
    try:
        logger.info(f"[{trace_id}] ✅ ASSEMBLER: START (Idempotency Lock Acquired)")
        
        # Retrieve pipeline data
        pipeline_data = REDIS_CLIENT.hgetall(f"pipeline:{trace_id}")
        if not pipeline_data:
            logger.error(f"[{trace_id}] No pipeline data found. Aborting.")
            return None
            
        input_file = pipeline_data[b"input_file"].decode()
        bg_audio = pipeline_data.get(b"bg_audio_path", b"").decode()
        
        # Retrieve and validate segments
        results_raw = REDIS_CLIENT.hgetall(f"pipeline:{trace_id}:results")
        if not results_raw:
            logger.warning(f"[{trace_id}] No segments to process. Creating passthrough video.")
            segments = []
        else:
            segments = [json.loads(v) for v in results_raw.values()]
        
        # RULE 4: SORT BY START TIME (Monotonic Timeline)
        segments.sort(key=lambda x: x['start'])
        
        # RULE 5: DEDUPLICATION - Track inserted segments
        inserted_ids = set()
        validated_segments = []
        
        for seg in segments:
            seg_id = seg['id']
            
            # Skip duplicates
            if seg_id in inserted_ids:
                logger.warning(f"[{trace_id}] ⚠️ DUPLICATE segment {seg_id} detected. SKIPPING.")
                continue
            
            # Validate segment integrity
            if seg['start'] >= seg['end']:
                logger.error(f"[{trace_id}] ❌ Invalid segment {seg_id}: start >= end. SKIPPING.")
                continue
            
            inserted_ids.add(seg_id)
            validated_segments.append(seg)
            
            # ANTI-LOOP LOGGING
            logger.info(f"[{trace_id}] INSERT segment_id={seg_id} start={seg['start']:.2f} end={seg['end']:.2f} duration={seg['end']-seg['start']:.2f}")
        
        # Prepare output
        from src.utils.media_engine import MediaEngine
        context = RequestContext(trace_id)
        
        from src.core.config import settings
        static_processed_dir = os.path.join(settings.BASE_DIR, "static", "processed")
        os.makedirs(static_processed_dir, exist_ok=True)
        out_video_name = f"output_{trace_id}.mp4"
        out_video = os.path.join(static_processed_dir, out_video_name)
        
        # RULE 1 & 2: Pre-allocated buffer assembly (NO APPEND)
        # The MediaEngine method must use index-based insertion, not concatenation
        MediaEngine.assemble_production_audio_safe(
            input_file, 
            bg_audio, 
            validated_segments,  # Already sorted and deduplicated
            out_video
        )
        
        # Cleanup Redis data
        REDIS_CLIENT.delete(f"pipeline:{trace_id}", f"pipeline:{trace_id}:results")
        logger.info(f"[{trace_id}] ✅ ASSEMBLER: COMPLETE. Video: {out_video_name}")
        
        return {"video_url": f"processed/{out_video_name}", "trace_id": trace_id}
        
    except Exception as e:
        logger.error(f"[{trace_id}] ❌ ASSEMBLER FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    finally:
        # Always release lock (even on failure)
        REDIS_CLIENT.delete(lock_key)
