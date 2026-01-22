# @title kokoro_app.py
# %%writefile /content/Multilingual-Dubbing/kokoro_app.py

import os
# Initalize a pipeline
try:
    from kokoro import KPipeline
    KOKORO_AVAILABLE = True
except (ImportError, AttributeError) as e:
    print(f"Warning: Kokoro TTS not available: {e}")
    print("Kokoro TTS features will be disabled. Only Microsoft TTS will be available.")
    KOKORO_AVAILABLE = False
    KPipeline = None
# from IPython.display import display, Audio
# import soundfile as sf
import os
from huggingface_hub import list_repo_files
import uuid
import re
import gc
import torch
# Initialize default pipeline
last_used_language = "a"

# Language mapping dictionary
language_map = {
    "American English": "a",
    "British English": "b",
    "Hindi": "h",
    "Spanish": "e",
    "French": "f",
    "Italian": "i",
    "Brazilian Portuguese": "p",
    "Japanese": "j",
    "Mandarin Chinese": "z"
}

# Print installation instructions if necessary
install_messages = {
    "Japanese": "pip install misaki[ja]",
    "Mandarin Chinese": "pip install misaki[zh]"
}



def update_pipeline(Language):
    """ Updates the pipeline only if the language has changed. """
    global kokoro_pipeline, last_used_language
    
    # If Kokoro is not available, skip all pipeline updates
    if not KOKORO_AVAILABLE:
        return

    # Print installation instructions if necessary
    if Language in install_messages:
        # raise gr.Error(f"To Use {Language} Install: {install_messages[Language]}",duration=10)
        # gr.Warning(f"To Use {Language} Install: {install_messages[Language]}",duration=10)
        # gr.Warning("Reverting to default English pipeline...", duration=5)
        # print(f"To use {Language} Install: {install_messages[Language]}")
        # print("Reverting to default English pipeline...")


        # Revert to default English and return immediately
        if KOKORO_AVAILABLE:
            kokoro_pipeline = KPipeline(lang_code="a")
            last_used_language = "a"
        return

    # Get language code, default to 'a' if not found
    new_lang = language_map.get(Language, "a")

    # Only update if the language is different
    if new_lang != last_used_language:
        try:
            if kokoro_pipeline is not None:
               del kokoro_pipeline
               gc.collect()
               torch.cuda.empty_cache()
            kokoro_pipeline = KPipeline(lang_code=new_lang)
            last_used_language = new_lang  # Update last used language
            # print(f"Pipeline updated to {Language} ({new_lang})")
        except Exception as e:
            print(f"Error initializing KPipeline: {e}")
            if KOKORO_AVAILABLE:
                print("Retrying with default language...")
                try:
                    kokoro_pipeline = KPipeline(lang_code="a")  # Fallback to English
                    last_used_language = "a"
                except:
                    print("Failed to initialize fallback pipeline")



def get_voice_names(repo_id):
    """Fetches and returns a list of voice names (without extensions) from the given Hugging Face repository."""
    return [os.path.splitext(file.replace("voices/", ""))[0] for file in list_repo_files(repo_id) if file.startswith("voices/")]

def create_audio_dir():
    global base_path
    audio_dir=f"{base_path}/temp/kokoro_audio"
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir,exist_ok=True)
        print(f"Created directory: {audio_dir}")
    else:
        print(f"Directory already exists: {audio_dir}")
    return audio_dir

import re

def clean_text(text):
    # Define replacement rules
    replacements = {
        "–": " ",  # Replace en-dash with space
        "-": " ",  # Replace hyphen with space
        "**": " ", # Replace double asterisks with space
        "*": " ",  # Replace single asterisk with space
        "#": " ",  # Replace hash with space
    }

    # Apply replacements
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove emojis using regex (covering wide range of Unicode characters)
    emoji_pattern = re.compile(
        r'[\U0001F600-\U0001F64F]|'  # Emoticons
        r'[\U0001F300-\U0001F5FF]|'  # Miscellaneous symbols and pictographs
        r'[\U0001F680-\U0001F6FF]|'  # Transport and map symbols
        r'[\U0001F700-\U0001F77F]|'  # Alchemical symbols
        r'[\U0001F780-\U0001F7FF]|'  # Geometric shapes extended
        r'[\U0001F800-\U0001F8FF]|'  # Supplemental arrows-C
        r'[\U0001F900-\U0001F9FF]|'  # Supplemental symbols and pictographs
        r'[\U0001FA00-\U0001FA6F]|'  # Chess symbols
        r'[\U0001FA70-\U0001FAFF]|'  # Symbols and pictographs extended-A
        r'[\U00002702-\U000027B0]|'  # Dingbats
        r'[\U0001F1E0-\U0001F1FF]'   # Flags (iOS)
        r'', flags=re.UNICODE)

    text = emoji_pattern.sub(r'', text)

    # Remove multiple spaces and extra line breaks
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def tts_file_name(text):
    global temp_folder_kokoro
    # Remove all non-alphabetic characters and convert to lowercase
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Retain only alphabets and spaces
    text = text.lower().strip()             # Convert to lowercase and strip leading/trailing spaces
    text = text.replace(" ", "_")           # Replace spaces with underscores

    # Truncate or handle empty text
    truncated_text = text[:20] if len(text) > 20 else text if len(text) > 0 else "empty"

    # Generate a random string for uniqueness
    random_string = uuid.uuid4().hex[:8].upper()

    # Construct the file name
    file_name = f"{temp_folder_kokoro}/{truncated_text}_{random_string}.wav"
    return file_name


# import soundfile as sf
import numpy as np
import wave
from pydub import AudioSegment
from pydub import silence
from pydub.silence import split_on_silence

def remove_silence_function(file_path,minimum_silence=50):
    # Extract file name and format from the provided path
    output_path = file_path.replace(".wav", "_no_silence.wav")
    audio_format = "wav"
    # Reading and splitting the audio file into chunks
    sound = AudioSegment.from_file(file_path, format=audio_format)
    dbfs = sound.dBFS
    audio_chunks = split_on_silence(sound,
                                    min_silence_len=100,
                                    silence_thresh=dbfs-16,
                                    keep_silence=minimum_silence)
    # Putting the file back together
    combined = AudioSegment.empty()
    for chunk in audio_chunks:
        combined += chunk
    combined.export(output_path, format=audio_format)
    return output_path
def generate_and_save_audio(text, Language="American English",voice="af_bella", speed=1,remove_silence=False,keep_silence_up_to=0.05):
    global kokoro_pipeline
    
    # If Kokoro is not available, return None to trigger fallback to Microsoft TTS
    if not KOKORO_AVAILABLE:
        return None, {}
    
    text=clean_text(text)
    update_pipeline(Language)
    
    # If pipeline is still None after update, return None
    if kokoro_pipeline is None:
        return None, {}
    
    generator = kokoro_pipeline(text, voice=voice, speed=speed, split_pattern=r'\n+')
    save_path=tts_file_name(text)
    # Open the WAV file for writing
    timestamps={}
    with wave.open(save_path, 'wb') as wav_file:
        # Set the WAV file parameters
        wav_file.setnchannels(1)  # Mono audio
        wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit audio)
        wav_file.setframerate(24000)  # Sample rate
        for i, result in enumerate(generator):
          gs = result.graphemes # str
        #   print(f"\n{i}: {gs}")
          ps = result.phonemes # str
          # audio = result.audio.cpu().numpy()
          audio = result.audio
          tokens = result.tokens # List[en.MToken]
          timestamps[i]={"text":gs,"words":[]}
          if Language in ["American English", "British English"]:
            for t in tokens:
                # print(t.text, repr(t.whitespace), t.start_ts, t.end_ts)
                timestamps[i]["words"].append({"word":t.text,"start":t.start_ts,"end":t.end_ts})
          audio_np = audio.numpy()  # Convert Tensor to NumPy array
          audio_int16 = (audio_np * 32767).astype(np.int16)  # Scale to 16-bit range
          audio_bytes = audio_int16.tobytes()  # Convert to bytes
          # Write the audio chunk to the WAV file
          wav_file.writeframes(audio_bytes)
    if remove_silence:
      keep_silence = int(keep_silence_up_to * 1000)
      new_wave_file=remove_silence_function(save_path,minimum_silence=keep_silence)
      return new_wave_file,timestamps
    return save_path,timestamps

def adjust_timestamps(timestamp_dict):
    adjusted_timestamps = []
    last_end_time = 0  # Tracks the last word's end time

    for segment_id in sorted(timestamp_dict.keys()):
        segment = timestamp_dict[segment_id]
        words = segment["words"]

        for word_entry in words:
            # Skip word entries with start or end time as None or 0
            if word_entry["start"] in [None, 0] and word_entry["end"] in [None, 0]:
                continue

            # Fill in None values with the last valid timestamp or use 0 as default
            word_start = word_entry["start"] if word_entry["start"] is not None else last_end_time
            word_end = word_entry["end"] if word_entry["end"] is not None else word_start  # Use word_start if end is None

            new_start = word_start + last_end_time
            new_end = word_end + last_end_time

            adjusted_timestamps.append({
                "word": word_entry["word"],
                "start": round(new_start, 3),
                "end": round(new_end, 3)
            })

        # Update last_end_time to the last word's end time in this segment
        if words:
            last_end_time = adjusted_timestamps[-1]["end"]

    return adjusted_timestamps


import string

def write_word_srt(word_level_timestamps, output_file="word.srt", skip_punctuation=True):
    with open(output_file, "w", encoding="utf-8") as f:
        index = 1  # Track subtitle numbering separately

        for entry in word_level_timestamps:
            word = entry["word"]

            # Skip punctuation if enabled
            if skip_punctuation and all(char in string.punctuation for char in word):
                continue

            start_time = entry["start"]
            end_time = entry["end"]

            # Convert seconds to SRT time format (HH:MM:SS,mmm)
            def format_srt_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                sec = int(seconds % 60)
                millisec = int((seconds % 1) * 1000)
                return f"{hours:02}:{minutes:02}:{sec:02},{millisec:03}"

            start_srt = format_srt_time(start_time)
            end_srt = format_srt_time(end_time)

            # Write entry to SRT file
            f.write(f"{index}\n{start_srt} --> {end_srt}\n{word}\n\n")
            index += 1  # Increment subtitle number

import string

def write_sentence_srt(word_level_timestamps, output_file="subtitles.srt", max_words=8, min_pause=0.1):
    subtitles = []  # Stores subtitle blocks
    subtitle_words = []  # Temporary list for words in the current subtitle
    start_time = None  # Tracks start time of current subtitle

    remove_punctuation = ['"',"—"]  # Add punctuations to remove if needed

    for i, entry in enumerate(word_level_timestamps):
        word = entry["word"]
        word_start = entry["start"]
        word_end = entry["end"]

        # Skip selected punctuation from remove_punctuation list
        if word in remove_punctuation:
            continue

        # Attach punctuation to the previous word
        if word in string.punctuation:
            if subtitle_words:
                subtitle_words[-1] = (subtitle_words[-1][0] + word, subtitle_words[-1][1])
            continue

        # Start a new subtitle block if needed
        if start_time is None:
            start_time = word_start

        # Calculate pause duration if this is not the first word
        if subtitle_words:
            last_word_end = subtitle_words[-1][1]
            pause_duration = word_start - last_word_end
        else:
            pause_duration = 0

        # **NEW FIX:** If pause is too long, create a new subtitle but ensure continuity
        if (word.endswith(('.', '!', '?')) and len(subtitle_words) >= 5) or len(subtitle_words) >= max_words or pause_duration > min_pause:
            end_time = subtitle_words[-1][1]  # Use last word's end time
            subtitle_text = " ".join(w[0] for w in subtitle_words)
            subtitles.append((start_time, end_time, subtitle_text))

            # Reset for the next subtitle, but **ensure continuity**
            subtitle_words = [(word, word_end)]  # **Carry the current word to avoid delay**
            start_time = word_start  # **Start at the current word, not None**

            continue  # Avoid adding the word twice

        # Add the current word to the subtitle
        subtitle_words.append((word, word_end))

    # Ensure last subtitle is added if anything remains
    if subtitle_words:
        end_time = subtitle_words[-1][1]
        subtitle_text = " ".join(w[0] for w in subtitle_words)
        subtitles.append((start_time, end_time, subtitle_text))

    # Function to format SRT timestamps
    def format_srt_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        sec = int(seconds % 60)
        millisec = int((seconds % 1) * 1000)
        return f"{hours:02}:{minutes:02}:{sec:02},{millisec:03}"

    # Write subtitles to SRT file
    with open(output_file, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(subtitles, start=1):
            f.write(f"{i}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n\n")

    # print(f"SRT file '{output_file}' created successfully!")


import json
import re

def fix_punctuation(text):
    # Remove spaces before punctuation marks (., ?, !, ,)
    text = re.sub(r'\s([.,?!])', r'\1', text)

    # Handle quotation marks: remove spaces before and after them
    text = text.replace('" ', '"')
    text = text.replace(' "', '"')
    text = text.replace('" ', '"')

    # Track quotation marks to add space after closing quotes
    track = 0
    result = []

    for index, char in enumerate(text):
        if char == '"':
            track += 1
            result.append(char)
            # If it's a closing quote (even number of quotes), add a space after it
            if track % 2 == 0:
                result.append(' ')
        else:
            result.append(char)
    text=''.join(result)
    return text.strip()



def make_json(word_timestamps, json_file_name):
    data = {}
    temp = []
    inside_quote = False  # Track if we are inside a quoted sentence
    start_time = word_timestamps[0]['start']  # Initialize with the first word's start time
    end_time = word_timestamps[0]['end']  # Initialize with the first word's end time
    words_in_sentence = []
    sentence_id = 0  # Initialize sentence ID

    # Process each word in word_timestamps
    for i, word_data in enumerate(word_timestamps):
        word = word_data['word']
        word_start = word_data['start']
        word_end = word_data['end']

        # Collect word info for JSON
        words_in_sentence.append({'word': word, 'start': word_start, 'end': word_end})

        # Update the end_time for the sentence based on the current word
        end_time = word_end

        # Properly handle opening and closing quotation marks
        if word == '"':
            if inside_quote:
                temp[-1] += '"'  # Attach closing quote to the last word
            else:
                temp.append('"')  # Keep opening quote as a separate entry
            inside_quote = not inside_quote  # Toggle inside_quote state
        else:
            temp.append(word)

        # Check if this is a sentence-ending punctuation
        if word.endswith(('.', '?', '!')) and not inside_quote:
            # Ensure the next word is NOT a dialogue tag before finalizing the sentence
            if i + 1 < len(word_timestamps):
                next_word = word_timestamps[i + 1]['word']
                if next_word[0].islower():  # Likely a dialogue tag like "he said"
                    continue  # Do not break the sentence yet

            # Store the full sentence for JSON and reset word collection for next sentence
            sentence = " ".join(temp)
            sentence = fix_punctuation(sentence)  # Fix punctuation in the sentence
            data[sentence_id] = {
                'text': sentence,
                'duration': end_time - start_time,
                'start': start_time,
                'end': end_time,
                'words': words_in_sentence
            }

            # Reset for the next sentence
            temp = []
            words_in_sentence = []
            start_time = word_data['start']  # Update the start time for the next sentence
            sentence_id += 1  # Increment sentence ID

    # Handle any remaining words if necessary
    if temp:
        sentence = " ".join(temp)
        sentence = fix_punctuation(sentence)  # Fix punctuation in the sentence
        data[sentence_id] = {
            'text': sentence,
            'duration': end_time - start_time,
            'start': start_time,
            'end': end_time,
            'words': words_in_sentence
        }

    # Write data to JSON file
    with open(json_file_name, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    return json_file_name




import os

def modify_filename(save_path: str, prefix: str = ""):
    directory, filename = os.path.split(save_path)
    name, ext = os.path.splitext(filename)
    new_filename = f"{prefix}{name}{ext}"
    return os.path.join(directory, new_filename)
import shutil
def save_current_data():
    global base_path
    folder=f"{base_path}/temp/transcription/"
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder,exist_ok=True)


from deep_translator import GoogleTranslator
language_map_local = {
    "American English": "en",  # No separate code, just "en"
    "British English": "en",  # No separate code, just "en"
    "Hindi": "hi",
    "Spanish": "es",
    "French": "fr",
    "Italian": "it",
    "Brazilian Portuguese": "pt-BR",
    "Japanese": "ja",
    "Mandarin Chinese": "zh-CN"
}

def translate_text(text,target_language):
    lang_code=language_map_local[target_language]
    translator = GoogleTranslator(target=lang_code)
    translation = translator.translate(text.strip())
    return str(translation)




def single_tts(text, Language="American English",voice="af_bella", speed=1,remove_silence=False,keep_silence_up_to=0.05,translate=False):
    global base_path
    if translate:
      text=translate_text(text,Language)
      # print(text)
    save_path,timestamps=generate_and_save_audio(text=text, Language=Language,voice=voice, speed=speed,remove_silence=remove_silence,keep_silence_up_to=keep_silence_up_to)
    
    # If Kokoro is not available, return None to trigger Microsoft TTS fallback
    if save_path is None:
        return None, None, None, None, None
    
    if remove_silence==False:
        if Language in ["American English", "British English"]:
            word_level_timestamps=adjust_timestamps(timestamps)
            word_level_srt = modify_filename(save_path.replace(".wav", ".srt"), prefix="word_level_")
            normal_srt = modify_filename(save_path.replace(".wav", ".srt"), prefix="sentence_")
            json_file = modify_filename(save_path.replace(".wav", ".json"), prefix="duration_")
            write_word_srt(word_level_timestamps, output_file=word_level_srt, skip_punctuation=True)
            write_sentence_srt(word_level_timestamps, output_file=normal_srt, min_pause=0.01)
            make_json(word_level_timestamps, json_file)
            save_current_data()
            folder=f"{base_path}/temp/transcription/"
            shutil.copy(save_path, folder)
            shutil.copy(word_level_srt, folder)
            shutil.copy(normal_srt, folder)
            shutil.copy(json_file, folder)
            return save_path,save_path,word_level_srt,normal_srt,json_file
    return save_path,save_path,None,None,None

from pydub import AudioSegment
from pydub.silence import detect_leading_silence
import os
def leading_remove_silence(audio_path, silence_thresh=-40, chunk_size=100,duration=2, start=True, end=True):
    try:
        base_name = os.path.basename(audio_path).replace(".wav", "_removed_silence.wav")
        output_path = os.path.join(os.path.dirname(audio_path), base_name)

        audio = AudioSegment.from_file(audio_path)
        duration_ms = len(audio)

        def detect_leading_silence(sound):
            trim_ms = 0
            while trim_ms < len(sound) and sound[trim_ms:trim_ms + chunk_size].dBFS < silence_thresh:
                trim_ms += chunk_size
            return trim_ms

        start_trim = 0
        end_trim = 0
        miliseconds = duration * 1000
        if start and duration_ms > 0:
            # Check first 10 seconds for silence, or full duration if shorter
            first_10s = audio[:min(miliseconds, duration_ms)]
            start_trim = detect_leading_silence(first_10s)

        if end and duration_ms > 0:
            # Check last 10 seconds for silence, or full duration if shorter
            last_10s = audio[-min(miliseconds, duration_ms):]
            end_trim = detect_leading_silence(last_10s.reverse())

        trimmed_audio = audio[start_trim:max(len(audio) - end_trim, start_trim)]
        trimmed_audio.export(output_path, format="wav")

        print(f"Silence removed from {audio_path} and saved at {output_path}")
        return output_path
    except Exception as e:
        print(f"Error processing {audio_path}: {e}")
        return audio_path


def bulk_tts(script_data,language_name="American English",voice_name="af_heart",audio_speed=0.85,remove_silence=False,start_silence=False,translate=False,speed_match=False):
  global temp_audio_dir,temp_subtile_dir, kokoro_pipeline,temp_folder_kokoro
  # boot_kokoro()
  clean_folder_data(temp_audio_dir)
  clean_folder_data(temp_subtile_dir)
  audio_list=[]
  noraml_srt_list=[]
  word_srt_list=[]
  json_list=[]
  for i in script_data:
    audio_text=script_data[i]['story_line']
    gen_prompt=script_data[i]['prompt']
    keywords=script_data[i]['keywords']
    actual_duration=script_data[i]['duration']
    kokoro_audio_paths=single_tts(audio_text, language_name, voice_name, audio_speed, remove_silence,translate=translate)
    temp_audio_path=kokoro_audio_paths[0]
    if speed_match:
      tts_audio = AudioSegment.from_file(temp_audio_path)
      tts_duration = len(tts_audio) / 1000  # Convert milliseconds to seconds
      if actual_duration > 0:
        if tts_duration > actual_duration:
            speedup_factor = tts_duration / actual_duration
            audio_speed=speedup_factor
            kokoro_audio_paths=single_tts(audio_text, language_name, voice_name, audio_speed, remove_silence,translate=translate)
            temp_audio_path=kokoro_audio_paths[0]
    else:
        pass

    audio_path=f"{temp_audio_dir}/{i}.wav"
    if start_silence:
      temp_audio_path=leading_remove_silence(temp_audio_path, silence_thresh=-40, chunk_size=100,duration=1, start=True, end=True)

    word_level_srt = f"{temp_subtile_dir}/{i}_word_level.srt"
    normal_srt = f"{temp_subtile_dir}/{i}.srt"
    json_file = f"{temp_subtile_dir}/{i}.json"
    shutil.copy(temp_audio_path, audio_path)
    audio_list.append(audio_path)
    if kokoro_audio_paths[2] is not None:
      shutil.copy(kokoro_audio_paths[2], word_level_srt)
      word_srt_list.append(word_level_srt)
    if kokoro_audio_paths[3] is not None:
      shutil.copy(kokoro_audio_paths[3], normal_srt)
      noraml_srt_list.append(normal_srt)
    if kokoro_audio_paths[4] is not None:
      shutil.copy(kokoro_audio_paths[4], json_file)
      json_list.append(json_file)

  # del kokoro_pipeline
  # gc.collect()
  # torch.cuda.empty_cache()
  # kokoro_pipeline=None
  return audio_list,noraml_srt_list,word_srt_list,json_list
kokoro_pipeline=None
temp_folder_kokoro=None
def boot_kokoro():
  global kokoro_pipeline,temp_folder_kokoro,last_used_language
  if not KOKORO_AVAILABLE:
    print("Kokoro TTS is not available, skipping initialization")
    return None
  try:
     if kokoro_pipeline is not None:
        del kokoro_pipeline
        gc.collect()
        torch.cuda.empty_cache()
  except:
    pass
  kokoro_pipeline = KPipeline(lang_code=last_used_language)
  temp_folder_kokoro = create_audio_dir()
  return kokoro_pipeline

def clean_folder_data(folder_path):
    try:
        # Check if the folder exists
        if os.path.exists(folder_path):
            # Iterate through all items in the folder
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)

                # Check if the item is a file or a directory
                if os.path.isfile(item_path):
                    # Remove the file
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    # Remove the directory and its contents
                    shutil.rmtree(item_path)
            # print(f"Successfully cleaned the folder: {folder_path}")
        else:
            print(f"Folder not found: {folder_path}")
    except Exception as e:
        print(f"Error cleaning folder {folder_path}: {e}")

base_path = "."  # Adjust if your base path is different

temp_audio_dir = f"{base_path}/temp/temp_audio"  # Define audio directory
temp_subtile_dir = f"{base_path}/temp/temp_subtile" # Define Subtile directory
os.makedirs(temp_audio_dir, exist_ok=True)  # Create if not exists
os.makedirs(temp_subtile_dir, exist_ok=True)  # Create if not exists

kokoro_pipeline=boot_kokoro()
