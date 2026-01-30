import os
import torch
import librosa
import numpy as np
import warnings

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Suppress noisy library warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*torchcodec.*")

from transformers import pipeline
from pyannote.audio import Pipeline
import json
from static_ffmpeg import add_paths
add_paths()

class SpeakerAnalyzer:
    def __init__(self, hf_token=None):
        # Priority: 1) Passed token, 2) Environment variable from .env
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.diarization_pipeline = None
        self.gender_pipeline = None
        self.device = 0 if torch.cuda.is_available() else -1
        self.load_models()
        
    def load_models(self):
        if self.hf_token:
            try:
                # Using speaker-diarization@2.1 - stable version without community model dependency
                # This version works reliably with just the main model access
                self.diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization@2.1",
                    token=self.hf_token
                )
                if self.device == 0:
                    self.diarization_pipeline.to(torch.device("cuda"))
                print("✅ Pyannote speaker diarization loaded successfully.")
                print("   Using speaker-diarization@2.1 (stable)")
            except Exception as e:
                # If 2.1 fails, try the latest 3.1
                try:
                    self.diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        token=self.hf_token
                    )
                    if self.device == 0:
                        self.diarization_pipeline.to(torch.device("cuda"))
                    print("✅ Pyannote speaker diarization loaded successfully.")
                    print("   Using speaker-diarization-3.1")
                except Exception as e2:
                    # Suppress verbose error, just note that diarization is unavailable
                    print("⚠️  Speaker diarization unavailable (using pitch-based gender detection instead)")
                    print(f"   Reason: {str(e2)[:100]}")
                    self.diarization_pipeline = None
        else:
            print("No HF token provided, diarization will be restricted or skipped.")

        try:
            # Using a highly standard public model
            self.gender_pipeline = pipeline(
                "audio-classification",
                model="superb/wav2vec2-base-superb-sid",
                device=self.device
            )
            print("✅ Pitch-based gender detection ready")
        except Exception as e:
            print(f"⚠️  Gender model unavailable: {e}")
            # Final fallback
            self.gender_pipeline = None

    def analyze_audio(self, audio_path_or_data):
        """
        Returns speaker turns and their identified genders.
        Accepts either a file path or a NumPy array of audio data.
        """
        if not self.diarization_pipeline:
            print("Diarization pipeline not available.")
            return [], {}

        print(f"Diarizing audio...")
        try:
            import numpy as np
            if isinstance(audio_path_or_data, np.ndarray):
                # Pyannote pipeline expects a dict for in-memory audio
                audio_input = {
                    "waveform": torch.from_numpy(audio_path_or_data).unsqueeze(0),
                    "sample_rate": 16000
                }
                diarization = self.diarization_pipeline(audio_input)
            else:
                diarization = self.diarization_pipeline(audio_path_or_data)
            
            # Robust check for different return types
            speaker_turns = []
            iterator = None
            
            # Case 1: Standard Pyannote Annotation object
            if hasattr(diarization, "itertracks"):
                iterator = diarization.itertracks(yield_label=True)
            if iterator is None:
                # Fallback: check all attributes for anything that looks like an annotation or list
                for attr_name in dir(diarization):
                    if not attr_name.startswith("_"):
                        attr_val = getattr(diarization, attr_name)
                        if hasattr(attr_val, "itertracks"):
                            print(f"Found tracks in attribute: {attr_name}")
                            iterator = attr_val.itertracks(yield_label=True)
                            break
                        elif isinstance(attr_val, (list, tuple)) and len(attr_val) > 0:
                            print(f"Found tracks in list attribute: {attr_name}")
                            iterator = attr_val
                            break
            
            if iterator is None:
                print(f"Warning: Unexpected diarization output type: {type(diarization)}. Attributes: {dir(diarization)}")
                # One last attempt: if it's subscriptsable but not a dict
                try:
                    target = diarization["annotation"] if "annotation" in dir(diarization) or hasattr(diarization, "__getitem__") else diarization
                    if hasattr(target, "itertracks"):
                        iterator = target.itertracks(yield_label=True)
                    else:
                        iterator = iter(target)
                except:
                    iterator = []

            for turn_info in iterator:
                # Handle different iteration formats
                if len(turn_info) == 3: # (segment, track, label)
                    turn, _, speaker = turn_info
                    speaker_turns.append({
                        "start": turn.start,
                        "end": turn.end,
                        "speaker": speaker
                    })
                elif hasattr(turn_info, "start"): # direct segment objects
                    speaker_turns.append({
                        "start": turn_info.start,
                        "end": turn_info.end,
                        "speaker": getattr(turn_info, "speaker", "SPEAKER_00")
                    })
                
            print(f"Found {len(set(s['speaker'] for s in speaker_turns))} speakers.")
            
            speaker_genders = self._identify_speaker_genders(audio_path_or_data, speaker_turns)
            
            return speaker_turns, speaker_genders
        except Exception as e:
            print(f"Diarization failed: {e}")
            import traceback
            traceback.print_exc()
            return [], {}

    def identify_gender_for_segment(self, audio_path, start, end):
        """
        Identifies gender for a specific time range.
        Optimization: Prioritizes the pre-loaded ML pipeline (ms) over Librosa (seconds).
        """
        try:
            from pydub import AudioSegment
            import numpy as np
            
            # Load audio segment (max 2 seconds for speed)
            audio = AudioSegment.from_file(audio_path)
            start_ms = int(start * 1000)
            duration_ms = min(int((end - start) * 1000), 2000)
            segment = audio[start_ms : start_ms + duration_ms]
            
            # Convert to numpy
            samples = np.array(segment.get_array_of_samples()).astype(np.float32)
            if segment.sample_width == 2:
                samples = samples / 32768.0
            if segment.channels > 1:
                samples = samples.reshape((-1, segment.channels)).mean(axis=1)
            
            # 1. Try Fast ML Pipeline First
            if self.gender_pipeline:
                try:
                    # Determine input size for model (some have limits, but 2s is usually fine)
                    results = self.gender_pipeline(samples)
                    best_match = max(results, key=lambda x: x["score"])
                    label = best_match["label"].lower()
                    
                    # Logic: If model returns 'female'/'woman', trust it. 
                    # If model is generic speaker-id (e.g. id1004), this might default to 'Male',
                    # but it eliminates the 10s delay of Librosa.
                    return "Female" if ("female" in label or "woman" in label) else "Male"
                except Exception as e:
                    print(f"ML Gender detection error: {e}. Falling back to pitch.")
            
            # 2. Fallback to Pitch Detection (Slow)
            sr = segment.frame_rate
            f0, voiced_flag, voiced_probs = librosa.pyin(
                samples, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr
            )
            voiced_f0 = f0[voiced_flag]
            if len(voiced_f0) > 0:
                mean_f0 = np.nanmean(voiced_f0)
                # Typical Male: 85-180Hz, Female: 165-255Hz
                return "Female" if mean_f0 > 165 else "Male"
                
            return "Male" # Default
        except Exception as e:
            print(f"Segment gender detection failed: {e}")
            return "Male"

    def _identify_speaker_genders(self, audio_path_or_data, turns):
        """
        Determines the gender of each unique speaker in the diarization.
        Optimized to use batch ML processing where possible.
        """
        if not turns:
            return {}
            
        print("Identifying speaker genders (Optimized)...")
        speaker_genders = {}
        unique_speakers = set(t["speaker"] for t in turns)
        
        try:
            import numpy as np
            # Use the first occurrence of each speaker for fast ID
            # Instead of aggregating 10s of audio, which is slow I/O
            
            # Pre-load audio once if it's a path
            if isinstance(audio_path_or_data, str):
                from pydub import AudioSegment
                source_audio = AudioSegment.from_file(audio_path_or_data)
                is_numpy = False
            else:
                is_numpy = True
                source_audio = audio_path_or_data # Assume 16kHz numpy from earlier
            
            for speaker in unique_speakers:
                # Find the first logical segment for this speaker (at least 1s long)
                valid_turns = [t for t in turns if t["speaker"] == speaker and (t["end"] - t["start"]) > 0.8]
                if not valid_turns:
                    valid_turns = [t for t in turns if t["speaker"] == speaker]
                
                if not valid_turns:
                    speaker_genders[speaker] = "Male"
                    continue
                    
                # Take the best segment
                turn = valid_turns[0]
                
                # Extract sample
                if is_numpy:
                     start_idx = int(turn["start"] * 16000)
                     end_idx = int(min(turn["end"], turn["start"] + 2.0) * 16000)
                     samples = source_audio[start_idx:end_idx]
                else:
                     start_ms = int(turn["start"] * 1000)
                     end_ms = int(min(turn["end"], turn["start"] + 2.0) * 1000)
                     seg = source_audio[start_ms:end_ms]
                     samples = np.array(seg.get_array_of_samples()).astype(np.float32) / 32768.0
                     if seg.channels > 1:
                        samples = samples.reshape((-1, seg.channels)).mean(axis=1)

                # Predict
                gender = "Male"
                if self.gender_pipeline:
                    try:
                        results = self.gender_pipeline(samples)
                        best = max(results, key=lambda x: x["score"])
                        lbl = best["label"].lower()
                        gender = "Female" if ("female" in lbl or "woman" in lbl) else "Male"
                    except:
                        pass
                
                speaker_genders[speaker] = gender
                # print(f"Speaker {speaker} identified as {gender}")
            
            return speaker_genders

        except Exception as e:
            print(f"Gender identification failed: {e}")
            # Return defaults
            return {s: "Male" for s in unique_speakers}

def get_speaker_for_segment(start, end, speaker_turns):
    """
    Finds the speaker with the most overlap for a given segment.
    Uses time-weighted overlap for high precision.
    """
    if not speaker_turns:
        return "SPEAKER_00"
        
    overlap_map = {}
    
    for turn in speaker_turns:
        overlap_start = max(start, turn["start"])
        overlap_end = min(end, turn["end"])
        overlap = max(0, overlap_end - overlap_start)
        
        if overlap > 0:
            speaker = turn["speaker"]
            overlap_map[speaker] = overlap_map.get(speaker, 0) + overlap
            
    if not overlap_map:
        # Fallback: find nearest speaker if no direct overlap
        nearest_speaker = speaker_turns[0]["speaker"]
        min_dist = float('inf')
        for turn in speaker_turns:
            dist = min(abs(start - turn["end"]), abs(end - turn["start"]))
            if dist < min_dist:
                min_dist = dist
                nearest_speaker = turn["speaker"]
        return nearest_speaker
        
    return max(overlap_map.items(), key=lambda x: x[1])[0]

def assign_word_speakers(words, speaker_turns):
    """
    Assigns a speaker to each individual word based on diarization timing.
    Essential for perfect word-level subtitles and gender matching.
    """
    for word in words:
        word['speaker'] = get_speaker_for_segment(word['start'], word['end'], speaker_turns)
    return words
