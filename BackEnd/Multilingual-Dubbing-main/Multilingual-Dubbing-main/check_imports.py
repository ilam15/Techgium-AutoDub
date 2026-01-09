modules = [
    "faster_whisper", "torch", "gradio", "pysrt", "deep_translator", 
    "edge_tts", "nltk", "ctranslate2", "kokoro", "librosa", 
    "pydub", "tqdm", "huggingface_hub", "audio_separator",
    "transformers", "num2words", "phonemizer", "loguru", "static_ffmpeg"
]

for module in modules:
    try:
        if module == "deep_translator":
            from deep_translator import GoogleTranslator
        elif module == "static_ffmpeg":
            import static_ffmpeg
        else:
            __import__(module)
        print(f"{module} OK")
    except ImportError as e:
        print(f"{module} FAIL: {e}")
    except Exception as e:
        print(f"{module} ERROR: {e}")

import torch
print(f"\nTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

import nltk
resources = ['punkt', 'punkt_tab', 'averaged_perceptron_tagger_eng']
for res in resources:
    try:
        nltk.data.find(f'tokenizers/{res}' if 'punkt' in res else f'taggers/{res}')
        print(f"NLTK resource {res} found")
    except LookupError:
        print(f"NLTK resource {res} NOT found")
