import os
import sys
import numpy as np

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src", "engines", "analysis")))
from feature_extractor import FeatureExtractor

def debug_features():
    extractor = FeatureExtractor(sample_rate=16000)
    data_dir = "dataset"
    
    for cls in ['male', 'female']:
        cls_dir = os.path.join(data_dir, cls)
        if not os.path.exists(cls_dir): continue
        
        files = [f for f in os.listdir(cls_dir) if f.endswith(('.wav', '.mp3', '.flac'))][:2]
        for f in files:
            path = os.path.join(cls_dir, f)
            print(f"\n--- Checking File: {path} ---")
            try:
                y = extractor.preprocess_audio(path)
                print(f"Audio Length: {len(y)} samples ({len(y)/16000:.2f}s)")
                feat = extractor.extract_features(y)
                print(f"Features (first 5): {feat[:5]}")
                print(f"Mean Frequency: {feat[0]}")
                print(f"Mean Fun (Pitch): {feat[12]}")
                if np.all(feat == 0):
                    print("⚠️ WARNING: All features are ZERO!")
                if np.any(np.isnan(feat)):
                    print("⚠️ WARNING: Contains NaNs!")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    debug_features()
