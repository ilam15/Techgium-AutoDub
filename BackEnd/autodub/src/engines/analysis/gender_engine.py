import os
import pickle
import logging
import numpy as np
import lightgbm as lgb
from typing import Dict, List, Any, Optional, Union
from .feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)

class GenderDetector:
    """
    Robust Gender Recognition following the 'Correct Architecture'.
    Uses merged speaker audio, 48-dim feature set, and 0.65 confidence threshold.
    """

    def __init__(self, model_path: Optional[str] = None, encoder_path: Optional[str] = None):
        self.model = None
        self.label_encoder = None
        self.extractor = FeatureExtractor(sample_rate=16000)
        
        # Default paths
        default_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "gender"))
        self.model_path = model_path or os.path.join(default_dir, "gender_lgbm.pkl")
        self.encoder_path = encoder_path or os.path.join(default_dir, "label_encoder.pkl")
        
        if os.path.exists(self.model_path) and os.path.exists(self.encoder_path):
            self.load_model()
        else:
            logger.warning(f"Model artifacts not found at {default_dir}")

    def load_model(self):
        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)
            with open(self.encoder_path, 'rb') as f:
                self.label_encoder = pickle.load(f)
            logger.info("✅ Global traits model loaded.")
        except Exception as e:
            logger.error(f"Failed to load global model: {e}")

    def extract_features(self, audio: Union[str, np.ndarray]) -> np.ndarray:
        y = self.extractor.preprocess_audio(audio)
        return self.extractor.extract_features(y)

    def predict(self, audio: Union[str, np.ndarray], prob_threshold: float = 0.55) -> Dict[str, Any]:
        """
        Predicts gender using ML + Pitch sanity check + Confidence gating.
        Lowered prob_threshold slightly for better recall on augmented model.
        """
        if self.model is None or self.label_encoder is None:
            return {"gender": "unknown", "confidence": 0.0}

        try:
            # 1. Feature Extraction
            features = self.extract_features(audio)
            if np.all(features == 0):
                return {"gender": "unknown", "confidence": 0.0}

            # 2. ML Prediction
            features_reshaped = features.reshape(1, -1)
            prob_dist = self.model.predict_proba(features_reshaped)[0]
            class_idx = np.argmax(prob_dist)
            model_confidence = float(prob_dist[class_idx])
            model_gender = self.label_encoder.inverse_transform([class_idx])[0]

            # 3. Hybrid Logic (Sanity Check)
            # Pitch mean is at index 40 in the 48-dim vector
            pitch_mean = features[40]
            
            final_gender = model_gender
            
            # biological register check (Refined thresholds)
            # Females usually > 165Hz, Males usually < 155Hz
            if pitch_mean > 190 and model_gender != 'female':
                 final_gender = 'female'
                 model_confidence = max(model_confidence, 0.85)
            elif 50 < pitch_mean < 100 and model_gender != 'male':
                 final_gender = 'male'
                 model_confidence = max(model_confidence, 0.85)

            # 4. Confidence Gating
            # If the model is very unsure, but pitch is very clear, we use pitch
            if model_confidence < prob_threshold:
                if pitch_mean > 200:
                    return {"gender": "female", "confidence": 0.60, "pitch": float(pitch_mean)}
                elif 50 < pitch_mean < 95:
                    return {"gender": "male", "confidence": 0.60, "pitch": float(pitch_mean)}
                
                logger.debug(f"Confidence too low ({model_confidence:.2f} < {prob_threshold})")
                return {"gender": "unknown", "confidence": model_confidence}

            return {
                "gender": final_gender,
                "confidence": model_confidence,
                "pitch": float(pitch_mean)
            }
        except Exception as e:
            logger.error(f"Global trait prediction error: {e}")
            return {"gender": "unknown", "confidence": 0.0}

    def batch_predict(self, audio_list: List[Union[str, np.ndarray]]) -> List[Dict[str, Any]]:
        return [self.predict(a) for a in audio_list]

def detect_gender_for_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    detector = GenderDetector()
    for seg in segments:
        audio = seg.get('audio_path') or seg.get('audio_data')
        if audio is not None:
            res = detector.predict(audio)
            seg['gender'] = res['gender']
            seg['gender_confidence'] = res['confidence']
    return segments
