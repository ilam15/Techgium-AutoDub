import sys
import os
import torch
import numpy as np
import librosa

# Add paths to sys.path so that absolute imports work
PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", "..")) # Assuming we are in autodub
# Wait, let's just use the current directory as root for autodub
ROOT = os.path.abspath(os.getcwd())
if ROOT not in sys.path: sys.path.insert(0, ROOT)

# Mock the package structure for the relative imports inside src
import src.engines.analysis.gender_engine as gender_engine
import src.utils.speaker_detection as speaker_detection

def debug_video_audio():
    audio_path = r"C:\Users\sweth\OneDrive\Desktop\AutoDub\BackEnd\autodub\audio_data\upload_11be89eb_SampleDemo1_vocals.wav"
    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        return

    print(f"Analyzing: {audio_path}")
    analyzer = speaker_detection.SpeakerAnalyzer()
    turns, genders = analyzer.analyze_audio(audio_path)
    
    print("\n--- RESULTS ---")
    for spk, gender in genders.items():
        print(f"{spk} -> {gender}")
        
    # Detailed check for each speaker
    detector = analyzer.new_gender_detector
    sr = 16000
    y, _ = librosa.load(audio_path, sr=sr)
    
    for spk in genders.keys():
        print(f"\nDetails for {spk}:")
        spk_turns = [t for t in turns if t["speaker"] == spk]
        samples = []
        for t in spk_turns:
            s_idx = int(t["start"] * sr)
            e_idx = int(t["end"] * sr)
            samples.append(y[s_idx:e_idx])
        
        if samples:
            combined = np.concatenate(samples)
            features = detector.extract_features(combined)
            pitch = features[12] * 1000.0
            prob_dist = detector.model.predict_proba(features.reshape(1, -1))[0]
            print(f"  Pitch: {pitch:.1f}Hz")
            print(f"  Model Prob: {prob_dist}") 
            print(f"  Final Decision: {detector.predict(combined)['gender']}")

if __name__ == "__main__":
    debug_video_audio()
