import os
import pandas as pd
import numpy as np
import lightgbm as lgb
import pickle
import logging
from sklearn.model_selection import train_test_split, KFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, classification_report

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("GenderCSVTraining")

def train_model_from_csv(csv_path: str, output_dir: str):
    """
    Trains a robust LightGBM gender recognition model using CSV data.
    Uses better parameters and cross-validation to ensure generalization.
    """
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        return

    logger.info(f"Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path)

    # 1. Cleaning
    # Drop Id if it exists
    if 'Id' in df.columns:
        df = df.drop(columns=['Id'])
    
    # Drop Rows with NaNs
    initial_rows = len(df)
    df = df.dropna()
    if len(df) < initial_rows:
        logger.info(f"Dropped {initial_rows - len(df)} rows with missing values.")

    X = df.drop(columns=['label'])
    y = df['label']

    logger.info(f"Cleaned Dataset Shape: {df.shape}")
    logger.info(f"Class distribution:\n{y.value_counts()}")

    # 2. Label Encoding
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # 3. Model Parameters (Optimized for generalization)
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 63,           # Increased from 31
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'lambda_l1': 0.1,           # Regularization
        'lambda_l2': 0.1,           # Regularization
        'verbose': -1,
        'n_jobs': -1,
        'n_estimators': 500         # Increased
    }

    # 4. Cross-Validation Training
    logger.info("Starting Cross-Validation Training...")
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    models = []
    scores = []
    
    for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
        X_t, X_v = X.iloc[train_idx], X.iloc[val_idx]
        y_t, y_v = y_encoded[train_idx], y_encoded[val_idx]
        
        m = lgb.LGBMClassifier(**params)
        m.fit(X_t, y_t, eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(stopping_rounds=50)])
        
        preds = m.predict(X_v)
        acc = accuracy_score(y_v, preds)
        scores.append(acc)
        models.append(m)
        logger.info(f"Fold {fold+1} Accuracy: {acc:.4f}")

    logger.info(f"Mean CV Accuracy: {np.mean(scores):.4f}")

    # 5. Final Model (Train on full cleaned data)
    logger.info("Training final model on full dataset...")
    final_model = lgb.LGBMClassifier(**params)
    final_model.fit(X, y_encoded)

    # 6. Final Evaluation (internal check)
    y_pred = final_model.predict(X)
    logger.info(f"Final Accuracy (on full train): {accuracy_score(y_encoded, y_pred):.4f}")
    logger.info("\nConfusion Matrix:\n" + str(confusion_matrix(y_encoded, y_pred)))

    # 7. Save Model and Encoder
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "gender_lgbm.pkl")
    encoder_path = os.path.join(output_dir, "label_encoder.pkl")

    with open(model_path, 'wb') as f:
        pickle.dump(final_model, f)
    with open(encoder_path, 'wb') as f:
        pickle.dump(le, f)

    logger.info(f"Complete Model saved to {model_path}")
    logger.info(f"Label encoder saved to {encoder_path}")

if __name__ == "__main__":
    csv_input = "BackEnd/autodub/train.csv"
    output_location = "BackEnd/autodub/models/gender"
    train_model_from_csv(csv_input, output_location)
