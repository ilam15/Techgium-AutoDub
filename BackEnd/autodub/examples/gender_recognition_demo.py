import os
import sys
import numpy as np

# Add src to path if needed (adjust based on where you run this)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from engines.analysis.gender_engine import GenderDetector, detect_gender_for_segments

def demo_single_prediction():
    print("--- Single Prediction Demo ---")
    detector = GenderDetector()
    
    # Example with a mock numpy array (silence or noise)
    # In a real scenario, passing a path to a wav file is better
    mock_audio = np.random.uniform(-1, 1, 16000 * 2) # 2 seconds of noise
    
    result = detector.predict(mock_audio)
    print(f"Prediction Result: {result}")

def demo_batch_integration():
    print("\n--- AutoDub Integration Demo ---")
    
    # Mock segments as they would appear in the pipeline
    segments = [
        {"id": 1, "text": "Hello world", "audio_data": np.random.uniform(-0.1, 0.1, 16000)},
        {"id": 2, "text": "How are you?", "audio_data": np.random.uniform(-0.1, 0.1, 32000)},
    ]
    
    updated_segments = detect_gender_for_segments(segments)
    
    for seg in updated_segments:
        print(f"Segment {seg['id']}: Gender={seg.get('gender')}, Confidence={seg.get('gender_confidence'):.2f}")

if __name__ == "__main__":
    # Note: This will show 'Model not found' warning if you haven't trained it yet
    # But it demonstrates the API usage.
    demo_single_prediction()
    demo_batch_integration()
