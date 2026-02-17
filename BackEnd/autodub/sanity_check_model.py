import pickle
import numpy as np
import os
import sys

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src", "engines", "analysis")))
from feature_extractor import FeatureExtractor

def sanity_check():
    model_path = "models/gender/gender_lgbm.pkl"
    encoder_path = "models/gender/label_encoder.pkl"
    
    if not os.path.exists(model_path):
        print(f"Error: Model file not found at {model_path}")
        return

    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    with open(encoder_path, 'rb') as f:
        le = pickle.load(f)

    print(f"Model loaded. Classes: {le.classes_}")
    
    extractor = FeatureExtractor(sample_rate=16000)
    data_dir = "dataset"
    
    correct = 0
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
            
            if pred_label == cls:
                correct += 1
            total += 1
            print(f"File: {f} | Actual: {cls} | Predicted: {pred_label}")

    print(f"\nFinal Sanity Check Accuracy on Training Set: {correct/total:.2%}")

if __name__ == "__main__":
    sanity_check()
