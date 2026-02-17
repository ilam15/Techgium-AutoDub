import os
import argparse
import logging
import pickle
import numpy as np
import lightgbm as lgb
import librosa
from sklearn.model_selection import KFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
from feature_extractor import FeatureExtractor
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GenderTraining")

def augment_audio(y, sr):
    """
    Generates augmented versions of the audio.
    """
    augmented = []
    
    # 1. Original
    augmented.append(y)
    
    # 2. Add Noise
    noise_amp = 0.005 * np.random.uniform() * np.amax(y)
    augmented.append(y + noise_amp * np.random.normal(size=y.shape))
    
    # 3. Pitch Shift (Wide range for robustness)
    for n_steps in [-2, -1, 1, 2]:
        augmented.append(librosa.effects.pitch_shift(y, sr=sr, n_steps=n_steps))
        
    # 4. Time Stretch (Speed up/down)
    for rate in [0.9, 1.1]:
        augmented.append(librosa.effects.time_stretch(y, rate=rate))
        
    return augmented

def segment_audio(y, sr, segment_len_s=3.0, overlap_s=1.5):
    """
    Splits audio into overlapping segments to increase dataset size.
    Following the 'Sweet Spot' recommendation: 3s segments with 50% overlap.
    """
    segment_samples = int(segment_len_s * sr)
    hop_samples = int((segment_len_s - overlap_s) * sr)
    
    segments = []
    for i in range(0, len(y) - segment_samples + 1, hop_samples):
        segments.append(y[i : i + segment_samples])
    
    # Discard fragments shorter than 2.0s as they lack sufficient vocal characteristics
    # If the file is between 2.0s and 3.0s, we pad it to 3.0s to match the expected input shape
    if not segments and len(y) >= sr * 2.0:
        padded = np.pad(y, (0, max(0, segment_samples - len(y))), mode='constant')
        segments.append(padded)
        
    return segments

def train_gender_model(data_dir: str, output_dir: str):
    """
    Trains a robust LightGBM gender recognition model using the 'Correct Architecture'.
    Uses aggressive augmentation and segmentation to leverage small datasets.
    """
    extractor = FeatureExtractor(sample_rate=16000)
    features = []
    labels = []

    if not os.path.exists(data_dir):
        logger.error(f"Data directory {data_dir} does not exist.")
        return

    classes = ['male', 'female']
    for cls in classes:
        cls_dir = os.path.join(data_dir, cls)
        if not os.path.exists(cls_dir):
            continue
        
        logger.info(f"Processing class: {cls}")
        files = [f for f in os.listdir(cls_dir) if f.endswith(('.wav', '.mp3', '.flac'))]
        
        for filename in files:
            filepath = os.path.join(cls_dir, filename)
            try:
                # Load raw
                y_raw = extractor.preprocess_audio(filepath)
                
                # 1. Segment the original audio
                segments = segment_audio(y_raw, sr=16000)
                
                for seg in segments:
                    # 2. Augment each segment
                    augmented_versions = augment_audio(seg, sr=16000)
                    
                    for y_aug in augmented_versions:
                        feat = extractor.extract_features(y_aug)
                        if not np.all(feat == 0):
                            features.append(feat)
                            labels.append(cls)
                             
            except Exception as e:
                logger.error(f"Error processing {filepath}: {e}")

    if not features:
        logger.error("No features extracted.")
        return

    X = np.array(features)
    y = np.array(labels)

    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    logger.info(f"Dataset extracted. Final Shape: {X.shape}")
    logger.info(f"Class distribution: {dict(zip(le.classes_, np.bincount(y_encoded)))}")

    # --- QUICK DIAGNOSIS TEST (Requested Fix #6) ---
    print(f"\n--- DIAGNOSIS TEST ---")
    print(f"X shape: {X.shape}")
    unique, counts = np.unique(y_encoded, return_counts=True)
    print(f"Class counts: {dict(zip(le.classes_, counts))}")
    print(f"----------------------\n")

    # Split data: 70% Train, 15% Val, 15% Test
    from sklearn.model_selection import train_test_split
    X_train, X_temp, y_train, y_temp = train_test_split(X, y_encoded, test_size=0.3, random_state=42, stratify=y_encoded)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp)

    # Model Parameters (Strictly following USER's recommendation in Fix #5)
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'n_estimators': 500,
        'learning_rate': 0.03,
        'num_leaves': 64,
        'max_depth': 8,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'class_weight': 'balanced',
        'random_state': 42,
        'verbose': -1
    }

    logger.info("Starting Training on 70/15/15 split...")
    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_train, y_train, 
        eval_set=[(X_val, y_val)], 
        callbacks=[lgb.early_stopping(stopping_rounds=50)]
    )
    
    # Evaluate on Test Set
    test_preds = model.predict(X_test)
    test_acc = accuracy_score(y_test, test_preds)
    logger.info(f"Test Set Accuracy: {test_acc:.4f}")
    logger.info("\n" + classification_report(y_test, test_preds, target_names=le.classes_))

    # Final Training on full data for production
    logger.info("Training final production model...")
    final_model = lgb.LGBMClassifier(**params)
    final_model.fit(X, y_encoded)

    # Save Artifacts
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "gender_lgbm.pkl")
    encoder_path = os.path.join(output_dir, "label_encoder.pkl")
    
    with open(model_path, 'wb') as f:
        pickle.dump(final_model, f)
    with open(encoder_path, 'wb') as f:
        pickle.dump(le, f)

    logger.info(f"✅ Production model saved to {model_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoDub Professional Gender Trainer")
    parser.add_argument("--data_dir", type=str, default="dataset")
    parser.add_argument("--output_dir", type=str, default="models/gender")
    args = parser.parse_args()
    
    # Run relative to script location OR absolute if provided
    train_gender_model(args.data_dir, args.output_dir)

