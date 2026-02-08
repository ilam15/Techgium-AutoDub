import os
import re
import urllib.request
import langid
from collections import Counter
from src.core.config import settings
from src.core.logger import logger
from src.utils.utils import get_language_name, language_dict

# Attempt fasttext import
try:
    import fasttext
except ImportError:
    fasttext = None

class DecisionEngine:
    _fasttext_model = None

    @classmethod
    def get_fasttext_model(cls):
        if cls._fasttext_model is None and fasttext:
            fasttext_model_dir = os.path.join(settings.BASE_DIR, "engine", "lid")
            os.makedirs(fasttext_model_dir, exist_ok=True)
            fasttext_model_path = os.path.join(fasttext_model_dir, "lid.176.bin")
            
            if not os.path.exists(fasttext_model_path):
                logger.info("Initializing fastText download...")
                try:
                    urllib.request.urlretrieve(
                        "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin",
                        fasttext_model_path
                    )
                except Exception as e:
                    logger.warning(f"Failed to download fastText: {e}")
                    return None
            
            try:
                cls._fasttext_model = fasttext.load_model(fasttext_model_path)
            except Exception as e:
                logger.warning(f"Failed to load fastText: {e}")
        return cls._fasttext_model

    @staticmethod
    def identify_language(text, whisper_lang, whisper_prob):
        if not text or len(text.strip()) < 3:
            return whisper_lang, 0.7, "audio_probe_short"

        fasttext_model = DecisionEngine.get_fasttext_model()
        
        try:
            if fasttext_model:
                predictions = fasttext_model.predict(text.replace('\n', ' '), k=1)
                text_lang = predictions[0][0].replace('__label__', '')
                text_conf = float(predictions[1][0])
                
                # Normalize
                lang_map = {'eng': 'en', 'hin': 'hi', 'tel': 'te', 'tam': 'ta', 'kan': 'kn', 
                           'mal': 'ml', 'mar': 'mr', 'guj': 'gu', 'ben': 'bn', 'pan': 'pa'}
                text_lang = lang_map.get(text_lang, text_lang[:2])
            else:
                text_lang, text_conf = langid.classify(text)
            
            # Hybrid Decision
            if whisper_lang != 'en' and (text_lang == 'en' or text_conf < 0.7):
                return whisper_lang, whisper_prob or 0.8, "audio_probe_priority"
            elif text_conf > 0.85:
                return text_lang, text_conf, "text_override"
            else:
                return whisper_lang, whisper_prob or 0.5, "whisper_fallback"
        except Exception as e:
            logger.warning(f"LID Error: {e}")
            return whisper_lang, 0.5, "error_fallback"

    @staticmethod
    def get_decision(segments, turns, speaker_genders, target_lang, user_known_languages, global_whisper_lang):
        """
        Full production decision logic.
        """
        from src.utils.speaker_detection import get_speaker_for_segment
        
        # Normalize target
        target_code = ""
        for k, v in language_dict.items():
            if k.lower() == target_lang.lower():
                target_code = v["lang_code"].lower()
                break
        if not target_code: target_code = target_lang.lower()

        processed_segments = []
        for s in segments:
            text = s['text']
            # Speaker
            speaker = get_speaker_for_segment(s['start'], s['end'], turns)
            gender = speaker_genders.get(speaker, "Male")
            
            # UID
            whisper_lang = s.get('segment_language') or global_whisper_lang
            whisper_prob = s.get('segment_language_prob') or 0.0
            
            detected_lang, conf, method = DecisionEngine.identify_language(text, whisper_lang, whisper_prob)
            
            # Decision logic
            is_noise = not bool(re.search(r'[a-zA-Z\u0900-\u0D7F]', text)) or len(text.strip()) < 2
            
            if is_noise:
                action = "KEEP"
                reason = "Noise/Silence"
            elif detected_lang == target_code:
                action = "KEEP"
                reason = f"Already in target ({target_code})"
            else:
                action = "TRANSLATE"
                reason = f"Source {detected_lang} -> Target {target_code}"
                
            s.update({
                "speaker": speaker,
                "gender": gender,
                "lang": detected_lang,
                "lid_confidence": conf,
                "lid_method": method,
                "action": action,
                "reason": reason
            })
            processed_segments.append(s)
            
        return processed_segments
