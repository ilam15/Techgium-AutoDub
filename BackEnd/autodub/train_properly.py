import os
import pandas as pd
import numpy as np
import pickle
import lightgbm as lgb
import logging
import sys
import librosa
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src", "engines", "analysis")))
try:
    from feature_extractor import FeatureExtractor
except ImportError:
    # Fallback for direct execution if structure is different
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src", "engines", "analysis")))
    from feature_extractor import FeatureExtractor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PerfectTrainer")

def augment_audio(y, sr):
    """
    Creates robust variations of the audio segment.
    """
    augmented = [y]
    
    # 1. Add Gaussian Noise
    noise = np.random.normal(0, 0.002, y.shape)
    augmented.append(y + noise)
    
    # 2. Pitch Shifting (Crucial for gender robustness)
    # Shift -2, -1, 1, 2 semitones
    for n in [-2, -1, 1, 2]:
        try:
            augmented.append(librosa.effects.pitch_shift(y, sr=sr, n_steps=n))
        except: pass
        
    # 3. Speed variations
    for rate in [0.9, 1.1]:
        try:
            augmented.append(librosa.effects.time_stretch(y, rate=rate))
        except: pass
        
    return augmented

def segment_audio(y, sr, segment_len_s=3.0, overlap_s=1.5):
    """
    Splits audio into overlapping segments. Pad if too short.
    """
    target_samples = int(segment_len_s * sr)
    hop_samples = int((segment_len_s - overlap_s) * sr)
    
    segments = []
    if len(y) < target_samples:
        if len(y) > sr * 0.5: # At least 0.5s for a snippet
            padded = np.pad(y, (0, target_samples - len(y)), mode='reflect')
            segments.append(padded)
    else:
        for i in range(0, len(y) - target_samples + 1, hop_samples):
            segments.append(y[i : i + target_samples])
            
        # Ensure we don't miss the last part if it's significant
        if len(y) % hop_samples > sr * 0.5:
            segments.append(y[-target_samples:])
            
    return segments

def train_perfectly():
    data_dir = "dataset"
    output_dir = "models/gender"
    os.makedirs(output_dir, exist_ok=True)
    
    extractor = FeatureExtractor(sample_rate=16000)
    all_features = []
    all_labels = []
    
    classes = ['male', 'female']
    
    logger.info("🚀 Starting Perfect Training Pipeline...")
    
    for cls in classes:
        cls_dir = os.path.join(data_dir, cls)
        if not os.path.exists(cls_dir):
            logger.warning(f"Directory {cls_dir} missing, skipping.")
            continue
            
        files = [f for f in os.listdir(cls_dir) if f.lower().endswith(('.wav', '.mp3', '.flac'))]
        logger.info(f"Processing {len(files)} files for class: {cls}")
        
        for idx, f in enumerate(files):
            path = os.path.join(cls_dir, f)
            try:
                # 1. Load and Normalize
                y_full = extractor.preprocess_audio(path)
                
                # 2. Segment
                segments = segment_audio(y_full, sr=16000)
                
                for seg in segments:
                    # 3. Augment
                    aug_versions = augment_audio(seg, sr=16000)
                    
                    for y_aug in aug_versions:
                        # 4. Extract 60 features
                        feat = extractor.extract_features(y_aug)
                        if not np.all(feat == 0):
                            all_features.append(feat)
                            all_labels.append(cls)
                
                if (idx + 1) % 10 == 0:
                    logger.info(f"  ... {idx + 1}/{len(files)} files processed")
                    
            except Exception as e:
                logger.error(f"Failed to process {f}: {e}")

    if not all_features:
        logger.error("❌ No data collected! Check your dataset folders.")
        return

    X = np.array(all_features)
    y = np.array(all_labels)
    
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    
    logger.info(f"✅ Data Extraction Complete. Samples: {len(X)}")
    logger.info(f"Distribution: {dict(zip(le.classes_, np.bincount(y_enc)))}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=0.2, random_state=42, stratify=y_enc)

    # Train LightGBM with robust params
    params = {
        'objective': 'binary',
        'metric': 'binary_error',
        'boosting_type': 'gbdt',
        'n_estimators': 300,
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': 6,
        'min_data_in_leaf': 20,
        'class_weight': 'balanced',
        'random_state': 42,
        'verbose': -1
    }
    
    logger.info("Training LightGBM model...")
    model = lgb.LGBMClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], callbacks=[lgb.early_stopping(30)])
    
    # Eval
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    logger.info(f"Test Accuracy: {acc:.2%}")
    logger.info("\n" + classification_report(y_test, preds, target_names=le.classes_))
    
    # Final train on all data
    logger.info("Retraining on full dataset for maximum accuracy...")
    final_model = lgb.LGBMClassifier(**params)
    final_model.fit(X, y_enc)

    # Save
    model_path = os.path.join(output_dir, "gender_lgbm.pkl")
    encoder_path = os.path.join(output_dir, "label_encoder.pkl")
    
    with open(model_path, 'wb') as f:
        pickle.dump(final_model, f)
    with open(encoder_path, 'wb') as f:
        pickle.dump(le, f)
        
    logger.info(f"✨ Perfect Model Saved to {model_path}")
    
    # Save features for debugging/reference
    df_feat = pd.DataFrame(X)
    df_feat['label'] = y
    csv_out = os.path.join(data_dir, "extracted_features_60.csv")
    df_feat.to_csv(csv_out, index=False)
    logger.info(f"📊 Features exported to {csv_out}")

if __name__ == "__main__":
    train_perfectly()
