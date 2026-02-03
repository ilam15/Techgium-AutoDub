
import re
import time
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor
from src.utils.utils import language_dict
from src.core.logger import logger

def get_log_extra():
    # Helper to maintain compatibility with logger calls if they use extra
    return {}

def translate_text(text, Source_Language, Destination_Language, max_retries=3):
    """
    Translates the given text using GoogleTranslator, preserving speaker/gender tags.
    Implements retry logic with exponential backoff for connection errors.
    """
    # If source and destination are the same, return original text
    if Source_Language == Destination_Language:
        return text
    
    # Safety: If Source_Language is already a code (e.g. 'en', 'hi'), resolve it or use as is
    source_language = language_dict.get(Source_Language, {}).get('lang_code', Source_Language)
    target_language = language_dict.get(Destination_Language, {}).get('lang_code', Destination_Language)

    # Adjust for specific language codes
    if Destination_Language == "Chinese":
        target_language = 'zh-CN'
    
    # Skip translation if language codes are the same
    if source_language == target_language:
        return text

    # Extract tags: <S:SPEAKER_00|G:Male> Text
    tag_match = re.match(r'(<S:.*?\|G:.*?>) (.*)', text)
    if tag_match:
        tag = tag_match.group(1)
        actual_text = tag_match.group(2)
    else:
        tag = ""
        actual_text = text

    if not actual_text.strip():
        return text
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            translator = GoogleTranslator(source=source_language, target=target_language)
            translation = translator.translate(actual_text.strip())
            
            if tag:
                # Ensure the tag is preserved exactly as it was
                return f"{tag} {str(translation)}"
            else:
                return str(translation)
                
        except (ConnectionResetError, ConnectionAbortedError, ConnectionError) as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5s, 1s, 2s
                logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Translation failed after {max_retries} attempts: {e}. Returning original text.")
                # Return original text with tag if present
                return text
                
        except Exception as e:
            logger.error(f"Translation error: {e}. Returning original text.")
            return text
    
    return text

def translate_subtitle(subtitles, Source_Language, Destination_Language):
    """
    Translates subtitles using robust ID-based batching.
    Extracts speaker/gender tags before translation to prevent mangling.
    """
    if Source_Language == Destination_Language:
        return subtitles, " ".join([s.text for s in subtitles])

    logger.info(f"ID-Batch translating {len(subtitles)} segments with tag-shielding...")
    
    # 1. Configuration
    batch_size = 15 
    batches = [subtitles[i:i + batch_size] for i in range(0, len(subtitles), batch_size)]
    
    translated_texts = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        def process_batch(batch_subs):
            # Extract tags: <S:XX|G:XX> Text -> (tag, text)
            tag_map = {}
            tagged_lines = []
            
            for idx, sub in enumerate(batch_subs):
                match = re.match(r'(<S:.*?\|G:.*?>) (.*)', sub.text)
                if match:
                    tag_map[idx] = match.group(1)
                    actual_text = match.group(2)
                else:
                    tag_map[idx] = ""
                    actual_text = sub.text
                
                # Wrap ONLY the actual text in protection IDs
                tagged_lines.append(f"[#{idx}#] {actual_text} [#{idx}#]")
            
            combined_text = "\n".join(tagged_lines)
            # Use raw translation on the protected block
            translated_block = translate_text(combined_text, Source_Language, Destination_Language)
            
            # Extract by ID and re-attach tags
            results = []
            for idx in range(len(batch_subs)):
                pattern = rf"\[#{idx}#\](.*?)(\[#{idx}#\]|$)"
                match = re.search(pattern, translated_block, re.DOTALL)
                if match:
                    cleaned_translation = match.group(1).strip()
                    # Re-attach the shielded tag
                    if tag_map[idx]:
                        results.append(f"{tag_map[idx]} {cleaned_translation}")
                    else:
                        results.append(cleaned_translation)
                else:
                    results.append(batch_subs[idx].text)
            return results

        batch_results = list(executor.map(process_batch, batches))
        for res in batch_results:
            translated_texts.extend(res)

    store_text = ""
    for i in range(min(len(subtitles), len(translated_texts))):
        subtitles[i].text = translated_texts[i]
        store_text += translated_texts[i] + " "

    return subtitles, store_text
