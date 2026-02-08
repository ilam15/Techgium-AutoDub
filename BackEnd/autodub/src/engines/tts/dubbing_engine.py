import os
import re
import uuid
import json
import shutil
import datetime
import subprocess
import librosa
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor
from pydub import AudioSegment
from src.core.logger import logger
from src.core.config import settings
from src.utils.media_engine import MediaEngine
from src.services.kokoro_app import single_tts
from src.services.microsoft_tts import edge_tts_pipeline as tts

def get_current_time():
    # Return current time as a string in the format HH_MM_AM/PM
    return datetime.datetime.now().strftime("%I_%M_%p")

def get_subtitle_Dub_path(srt_file_path, Language="en"):
    file_name = os.path.splitext(os.path.basename(srt_file_path))[0]
    tts_dub_dir = os.path.join(settings.BASE_DIR, "TTS_DUB")
    if not os.path.exists(tts_dub_dir):
        os.makedirs(tts_dub_dir, exist_ok=True)
    random_string = str(uuid.uuid4())[:6]
    new_path = os.path.join(tts_dub_dir, f"{file_name}_{Language}_{get_current_time()}_{random_string}.wav")
    return new_path

def edge_silence_remove(audio_path):
    try:
        y, sr = librosa.load(audio_path)
        # Trim leading and trailing silence
        y_trimmed, index = librosa.effects.trim(y, top_db=30)
        save_path = audio_path.replace(".wav", "_no_edge_silence.wav")
        sf.write(save_path, y_trimmed, sr)
        return save_path
    except Exception as e:
        logger.warning(f"Failed to remove edge silence for {audio_path}: {e}")
        return audio_path

def your_tts(text, lang, gender, audio_path, actual_duration, speed=1.0, tts_model="Kokoro TTS", voice_name="af_heart"):
    kokoro_lang = ["English", "Hindi", "Spanish", "French", "Italian", "Portuguese", "Japanese", "Chinese"]
    
    # 1. Automatic Engine Selector (Architecture P2)
    if tts_model == "Kokoro TTS" and lang not in kokoro_lang:
        # logger.info(f"Target language '{lang}' not supported by Kokoro. Auto-switching to Microsoft TTS.")
        tts_model = "Microsoft TTS"

    # Normalize lang names for Kokoro
    lang_map = {"English": "American English", "Portuguese": "Brazilian Portuguese", "Chinese": "Mandarin Chinese"}
    norm_lang = lang_map.get(lang, lang)

    # Gender-based voice selection for Kokoro
    if tts_model == "Kokoro TTS":
        # If the user-provided voice doesn't match the detected gender, switch it
        if gender == "Female" and not voice_name.startswith("af_"):
            voice_name = "af_heart"
        elif gender == "Male" and not voice_name.startswith("am_"):
            voice_name = "am_adam"

    # 2. Initial Generation
    if tts_model == "Kokoro TTS":
        # Terminal 2 handles translation; we only synthesize here.
        tts_path, _, _, _, _ = single_tts(text, Language=norm_lang, voice=voice_name, speed=speed, translate=False)
        if tts_path is None:
            tts_model = "Microsoft TTS"
            tts_path = tts(text, Language=lang, speed=speed, Gender=gender, translate_text_flag=False)
        else:
            tts_path = edge_silence_remove(tts_path)
    else:
        # Terminal 2 handles translation; we only synthesize here.
        tts_path = tts(text, Language=lang, speed=speed, Gender=gender, translate_text_flag=False)

    # 3. Elastic Speed Engine (Architecture P1)
    if not tts_path or not os.path.exists(tts_path):
        logger.error(f"TTS generation failed to produce a file for: {text[:30]}")
        return None

    try:
        if actual_duration > 0:
            # 3. Precision Timing & Elastic Stretching (Lipsync Foundation)
            # Calculate the current duration
            tts_audio = AudioSegment.from_file(tts_path)
            current_dur_ms = len(tts_audio)
            target_dur_ms = int(actual_duration * 1000)
            
            # If difference is > 50ms, we must stretch to ensure perfect lipsync
            if abs(current_dur_ms - target_dur_ms) > 50:
                stretch_factor = current_dur_ms / target_dur_ms
                logger.info(f"⏳ Sync needed: {current_dur_ms}ms -> {target_dur_ms}ms (Raw factor: {stretch_factor:.2f}x)")
                
                # Point 7: Cap Time-Stretch Ratio
                if stretch_factor > settings.TTS_SPEED_CAP:
                    logger.warning(f"Capping speedup: {stretch_factor:.2f}x -> {settings.TTS_SPEED_CAP}x (Max Limit)")
                    stretch_factor = settings.TTS_SPEED_CAP
                elif stretch_factor < settings.TTS_SLOW_DOWN_CAP:
                     logger.warning(f"Capping slowdown: {stretch_factor:.2f}x -> {settings.TTS_SLOW_DOWN_CAP}x (Min Limit)")
                     stretch_factor = settings.TTS_SLOW_DOWN_CAP
                
                # Use FFmpeg atempo for high-quality time stretching without pitch shift
                stretched_path = tts_path.replace(".wav", "_stretched.wav")
                atempo = f"atempo={stretch_factor}"
                
                cmd = [
                    MediaEngine.FFMPEG_PATH, "-y", "-i", tts_path,
                    "-filter:a", atempo,
                    "-ar", "44100",
                    "-loglevel", "error", # Quieter logging
                    stretched_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                tts_path = stretched_path

        if tts_path and os.path.exists(tts_path):
            # Final Precision Sync (Lipsync Guard)
            # Ensures the final audio segment matches the expected duration exactly.
            # This prevents accumulative drift where small errors add up to seconds of offset.
            try:
                final_audio = AudioSegment.from_file(tts_path)
                current_len = len(final_audio)
                
                # We target milliseconds for maximum precision
                if abs(current_len - target_dur_ms) > 5 or final_audio.frame_rate != 44100: 
                    logger.info(f"📏 Finalizing Sync: {current_len}ms -> {target_dur_ms}ms (Precision padding/trim + 44.1kHz normalization)")
                    
                    # Normalize frame rate first for consistency
                    if final_audio.frame_rate != 44100:
                        final_audio = final_audio.set_frame_rate(44100)
                        
                    if current_len > target_dur_ms:
                        # FIX: Do NOT trim speech. Trimming causes word loss. 
                        # In the Overlay model, it's safer to let it bleed/overlap.
                        # We only trim if it's extremely long (e.g. > 2x original) as a safety.
                        if current_len > target_dur_ms * 2:
                            logger.warning(f"⚠️ Segment extremely long ({current_len}ms vs {target_dur_ms}ms). Trimming to 2x.")
                            final_audio = final_audio[:target_dur_ms * 2]
                    else:
                        # Pad with silence if too short (optional for overlay, but good for stability)
                        padding = AudioSegment.silent(duration=target_dur_ms - current_len, frame_rate=44100)
                        final_audio = final_audio + padding
                    
                    # FIX 3: Apply fade-in / fade-out at boundaries (Professional smoothing)
                    fade_ms = 100 
                    if len(final_audio) > fade_ms * 2:
                        final_audio = final_audio.fade_in(fade_ms).fade_out(fade_ms)
                    
                    # FIX 6: Guardrail validation
                    if len(final_audio) < target_dur_ms * 0.8:
                        logger.warning(f"⚠️ Guardrail breach (Short): {len(final_audio)}ms vs {target_dur_ms}ms.")

                    final_audio.export(audio_path, format="wav")
                else:
                    # Normalize for overlay
                    if final_audio.frame_rate != 44100:
                        final_audio = final_audio.set_frame_rate(44100)
                    
                    fade_ms = 50
                    if len(final_audio) > fade_ms * 2:
                        final_audio = final_audio.fade_in(fade_ms).fade_out(fade_ms)
                    final_audio.export(audio_path, format="wav")
            except Exception as e:
                logger.warning(f"Final duration sync failed: {e}. Falling back to raw copy.")
                shutil.copy(tts_path, audio_path)
                
            return audio_path
    except Exception as e:
        logger.error(f"Error in your_tts processing: {e}")
    
    return None

class SRTDubbing:
    def __init__(self):
        pass
    
    @staticmethod
    def convert_to_millisecond(time_str):
        if isinstance(time_str, str):
            hours, minutes, second_millisecond = time_str.split(':')
            seconds, milliseconds = second_millisecond.split(",")

            total_milliseconds = (
                int(hours) * 3600000 +
                int(minutes) * 60000 +
                int(seconds) * 1000 +
                int(milliseconds)
            )

            return total_milliseconds

    def create_folder_for_srt(self, srt_path, base_dir=None):
        name = os.path.splitext(os.path.basename(srt_path))[0]
        if not base_dir:
            base_dir = settings.TEMP_DIR
        folder = os.path.join(base_dir, f"dub_{name}_{uuid.uuid4().hex[:8]}")
        os.makedirs(folder, exist_ok=True)
        return folder

    def make_silence(self, duration_ms, output_path):
        """Generates a high-quality silent WAV file of specific duration."""
        # Use 44.1kHz to match the production mixing standard
        silence = AudioSegment.silent(duration=int(duration_ms), frame_rate=44100)
        silence.export(output_path, format="wav")

    @staticmethod
    def read_srt_file(file_path):
        entries = []
        default_start = 0
        previous_end_time = default_start
        entry_number = 1
        audio_name_template = "{}.wav"
        previous_pause_template = "{}_before_pause.wav"

        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            # print(lines)
            for i in range(0, len(lines), 4):
                time_info = re.findall(r'(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)', lines[i + 1])
                start_time = SRTDubbing.convert_to_millisecond(time_info[0][0])
                end_time = SRTDubbing.convert_to_millisecond(time_info[0][1])

                text_raw = lines[i + 2].strip()
                # Try to parse speaker/gender tags: <S:SPEAKER_00|G:Male> Text
                # Use a more robust regex that ignores case and extra spaces
                match = re.match(r'<\s*S\s*:\s*(.*?)\s*\|\s*G\s*:\s*(.*?)\s*>\s*(.*)', text_raw, re.IGNORECASE)
                if match:
                    speaker = match.group(1).strip()
                    # Standardize gender to 'Male' or 'Female'
                    gender_str = match.group(2).strip().lower()
                    gender = "Female" if "female" in gender_str or "woman" in gender_str or "பெண்" in gender_str else "Male"
                    text = match.group(3).strip()
                else:
                    speaker = "SPEAKER_00"
                    gender = "Male" # Default
                    text = text_raw

                current_entry = {
                    'entry_number': entry_number,
                    'start_time': start_time,
                    'end_time': end_time,
                    'text': text,
                    'speaker': speaker,
                    'gender': gender,
                    'pause_time': start_time - previous_end_time if entry_number != 1 else start_time - default_start,
                    'audio_name': audio_name_template.format(entry_number),
                    'previous_pause': previous_pause_template.format(entry_number),
                }

                entries.append(current_entry)
                previous_end_time = end_time
                entry_number += 1

        json_path = os.path.join(os.path.dirname(file_path), "entries.json")
        with open(json_path, "w") as file:
            json.dump(entries, file, indent=4)
        return entries

    @staticmethod
    def process_tts_audio_file(text, audio_path, actual_duration, tts_generated_path):
        """
        Post-processes a generated TTS file:
        1. Checks duration
        2. Applies SMART speed limits (avoiding chipmunk/monster effects)
        3. Moves/Saves to final location
        """
        try:
            if not os.path.exists(tts_generated_path):
                logger.warning(f"TTS file missing for: {text[:20]}")
                return

            # Check duration
            tts_audio = AudioSegment.from_file(tts_generated_path)
            tts_duration = len(tts_audio)

            if actual_duration <= 0:
                shutil.move(tts_generated_path, audio_path)
                return

            speed_factor = tts_duration / actual_duration
            
            # Smart Speed Limits (Points 7 & 10 from Config)
            # Don't speed up more than limit (unintelligible)
            # Don't slow down more than limit (unnatural)
            
            final_path = audio_path
            
            if speed_factor > settings.TTS_SPEED_CAP:
                # Audio is way too long. Cap at LIMIT and let it overflow slightly
                logger.info(f"Limiting speedup: {speed_factor:.2f}x -> {settings.TTS_SPEED_CAP}x for '{text[:15]}...'")
                speedup_factor = settings.TTS_SPEED_CAP
                
                unique_id = uuid.uuid4().hex
                speedup_filename = os.path.join(settings.TEMP_DIR, f"speedup_{unique_id}.wav")
                
                subprocess.run([
                    "ffmpeg", "-y", "-v", "error",
                    "-i", tts_generated_path,
                    "-filter:a", f"atempo={speedup_factor}",
                    speedup_filename
                ], check=True)
                
                shutil.move(speedup_filename, audio_path)
                
            elif 1.0 < speed_factor <= settings.TTS_SPEED_CAP:
                # Moderate speedup needed - do exact fit
                unique_id = uuid.uuid4().hex
                speedup_filename = os.path.join(settings.TEMP_DIR, f"speedup_{unique_id}.wav")
                
                subprocess.run([
                    "ffmpeg", "-y", "-v", "error",
                    "-i", tts_generated_path,
                    "-filter:a", f"atempo={speed_factor}",
                    speedup_filename
                ], check=True)
                
                shutil.move(speedup_filename, audio_path)
                
            elif speed_factor < settings.TTS_SLOW_DOWN_CAP:
                # Audio is too short. Don't stretch it to fill (monster voice).
                # Instead, center it or just pad with silence.
                logger.info(f"Avoiding slow-down: {speed_factor:.2f}x. Padding with silence instead.")
                silence_gap = actual_duration - tts_duration
                # Add half silence before, half after for centering
                silence_half = AudioSegment.silent(duration=int(silence_gap / 2), frame_rate=24000)
                new_audio = silence_half + tts_audio + silence_half
                
                # Ensure exact fit if rounding errors
                if len(new_audio) < actual_duration:
                    new_audio += AudioSegment.silent(duration=actual_duration - len(new_audio), frame_rate=24000)
                    
                new_audio.export(audio_path, format="wav")
                
            else:
                # speed_factor between LOW_CAP and 1.0 (slightly short)
                # Pad end with silence
                silence_gap = actual_duration - tts_duration
                silence = AudioSegment.silent(duration=int(silence_gap), frame_rate=24000)
                new_audio = tts_audio + silence
                new_audio.export(audio_path, format="wav")

        except Exception as e:
            logger.error(f"Post-processing error for '{text[:15]}': {e}")
            if os.path.exists(tts_generated_path):
                shutil.move(tts_generated_path, audio_path) # Fallback
        finally:
            if os.path.exists(tts_generated_path):
                try: os.remove(tts_generated_path) 
                except: pass

    def srt_to_dub(self, srt_file_path, dub_save_path, language='English', gender='Male', tts_model="Kokoro TTS", voice_name="af_heart", sandbox_dir=None):
        result = self.read_srt_file(srt_file_path)
        new_folder_path = self.create_folder_for_srt(srt_file_path, base_dir=sandbox_dir)
        join_path = []
        
        logger.info(f"Processing {len(result)} segments in BATCH mode...")
        
        # 1. Prepare Batch Request
        batch_items = []
        segments_map = {} # Map index to segment data
        
        for index, i in enumerate(result):
            text = i['text']
            # Determine path
            audio_path = f"{new_folder_path}/{i['audio_name']}"
            silent_path = f"{new_folder_path}/pause_{index}.wav"
            
            # Add to join path in order
            join_path.extend([silent_path, audio_path])
            
            # Generate Pause immediately (CPU bound, fast)
            self.make_silence(i['pause_time'], silent_path)
            
            # Determine if we need TTS
            temp_tts_path = os.path.join(new_folder_path, f"temp_gen_{index}.wav")
            
            # Gender switching logic
            seg_gender = i.get('gender', gender)
            # You might want to switch voice based on gender here if supported by batch
            # For now, we assume one voice for batch simplicity, OR we split batches by voice
            
            # Add to batch
            batch_items.append({
                'text': text,
                'output_path': temp_tts_path,
                'index': index
            })
            segments_map[index] = {
                'audio_path': audio_path,
                'duration': i['end_time'] - i['start_time'],
                'temp_path': temp_tts_path,
                'text': text
            }

        # 2. Execute Batch TTS (Serialized, Efficient)
        from src.services.kokoro_app import batch_tts_generation
        
        # If we need multiple voices, we should group by voice. 
        # For simplicity in this optimization step, we use the primary voice.
        # Ideally, grouping by (voice, speed) is best.
        
        logger.info(f"Sending batch of {len(batch_items)} items to Kokoro...")
        generated_files = batch_tts_generation(batch_items, Language=language, voice=voice_name)
        
        # 3. Parallel Post-Processing (Speed/Stretch)
        # Now we process the generated files in parallel because FFmpeg is independent
        logger.info("Post-processing audio (Stretching/Padding)...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for item in batch_items:
                idx = item['index']
                seg = segments_map[idx]
                
                futures.append(executor.submit(
                    self.process_tts_audio_file,
                    seg['text'],
                    seg['audio_path'],
                    seg['duration'],
                    seg['temp_path']
                ))
            
            for f in futures:
                f.result()
                
        # 4. Concatenate
        MediaEngine.concat_audio_files(join_path, dub_save_path)

def dubbing(srt_file_path, langauge, gender, tts_model="Kokoro TTS", voice_name="af_heart", sandbox_dir=None):
    srt_dubbing = SRTDubbing()
    dub_save_path = get_subtitle_Dub_path(srt_file_path, langauge)
    srt_dubbing.srt_to_dub(srt_file_path, dub_save_path, langauge, gender=gender, tts_model=tts_model, voice_name=voice_name, sandbox_dir=sandbox_dir)
    return dub_save_path
