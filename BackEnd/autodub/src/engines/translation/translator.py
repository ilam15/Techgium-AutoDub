import time
import hashlib
from typing import List, Tuple
from src.core.context import RequestContext
from src.core.logger import logger
from src.core.exceptions import TranslationError
from src.services.google_translate import translate_subtitle

class TranslationService:
    def __init__(self, context: RequestContext):
        self.context = context
        self._cache = {} # In-memory cache for the session (could extend to Redis)

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
        try:
            from src.app import model_manager
            
            # Shield speaker tags: <S:XX|G:XX> Text
            shielded_texts = []
            tags = []
            for sub in subtitles:
                match = re.search(r'(<S:.*?\|G:.*?>)?(.*)', sub.text, re.DOTALL)
                tag = match.group(1) or ""
                actual_text = match.group(2).strip()
                tags.append(tag)
                shielded_texts.append(actual_text)

            logger.info(f"Local NLLB translating {len(subtitles)} chunks...")
            
            # Batch translation
            translator = model_manager.get_translator()
            # NLLB pipeline can handle batches
            translations = translator(shielded_texts, src_lang=src_meta, tgt_lang=dst_meta, max_length=512)
            
            full_text_list = []
            for i, res in enumerate(translations):
                translated_txt = res['translation_text']
                # Re-attach tag
                final_text = f"{tags[i]} {translated_txt}".strip() if tags[i] else translated_txt
                subtitles[i].text = final_text
                full_text_list.append(final_text)
                
                if i == 0:
                    logger.info(f"Translation Sample: '{shielded_texts[0][:40]}' -> '{translated_txt[:40]}'")

            self.context.add_metric("translation_nllb", time.time() - st)
            return subtitles, " ".join(full_text_list)

        except Exception as e:
            logger.error(f"Local NLLB translation failed: {e}. Falling back to Google.")
            try:
                results, full_text = translate_subtitle(subtitles, src_name, dst_name)
                return results, full_text
            except Exception as e2:
                logger.error(f"All translation engines failed: {e2}")
                raise TranslationError(f"Translation pipeline failed: {e2}")
