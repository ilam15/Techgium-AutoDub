import sys
import subprocess

def check_module(module_name):
    try:
        __import__(module_name)
        return True, ""
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return True, f"Imported with warning/error: {e}"

modules = [
    "faster_whisper", "torch", "gradio", "pysrt", 
    "deep_translator", "edge_tts", "nltk", "ctranslate2", 
    "librosa", "pydub", "tqdm", "huggingface_hub", 
    "audio_separator", "transformers", "num2words", 
    "phonemizer", "loguru", "static_ffmpeg"
]

print("--- Dependency Check ---")
all_ok = True
for m in modules:
    ok, msg = check_module(m)
    status = "OK" if ok else "FAIL"
    print(f"{m:20} : {status} {msg}")
    if not ok: all_ok = False

print("\n--- NLTK Resources ---")
import nltk
resources = ['punkt_tab', 'averaged_perceptron_tagger_eng', 'punkt']
for res in resources:
    try:
        if res == 'punkt_tab':
            nltk.data.find('tokenizers/punkt_tab')
        elif res == 'averaged_perceptron_tagger_eng':
            nltk.data.find('taggers/averaged_perceptron_tagger_eng')
        else:
            nltk.data.find(f'tokenizers/{res}')
        print(f"{res:30} : FOUND")
    except LookupError:
        print(f"{res:30} : MISSING")
        all_ok = False

if all_ok:
    print("\nSYSTEM READY")
else:
    print("\nSYSTEM HAS MISSING DEPENDENCIES")
