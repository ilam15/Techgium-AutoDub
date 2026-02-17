import pickle
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src", "engines", "analysis")))
from feature_extractor import FeatureExtractor

def detailed_check():
    model_path = "models/gender/gender_lgbm.pkl"
    encoder_path = "models/gender/label_encoder.pkl"
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    with open(encoder_path, 'rb') as f:
        le = pickle.load(f)

    extractor = FeatureExtractor(sample_rate=16000)
    data_dir = "dataset"
    
    fails = []
    total = 0
    
    for cls in ['male', 'female']:
        cls_dir = os.path.join(data_dir, cls)
        if not os.path.exists(cls_dir): continue
        files = [f for f in os.listdir(cls_dir) if f.endswith(('.wav', '.mp3', '.flac'))]
        for f in files:
            path = os.path.join(cls_dir, f)
            y = extractor.preprocess_audio(path)
            feat = extractor.extract_features(y).reshape(1, -1)
            pred_idx = model.predict(feat)[0]
            pred_label = le.inverse_transform([pred_idx])[0]
            if pred_label != cls:
                fails.append(f"{f}: {cls} -> {pred_label}")
            total += 1

    if fails:
        print(f"Fails ({len(fails)}/{total}):")
        for fail in fails: print(fail)
    else:
        print(f"All {total} files passed 100%!")

if __name__ == "__main__":
    detailed_check()
