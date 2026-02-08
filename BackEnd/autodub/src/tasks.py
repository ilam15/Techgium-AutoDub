import os
import shutil
import time
import json
import uuid
import soundfile as sf
from typing import List, Dict, Any
from celery import group, chain, chord
from src.core.celery_app import celery_app
from src.core.logger import logger
from src.core.context import RequestContext
from src.engines.audio.processor import AudioProcessor
from src.engines.asr.transcriber import ASRTranscriber
from src.engines.translation.decision import DecisionEngine
from collections import Counter

# ==========================================
# Task Orchestrator (The Entry Point)
# ==========================================

def trigger_autodub_pipeline(input_file, src_lang, dst_lang, gender, recover_bg, user_known_languages, trace_id):
    """
    Constructs and starts the Celery task chain.
    """
    # 1. Extraction & ASR
    # 2. Decision
    # 3. Translation (Parallel)
    # 4. TTS (Serialized via queue)
    # 5. Merge
    
    # We use a chain of tasks. 
    # Some tasks will trigger sub-workflows (groups) using Celery's dynamic task generation if needed,
    # or we can construct a flat chain with groups in between.
    
    workflow = chain(
        extract_audio_task.s(input_file, trace_id, recover_bg),
        asr_task.s(src_lang),
        decision_task.s(dst_lang, user_known_languages),
        # The decision_task will return the list of segments.
        # We then need to process them.
        process_segments_orchestrator.s(dst_lang)
    )
    
    result = workflow.apply_async()
    return result.id

# ==========================================
# Individual Tasks
# ==========================================

@celery_app.task(bind=True, name="src.tasks.extract_audio_task")
def extract_audio_task(self, input_file: str, trace_id: str, recover_music: bool = False):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'stage': 'Extraction'})
    logger.info(f"[{trace_id}] Stage: Extraction")
    context = RequestContext(trace_id)
    audio_proc = AudioProcessor()
    
    # Extraction (Direct to Memory)
    audio_data = audio_proc.extract_to_numpy(input_file)
    
    # Background Separator
    bg_audio_path = None
    vocal_audio_path = None
    if recover_music:
        try:
            self.update_state(state='PROGRESS', meta={'progress': 15, 'stage': 'Vocal Separation'})
            vocal_audio_path, bg_audio_path = audio_proc.extract_vocal_and_bg(input_file, context.sandbox_path)
        except Exception as e:
            logger.warning(f"Background separation failed: {e}")

    # Save temp audio for ASR
    temp_audio_path = context.get_path("extracted_audio.wav")
    sf.write(temp_audio_path, audio_data, 16000)
    
    return {
        "input_file": input_file,
        "audio_path": temp_audio_path,
        "vocal_path": vocal_audio_path,
        "bg_path": bg_audio_path,
        "trace_id": trace_id,
        "recover_music": recover_music
    }

@celery_app.task(bind=True, name="src.tasks.asr_task")
def asr_task(self, prev_result: Dict[str, Any], src_lang: str):
    trace_id = prev_result["trace_id"]
    audio_path = prev_result["audio_path"]
    self.update_state(state='PROGRESS', meta={'progress': 30, 'stage': 'ASR & Diarization'})
    logger.info(f"[{trace_id}] Stage: ASR & Diarization")
    
    context = RequestContext(trace_id)
    asr = ASRTranscriber(context)
    
    audio_data, _ = sf.read(audio_path, dtype='float32')
    segments, info, turns, speaker_genders = asr.process_file(audio_data, src_lang)
    
    # Convert Whisper segments to serializable dicts
    serializable_segments = []
    for i, seg in enumerate(segments):
        serializable_segments.append({
            "id": i,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "segment_language": getattr(seg, 'segment_language', None),
            "segment_language_prob": getattr(seg, 'segment_language_prob', None)
        })
    
    return {
        **prev_result,
        "segments": serializable_segments,
        "info_language": info.language,
        "info_probability": info.language_probability,
        "speaker_genders": speaker_genders,
        "turns": turns, # Note: turns might need serialization if it's complex
        "original_src_lang": src_lang
    }

@celery_app.task(bind=True, name="src.tasks.decision_task")
def decision_task(self, prev_result: Dict[str, Any], dst_lang: str, user_known_languages: List[str]):
    trace_id = prev_result["trace_id"]
    self.update_state(state='PROGRESS', meta={'progress': 60, 'stage': 'Decision Engine'})
    logger.info(f"[{trace_id}] Stage: Decision Engine")
    
    segments = prev_result["segments"]
    turns = prev_result["turns"]
    speaker_genders = prev_result["speaker_genders"]
    global_whisper_lang = prev_result["info_language"]
    
    # Process segments through the shared decision engine
    processed_segments = DecisionEngine.get_decision(
        segments,
        turns,
        speaker_genders,
        dst_lang,
        user_known_languages,
        global_whisper_lang
    )
    
    prev_result["segments"] = processed_segments
    prev_result["dst_lang"] = dst_lang
    return prev_result

@celery_app.task(bind=True, name="src.tasks.process_segments_orchestrator")
def process_segments_orchestrator(self, prev_result: Dict[str, Any], dst_lang: str):
    """
    This task fans out the translation and TTS tasks.
    It uses a chord to wait for all parallel/serial operations to finish before merging.
    """
    segments = prev_result["segments"]
    trace_id = prev_result["trace_id"]
    
    # Create a sub-workflow for each segment: Translate -> TTS
    segment_tasks = []
    for s in segments:
        if s["action"] == "TRANSLATE":
            # Chain: Translate -> TTS
            seg_chain = chain(
                translate_segment_task.s(s, prev_result["original_src_lang"], dst_lang, trace_id),
                tts_segment_task.s(dst_lang, trace_id)
            )
            segment_tasks.append(seg_chain)
        else:
            # Just return the segment as is
            segment_tasks.append(noop_segment_task.s(s))
            
    # chord(header, callback) - waits for all in header to finish, then calls callback
    callback = merge_audio_video_task.s(prev_result)
    
    # Fix: Use self.replace so the orchestrator task ID properly represents the chord result
    return self.replace(chord(segment_tasks, callback))

@celery_app.task(
    bind=True, 
    name="src.tasks.translate_segment_task",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True
)
def translate_segment_task(self, segment: Dict[str, Any], src_lang: str, dst_lang: str, trace_id: str):
    if segment.get("action") != "TRANSLATE":
        return segment
        
    context = RequestContext(trace_id)
    from src.engines.translation.translator import TranslationService
    translator = TranslationService(context)
    
    # We need to map the segment's detected language to its name for the translator
    from src.utils.utils import get_language_name
    src_name = get_language_name(segment.get('lang', 'en'))
    
    try:
        translated_text = translator.translate_text(segment['text'], src_name, dst_lang)
        segment["translated_text"] = translated_text
        logger.info(f"[{trace_id}] TR Seg {segment['id']}: {segment['text'][:20]}... -> {translated_text[:20]}...")
    except Exception as e:
        logger.error(f"Translation failed for segment {segment['id']}: {e}")
        segment["translated_text"] = segment["text"] # Fallback
        
    return segment

@celery_app.task(
    bind=True,
    name="src.tasks.tts_segment_task", 
    queue="tts",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True
)
def tts_segment_task(self, segment: Dict[str, Any], dst_lang: str, trace_id: str):
    """
    STRICTLY SERIALIZED via 'tts' queue and concurrency=1 on the worker.
    """
    if segment.get("action") != "TRANSLATE":
        return {**segment, "tts_path": None}
        
    context = RequestContext(trace_id)
    from src.engines.tts.dubbing_engine import your_tts
    
    chunk_path = context.get_path(f"seg_{segment['id']}.wav")
    
    try:
        # Microsoft TTS call via your_tts
        tts_file = your_tts(
            segment['translated_text'], 
            dst_lang, 
            segment['gender'], 
            chunk_path, 
            actual_duration=segment['end'] - segment['start']
        )
        return {**segment, "tts_path": tts_file}
    except Exception as e:
        logger.error(f"TTS Error [Seg {segment['id']}]: {e}")
        return {**segment, "tts_path": None}

@celery_app.task(name="src.tasks.noop_segment_task")
def noop_segment_task(segment: Dict[str, Any]):
    return {**segment, "tts_path": None}

@celery_app.task(bind=True, name="src.tasks.merge_audio_video_task")
def merge_audio_video_task(self, segments_with_tts: List[Dict[str, Any]], prev_data: Dict[str, Any]):
    trace_id = prev_data["trace_id"]
    input_file = prev_data["input_file"]
    vocal_path = prev_data["vocal_path"]
    bg_path = prev_data["bg_path"]
    
    self.update_state(state='PROGRESS', meta={'progress': 90, 'stage': 'Final Merge'})
    logger.info(f"[{trace_id}] Stage: Final Merge (Optimized)")
    
    context = RequestContext(trace_id)
    from src.utils.media_engine import MediaEngine
    
    # 1. Determine Source Audio for slicing
    source_audio = vocal_path if (vocal_path and os.path.exists(vocal_path)) else prev_data["audio_path"]
    
    # Get total duration for the final tail slice
    probe = MediaEngine.get_probe_info(source_audio)
    total_duration = float(probe['format']['duration'])
    
    # 2. Build the timeline of audio chunks
    # We slice the original audio for the parts we keep, and use TTS for the parts we translated.
    # This is MUCH faster than pydub.overlay because it's a single pass.
    segments_with_tts.sort(key=lambda x: x['start'])
    
    audio_chunks = []
    current_time = 0.0
    
    for i, s in enumerate(segments_with_tts):
        start = s['start']
        end = s['end']
        
        # Gap between current_time and segment start (untouched background/original)
        if start > current_time + 0.001: # Small epsilon for float precision
            chunk_path = context.get_path(f"orig_gap_{i}.wav")
            MediaEngine.slice_audio(source_audio, current_time, start, chunk_path)
            audio_chunks.append(chunk_path)
            
        if s.get("action") == "TRANSLATE" and s.get("tts_path") and os.path.exists(s["tts_path"]):
            # Use Translated TTS
            audio_chunks.append(s["tts_path"])
        else:
            # Use Original Segment (Keep)
            chunk_path = context.get_path(f"orig_keep_{i}.wav")
            MediaEngine.slice_audio(source_audio, start, end, chunk_path)
            audio_chunks.append(chunk_path)
            
        current_time = end

    # Handle the remaining audio after the last segment
    if current_time < total_duration:
        chunk_path = context.get_path(f"orig_tail.wav")
        MediaEngine.slice_audio(source_audio, current_time, total_duration, chunk_path)
        audio_chunks.append(chunk_path)

    # 3. Concatenate all chunks into one final vocal track
    dubbed_vocal_path = context.get_path("dubbed_vocal_celery.wav")
    os.makedirs(os.path.dirname(dubbed_vocal_path), exist_ok=True)
    
    # Note: MediaEngine.concat_audio_files uses ffmpeg concat which is O(L)
    MediaEngine.concat_audio_files(audio_chunks, dubbed_vocal_path)
    
    # 4. Final Video Merge (Remuxing)
    from src.utils.media_engine import MediaEngine
    output_filename = f"output_{trace_id}.mp4"
    output_video_path = os.path.join("static", output_filename)
    
    # Ensure static directory exists (though it should from volume)
    os.makedirs("static", exist_ok=True)
    
    if bg_path and os.path.exists(bg_path):
        result_video = MediaEngine.merge_complex(input_file, dubbed_vocal_path, bg_path, output_video_path)
    else:
        result_video = MediaEngine.merge_audio_video(input_file, dubbed_vocal_path, output_video_path)
        
    logger.info(f"[{trace_id}] Pipeline Complete: {result_video}")
    
    # 3. Copy original video to static for preview (DO THIS BEFORE CLEANUP)
    original_filename = f"input_{trace_id}.mp4"
    original_static_path = os.path.join("static", original_filename)
    try:
        shutil.copy2(input_file, original_static_path)
        logger.info(f"[{trace_id}] Original video copied to static for preview")
    except Exception as e:
        logger.warning(f"Failed to copy original video to static: {e}")
        original_filename = os.path.basename(input_file)

    # 4. Cleanup Sandbox
    try:
        context.cleanup()
    except Exception as e:
        logger.warning(f"Cleanup failed for {trace_id}: {e}")

    return {
        "status": "success",
        "video_url": output_filename,
        "original_video_url": original_filename,
        "trace_id": trace_id
    }
