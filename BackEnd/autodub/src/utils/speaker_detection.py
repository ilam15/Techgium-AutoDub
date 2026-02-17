import os
import torch
import librosa
import numpy as np
import warnings
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*torchcodec.*")

from src.core.config import settings
import src.config_constants as config
from src.engines.analysis.gender_engine import GenderDetector
from src.core.logger import logger

class SpeakerAnalyzer:
    """
    Revised Speaker Analyzer following the 'Gender is a speaker trait' architecture.
    1. Diarization groups audio by speaker over the entire file.
    2. All turns for a speaker are merged.
    3. Merged audio is normalized.
    4. Gender is predicted ONCE per speaker with a 3s minimum requirement.
    """
    def __init__(self, hf_token=None):
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.diarization_pipeline = None
        self.device = 0 if torch.cuda.is_available() else -1
        
        if settings.ENABLE_GENDER_DETECTION:
             logger.info("🚀 Initializing Global Speaker-Trait Architecture.")
             self.load_models()
             self.new_gender_detector = GenderDetector()
        else:
             self.new_gender_detector = None

    def load_models(self):
        try:
             from pyannote.audio import Pipeline
        except ImportError:
             logger.warning("⚠️ Pyannote not installed.")
             return

        if self.hf_token:
            model_id = "pyannote/speaker-diarization-3.1"
            try:
                # Standard for pyannote.audio 3.1+
                self.diarization_pipeline = Pipeline.from_pretrained(model_id, token=self.hf_token)
                logger.info("✅ Diarization pipeline ready (using 'token').")
            except TypeError as e:
                if "unexpected keyword argument 'token'" in str(e):
                    try:
                        self.diarization_pipeline = Pipeline.from_pretrained(model_id, use_auth_token=self.hf_token)
                        logger.info("✅ Diarization pipeline ready (using 'use_auth_token' fallback).")
                    except Exception as fallback_e:
                        logger.error(f"❌ Diarization fallback failed: {fallback_e}")
                else:
                    logger.error(f"❌ Diarization setup error: {e}")
            except Exception as e:
                logger.error(f"❌ Diarization setup failed: {e}")

            if self.diarization_pipeline and self.device == 0:
                try:
                    self.diarization_pipeline.to(torch.device("cuda"))
                except Exception as e:
                    logger.warning(f"Could not move diarization to CUDA: {e}")


    def analyze_audio(self, audio_path_or_data):
        """
        Groups audio by speaker and identifies genders for the whole file.
        """
        if not self.diarization_pipeline:
            return self._fallback_single_speaker(audio_path_or_data)

        try:
            # 1. Diarization
            if isinstance(audio_path_or_data, np.ndarray):
                waveform = torch.from_numpy(audio_path_or_data).float()
                if waveform.ndim == 1: waveform = waveform.unsqueeze(0)
                diarization = self.diarization_pipeline({"waveform": waveform, "sample_rate": 16000})
                y = audio_path_or_data
            else:
                diarization = self.diarization_pipeline(audio_path_or_data)
                y, _ = librosa.load(audio_path_or_data, sr=16000)

            # 2. Group by Speaker
            speaker_turns = []
            speaker_audio = {}
            sr = 16000
            
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speaker_turns.append({"start": turn.start, "end": turn.end, "speaker": speaker})
                
                # Collect audio chunk for this speaker
                start_f = int(turn.start * sr)
                end_f = int(turn.end * sr)
                if end_f > start_f:
                    chunk = y[start_f:end_f]
                    speaker_audio.setdefault(speaker, []).append(chunk)

            # 3. Merge and Predict per Speaker
            speaker_genders = {}
            for spk, chunks in speaker_audio.items():
                merged_audio = np.concatenate(chunks)
                
                # Minimum duration rule for stable prediction (Fix #2: Sweet Spot)
                # Accuracy increases significantly with segment length up to 3-5s.
                # We enforce a 2.5s minimum as requested in 'Best Settings'.
                if len(merged_audio) < sr * 2.5:
                    logger.info(f"Speaker {spk} has < 2.5s audio ({len(merged_audio)/sr:.1f}s). Labelling as Unknown.")
                    speaker_genders[spk] = "Unknown"
                    continue
                
                # Predict once per speaker
                result = self.new_gender_detector.predict(merged_audio)
                gender = result.get("gender", "Unknown").capitalize()
                
                logger.info(f"✅ Speaker {spk} Identified: {gender} (Conf: {result.get('confidence', 0):.2f})")
                speaker_genders[spk] = gender

            return speaker_turns, speaker_genders

        except Exception as e:
            logger.error(f"Global diarization analysis failed: {e}")
            return [], {}

    def _fallback_single_speaker(self, audio_path_or_data):
        if isinstance(audio_path_or_data, np.ndarray):
            y = audio_path_or_data
        else:
            y, _ = librosa.load(audio_path_or_data, sr=16000)
            
        duration = len(y) / 16000.0
        turns = [{"start": 0.0, "end": duration, "speaker": "SPEAKER_00"}]
        
        if self.new_gender_detector:
            res = self.new_gender_detector.predict(y)
            genders = {"SPEAKER_00": res.get("gender", "Unknown").capitalize()}
        else:
            genders = {"SPEAKER_00": "Male"}
            
        return turns, genders

    def identify_gender_for_segment(self, audio_path_or_data, start, duration):
        """
        Segment-based predictor (backup only).
        Uses the new robust feature set.
        """
        try:
            from src.utils.media_engine import MediaEngine
            if isinstance(audio_path_or_data, np.ndarray):
                s_idx = int(start * 16000)
                e_idx = s_idx + int(duration * 16000)
                chunk = audio_path_or_data[s_idx:e_idx]
            else:
                chunk = MediaEngine.extract_pure_audio_numpy_segment(audio_path_or_data, start, duration)
            
            if len(chunk) < 1024: return "Unknown"
            
            res = self.new_gender_detector.predict(chunk)
            return res.get("gender", "Unknown").capitalize()
        except:
            return "Unknown"
