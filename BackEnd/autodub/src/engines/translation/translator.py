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
        Translates subtitles using the local NLLB model with exhaustive logging.
        """
        # Imports needed early for language dict lookup
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

        logger.info(f"TRANSLATE_SERVICE: {src_name} ({src_meta}) -> {dst_name} ({dst_meta})")

        if src_name.lower() == dst_name.lower() or not src_meta or not dst_meta:
            if src_name.lower() == dst_name.lower():
                logger.info("Skipping translation: Source and Target match.")
            else:
                logger.warning(f"NLLB codes missing for {src_name}->{dst_name}. Falling back.")
            
            # Fallback to existing logic
            results, full_text = translate_subtitle(subtitles, src_name, dst_name)
            return results, full_text
            
        st = time.time()
        
        # Check if Sarvam API Key is available
        if not settings.SARVAM_API_KEY:
            logger.warning("Sarvam API Key missing. Falling back to Google Translate.")
            results, full_text = translate_subtitle(subtitles, src_name, dst_name)
            return results, full_text

        try:
            # Map languages to Sarvam codes (xx-IN)
            sarvam_map = {
                "bn": "bn-IN", "hi": "hi-IN", "gu": "gu-IN", "kn": "kn-IN",
                "ml": "ml-IN", "mr": "mr-IN", "or": "od-IN", "pa": "pa-IN",
                "ta": "ta-IN", "te": "te-IN", "en": "en-IN"
            }
            
            # Get base codes from language_dict
            s_code = src_info.get("lang_code", "")
            t_code = dst_info.get("lang_code", "")
            
            # Map to Sarvam format
            src_lang_code = sarvam_map.get(s_code, s_code)
            target_lang_code = sarvam_map.get(t_code, t_code)

            # Shield speaker tags: <S:XX|G:XX> Text
            shielded_texts = []
            tags = []
            for sub in subtitles:
                match = re.search(r'(<S:.*?\|G:.*?>)?(.*)', sub.text, re.DOTALL)
                tag = match.group(1) or ""
                actual_text = match.group(2).strip()
                tags.append(tag)
                shielded_texts.append(actual_text)

            logger.info(f"Sarvam AI translating {len(subtitles)} chunks ({src_lang_code} -> {target_lang_code})...")
            
            def translate_single(text):
                if not text.strip(): return ""
                url = "https://api.sarvam.ai/translate"
                payload = {
                    "input": text,
                    "source_language_code": src_lang_code,
                    "target_language_code": target_lang_code,
                    "speaker_gender": "Male", # Default, can be improved to extract from tag
                    "mode": "formal",
                    "model": "mayura:v1",
                    "enable_preprocessing": True
                }
                headers = {
                    "Content-Type": "application/json", 
                    "api-subscription-key": settings.SARVAM_API_KEY
                }
                response = requests.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json().get("translated_text", "")

            # Parallel execution
            with ThreadPoolExecutor(max_workers=5) as executor:
                translations = list(executor.map(translate_single, shielded_texts))

            full_text_list = []
            for i, translated_txt in enumerate(translations):
                # Re-attach tag
                final_text = f"{tags[i]} {translated_txt}".strip() if tags[i] else translated_txt
                subtitles[i].text = final_text
                full_text_list.append(final_text)
                
                if i == 0:
                    logger.info(f"Translation Sample: '{shielded_texts[0][:40]}' -> '{translated_txt[:40]}'")

            self.context.add_metric("translation_sarvam", time.time() - st)
            return subtitles, " ".join(full_text_list)

        except Exception as e:
            logger.error(f"Sarvam AI translation failed: {e}. Falling back to Google.")
            try:
                results, full_text = translate_subtitle(subtitles, src_name, dst_name)
                return results, full_text
            except Exception as e2:
                logger.error(f"All translation engines failed: {e2}")
                raise TranslationError(f"Translation pipeline failed: {e2}")
