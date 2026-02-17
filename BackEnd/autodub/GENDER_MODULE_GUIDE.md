# Gender Recognition Module for AutoDub

This module provides production-ready gender detection (male/female) for audio segments using LightGBM and robust acoustic features.

## Folder Structure

```text
autodub/
├── models/
│   └── gender/
│       ├── gender_lgbm.pkl      # Trained LightGBM model
│       └── label_encoder.pkl     # Label encoder for classes
├── src/
│   └── engines/
│       └── analysis/
│           ├── __init__.py
│           ├── gender_engine.py      # Main detection logic
│           ├── feature_extractor.py  # Feature extraction (MFCC, Pitch, etc.)
│           └── training_pipeline.py # Script to train the model
├── examples/
│   └── gender_recognition_demo.py   # Usage examples
└── requirements_gender.txt           # Dependencies
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements_gender.txt
```

2. Ensure the `models/gender/` directory exists.

## Training the Model

To train the model, you need a dataset organized into `male` and `female` folders:

```bash
python src/engines/analysis/training_pipeline.py --data_dir /path/to/dataset --output_dir models/gender
```

## Example Usage

### Integrating into AutoDub Pipeline

```python
from engines.analysis.gender_engine import detect_gender_for_segments

# List of segments from ASR/Diarization
segments = [
    {"id": 1, "audio_path": "path/to/seg1.wav"},
    {"id": 2, "audio_path": "path/to/seg2.wav"}
]

# Adds 'gender' and 'gender_confidence' to each segment
processed_segments = detect_gender_for_segments(segments)
```

### Direct Inference

```python
from engines.analysis.gender_engine import GenderDetector

detector = GenderDetector()
result = detector.predict("audio.wav")
print(f"Gender: {result['gender']}, Confidence: {result['confidence']}")
```

## Performance Specs
- **Latency**: <30ms per 5s segment on modern CPU.
- **Accuracy**: Dependent on training data (typically >90% on common datasets like LibriSpeech/CommonVoice).
- **Features**: MFCC (20), Pitch (F0), Zero Crossing Rate, RMS Energy, Spectral Centroid.
