import time
import hashlib
from typing import List, Tuple
from src.core.context import RequestContext
from src.core.logger import logger
from src.core.exceptions import TranslationError
from src.services.google_translate import translate_subtitle
import requests
from concurrent.futures import ThreadPoolExecutor
from src.core.config import settings

class TranslationService:
    def __init__(self, context: RequestContext):
        self.context = context
        self._cache = {} # In-memory cache for the session (could extend to Redis)

    def translate_text(self, text: str, src_name: str, dst_name: str) -> str:
        """Translates a single string using the batch engine."""
        from types import SimpleNamespace
        sub = SimpleNamespace(text=text)
        results, _ = self.translate_batches([sub], src_name, dst_name)
        return results[0].text

    def translate_batches(self, subtitles, src_name: str, dst_name: str):
        """
        Robust Translation Pipeline: 
        1. Sarvam AI (Indian Languages + English)
        2. Local NLLB Model (Offline / General)
        3. Google Translate (Final Fallback)
        """
        from src.utils.utils import language_dict
        import re

        # Normalize names for dict lookup
        def find_lang_info(name):
            for k, v in language_dict.items():
                if k.lower() == name.lower(): return v
            return {}

        src_info = find_lang_info(src_name)
        dst_info = find_lang_info(dst_name)
        
        src_meta = src_info.get("meta_code")
        dst_meta = dst_info.get("meta_code")
        s_code = src_info.get("lang_code", "")
        t_code = dst_info.get("lang_code", "")

        logger.info(f"TRANSLATE_SERVICE: {src_name} ({s_code}) -> {dst_name} ({t_code})")

        # Skip if languages are identical
        if src_name.lower() == dst_name.lower() or (s_code and s_code == t_code):
            logger.info("Skipping translation: Source and Target match.")
            return subtitles, " ".join([s.text for s in subtitles])

        st = time.time()
        
        # ---------------------------------------------------------
        # 1. SARVAM AI (Priority for Indian Languages)
        # ---------------------------------------------------------
        sarvam_supported = {
            "bn", "hi", "gu", "kn", "ml", "mr", "or", "pa", "ta", "te", "en"
        }
        
        if settings.SARVAM_API_KEY and s_code in sarvam_supported and t_code in sarvam_supported:
            try:
                sarvam_map = {
                    "bn": "bn-IN", "hi": "hi-IN", "gu": "gu-IN", "kn": "kn-IN",
                    "ml": "ml-IN", "mr": "mr-IN", "or": "od-IN", "pa": "pa-IN",
                    "ta": "ta-IN", "te": "te-IN", "en": "en-IN"
                }
                src_lang_sarvam = sarvam_map.get(s_code, f"{s_code}-IN")
                tgt_lang_sarvam = sarvam_map.get(t_code, f"{t_code}-IN")

                # Shield speaker tags: <S:XX|G:XX> Text
                shielded_texts = []
                tags = []
                for sub in subtitles:
                    match = re.search(r'(<S:.*?\|G:(.*?)>)?(.*)', sub.text, re.DOTALL)
                    tag = match.group(1) or ""
                    gender_hint = match.group(2) or "Male"
                    actual_text = match.group(3).strip()
                    tags.append((tag, gender_hint))
                    shielded_texts.append(actual_text)

                logger.info(f"Sarvam AI translating {len(subtitles)} chunks...")
                
                def translate_single_sarvam(item):
                    text, gender = item
                    if not text.strip(): return ""
                    url = "https://api.sarvam.ai/translate"
                    payload = {
                        "input": text,
                        "source_language_code": src_lang_sarvam,
                        "target_language_code": tgt_lang_sarvam,
                        "speaker_gender": gender,
                        "mode": "formal",
                        "model": "mayura:v1",
                        "enable_preprocessing": True
                    }
                    headers = {
                        "Content-Type": "application/json", 
                        "api-subscription-key": settings.SARVAM_API_KEY
                    }
                    # Add timeout to avoid hanging on DNS/Network issues
                    response = requests.post(url, json=payload, headers=headers, timeout=10)
                    response.raise_for_status()
                    return response.json().get("translated_text", "")

                with ThreadPoolExecutor(max_workers=5) as executor:
                    translations = list(executor.map(translate_single_sarvam, zip(shielded_texts, [t[1] for t in tags])))

                full_text_list = []
                for i, translated_txt in enumerate(translations):
                    final_text = f"{tags[i][0]} {translated_txt}".strip() if tags[i][0] else translated_txt
                    subtitles[i].text = final_text
                    full_text_list.append(final_text)

                self.context.add_metric("translation_sarvam", time.time() - st)
                return subtitles, " ".join(full_text_list)

            except Exception as e:
                logger.warning(f"Sarvam AI failed ({e}). Falling back to Local NLLB.")

        # ---------------------------------------------------------
        # 2. LOCAL NLLB MODEL (The Reliable Offline Choice)
        # ---------------------------------------------------------
        if src_meta and dst_meta:
            try:
                from src.app import model_manager
                
                shielded_texts = []
                tags = []
                for sub in subtitles:
                    match = re.search(r'(<S:.*?\|G:.*?>)?(.*)', sub.text, re.DOTALL)
                    tag = match.group(1) or ""
                    actual_text = match.group(2).strip()
                    tags.append(tag)
                    shielded_texts.append(actual_text)

                logger.info(f"Local NLLB translating {len(subtitles)} chunks...")
                translator = model_manager.get_translator()
                translations = translator(shielded_texts, src_lang=src_meta, tgt_lang=dst_meta, max_length=512)
                
                full_text_list = []
                for i, res in enumerate(translations):
                    translated_txt = res['translation_text']
                    final_text = f"{tags[i]} {translated_txt}".strip() if tags[i] else translated_txt
                    subtitles[i].text = final_text
                    full_text_list.append(final_text)

                self.context.add_metric("translation_nllb", time.time() - st)
                return subtitles, " ".join(full_text_list)
            except Exception as e:
                logger.error(f"Local NLLB failed ({e}). Falling back to Google.")

        # ---------------------------------------------------------
        # 3. GOOGLE TRANSLATE (The Universal Web Safety Net)
        # ---------------------------------------------------------
        try:
            results, full_text = translate_subtitle(subtitles, src_name, dst_name)
            return results, full_text
        except Exception as e:
            logger.error(f"All translation engines failed: {e}")
            raise TranslationError(f"Translation pipeline failed: {e}")
