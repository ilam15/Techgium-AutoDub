import os
import sys
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from engines.analysis.gender_engine import GenderDetector

def test_inference():
    print("--- Testing Gender Recognition Inference ---")
    detector = GenderDetector()
    
    # Test with a real file if it exists
    test_file = "BackEnd/autodub/audio_data/Video10_vocals.wav"
    if os.path.exists(test_file):
        print(f"Testing with file: {test_file}")
        result = detector.predict(test_file)
        print(f"Result: {result}")
    else:
        # Fallback to noise demo
        print("Test file not found, testing with random noise...")
        mock_audio = np.random.uniform(-0.1, 0.1, 16000 * 3) # 3 seconds
        result = detector.predict(mock_audio)
        print(f"Result (Noise): {result}")

if __name__ == "__main__":
    test_inference()
