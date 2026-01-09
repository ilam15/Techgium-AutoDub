from utils import language_dict
import math
import torch
import gc
import time
from faster_whisper import WhisperModel
import os
import re
import uuid
import shutil


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
            srt_file.write(f"{index + 1}\n{start_time} --> {end_time}\n{sentence['text']}\n\n")

def get_audio_file(uploaded_file):
    global temp_folder
    file_path = os.path.join(temp_folder, os.path.basename(uploaded_file))
    file_path=clean_file_name(file_path)
    shutil.copy(uploaded_file, file_path)
    return file_path

def whisper_subtitle(uploaded_file,Source_Language,max_words_per_subtitle=8):
  global language_dict,base_path,subtitle_folder
  #Load model
  if torch.cuda.is_available():
      # If CUDA is available, use GPU with float16 precision
      device = "cuda"
      compute_type = "float16"
      # compute_type="int8_float16"
  else:
      # If CUDA is not available, use CPU with int8 precision
      device = "cpu"
      compute_type = "int8"
  faster_whisper_model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2",device=device, compute_type=compute_type)
  audio_path=get_audio_file(uploaded_file)
  if Source_Language=="Automatic":
      segments,d = faster_whisper_model.transcribe(audio_path, word_timestamps=True)
      lang_code=d.language
      src_lang=get_language_name(lang_code)
  else:
    lang=language_dict[Source_Language]['lang_code']
    segments,d = faster_whisper_model.transcribe(audio_path, word_timestamps=True,language=lang)
    src_lang=Source_Language
      
  sentence_timestamp,words_timestamp,text=format_segments(segments)
  if os.path.exists(audio_path):
    os.remove(audio_path)
  del faster_whisper_model
  gc.collect()
  torch.cuda.empty_cache()
  
  word_segments=combine_word_segments(words_timestamp, max_words_per_subtitle=max_words_per_subtitle, min_silence_between_words=0.5)
  shorts_segments=custom_word_segments(words_timestamp, min_silence_between_words=0.3, max_characters_per_subtitle=17)
  #setup srt file names
  base_name = os.path.basename(uploaded_file).rsplit('.', 1)[0][:30]
  save_name = f"{subtitle_folder}/{base_name}_{src_lang}.srt"
  original_srt_name=clean_file_name(save_name)
  original_txt_name=original_srt_name.replace(".srt",".txt")
  word_level_srt_name=original_srt_name.replace(".srt","_word_level.srt")
  customize_srt_name=original_srt_name.replace(".srt","_customize.srt")
  shorts_srt_name=original_srt_name.replace(".srt","_shorts.srt")
    
  generate_srt_from_sentences(sentence_timestamp, srt_path=original_srt_name)
  word_level_srt(words_timestamp, srt_path=word_level_srt_name)
  word_level_srt(shorts_segments, srt_path=shorts_srt_name,shorts=True)
  write_subtitles_to_file(word_segments, filename=customize_srt_name)
  with open(original_txt_name, 'w', encoding='utf-8') as f1:
    f1.write(text)
  return original_srt_name,customize_srt_name,word_level_srt_name,shorts_srt_name,original_txt_name,src_lang


from utils import language_dict
import pysrt
from deep_translator import GoogleTranslator

def translate_text(text, Source_Language, Destination_Language):
    """
    Translates the given text using GoogleTranslator.
    """
    source_language = language_dict[Source_Language]['lang_code']
    target_language = language_dict[Destination_Language]['lang_code']
    
    # Adjust for specific language codes
    if Destination_Language == "Chinese":
        target_language = 'zh-CN'
    
    translator = GoogleTranslator(source=source_language, target=target_language)
    translation = translator.translate(text.strip())
    return str(translation)

def translate_subtitle(subtitles, Source_Language, Destination_Language):
    """
    Translates subtitles while preserving their timing.
    """
    global language_dict
    store_text = ""
    for subtitle in subtitles:
        # Translate the text of each subtitle
        text_translated = translate_text(subtitle.text, Source_Language, Destination_Language)
        subtitle.text = text_translated  # Update the subtitle text
        store_text += text_translated.strip() + " "  # Use translated text for storing
    
    return subtitles, store_text


#@title Using Gradio Interface
def subtitle_maker(Audio_or_Video_File,Source_Language,Destination_Language,Gender='Male',recover_music=False,make_video=False,max_words_per_subtitle=8):
  try:
    default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=whisper_subtitle(Audio_or_Video_File,Source_Language,max_words_per_subtitle=max_words_per_subtitle)
  except Exception as e:
    print(f"Error in whisper_subtitle: {e}")
    default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=None,None,None,None,None,None
  global subtitle_folder
  # print(src_lang)
  dubb_voice=None
  if src_lang!=Destination_Language:
    subtitles = pysrt.open(default_srt_path, encoding='utf-8')
    translated_subtitles, _ = translate_subtitle(subtitles, src_lang, Destination_Language)
    tra_srt_name=os.path.basename(default_srt_path).replace(".srt",f"_{Destination_Language}.srt")
    output_srt_path=f"{subtitle_folder}/{tra_srt_name}"
    translated_subtitles.save(output_srt_path, encoding='utf-8')
    dubb_voice=dubbing(output_srt_path,Destination_Language,gender=Gender)
  else:
    output_srt_path=default_srt_path
    dubb_voice=dubbing(output_srt_path,Destination_Language,gender=Gender)
  if recover_music:
    dubb_voice=recover_audio(Audio_or_Video_File, dubb_voice)
  new_video=None
  if make_video:
      new_video=video_edit(Audio_or_Video_File, dubb_voice)
  if src_lang!=Destination_Language:
    try:
      default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=whisper_subtitle(dubb_voice,Destination_Language,max_words_per_subtitle=max_words_per_subtitle)
    except Exception as e:
      default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,src_lang=None,None,None,None,None,None

  # return dubb_voice,default_srt_path,customize_srt_path,word_level_srt_path,shorts_srt_name,text_path,new_video
  return dubb_voice,shorts_srt_name,word_level_srt_path,new_video


























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


from microsoft_tts import edge_tts_pipeline
def tts(text,Language='English',Gender='Male',speed=1.0,translate_text_flag=False, no_silence=True, long_sentence=True):
    voice_name=None
    tts_save_path=''         
    edge_save_path = edge_tts_pipeline(text, Language,voice_name, Gender, translate_text_flag=translate_text_flag, 
                                        no_silence=no_silence, speed=speed, tts_save_path=tts_save_path, 
                                        long_sentence=long_sentence)
    return edge_save_path


def your_tts(text,lang,gender,audio_path,actual_duration,speed=1.0):
  tts_path=tts(text, Language=lang,speed=speed,Gender=gender)
  tts_audio = AudioSegment.from_file(tts_path)
  tts_duration = len(tts_audio)
  if tts_duration > actual_duration:
    speedup_factor = tts_duration / actual_duration
    tts_path=tts(text, Language=lang,speed=speedup_factor,Gender=gender)
  shutil.copy(tts_path,audio_path)




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
    def text_to_speech_srt(text, audio_path, language, actual_duration,gender='Male'):
        tts_filename = f"{base_path}/temp.wav"
        your_tts(text,language,gender,tts_filename,actual_duration,speed=1.0)
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
            speedup_filename = f"{base_path}/speedup_temp.wav"
            # Use ffmpeg to change audio speed
            subprocess.run([
                "ffmpeg",
                "-i", tts_filename,
                "-filter:a", f"atempo={speedup_factor}",
                speedup_filename,
                "-y"
            ], check=True)

            # Replace the original TTS audio with the sped-up version
            shutil.move(speedup_filename, audio_path)
        elif tts_duration < actual_duration:
            # If TTS audio duration is less than actual duration, add silence to match the duration
            silence_gap = actual_duration - tts_duration
            silence = AudioSegment.silent(duration=int(silence_gap))
            new_audio = tts_audio + silence

            # Save the new audio with added silence
            new_audio.export(audio_path, format="wav")
        else:
            # If TTS audio duration is equal to actual duration, use the original TTS audio
            shutil.move(tts_filename, audio_path)

    @staticmethod
    def make_silence(pause_time, pause_save_path):
        silence = AudioSegment.silent(duration=pause_time)
        silence.export(pause_save_path, format="wav")
        return pause_save_path

    @staticmethod
    def create_folder_for_srt(srt_file_path):
        srt_base_name = os.path.splitext(os.path.basename(srt_file_path))[0]
        random_uuid = str(uuid.uuid4())[:4]
        dummy_folder_path = f"{base_path}/dummy"
        if not os.path.exists(dummy_folder_path):
            os.makedirs(dummy_folder_path)
        folder_path = os.path.join(dummy_folder_path, f"{srt_base_name}_{random_uuid}")
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    @staticmethod
    def concatenate_audio_files(audio_paths, output_path):
        concatenated_audio = AudioSegment.silent(duration=0)
        for audio_path in audio_paths:
            audio_segment = AudioSegment.from_file(audio_path)
            concatenated_audio += audio_segment
        concatenated_audio.export(output_path, format="wav")

    def srt_to_dub(self, srt_file_path,dub_save_path,language='English',gender='Male'):
        result = self.read_srt_file(srt_file_path)
        new_folder_path = self.create_folder_for_srt(srt_file_path)
        join_path = []
        for i in tqdm(result):
        # for i in result:
            text = i['text']
            actual_duration = i['end_time'] - i['start_time']
            pause_time = i['pause_time']
            slient_path = f"{new_folder_path}/{i['previous_pause']}"
            self.make_silence(pause_time, slient_path)
            join_path.append(slient_path)
            tts_path = f"{new_folder_path}/{i['audio_name']}"
            self.text_to_speech_srt(text, tts_path, language, actual_duration,gender=gender)
            join_path.append(tts_path)
        self.concatenate_audio_files(join_path, dub_save_path)

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

                current_entry = {
                    'entry_number': entry_number,
                    'start_time': start_time,
                    'end_time': end_time,
                    'text': lines[i + 2].strip(),
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


def dubbing(srt_file_path,langauge,gender):
  srt_dubbing = SRTDubbing()
  dub_save_path=get_subtitle_Dub_path(srt_file_path,langauge)
  srt_dubbing.srt_to_dub(srt_file_path,dub_save_path,langauge,gender=gender)
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

        # Use a system temporary folder to avoid conflicts
        temp_folder = os.path.join(os.path.abspath(os.sep), "tmp", "audio_separate")
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)

        os.makedirs(temp_folder, exist_ok=True)

        # Run the audio separator command
        command = f"audio-separator {source_path} --model_filename UVR-MDX-NET-Inst_HQ_3.onnx --output_dir {temp_folder}"
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
    gpu=True
    command=f"ffmpeg -i {video_path}  -i {new_audio_path} -map 0:v -map 1:a -c:v copy -shortest {output_path} -y"
    gpu_command = f'ffmpeg -hwaccel cuda -i {video_path} -i {new_audio_path} -map 0:v -map 1:a -c:v copy -shortest {output_path} -y'
    if gpu:
      command=gpu_command
    var=os.system(command)
    if var == 0:
        return output_path
    else:
        print(f"Failed to replace audio. Command:\n {command}")
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
    
source_lang_list = ['Automatic']

available_language=language_dict.keys()
source_lang_list.extend(available_language)  

target_lang_list = []
target_lang_list.extend(available_language)  
@click.command()
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode.")
@click.option("--share", is_flag=True, default=False, help="Enable sharing of the interface.")
def main(debug, share):
    description = """**Note**: Avoid uploading large video files. [Max 1-2 Min Video, otherwise it will take a long time]
    We are using [faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2) and Edge TTS"""
    # Define Gradio inputs and outputs
    gradio_inputs = [
        gr.File(label="Upload Audio or Video File"),
        gr.Dropdown(label="Source Language", choices=source_lang_list, value="Automatic"),
        gr.Dropdown(label="Translate Into", choices=target_lang_list, value="English"),
        gr.Dropdown(label="Dub Voice Geneder", choices=['Male','Female'], value="Male"),
        gr.Checkbox(label="Recover Background Music",value=False),
        gr.Checkbox(label="Make Video",value=False)
        # gr.Number(label="Max Word Per Subtitle Segment [Useful for Vertical Videos]", value=8)
    ]
    gradio_outputs = [
        gr.Audio(label="Dub Audio", show_label=True),
        gr.File(label="Translated SRT File", show_label=True),
        # gr.File(label="Customize SRT File", show_label=True),
        gr.File(label="Word Level SRT File", show_label=True),
        # gr.File(label="SRT File For Shorts", show_label=True),
        # gr.File(label="Text File", show_label=True),
        gr.Video(label="Dubbed Video", show_label=True)
    ]

    # Create Gradio interface
    demo = gr.Interface(theme='JohnSmith9982/small_and_pretty',fn=subtitle_maker, inputs=gradio_inputs, outputs=gradio_outputs, title="Multilingual Video Dubbing",description=description)

    # Launch Gradio with command-line options
    demo.queue().launch(debug=debug, share=share)
if __name__ == "__main__":
    main()
