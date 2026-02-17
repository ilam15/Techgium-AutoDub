import pyannote.audio
print(f"Version: {pyannote.audio.__version__}")
try:
    from pyannote.audio import Pipeline
    print(f"Pipeline: {Pipeline}")
except Exception as e:
    print(f"Import error: {e}")
