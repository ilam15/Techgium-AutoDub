import os
import shutil
import time
import json
import uuid
import re  # New import
import soundfile as sf
import torch
import numpy as np
import redis
from typing import List, Dict, Any, Tuple
from types import SimpleNamespace
from celery import group, chain, chord
from src.core.celery_app import celery_app
from src.core.logger import logger
from src.core.context import RequestContext
from src.core.config import settings
import src.config_constants as config
from src.models import model_manager

# Redis connection for bookkeeping
REDIS_CLIENT = redis.from_url(settings.CELERY_BROKER_URL)

# ==============================================================================
# HELPER FUNCTIONS (Split Logic)
# ==============================================================================

def is_devanagari(text):
    """Check if text contains Devanagari script (for Hindi/Marathi/etc)."""
    return any('\u0900' <= c <= '\u097F' for c in text)

def contains_english(text):
    """Check for significant English content (words > 3 chars)."""
    return bool(re.search(r'[a-zA-Z]{3,}', text))

def prepare_audio(input_file: str, recover_bg: bool, trace_id: str) -> Tuple[Any, Any, Any]:
    """Extracts audio and optionally separates vocals/background."""
    from src.engines.audio.processor import AudioProcessor
    audio_proc = AudioProcessor()
    
    # 1. Extraction
    audio_data = audio_proc.extract_to_numpy(input_file)
    
    # 2. Separation
    vocal_path = None
    bg_path = None
    
    if recover_bg:
        try:
            from src.utils.audio_separator import separate_audio
            vocal_path, bg_path = separate_audio(input_file)
        except Exception as e:
            logger.warning(f"[{trace_id}] Separation failed, using original: {e}")
    
    return vocal_path, bg_path, audio_data

def perform_vad(vad_source: Any, trace_id: str) -> List[SimpleNamespace]:
    """Performs VAD using Whisper to get raw segments."""
    whisper_model = model_manager.get_whisper()
    
    segments_iter, _ = whisper_model.transcribe(
        vad_source, 
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=config.VAD_MIN_SILENCE_DURATION_MS,
            speech_pad_ms=config.VAD_SPEECH_PAD_MS,
            threshold=config.VAD_THRESHOLD,
            min_speech_duration_ms=config.VAD_MIN_SPEECH_DURATION_MS,
            max_speech_duration_s=config.VAD_MAX_SPEECH_DURATION_S
        ),
        word_timestamps=True,
        condition_on_previous_text=False
    )
    
    return [SimpleNamespace(start=s.start, end=s.end, text=s.text) for s in segments_iter]

def clean_segments(raw_segments: List[SimpleNamespace], trace_id: str) -> List[Any]:
    """Merges and filters segments."""
    processed_segments = []
    
    # Merge Logic
    if raw_segments:
        curr = raw_segments[0]
        for next_seg in raw_segments[1:]:
            gap = next_seg.start - curr.end
            curr_duration = curr.end - curr.start
            combined_duration = curr_duration + (next_seg.end - next_seg.start)
            
            should_merge = False
            
            # Logic: Merge if gap is small OR if current segment is too short (context improvement)
            if combined_duration < config.SEGMENT_MAX_DURATION:
                if gap < config.SEGMENT_MIN_GAP_MERGE:
                    should_merge = True
                elif curr_duration < 1.5:  # Force merge small chunks for better NLLB translation
                    should_merge = True
            
            if should_merge:
                curr.end = next_seg.end
                curr.text = curr.text + " " + next_seg.text
            else:
                if (curr.end - curr.start) >= config.SEGMENT_MIN_DURATION:
                    processed_segments.append(curr)
                else:
                    if gap < 0.5:
                        next_seg.start = curr.start
                        next_seg.text = curr.text + " " + next_seg.text
                curr = next_seg
                
        if (curr.end - curr.start) >= config.SEGMENT_MIN_DURATION:
            processed_segments.append(curr)

    # Hallucination Filter
    final_segments = []
    if processed_segments:
        last_text = ""
        for seg in processed_segments:
            text = seg.text.strip()
            text_lower = text.lower()
            
            if any(phrase in text_lower for phrase in config.BANNED_PHRASES):
                logger.info(f"[{trace_id}] Dropping banned phrase: {text}")
                continue
                
            if len(text) < config.MIN_TEXT_LENGTH:
                continue
                
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, last_text, text_lower).ratio()
            if similarity > config.DUPLICATE_SIMILARITY_THRESHOLD:
                logger.info(f"[{trace_id}] Dropping duplicate/hallucination: {text}")
                continue
                
            final_segments.append(seg)
            last_text = text_lower
            
    return final_segments

# ==============================================================================
# PIPELINE ENTRY POINT
# ==============================================================================

def trigger_autodub_pipeline(input_file, src_lang, dst_lang, gender, recover_bg, user_known_languages, trace_id):
    """Kicks off the 3-terminal streaming pipeline."""
    logger.info(f"[{trace_id}] Launching 3-Terminal Pipeline...")
    
    pipeline_key = config.PIPELINE_KEY_TEMPLATE.format(trace_id=trace_id)
    
    # pipeline writes
    pipe = REDIS_CLIENT.pipeline()
    pipe.hset(pipeline_key, "input_file", input_file)
    pipe.hset(pipeline_key, "original_video_path", input_file)
    pipe.expire(pipeline_key, config.PIPELINE_TTL)
    pipe.execute()
    
    # Start Terminal 1
    task = separation_task.apply_async(
        args=[input_file, src_lang, dst_lang, gender, recover_bg, user_known_languages, trace_id],
        queue='separation'
    )
    
    REDIS_CLIENT.set(config.TASK_TRACE_MAP_TEMPLATE.format(task_id=task.id), trace_id, ex=config.PIPELINE_TTL)
    return task.id

# ==============================================================================
# TERMINAL 1: CONTROLLER
# ==============================================================================

@celery_app.task(bind=True, name="src.tasks.separation_task")
def separation_task(self, input_file: str, src_lang: str, dst_lang: str, gender: str, recover_bg: bool, user_known_languages: List[str], trace_id: str):
    """CONTROLLER: Extract, VAD, and Dispatch utilizing Helper Functions and Chord."""
    self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': 'VAD & Separation'})
    logger.info(f"[{trace_id}] CONTROLLER: START - VAD Segmentation")
    
    # 1. Prepare
    vocal_path, bg_path, audio_data = prepare_audio(input_file, recover_bg, trace_id)
    
    # Optimizing Redis updates
    pipeline_key = config.PIPELINE_KEY_TEMPLATE.format(trace_id=trace_id)
    pipe = REDIS_CLIENT.pipeline()
    pipe.hset(pipeline_key, "input_file", input_file)
    pipe.hset(pipeline_key, "segments_done", 0)
    if bg_path:
         pipe.hset(pipeline_key, "bg_audio_path", bg_path)
    # Use vocal path if available, else original
    source_audio_path = vocal_path or input_file
    pipe.hset(pipeline_key, "source_audio_path", source_audio_path)
    pipe.execute()
    
    # 2. VAD
    vad_source = vocal_path if vocal_path and os.path.exists(vocal_path) else audio_data
    raw_segments = perform_vad(vad_source, trace_id)
    
    # 3. Clean
    processed_segments = clean_segments(raw_segments, trace_id)
    
    # Update count
    REDIS_CLIENT.hset(pipeline_key, "total_segments", len(processed_segments))

    # 4. Dispatch with Chord
    if not processed_segments:
        logger.warning(f"[{trace_id}] No segments found. Triggering empty merge.")
        merge_final_video_task.apply_async(args=[[], trace_id], queue='merge') # Pass empty list
        return {"total_segments": 0}

    # Prepare signature group
    tasks_group = []
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
        # Create signature - Updated to pass src_lang
        sig = segment_worker_task.s(seg_data, src_lang, dst_lang, gender).set(queue='analysis')
        tasks_group.append(sig)

    logger.info(f"[{trace_id}] Dispatching chord with {len(tasks_group)} tasks")
    
    # Execute Chord: Group -> Merge
    workflow = chord(tasks_group, merge_final_video_task.s(trace_id).set(queue='merge'))
    workflow.apply_async()
    
    return {"total_segments": len(processed_segments)}

# ==============================================================================
# TERMINAL 2: SEGMENT WORKER
# ==============================================================================

@celery_app.task(name="src.tasks.segment_worker_task")
def segment_worker_task(segment: Dict[str, Any], src_lang: str, dst_lang: str, global_gender: str):
    """WORKER: Stateless processing. Returns segment data instead of writing to Redis if possible."""
    trace_id = segment["trace_id"]
    from src.utils.utils import get_language_name
    from src.utils.media_engine import MediaEngine
    from src.engines.translation.translator import TranslationService
    from src.engines.tts.dubbing_engine import your_tts
    import langid

    # Audio Extraction
    audio_chunk = MediaEngine.extract_pure_audio_numpy_segment(
        segment["source_audio_path"],
        segment["start"],
        segment["duration"]
    )
    
    # Models
    whisper_model = model_manager.get_whisper()
    active_beam = 5 if settings.DEVICE == "cuda" else 2
    
    # ASR
    results, info = whisper_model.transcribe(audio_chunk, beam_size=active_beam, word_timestamps=True)
    results = list(results)
    
    audio_lang = info.language
    audio_conf = info.language_probability
    
    # Filter
    valid_text_segments = []
    for r in results:
        if hasattr(r, 'no_speech_prob') and r.no_speech_prob > config.HALLUCINATION_NO_SPEECH_PROB: continue
        if hasattr(r, 'avg_logprob') and r.avg_logprob < config.HALLUCINATION_LOGPROB_THRESHOLD: continue
        
        text_lower = r.text.lower()
        if any(phrase in text_lower for phrase in config.BANNED_PHRASES): continue
        valid_text_segments.append(r.text)
        
    asr_text = " ".join(valid_text_segments).strip()
    
    # Repetition Removal
    words = asr_text.split()
    if words:
        deduped = [words[0]]
        for w in words[1:]:
            if w.lower() != deduped[-1].lower(): deduped.append(w)
        asr_text = " ".join(deduped)

    if not asr_text:
        segment["action"] = "KEEP"
        detected_lang_name = "UNKNOWN"
        target_lang_name = "UNKNOWN"
    else:
        # Detect Lang - Using LOWER Threshold (0.50) to catch more valid detections
        final_lang_code = audio_lang if audio_conf >= config.LANG_DETECT_AUDIO_THRESHOLD else "UNKNOWN"
        if final_lang_code == "UNKNOWN":
            try:
                res_lang, res_prob = langid.classify(asr_text)
                if res_prob >= 0.85: final_lang_code = res_lang
            except: pass
            
        detected_lang_name = get_language_name(final_lang_code) if final_lang_code != "UNKNOWN" else "UNKNOWN"
        target_lang_name = get_language_name(dst_lang) if len(dst_lang) <= 3 else dst_lang
        
        segment.update({
            "detected_lang": detected_lang_name,
            "detect_prob": audio_conf,
            "asr_text": asr_text,
            "target_lang": target_lang_name
        })
        
        # --- DECISION LOGIC ---
        should_translate = True
        
        if audio_conf < 0.50:
            # Very low confidence -> Assume hallucination/error -> FORCE TRANSLATE
            logger.info(f"[{trace_id}] Segment {segment['id']} Low Conf ({audio_conf:.2f}) -> Force TRANSLATE")
            should_translate = True
            # Override detected lang to Source Lang if we are forcing translation due to low conf
            if detected_lang_name == "UNKNOWN":
                 detected_lang_name = get_language_name(src_lang)

        elif detected_lang_name.lower() == target_lang_name.lower():
            # Potential Match? Check for lies.
            is_hindi_target = (target_lang_name.lower() == "hindi")
            
            if contains_english(asr_text) and target_lang_name.lower() != "english":
                # English words in non-English target -> Hallucination -> TRANSLATE
                logger.info(f"[{trace_id}] Segment {segment['id']} English Detected in {target_lang_name} -> Force TRANSLATE")
                should_translate = True
                detected_lang_name = "English" # Update for translator
                
            elif is_hindi_target and not is_devanagari(asr_text):
                # Script mismatch -> Hallucination -> TRANSLATE
                logger.info(f"[{trace_id}] Segment {segment['id']} Hindi without Devanagari -> Force TRANSLATE")
                should_translate = True
                detected_lang_name = get_language_name(src_lang) # Fallback to source
                
            elif src_lang.lower() != target_lang_name.lower():
                # Source is NOT target, but we detected Target.
                # Likely hallucination (e.g. Source English, Detected Hindi, Target Hindi).
                # Force Translate to ensure we don't just keep the English audio.
                logger.info(f"[{trace_id}] Segment {segment['id']} Detected == Target but Source != Target -> Force TRANSLATE")
                should_translate = True
                detected_lang_name = get_language_name(src_lang) # Trust Source Lang over extraction
            else:
                should_translate = False
        else:
            # Languages differ -> Translate
            should_translate = True

        if should_translate:
            segment["action"] = "TRANSLATE"
            context = RequestContext(trace_id)
            translator = TranslationService(context)
            try:
                # Use adjusted detected_lang_name
                segment["translated_text"] = translator.translate_text(asr_text, detected_lang_name, target_lang_name)
            except:
                segment["translated_text"] = asr_text

            # TTS
            tts_path = context.get_path(f"dub_{segment['id']}.wav")
            try:
                analyzer = model_manager.get_diarization()
                seg_gender = analyzer.identify_gender_for_segment(segment["source_audio_path"], segment["start"], segment["duration"])
                if seg_gender == "Unknown": seg_gender = global_gender
                seg_gender = seg_gender.capitalize()
                
                final_tts = your_tts(
                    segment["translated_text"],
                    target_lang_name,
                    seg_gender,
                    tts_path,
                    actual_duration=segment["duration"]
                )
                segment["dub_audio_path"] = final_tts
            except Exception as e:
                logger.error(f"TTS Failed: {e}")
                segment["action"] = "KEEP"
        else:
            segment["action"] = "KEEP"

    logger.info(f"SEG_DONE: {segment['id']} | Action: {segment['action']}")
    
    # Progress Update (Fire and Forget)
    REDIS_CLIENT.hincrby(config.PIPELINE_KEY_TEMPLATE.format(trace_id=trace_id), "segments_done", 1)
    
    # RETURN RESULT (Critical for Chord)
    return segment

# ==============================================================================
# TERMINAL 3: ASSEMBLER
# ==============================================================================

@celery_app.task(
    name="src.tasks.merge_final_video_task",
    autoretry_for=(),
    acks_late=False,
    max_retries=0
)
def merge_final_video_task(results: List[Dict], trace_id: str):
    """ASSEMBLER: Receives results from Chord."""
    lock_key = config.ASSEMBLER_LOCK_TEMPLATE.format(trace_id=trace_id)
    if not REDIS_CLIENT.set(lock_key, "1", nx=True, ex=config.LOCK_TTL):
        logger.warning(f"[{trace_id}] ASSEMBLER skipped (locked/done).")
        return {"status": "already_processed"}
        
    try:
        logger.info(f"[{trace_id}] ASSEMBLER: START with {len(results or [])} results")
        pipeline_key = config.PIPELINE_KEY_TEMPLATE.format(trace_id=trace_id)
        pipeline_data = REDIS_CLIENT.hgetall(pipeline_key)
        
        if not pipeline_data:
            logger.error(f"[{trace_id}] No pipeline data.")
            return None
            
        input_file = pipeline_data[b"input_file"].decode()
        bg_audio = pipeline_data.get(b"bg_audio_path", b"").decode()
        
        # Valid Segments (Filter Nones)
        segments = [s for s in results if s]
        segments.sort(key=lambda x: x['start'])
        
        # Deduplicate
        seen = set()
        validated = []
        for s in segments:
            if s['id'] in seen: continue
            if s['start'] >= s['end']: continue
            seen.add(s['id'])
            validated.append(s)
            
        # Assemble
        from src.utils.media_engine import MediaEngine
        static_processed_dir = os.path.join(settings.BASE_DIR, "static", "processed")
        os.makedirs(static_processed_dir, exist_ok=True)
        out_name = f"output_{trace_id}.mp4"
        out_path = os.path.join(static_processed_dir, out_name)
        
        MediaEngine.assemble_production_audio_safe(input_file, bg_audio, validated, out_path)
        
        # Clean
        REDIS_CLIENT.delete(pipeline_key)
        
        return {"video_url": f"processed/{out_name}", "trace_id": trace_id}
        
    except Exception as e:
        logger.error(f"[{trace_id}] ASSEMBLER FAILED: {e}")
        return None
    finally:
        REDIS_CLIENT.delete(lock_key)
