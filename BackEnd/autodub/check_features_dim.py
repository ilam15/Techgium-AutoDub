import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src", "engines", "analysis")))
from feature_extractor import FeatureExtractor
import numpy as np

extractor = FeatureExtractor()
dummy_audio = np.random.uniform(-1, 1, 16000 * 2) # 2 seconds of noise
features = extractor.extract_features(dummy_audio)
print(f"Number of features: {len(features)}")
