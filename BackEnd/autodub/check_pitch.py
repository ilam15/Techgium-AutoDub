import os
import sys
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src", "engines", "analysis")))
from feature_extractor import FeatureExtractor

def check_pitch_stats():
    extractor = FeatureExtractor(sample_rate=16000)
    data_dir = "dataset"
    
    for cls in ['female', 'male']:
        cls_dir = os.path.join(data_dir, cls)
        if not os.path.exists(cls_dir): continue
        
        print(f"\n--- {cls.upper()} PITCH STATS ---")
        files = [f for f in os.listdir(cls_dir) if f.endswith(('.wav', '.mp3', '.flac'))]
        pitches = []
        for f in files:
            path = os.path.join(cls_dir, f)
            y = extractor.preprocess_audio(path)
            feat = extractor.extract_features(y)
            # meanfun is index 12 (0-based)
            pitches.append(feat[12] * 1000.0) # back to Hz
            print(f"{f}: {feat[12]*1000:.1f}Hz")
        
        print(f"Mean Pitch for {cls}: {np.mean(pitches):.1f}Hz")

if __name__ == "__main__":
    check_pitch_stats()
