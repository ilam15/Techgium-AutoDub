#@title hide

from utils import language_dict
import math
import torch
import gc
import time
import threading
from faster_whisper import WhisperModel
import os
import re
import uuid
import shutil
from static_ffmpeg import add_paths
add_paths()
from speaker_detection import SpeakerAnalyzer, get_speaker_for_segment
from concurrent.futures import ThreadPoolExecutor
from media_engine import MediaEngine
import logging

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(trace_id)s] %(message)s'
)
logger = logging.getLogger("AutoDub")

def get_log_extra(trace_id=None):
    return {"trace_id": trace_id or "GLOBAL"}

# Initialize MediaEngine with static_ffmpeg path
try:
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe:
        MediaEngine.set_ffmpeg_path(ffmpeg_exe)
        print(f"MediaEngine using FFmpeg at: {ffmpeg_exe}")
except Exception as e:
    print(f"Warning: Could not set MediaEngine ffmpeg path: {e}")

# Model Management Layer with Production Pooling & Idle Timeout
class InferenceModelManager:
    _instance = None
    _lock = threading.Lock()
    _whisper_model = None
    _speaker_analyzer = None
    _last_access_time = 0
    _idle_timeout = 300 # 5 minutes

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(InferenceModelManager, cls).__new__(cls)
                    cls._instance._start_cleanup_thread()
        return cls._instance

    def _start_cleanup_thread(self):
        def cleanup_loop():
            while True:
                time.sleep(60)
                if self._last_access_time > 0 and (time.time() - self._last_access_time) > self._idle_timeout:
                    if self._whisper_model or self._speaker_analyzer:
                        logger.info("Idle timeout reached. Offloading models to free resources...", extra=get_log_extra())
                        self.clear_cache()
        
        t = threading.Thread(target=cleanup_loop, daemon=True)
        t.start()

    def get_whisper(self, device=None, compute_type=None):
        with self._lock:
            self._last_access_time = time.time()
            if self._whisper_model is None:
                device = device or ("cuda" if torch.cuda.is_available() else "cpu")
                compute_type = compute_type or ("float16" if device == "cuda" else "int8")
                logger.info(f"Initializing Whisper Model [{device}/{compute_type}]...", extra=get_log_extra())
                self._whisper_model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device=device, compute_type=compute_type)
            return self._whisper_model

    def get_analyzer(self, hf_token=None):
        with self._lock:
            self._last_access_time = time.time()
            if self._speaker_analyzer is None:
                logger.info("Initializing Speaker Analyzer...", extra=get_log_extra())
                self._speaker_analyzer = SpeakerAnalyzer(hf_token=hf_token)
            return self._speaker_analyzer

    def clear_cache(self):
        """Strategic cleanup to prevent VRAM fragmentation."""
        with self._lock:
            self._whisper_model = None
            self._speaker_analyzer = None
            self._last_access_time = 0
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

model_manager = InferenceModelManager()

# Legacy wrappers for backward compatibility
def get_whisper_model(device, compute_type):
    return model_manager.get_whisper(device, compute_type)

def get_speaker_analyzer(hf_token=None):
    return model_manager.get_analyzer(hf_token=hf_token)


def get_language_name(lang_code):
    global language_dict
    # Iterate through the language dictionary
    for language, details in language_dict.items():
        # Check if the language code matches
        if details["lang_code"] == lang_code:
            return language  # Return the language name
    return lang_code

def clean_file_name(file_path):
    # Get the base file name and extension
    file_name = os.path.basename(file_path)
    file_name, file_extension = os.path.splitext(file_name)

    # Replace non-alphanumeric characters with an underscore
    cleaned = re.sub(r'[^a-zA-Z\d]+', '_', file_name)

    # Remove any multiple underscores
    clean_file_name = re.sub(r'_+', '_', cleaned).strip('_')

    # Generate a random UUID for uniqueness
    random_uuid = uuid.uuid4().hex[:6]

    # Combine cleaned file name with the original extension
    clean_file_path = os.path.join(os.path.dirname(file_path), clean_file_name + f"_{random_uuid}" + file_extension)

    return clean_file_path



def format_segments(segments):
    saved_segments = list(segments)
    sentence_timestamp = []
    words_timestamp = []
    speech_to_text = ""

    for i in saved_segments:
        temp_sentence_timestamp = {}
        # Store sentence information in sentence_timestamp
        text = i.text.strip()
        sentence_id = len(sentence_timestamp)  # Get the current index for the new entry
        sentence_timestamp.append({
            "id": sentence_id,  # Use the index as the id
            "text": text,
            "start": i.start,
            "end": i.end,
            "words": []  # Initialize words as an empty list within the sentence
        })
        speech_to_text += text + " "

        # Process each word in the sentence
        for word in i.words:
            word_data = {
                "word": word.word.strip(),
                "start": word.start,
                "end": word.end
            }

            # Append word timestamps to the sentence's word list
            sentence_timestamp[sentence_id]["words"].append(word_data)

            # Optionally, add the word data to the global words_timestamp list
            words_timestamp.append(word_data)

    return sentence_timestamp, words_timestamp, speech_to_text

def combine_word_segments(words_timestamp, max_words_per_subtitle=8, min_silence_between_words=0.5):
    if max_words_per_subtitle<=1:
        max_words_per_subtitle=1
    before_translate = {}
    id = 1
    text = ""
    start = None
    end = None
    word_count = 0
    last_end_time = None

    for i in words_timestamp:
        try:
            word = i['word']
            word_start = i['start']
            word_end = i['end']

            # Check for sentence-ending punctuation
            is_end_of_sentence = word.endswith(('.', '?', '!'))

            # Check for conditions to create a new subtitle
            if ((last_end_time is not None and word_start - last_end_time > min_silence_between_words)
                or word_count >= max_words_per_subtitle
                or is_end_of_sentence):

                # Store the previous subtitle if there's any
                if text:
                    before_translate[id] = {
                        "text": text,
                        "start": start,
                        "end": end
                    }
                    id += 1

                # Reset for the new subtitle segment
                text = word
                start = word_start  # Set the start time for the new subtitle
                word_count = 1
            else:
                if word_count == 0:  # First word in the subtitle
                    start = word_start  # Ensure the start time is set
                text += " " + word
                word_count += 1

            end = word_end  # Update the end timestamp
            last_end_time = word_end  # Update the last end timestamp

        except KeyError as e:
            print(f"KeyError: {e} - Skipping word")
            pass

    # After the loop, make sure to add the last subtitle segment
    if text:
        before_translate[id] = {
            "text": text,
            "start": start,
            "end": end
        }

    return before_translate

def custom_word_segments(words_timestamp, min_silence_between_words=0.3, max_characters_per_subtitle=17):
    before_translate = []
    id = 1
    text = ""
    start = None
    end = None
    last_end_time = None

    i = 0
    while i < len(words_timestamp):
        word = words_timestamp[i]['word']
        word_start = words_timestamp[i]['start']
        word_end = words_timestamp[i]['end']

        # Look ahead to check if the next word (i+1) starts with a hyphen
        if i + 1 < len(words_timestamp) and words_timestamp[i + 1]['word'].startswith("-"):
            # Combine the current word and the next word (i, i+1) if next word starts with a hyphen
            combined_text = word + words_timestamp[i + 1]['word'][:]  # Skip the hyphen and combine
            combined_start_time = word_start
            combined_end_time = words_timestamp[i + 1]['end']

            i += 1  # Skip the next word (i+1) since it has been combined

            # Look ahead for the next non-hyphenated word, check further if needed (i+2, i+3, etc.)
            while i + 1 < len(words_timestamp) and words_timestamp[i + 1]['word'].startswith("-"):
                combined_text += words_timestamp[i + 1]['word'][:]  # Add word excluding hyphen
                combined_end_time = words_timestamp[i + 1]['end']
                i += 1  # Skip the next hyphenated word

        else:
            # No hyphen at the next word, just take the current word
            combined_text = word
            combined_start_time = word_start
            combined_end_time = word_end

        # Check if the combined text exceeds the maximum character limit
        if len(text) + len(combined_text) > max_characters_per_subtitle:
            # If accumulated text is non-empty, store it as a subtitle
            if text:
                before_translate.append({
                    "word": text.strip(),
                    "start": start,
                    "end": end
                })
                id += 1
            # Start a new subtitle with the combined text
            text = combined_text
            start = combined_start_time
        else:
            # Accumulate text
            if not text:
                start = combined_start_time
            text += " " + combined_text

        # Update the end timestamp
        end = combined_end_time
        last_end_time = end

        # Move to the next word
        i += 1

    # Add the final subtitle segment if text is not empty
    if text:
        before_translate.append({
            "word": text.strip(),
            "start": start,
            "end": end
        })

    return before_translate



def convert_time_to_srt_format(seconds):
    """ Convert seconds to SRT time format (HH:MM:SS,ms) """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"
def write_subtitles_to_file(subtitles, filename="subtitles.srt"):

    # Open the file with UTF-8 encoding
    with open(filename, 'w', encoding='utf-8') as f:
        for id, entry in subtitles.items():
            # Write the subtitle index
            f.write(f"{id}\n")
            if entry['start'] is None or entry['end'] is None:
              print(id)
            # Write the start and end time in SRT format
            start_time = convert_time_to_srt_format(entry['start'])
            end_time = convert_time_to_srt_format(entry['end'])
            f.write(f"{start_time} --> {end_time}\n")

            # Write the text and speaker information
            f.write(f"{entry['text']}\n\n")


def word_level_srt(words_timestamp, srt_path="world_level_subtitle.srt",shorts=False):
    punctuation_pattern = re.compile(r'[.,!?;:"\–—_~^+*|]')
    with open(srt_path, 'w', encoding='utf-8') as srt_file:
        for i, word_info in enumerate(words_timestamp, start=1):
            start_time = convert_time_to_srt_format(word_info['start'])
            end_time = convert_time_to_srt_format(word_info['end'])
            word=word_info['word']
            word =re.sub(punctuation_pattern, '', word)
            if word.strip() == 'i':
                word = "I"
            if shorts==False:
              word=word.replace("-","")
            srt_file.write(f"{i}\n{start_time} --> {end_time}\n{word}\n\n")


def generate_srt_from_sentences(sentence_timestamp, srt_path="default_subtitle.srt"):
    with open(srt_path, 'w', encoding='utf-8') as srt_file:
        for index, sentence in enumerate(sentence_timestamp):
            start_time = convert_time_to_srt_format(sentence['start'])
            end_time = convert_time_to_srt_format(sentence['end'])
            speaker = sentence.get('speaker', 'SPEAKER_00')
            gender = sentence.get('gender', 'Male')
            srt_file.write(f"{index + 1}\n{start_time} --> {end_time}\n<S:{speaker}|G:{gender}> {sentence['text']}\n\n")

def get_audio_file(uploaded_file):
    global temp_folder
    # Optimize: Use MediaEngine to extract 16k mono wav directly for ASR
    # This avoids additional resampling passes during transcription
    source_name = os.path.basename(uploaded_file)
    output_path = os.path.join(temp_folder, f"{os.path.splitext(source_name)[0]}_asr.wav")
    output_path = clean_file_name(output_path)
    
    print(f"Extracting ASR-friendly audio to {output_path}...")
    
    # We save to file here because WhisperModel.transcribe currently takes a path in this app
    with open(output_path, "wb") as f:
        for chunk in MediaEngine.extract_audio_stream(uploaded_file):
            f.write(chunk)
            
    return output_path

def whisper_subtitle(uploaded_file, Source_Language, max_words_per_subtitle=8, hf_token=None):
    global language_dict, subtitle_folder
    
    # Model configuration
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    # Extract audio to memory once
    print("Extracting audio to memory...")
    audio_data = MediaEngine.extract_audio_numpy(uploaded_file)
    
    # Run Diarization and ASR in parallel
    print("Starting ASR and Diarization in parallel...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        # ASR task
        def run_asr():
            model = get_whisper_model(device, compute_type)
            lang = None if Source_Language == "Automatic" else language_dict[Source_Language]['lang_code']
            return model.transcribe(audio_data, word_timestamps=True, language=lang)
        
        # Diarization task
        def run_diarization():
            analyzer = get_speaker_analyzer(hf_token=hf_token)
            return analyzer.analyze_audio(audio_data)
        
        asr_future = executor.submit(run_asr)
        diar_future = executor.submit(run_diarization)
        
        # Wait for both
        segments, info = asr_future.result()
        speaker_turns, speaker_genders = diar_future.result()

    src_lang = get_language_name(info.language) if Source_Language == "Automatic" else Source_Language
    
    # 3. Format & Align (Architecture P2)
    sentence_timestamp, words_timestamp, text = format_segments(segments)
    
    # Apply high-precision word-level speaker assignment
    if speaker_turns:
        logger.info("Applying word-level speaker alignment...", extra=get_log_extra())
        # Assign speakers to each word first
        for word in words_timestamp:
            word['speaker'] = get_speaker_for_segment(word['start'], word['end'], speaker_turns)
            word['gender'] = speaker_genders.get(word['speaker'], "Male")
            
        # Re-derive sentence speakers from word majority
        for sentence in sentence_timestamp:
            # Filter words for this sentence
            sentence_words = [w for w in words_timestamp if w['start'] >= sentence['start'] and w['end'] <= sentence['end']]
            if sentence_words:
                # Majority vote for speaker
                from collections import Counter
                speakers = [w['speaker'] for w in sentence_words]
                sentence['speaker'] = Counter(speakers).most_common(1)[0][0]
                sentence['gender'] = speaker_genders.get(sentence['speaker'], "Male")
            else:
                # Fallback to direct segment lookup
                sentence['speaker'] = get_speaker_for_segment(sentence['start'], sentence['end'], speaker_turns)
                sentence['gender'] = speaker_genders.get(sentence['speaker'], "Male")
    else:
        logger.warning("No diarization data available. Using single speaker fallback.", extra=get_log_extra())
        for sentence in sentence_timestamp:
            sentence['speaker'] = "SPEAKER_00"
            sentence['gender'] = "Male"

    word_segments = combine_word_segments(words_timestamp, max_words_per_subtitle=max_words_per_subtitle, min_silence_between_words=0.5)
    shorts_segments = custom_word_segments(words_timestamp, min_silence_between_words=0.3, max_characters_per_subtitle=17)
    
    # setup srt file names
    base_name = os.path.basename(uploaded_file).rsplit('.', 1)[0][:30]
    save_name = f"{subtitle_folder}/{base_name}_{src_lang}.srt"
    original_srt_name = clean_file_name(save_name)
    original_txt_name = original_srt_name.replace(".srt", ".txt")
    word_level_srt_name = original_srt_name.replace(".srt", "_word_level.srt")
    customize_srt_name = original_srt_name.replace(".srt", "_customize.srt")
    shorts_srt_name = original_srt_name.replace(".srt", "_shorts.srt")

    generate_srt_from_sentences(sentence_timestamp, srt_path=original_srt_name)
    word_level_srt(words_timestamp, srt_path=word_level_srt_name)
    word_level_srt(shorts_segments, srt_path=shorts_srt_name, shorts=True)
    write_subtitles_to_file(word_segments, filename=customize_srt_name)
    
    with open(original_txt_name, 'w', encoding='utf-8') as f1:
        f1.write(text)
    
    return original_srt_name, customize_srt_name, word_level_srt_name, shorts_srt_name, original_txt_name, src_lang

from utils import language_dict
import pysrt
from deep_translator import GoogleTranslator

def translate_text(text, Source_Language, Destination_Language, max_retries=3):
    """
    Translates the given text using GoogleTranslator, preserving speaker/gender tags.
    Implements retry logic with exponential backoff for connection errors.
    """
    # If source and destination are the same, return original text
    if Source_Language == Destination_Language:
        return text
    
    source_language = language_dict[Source_Language]['lang_code']
    target_language = language_dict[Destination_Language]['lang_code']

    # Adjust for specific language codes
    if Destination_Language == "Chinese":
        target_language = 'zh-CN'
    
    # Skip translation if language codes are the same
    if source_language == target_language:
        return text

    # Extract tags: <S:SPEAKER_00|G:Male> Text
    tag_match = re.match(r'(<S:.*?\|G:.*?>) (.*)', text)
    if tag_match:
        tag = tag_match.group(1)
        actual_text = tag_match.group(2)
    else:
        tag = ""
        actual_text = text

    if not actual_text.strip():
        return text
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            translator = GoogleTranslator(source=source_language, target=target_language)
            translation = translator.translate(actual_text.strip())
            
            if tag:
                # Ensure the tag is preserved exactly as it was
                return f"{tag} {str(translation)}"
            else:
                return str(translation)
                
        except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5s, 1s, 2s
                print(f"Connection error on attempt {attempt + 1}/{max_retries}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Translation failed after {max_retries} attempts: {e}. Returning original text.")
                # Return original text with tag if present
                return text
                
        except Exception as e:
            print(f"Translation error: {e}. Returning original text.")
            return text
    
    return text

def translate_chunk(subtitle, Source_Language, Destination_Language):
    try:
        translated_text = translate_text(subtitle.text, Source_Language, Destination_Language)
        return translated_text
    except Exception as e:
        print(f"Translation failed for chunk: {e}")
        return subtitle.text

# Persistent Translation Cache (Architecture P1)
_translation_cache = {}

def translate_subtitle(subtitles, Source_Language, Destination_Language):
    """
    Translates subtitles using robust ID-based batching.
    Extracts speaker/gender tags before translation to prevent mangling.
    """
    global language_dict, _translation_cache
    if Source_Language == Destination_Language:
        return subtitles, " ".join([s.text for s in subtitles])

    logger.info(f"ID-Batch translating {len(subtitles)} segments with tag-shielding...", extra=get_log_extra())
    
    # 1. Configuration
    batch_size = 15 
    batches = [subtitles[i:i + batch_size] for i in range(0, len(subtitles), batch_size)]
    
    translated_texts = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        def process_batch(batch_subs):
            # Extract tags: <S:XX|G:XX> Text -> (tag, text)
            tag_map = {}
            tagged_lines = []
            
            for idx, sub in enumerate(batch_subs):
                match = re.match(r'(<S:.*?\|G:.*?>) (.*)', sub.text)
                if match:
                    tag_map[idx] = match.group(1)
                    actual_text = match.group(2)
                else:
                    tag_map[idx] = ""
                    actual_text = sub.text
                
                # Wrap ONLY the actual text in protection IDs
                tagged_lines.append(f"[#{idx}#] {actual_text} [#{idx}#]")
            
            combined_text = "\n".join(tagged_lines)
            # Use raw translation on the protected block
            translated_block = translate_text(combined_text, Source_Language, Destination_Language)
            
            # Extract by ID and re-attach tags
            results = []
            for idx in range(len(batch_subs)):
                pattern = rf"\[#{idx}#\](.*?)(?=\[#{idx}#\]|$)"
                match = re.search(pattern, translated_block, re.DOTALL)
                if match:
                    cleaned_translation = match.group(1).strip()
                    # Re-attach the shielded tag
                    if tag_map[idx]:
                        results.append(f"{tag_map[idx]} {cleaned_translation}")
                    else:
                        results.append(cleaned_translation)
                else:
                    results.append(batch_subs[idx].text)
            return results

        batch_results = list(executor.map(process_batch, batches))
        for res in batch_results:
            translated_texts.extend(res)

    store_text = ""
    for i in range(min(len(subtitles), len(translated_texts))):
        subtitles[i].text = translated_texts[i]
        store_text += translated_texts[i] + " "

    return subtitles, store_text


# #@title Using Gradio Interface
# def subtitle_maker(Audio_or_Video_File,Source_Language,Destination_Language,Gender='Male',recover_music=False,make_video=False,max_words_per_subtitle=8):
#   try:
#     default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=whisper_subtitle(Audio_or_Video_File,Source_Language,max_words_per_subtitle=max_words_per_subtitle)
#   except Exception as e:
#     print(f"Error in whisper_subtitle: {e}")
#     default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=None,None,None,None,None,None
#   global subtitle_folder
#   # print(src_lang)
#   dubb_voice=None
#   if src_lang!=Destination_Language:
#     subtitles = pysrt.open(default_srt_path, encoding='utf-8')
#     translated_subtitles, _ = translate_subtitle(subtitles, src_lang, Destination_Language)
#     tra_srt_name=os.path.basename(default_srt_path).replace(".srt",f"_{Destination_Language}.srt")
#     output_srt_path=f"{subtitle_folder}/{tra_srt_name}"
#     translated_subtitles.save(output_srt_path, encoding='utf-8')
#     dubb_voice=dubbing(output_srt_path,Destination_Language,gender=Gender)
#   else:
#     output_srt_path=default_srt_path
#     dubb_voice=dubbing(output_srt_path,Destination_Language,gender=Gender)
#   if recover_music:
#     dubb_voice=recover_audio(Audio_or_Video_File, dubb_voice)
#   new_video=None
#   if make_video:
#       new_video=video_edit(Audio_or_Video_File, dubb_voice)
#   if src_lang!=Destination_Language:
#     try:
#       default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=whisper_subtitle(dubb_voice,Destination_Language,max_words_per_subtitle=max_words_per_subtitle)
#     except Exception as e:
#       default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=None,None,None,None,None,None

#   # return dubb_voice,default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,new_video
#   return dubb_voice,shorts_srt_name,word_level_srt_path,new_video


























#@title Generate Audio File From Subtitle
# from tqdm.notebook import tqdm
from tqdm import tqdm
import subprocess
import json
import pysrt
import os
from pydub import AudioSegment
import shutil
import uuid
import re
import time

# os.chdir(install_path)

from kokoro_app import single_tts

from microsoft_tts import edge_tts_pipeline
def tts(text,Language='English',Gender='Male',speed=1.0,translate_text_flag=False, no_silence=True, long_sentence=True):
    voice_name=None
    tts_save_path=''
    edge_save_path = edge_tts_pipeline(text, Language,voice_name, Gender, translate_text_flag=translate_text_flag,
                                        no_silence=no_silence, speed=speed, tts_save_path=tts_save_path,
                                        long_sentence=long_sentence)
    return edge_save_path
import librosa
import soundfile as sf
def edge_silence_remove(audio_path):
  y, sr = librosa.load(audio_path)
  # Trim leading and trailing silence
  y_trimmed, index = librosa.effects.trim(y, top_db=30)
  save_path=audio_path.replace(".wav","_no_edge_silence.wav")
  sf.write(save_path, y_trimmed, sr)
  return save_path



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
        tts_path, _, _, _, _ = single_tts(text, Language=norm_lang, voice=voice_name, speed=speed)
        if tts_path is None:
            tts_model = "Microsoft TTS"
            tts_path = tts(text, Language=lang, speed=speed, Gender=gender)
        else:
            tts_path = edge_silence_remove(tts_path)
    else:
        tts_path = tts(text, Language=lang, speed=speed, Gender=gender)

    # 3. Elastic Speed Engine (Architecture P1)
    tts_audio = AudioSegment.from_file(tts_path)
    tts_duration = len(tts_audio)
    
    if actual_duration > 0:
        # Avoid robotic speedup (> 1.25x)
        raw_speed_factor = tts_duration / actual_duration
        safe_speed_factor = min(raw_speed_factor, 1.25)
        
        if raw_speed_factor > 1.05: # Only re-generate if > 5% difference
            # logger.info(f"Elastic Sync: Required {raw_speed_factor:.2f}x | Capping at {safe_speed_factor:.2f}x")
            if tts_model == "Kokoro TTS":
                tts_path, _, _, _, _ = single_tts(text, Language=norm_lang, voice=voice_name, speed=safe_speed_factor)
                if tts_path: tts_path = edge_silence_remove(tts_path)
            else:
                tts_path = tts(text, Language=lang, speed=safe_speed_factor, Gender=gender)

    shutil.copy(tts_path, audio_path)




import datetime
def get_current_time():
    # Return current time as a string in the format HH_MM_AM/PM
    return datetime.datetime.now().strftime("%I_%M_%p")

def get_subtitle_Dub_path(srt_file_path,Language="en"):
  file_name = os.path.splitext(os.path.basename(srt_file_path))[0]
  if not os.path.exists(f"{base_path}/TTS_DUB"):
    os.mkdir(f"{base_path}/TTS_DUB")
  random_string = str(uuid.uuid4())[:6]
  new_path=f"{base_path}/TTS_DUB/{file_name}_{Language}_{get_current_time()}_{random_string}.wav"
  return new_path








def clean_srt(input_path):
    file_name = os.path.basename(input_path)
    output_folder = f"{base_path}/save_srt"
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    output_path = f"{output_folder}/{file_name}"

    def clean_srt_line(text):
        bad_list = ["[", "]", "♫", "\n"]
        for i in bad_list:
            text = text.replace(i, "")
        return text.strip()

    # Load the subtitle file
    subs = pysrt.open(input_path)

    # Iterate through each subtitle and print its details
    with open(output_path, "w", encoding='utf-8') as file:
        for sub in subs:
            file.write(f"{sub.index}\n")
            file.write(f"{sub.start} --> {sub.end}\n")
            file.write(f"{clean_srt_line(sub.text)}\n")
            file.write("\n")
        file.close()
    # print(f"Clean SRT saved at: {output_path}")
    return output_path
# Example usage






class SRTDubbing:
    def __init__(self):
        pass

    @staticmethod
    def text_to_speech_srt(text, audio_path, language, actual_duration,gender='Male',tts_model="Kokoro TTS",voice_name="af_heart"):
        # Use unique temp filenames to avoid race conditions in parallel execution
        unique_id = uuid.uuid4().hex
        tts_filename = f"{base_path}/temp_{unique_id}.wav"
        
        try:
            your_tts(text,language,gender,tts_filename,actual_duration,speed=1.0,tts_model=tts_model,voice_name=voice_name)
            
            if not os.path.exists(tts_filename):
                print(f"Warning: TTS failed to generate file for text: {text[:20]}...")
                return

            # Check the duration of the generated TTS audio
            tts_audio = AudioSegment.from_file(tts_filename)
            tts_duration = len(tts_audio)

            if actual_duration == 0:
                # If actual duration is zero, use the original TTS audio without modifications
                shutil.move(tts_filename, audio_path)
                return
            
            # If TTS audio duration is longer than actual duration, speed up the audio
            if tts_duration > actual_duration:
                speedup_factor = tts_duration / actual_duration
                speedup_filename = f"{base_path}/speedup_temp_{unique_id}.wav"
                # Use ffmpeg to change audio speed
                # Silence ffmpeg output to reduce log clutter
                subprocess.run([
                    "ffmpeg",
                    "-i", tts_filename,
                    "-filter:a", f"atempo={speedup_factor}",
                    speedup_filename,
                    "-y"
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Replace the original TTS audio with the sped-up version
                shutil.move(speedup_filename, audio_path)
                
            elif tts_duration < actual_duration:
                # If TTS audio duration is less than actual duration, add silence to match the duration
                silence_gap = actual_duration - tts_duration
                silence = AudioSegment.silent(duration=int(silence_gap), frame_rate=24000)
                new_audio = tts_audio + silence

                # Save the new audio with added silence
                new_audio.export(audio_path, format="wav")
            else:
                # If TTS audio duration is equal to actual duration, use the original TTS audio
                shutil.move(tts_filename, audio_path)
                
        except Exception as e:
            print(f"Error in text_to_speech_srt: {e}")
        finally:
            # Clean up temp file if it still exists (e.g. was used for input but not moved)
            if os.path.exists(tts_filename):
                try:
                    os.remove(tts_filename)
                except:
                    pass

    @staticmethod
    def make_silence(pause_time, pause_save_path):
        silence = AudioSegment.silent(duration=pause_time, frame_rate=24000)
        silence.export(pause_save_path, format="wav")
        return pause_save_path

    @staticmethod
    def create_folder_for_srt(srt_file_path, base_dir=None):
        srt_base_name = os.path.splitext(os.path.basename(srt_file_path))[0]
        random_uuid = str(uuid.uuid4())[:4]
        # Respect request-sandbox if provided
        parent_dir = base_dir if base_dir else os.path.abspath(os.path.join(base_path, "dummy"))
        os.makedirs(parent_dir, exist_ok=True)
        folder_path = os.path.join(parent_dir, f"{srt_base_name}_{random_uuid}")
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    @staticmethod
    def concatenate_audio_files(audio_paths, output_path):
        concatenated_audio = AudioSegment.silent(duration=0)
        for audio_path in audio_paths:
            audio_segment = AudioSegment.from_file(audio_path)
            concatenated_audio += audio_segment
        concatenated_audio.export(output_path, format="wav")

    def srt_to_dub(self, srt_file_path, dub_save_path, language='English', gender='Male', tts_model="Kokoro TTS", voice_name="af_heart", sandbox_dir=None):
        result = self.read_srt_file(srt_file_path)
        new_folder_path = self.create_folder_for_srt(srt_file_path, base_dir=sandbox_dir)
        join_path = []
        
        print(f"Generating TTS for {len(result)} segments...")
        
        with ThreadPoolExecutor(max_workers=10) as executor: 
            futures = []
            for index, i in enumerate(result):
                text = i['text']
                actual_duration = i['end_time'] - i['start_time']
                pause_time = i['pause_time']
                speaker_gender = i.get('gender', gender)
                
                silent_path = f"{new_folder_path}/pause_{index}.wav"
                self.make_silence(pause_time, silent_path)
                
                tts_path = f"{new_folder_path}/tts_{index}.wav"
                future = executor.submit(
                    self.text_to_speech_srt, 
                    text, tts_path, language, actual_duration, 
                    gender=speaker_gender, tts_model=tts_model, voice_name=voice_name
                )
                futures.append((index, future, silent_path, tts_path))

            for index, future, silent_path, tts_path in futures:
                try:
                    future.result()
                    join_path.append(silent_path)
                    if os.path.exists(tts_path):
                        join_path.append(tts_path)
                except Exception as e:
                    print(f"Error in TTS segment {index}: {e}")

        MediaEngine.concat_audio_files(join_path, dub_save_path)
        
        # Cleanup
        try:
            shutil.rmtree(new_folder_path)
        except:
            pass
        return dub_save_path

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

        with open("entries.json", "w") as file:
            json.dump(entries, file, indent=4)
        return entries


def dubbing(srt_file_path, langauge, gender, tts_model="Kokoro TTS", voice_name="af_heart", sandbox_dir=None):
    srt_dubbing = SRTDubbing()
    dub_save_path = get_subtitle_Dub_path(srt_file_path, langauge)
    srt_dubbing.srt_to_dub(srt_file_path, dub_save_path, langauge, gender=gender, tts_model=tts_model, voice_name=voice_name, sandbox_dir=sandbox_dir)
    return dub_save_path

import os
import shutil
import subprocess
from pydub import AudioSegment

def separate_audio(source_path):
    try:
        global base_path
        save_at = os.path.join(base_path, "audio_data")
        os.makedirs(save_at, exist_ok=True)

        # Use a local temporary folder to avoid conflicts
        temp_folder = os.path.join(base_path, "temp", "audio_separate")
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)

        os.makedirs(temp_folder, exist_ok=True)

        # Run the audio separator command
        command = f'audio-separator "{source_path}" --model_filename UVR-MDX-NET-Inst_HQ_3.onnx --output_dir "{temp_folder}"'
        result = subprocess.run(command, shell=True)
        vocal_path, noise_path = None, None

        if result.returncode == 0:  # Check if the command was successful
            for file_name in os.listdir(temp_folder):
                if "instrumental" in file_name.lower():
                    noise_path = save_processed_file(file_name, temp_folder, save_at, source_path, "noise")

                if "vocals" in file_name.lower():
                    vocal_path = save_processed_file(file_name, temp_folder, save_at, source_path, "vocals")

            # Clean up temporary folder after processing
            shutil.rmtree(temp_folder)
        else:
            print("Audio separation failed.")

        return vocal_path, noise_path

    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

def save_processed_file(file_name, temp_folder, save_at, source_path, file_type):
    try:
        source_base_name = os.path.splitext(os.path.basename(source_path))[0]
        output_file_name = f"{source_base_name}_{file_type}.wav"
        output_file_path = os.path.join(save_at, output_file_name)

        input_file_path = os.path.join(temp_folder, file_name)
        if input_file_path.endswith(".flac"):
            # Convert FLAC to WAV
            audio = AudioSegment.from_file(input_file_path, format="flac")
            audio.export(output_file_path, format="wav")
            print(f"Saved {file_type} to {output_file_path}")
        else:
            shutil.copy(input_file_path, output_file_path)
            print(f"Copied {file_type} to {output_file_path}")

        return output_file_path
    except Exception as e:
        print(f"Error processing file {file_name}: {e}")
        return None

# base_path="/content/"
from pydub import AudioSegment
import os

def recover_audio(input_file, tts_path):
    # Separate the input audio to get the background audio
    _, background_audio_path = separate_audio(input_file)

    if background_audio_path is None:
        print("Warning: Could not separate background audio. Using TTS audio only.")
        return tts_path

    # Load the background and TTS audio
    background_audio = AudioSegment.from_file(background_audio_path)
    tts_audio = AudioSegment.from_file(tts_path)

    # Calculate the durations of both audio files
    background_duration = len(background_audio)
    tts_duration = len(tts_audio)

    # Align the durations by adding silence to the shorter audio
    if tts_duration >= background_duration:
        silence_duration = tts_duration - background_duration
        background_audio += AudioSegment.silent(duration=silence_duration)
    else:
        silence_duration = background_duration - tts_duration
        tts_audio += AudioSegment.silent(duration=silence_duration)

    # Overlay the TTS audio on the background audio
    # background_audio = background_audio - 25
    mixed_audio = tts_audio.overlay(background_audio)

    # Prepare the output file path
    base_folder = os.path.dirname(background_audio_path)
    tts_base_name = os.path.splitext(os.path.basename(tts_path))[0]
    output_file = os.path.join(base_folder, f"{tts_base_name}_recover.wav")

    # Export the final audio
    mixed_audio.export(output_file, format="wav")

    return output_file


# recovered_audio = recover_audio("/content/video.mp4", "/content/tts.wav")
# print(f"Recovered audio saved at: {recovered_audio}")



def video_edit(video_path, new_audio_path):
    global temp_folder
    if not video_path.lower().endswith(".mp4"):
        print("Invalid video file format. Only .mp4 files are supported.")
        return

    # Extract file name without extension
    only_name = os.path.splitext(os.path.basename(new_audio_path))[0]
    output_path = f"{temp_folder}/{only_name}.mp4"

    # Call replace_audio function
    replace_video=replace_audio(video_path, new_audio_path, output_path)
    return replace_video

def replace_audio(video_path, new_audio_path, output_path):
    try:
        return MediaEngine.merge_audio_video(video_path, new_audio_path, output_path)
    except Exception as e:
        print(f"Failed to replace audio using MediaEngine: {e}")
        return None





import gradio as gr
import click

base_path="."
subtitle_folder=f"{base_path}/generated_subtitle"
temp_folder = f"{base_path}/subtitle_audio"

if not os.path.exists(subtitle_folder):
    os.makedirs(subtitle_folder, exist_ok=True)
if not os.path.exists(temp_folder):
    os.makedirs(temp_folder, exist_ok=True)

source_lang_list = ['Automatic',"English","Hindi","Bengali"]

available_language=language_dict.keys()
source_lang_list.extend(available_language)

target_lang_list = ["English","Hindi","Bengali"]
target_lang_list.extend(available_language)



def subtitle_maker(Audio_or_Video_File, Source_Language, Destination_Language, subtitle_upload=None, Gender='Male',
                   recover_music=False, make_video=False, tts_model="Kokoro TTS", voice_name="af_heart", 
                   max_words_per_subtitle=8, hf_token=None):
    
    # 0. Request Isolation setup (Architecture P0)
    request_id = uuid.uuid4().hex[:6]
    log_extra = get_log_extra(request_id)
    
    # Create request-specific sandbox
    request_sandbox = os.path.abspath(os.path.join(base_path, "temp", "requests", request_id))
    os.makedirs(request_sandbox, exist_ok=True)
    
    # Redirect global outputs for this request to sandbox
    # Note: We keep global directories as fallbacks but sandbox local work
    logger.info(f"Starting isolated request [{request_id}] for: {Audio_or_Video_File}", extra=log_extra)

    # 1. Start Parallel Pre-processing
    with ThreadPoolExecutor(max_workers=3) as executor:
        # ASR & Diarization (already parallelized inside whisper_subtitle)
        def run_main_pipeline():
            if subtitle_upload is None:
                return whisper_subtitle(Audio_or_Video_File, Source_Language, max_words_per_subtitle=max_words_per_subtitle, hf_token=hf_token)
            else:
                return subtitle_upload, None, None, None, None, Source_Language

        # Background Audio Separation (Optional)
        def run_separation():
            if recover_music:
                logger.info("Starting Audio Separation in background...", extra=log_extra)
                _, bg_path = separate_audio(Audio_or_Video_File)
                return bg_path
            return None

        pipeline_future = executor.submit(run_main_pipeline)
        bg_future = executor.submit(run_separation)

        # Wait for ASR/Diarization results
        default_srt_path, customize_srt_path, word_level_srt_path, shorts_srt_name, text_path, src_lang = pipeline_future.result()
        bg_audio_path = bg_future.result()

    # 2. Translation & Dubbing
    dubb_voice = None
    try:
        if src_lang and src_lang != Destination_Language:
            logger.info(f"Translating subtitles to {Destination_Language}...", extra=log_extra)
            subtitles = pysrt.open(default_srt_path, encoding='utf-8')
            translated_subtitles, _ = translate_subtitle(subtitles, src_lang, Destination_Language)
            
            tra_srt_name = os.path.basename(default_srt_path).replace(".srt", f"_{Destination_Language}.srt")
            output_srt_path = os.path.join(subtitle_folder, tra_srt_name)
            translated_subtitles.save(output_srt_path, encoding='utf-8')
            
            dubb_voice = dubbing(output_srt_path, Destination_Language, gender=Gender, tts_model=tts_model, voice_name=voice_name, sandbox_dir=request_sandbox)
        else:
            output_srt_path = default_srt_path
            dubb_voice = dubbing(output_srt_path, Destination_Language, gender=Gender, tts_model=tts_model, voice_name=voice_name, sandbox_dir=request_sandbox)

        # 3. Final Muxing (Intelligent & Efficient)
        result_video = None
        if make_video:
            output_video_path = os.path.join(temp_folder, f"final_{request_id}.mp4")
            if recover_music and bg_audio_path:
                logger.info("Performing one-pass complex merge with sidechain ducking...", extra=log_extra)
                # Video + Dubbed Vocals + Background Music
                result_video = MediaEngine.merge_complex(Audio_or_Video_File, dubb_voice, bg_audio_path, output_video_path)
            else:
                logger.info("Performing direct audio-video merge...", extra=log_extra)
                result_video = MediaEngine.merge_audio_video(Audio_or_Video_File, dubb_voice, output_video_path)
        
        # Optional: Generate word-level info for dubbed version for high-end players
        try:
            _, customize_srt_path, word_level_srt_path, shorts_srt_name, text_path, _ = whisper_subtitle(dubb_voice, Destination_Language, max_words_per_subtitle=max_words_per_subtitle, hf_token=hf_token)
        except Exception as e:
            logger.warning(f"Could not generate dubbed metadata: {e}", extra=log_extra)

        return dubb_voice, default_srt_path, result_video, customize_srt_path, word_level_srt_path, shorts_srt_name, text_path, result_video

    finally:
        # Laboratory-grade cleanup (Architecture P0)
        logger.info(f"Cleaning up sandbox for request [{request_id}]...", extra=log_extra)
        try:
            # We keep major outputs but dump segment fragments
            if os.path.exists(request_sandbox):
                shutil.rmtree(request_sandbox)
        except Exception as e:
            logger.error(f"Cleanup failed for {request_id}: {e}", extra=log_extra)

from huggingface_hub import list_repo_files

def get_voice_names(repo_id):
    return [os.path.splitext(file.replace("voices/", ""))[0] for file in list_repo_files(repo_id) if file.startswith("voices/")]

# lang_list = ['American English', 'British English', 'Hindi', 'Spanish', 'French', 'Italian', 'Brazilian Portuguese']
voice_names = get_voice_names("hexgrad/Kokoro-82M")

import gradio as gr

def old_ui():
    with gr.Blocks() as demo:
        # gr.Markdown("""**Note**: Avoid uploading large video files. [Max 1-2 Min Video, otherwise it will take a long time]
        # We are using [faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2) and Edge TTS""")

        with gr.Row():
            with gr.Column():
                audio_video_file = gr.File(label="Upload Audio or Video File")
                source_lang = gr.Dropdown(label="Source Language", choices=source_lang_list,  value="English")#,value="Automatic")
                target_lang = gr.Dropdown(label="Translate Into", choices=target_lang_list, value="English")
                tts_model=gr.Dropdown(label="🤖 TTS MODEl", choices=["Kokoro TTS","Edge TTS"], value="Kokoro TTS")
                voice_name = gr.Dropdown(label="🗣️ Voice", choices=voice_names, value="af_heart")
                gender = gr.Dropdown(label="Dub Voice Gender", choices=['Male', 'Female'], value="Male")
                recover_music = gr.Checkbox(label="Recover Background Music", value=False)
                make_video = gr.Checkbox(label="Make Video", value=False)
                generate_btn = gr.Button('Generate', variant='primary')
                with gr.Accordion('🎬 Others', open=False):
                  srt_file = gr.File(label="Upload Subtitle File (Optional)")

            with gr.Column():
                dub_audio = gr.Audio(label="Dub Audio", interactive=False)
                default_srt = gr.File(label="Default SRT File")
                dubbed_video = gr.Video(label="Dubbed Video")

                with gr.Accordion('🎬 Others', open=False):
                    customize_srt = gr.File(label="Customized SRT File")
                    word_level_srt = gr.File(label="Word Level SRT File")
                    shorts_srt = gr.File(label="SRT File for Shorts")
                    text_output = gr.File(label="Text Output")
                    download_video = gr.File(label="Download Video")

        generate_btn.click(
            subtitle_maker,
            inputs=[audio_video_file, source_lang, target_lang, srt_file, gender, recover_music, make_video,tts_model,voice_name],
            outputs=[dub_audio,default_srt, dubbed_video, customize_srt, word_level_srt, shorts_srt, text_output, download_video]
        )

    return demo





def temp_whisper_subtitle(Audio_or_Video_File,Source_Language,Destination_Language,max_words_per_subtitle=8):
  try:
    default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=whisper_subtitle(Audio_or_Video_File,Source_Language,max_words_per_subtitle=max_words_per_subtitle)
  except Exception as e:
    print(f"Error in whisper_subtitle: {e}")
    default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=None,None,None,None,None,None
  global subtitle_folder
  # print(src_lang)
  dubb_voice=None
  trans_srt=None
  if src_lang!=Destination_Language:
    subtitles = pysrt.open(default_srt_path, encoding='utf-8')
    translated_subtitles, _ = translate_subtitle(subtitles, src_lang, Destination_Language)
    tra_srt_name=os.path.basename(default_srt_path).replace(".srt",f"_{Destination_Language}.srt")
    trans_srt=f"{subtitle_folder}/{tra_srt_name}"
    translated_subtitles.save(trans_srt, encoding='utf-8')
  else:
    trans_srt=default_srt_path

  return default_srt_path,trans_srt,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path


def only_subtitle_ui():
    # description = """**Note**: Avoid uploading large video files. Instead, upload the audio from the video for faster processing.
    # You can find the model at [faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2)"""

    with gr.Blocks() as demo:
        # gr.Markdown("""<center><h1>Auto Subtitle Generator</h1></center>""")
        # gr.Markdown(description)

        with gr.Row():
            with gr.Column():
                file_input = gr.File(label="Upload Audio or Video File")

                source_lang = gr.Dropdown(label="Source Language", choices=source_lang_list, value="Automatic")
                target_lang = gr.Dropdown(label="Translate Into", choices=target_lang_list, value="English")


                generate_btn = gr.Button("Generate Subtitles", variant="primary")
                with gr.Accordion('other Feature', open=False):
                  max_words = gr.Number(label="Max Words Per Subtitle Segment", value=8)
            with gr.Column():
                default_srt = gr.File(label="Default SRT File")
                translated_srt = gr.File(label="Translated SRT File")
                with gr.Accordion('Other Subtitles', open=False):
                  customize_srt = gr.File(label="Customize SRT File")
                  word_level_srt = gr.File(label="Word Level SRT File")
                  shorts_srt = gr.File(label="SRT File For Shorts")
                  text_file = gr.File(label="Text File")

        generate_btn.click(
            temp_whisper_subtitle,
            inputs=[file_input, source_lang, target_lang, max_words],
            outputs=[default_srt, translated_srt, customize_srt, word_level_srt, shorts_srt, text_file]
        )

    return demo

# demo = only_subtitle_ui()
# demo.queue().launch(debug=True, share=True)


# def old_ui():
#     with gr.Blocks() as demo:
#         gr.Markdown("""**Note**: Avoid uploading large video files. [Max 1-2 Min Video, otherwise it will take a long time]
#         We are using [faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2) and Edge TTS""")

#         with gr.Row():
#             with gr.Column():
#                 audio_video_file = gr.File(label="Upload Audio or Video File")
#                 source_lang = gr.Dropdown(label="Source Language", choices=source_lang_list, value="Automatic")
#                 target_lang = gr.Dropdown(label="Translate Into", choices=target_lang_list, value="English")
#                 gender = gr.Dropdown(label="Dub Voice Gender", choices=['Male','Female'], value="Male")
#                 recover_music = gr.Checkbox(label="Recover Background Music", value=False)
#                 make_video = gr.Checkbox(label="Make Video", value=False)
#                 generate_btn = gr.Button('Generate', variant='primary')

#             with gr.Column():
#                 dub_audio = gr.Audio(label="Dub Audio", interactive=False)
#                 trans_srt = gr.File(label="Translated SRT File")
#                 word_level_srt = gr.File(label="Word Level SRT File")
#                 dubbed_video = gr.Video(label="Dubbed Video")

#         generate_btn.click(subtitle_maker, inputs=[audio_video_file, source_lang, target_lang, gender, recover_music, make_video], outputs=[dub_audio, trans_srt, word_level_srt, dubbed_video])

#     return demo


# def old_ui():
#     description = """**Note**: Avoid uploading large video files. [Max 1-2 Min Video, otherwise it will take a long time]
#     We are using [faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2) and Edge TTS"""
#     # Define Gradio inputs and outputs
#     gradio_inputs = [
#         gr.File(label="Upload Audio or Video File"),
#         gr.Dropdown(label="Source Language", choices=source_lang_list, value="Automatic"),
#         gr.Dropdown(label="Translate Into", choices=target_lang_list, value="English"),
#         gr.Dropdown(label="Dub Voice Geneder", choices=['Male','Female'], value="Male"),
#         gr.Checkbox(label="Recover Background Music",value=False),
#         gr.Checkbox(label="Make Video",value=False)
#         # gr.Number(label="Max Word Per Subtitle Segment [Useful for Vertical Videos]", value=8)
#     ]
#     gradio_outputs = [
#         gr.Audio(label="Dub Audio", show_label=True),
#         gr.File(label="Translated SRT File", show_label=True),
#         # gr.File(label="Customize SRT File", show_label=True),
#         gr.File(label="Word Level SRT File", show_label=True),
#         # gr.File(label="SRT File For Shorts", show_label=True),
#         # gr.File(label="Text File", show_label=True),
#         gr.Video(label="Dubbed Video", show_label=True)
#     ]

#     # Create Gradio interface
#     demo = gr.Interface(fn=subtitle_maker, inputs=gradio_inputs, outputs=gradio_outputs, title="Multilingual Video Dubbing",description=description)
#     return demo



@click.command()
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode.")
@click.option("--share", is_flag=True, default=False, help="Enable sharing of the interface.")
def main(debug, share):
    demo1=only_subtitle_ui()
    demo2=old_ui()
    demo = gr.TabbedInterface([demo1, demo2],["Only Subtitle","Video Dubbing"],title="MultiLang Dubbing")
    demo.queue().launch(debug=debug, share=share, server_name="0.0.0.0")


if __name__ == "__main__":
    main()
