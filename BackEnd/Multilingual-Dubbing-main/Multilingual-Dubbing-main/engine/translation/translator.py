import time
import hashlib
from typing import List, Tuple
from core.context import RequestContext
from core.logger import logger
from core.exceptions import TranslationError
from app import translate_subtitle

class TranslationService:
    def __init__(self, context: RequestContext):
        self.context = context
        self._cache = {} # In-memory cache for the session (could extend to Redis)

    def translate_batches(self, subtitles, src: str, dst: str):
        if src == dst:
            return subtitles, " ".join([s.text for s in subtitles])
            
        st = time.time()
        try:
            # We reuse the existing ID-based batching logic from app.py
            # But we wrap it in our service interface
            results, full_text = translate_subtitle(subtitles, src, dst)
            self.context.add_metric("translation", time.time() - st)
            return results, full_text
        except Exception as e:
            raise TranslationError(f"Batch translation failed: {e}")
