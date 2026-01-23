# ===============================
# Config
# ===============================
edge_folder = "."

import os
import re
import uuid
import time
import shutil
import torch
import nltk
nltk.download("punkt")

from nltk.tokenize import sent_tokenize
from transformers import pipeline
from pydub import AudioSegment
from pydub.silence import split_on_silence

from lang_data import languages, male_voice_list, female_voice_list


# ===============================
# NLLB-200 Language Mapping
# ===============================
NLLB_LANG_MAP = {
    "English": "eng_Latn",
    "Tamil": "tam_Taml",
    "Hindi": "hin_Deva",
    "Telugu": "tel_Telu",
    "Malayalam": "mal_Mlym",
    "Kannada": "kan_Knda",
    "Chinese": "zho_Hans",
    "Japanese": "jpn_Jpan",
    "Korean": "kor_Hang",
    "French": "fra_Latn",
    "German": "deu_Latn",
    "Spanish": "spa_Latn",
    "Russian": "rus_Cyrl",
    "Arabic": "arb_Arab",
    "Portuguese": "por_Latn",
    "Urdu": "urd_Arab",
}

# ===============================
# Load NLLB-200 ONCE
# ===============================
print("Loading NLLB-200 translation model...")

translator = pipeline(
    "translation",
    model="facebook/nllb-200-distilled-600M",
    device=0 if torch.cuda.is_available() else -1
)

print("NLLB-200 loaded successfully")


# ===============================
# Translation Function (REPLACED)
# ===============================
def translate_text(text, Language):
    if not text or not text.strip():
        return ""

    tgt_lang = NLLB_LANG_MAP.get(Language)
    if not tgt_lang:
        raise ValueError(f"Unsupported language: {Language}")

    result = translator(
        text.strip(),
        src_lang="eng_Latn",   # Change only if ASR source is not English
        tgt_lang=tgt_lang,
        max_length=512
    )

    return result[0]["translation_text"]


# ===============================
# Sentence Chunking
# ===============================
def chunks_sentences(paragraph, join_limit=2):
    sentences = sent_tokenize(paragraph)
    new_sentences = []

    for i in range(0, len(sentences), join_limit):
        new_sentence = " ".join(sentences[i:i + join_limit])
        new_sentences.append(new_sentence)

    return new_sentences


def make_chunks(input_text, language):
    try:
        return chunks_sentences(input_text, join_limit=2)
    except Exception:
        temp_list = re.split(r'([.!?。！？])', input_text)
        filtered_list = []
        for i in range(0, len(temp_list) - 1, 2):
            filtered_list.append(temp_list[i] + temp_list[i + 1])
        if len(temp_list) % 2 != 0 and temp_list[-1]:
            filtered_list.append(temp_list[-1])
        return filtered_list


# ===============================
# Rate Calculation
# ===============================
def calculate_rate_string(input_value):
    rate = (input_value - 1) * 100
    sign = "+" if input_value >= 1 else "-"
    return f"{sign}{abs(int(rate))}"


# ===============================
# Audio Utilities
# ===============================
def random_audio_name_generate():
    return f"{uuid.uuid4().hex[:8]}.mp3"


def merge_audio_files(audio_paths, output_path):
    merged_audio = AudioSegment.silent(duration=0)
    for audio_path in audio_paths:
        merged_audio += AudioSegment.from_file(audio_path)
    merged_audio.export(output_path, format="mp3")


def mp3_to_wav(mp3_file, wav_file):
    audio = AudioSegment.from_mp3(mp3_file)
    audio.export(wav_file, format="wav")


def remove_silence(file_path, output_path):
    sound = AudioSegment.from_file(file_path, format="wav")
    chunks = split_on_silence(
        sound,
        min_silence_len=100,
        silence_thresh=-45,
        keep_silence=50
    )

    combined = AudioSegment.empty()
    for chunk in chunks:
        combined += chunk

    combined.export(output_path, format="wav")
    return output_path


# ===============================
# Edge TTS Core
# ===============================
def edge_free_tts(chunks_list, speed, voice_name, save_path, translate_text_flag, Language):
    store_text = ""

    if len(chunks_list) > 1:
        chunk_audio_list = []

        edge_voice_dir = f"{edge_folder}/edge_tts_voice"
        if os.path.exists(edge_voice_dir):
            shutil.rmtree(edge_voice_dir)
        os.mkdir(edge_voice_dir)

        for idx, chunk in enumerate(chunks_list, start=1):
            text = translate_text(chunk, Language) if translate_text_flag else chunk
            store_text += text + " "
            text = text.replace('"', "")

            out_mp3 = f"{edge_voice_dir}/{idx}.mp3"
            cmd = (
                f'edge-tts --rate={calculate_rate_string(speed)}% '
                f'--voice {voice_name} --text "{text}" --write-media {out_mp3}'
            )

            for attempt in range(3):
                if os.system(cmd) == 0:
                    break
                time.sleep(2)
            else:
                raise RuntimeError(f"Edge TTS failed: {chunk}")

            chunk_audio_list.append(out_mp3)

        merge_audio_files(chunk_audio_list, save_path)

    else:
        text = translate_text(chunks_list[0], Language) if translate_text_flag else chunks_list[0]
        store_text += text + " "
        text = text.replace('"', "")

        cmd = (
            f'edge-tts --rate={calculate_rate_string(speed)}% '
            f'--voice {voice_name} --text "{text}" --write-media {save_path}'
        )

        for attempt in range(3):
            if os.system(cmd) == 0:
                break
            time.sleep(2)
        else:
            raise RuntimeError(f"Edge TTS failed: {text}")

    with open("./temp.txt", "w", encoding="utf-8") as f:
        f.write(store_text)

    return save_path


# ===============================
# Public Pipeline
# ===============================
def edge_tts_pipeline(
    input_text,
    Language="English",
    voice_name=None,
    Gender="Male",
    translate_text_flag=True,
    no_silence=False,
    speed=1,
    tts_save_path="",
    long_sentence=True
):
    if not voice_name:
        if Gender == "Female":
            voice_name = female_voice_list.get(Language, "en-US-AvaMultilingualNeural")
        else:
            voice_name = male_voice_list.get(Language, "en-US-BrianMultilingualNeural")

    chunks_list = make_chunks(input_text, Language) if long_sentence else [input_text]

    if not os.path.exists(f"{edge_folder}/audio"):
        os.mkdir(f"{edge_folder}/audio")

    temp_mp3 = f"{edge_folder}/audio/{random_audio_name_generate()}"
    temp_wav = temp_mp3.replace(".mp3", ".wav")

    edge_save = edge_free_tts(
        chunks_list, speed, voice_name, temp_mp3, translate_text_flag, Language
    )

    mp3_to_wav(edge_save, temp_wav)

    final_path = temp_wav

    if no_silence:
        clean_path = temp_wav.replace(".wav", "_clean.wav")
        final_path = remove_silence(temp_wav, clean_path)

    if tts_save_path:
        shutil.copyfile(final_path, tts_save_path)

    return final_path
