import inspect
try:
    from pyannote.audio import Pipeline
    print(f"Signature: {inspect.signature(Pipeline.from_pretrained)}")
except Exception as e:
    print(f"Error: {e}")
