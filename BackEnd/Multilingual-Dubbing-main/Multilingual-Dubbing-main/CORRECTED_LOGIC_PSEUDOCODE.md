# Corrected Dubbing Logic - Pseudo-Code

## High-Level Algorithm

```
FOR each video segment:
    1. Get per-segment language from Whisper (audio-based)
    2. Validate with text-based LID (fastText/langid)
    3. Decide: Whisper or text-based detection
    4. Compare detected_language with target_language
    5. IF detected_language != target_language:
           TRANSLATE segment
       ELSE:
           KEEP original audio
```

## Detailed Pseudo-Code

```python
# STEP 1: ASR with Per-Segment Language Detection
def transcribe_audio(audio_data, source_lang_hint):
    segments, global_info = whisper.transcribe(audio_data, language=source_lang_hint)
    
    for seg in segments:
        # CRITICAL: Capture per-segment language (not just global)
        seg.segment_language = seg.language or global_info.language
        seg.global_hint = global_info.language
    
    return segments, global_info


# STEP 2: Hybrid Per-Segment Language Detection
def detect_segment_language(segment, text, fasttext_model):
    # Priority 1: Whisper's per-segment audio-based detection
    whisper_lang = segment.segment_language
    
    # Priority 2: Text-based validation
    if len(text) < 3:
        # Too short for text analysis, trust Whisper's audio detection
        return whisper_lang, 0.7, "whisper_audio"
    
    # Use fastText for text-based detection
    text_lang, text_confidence = fasttext_model.predict(text)
    
    # Hybrid decision: Combine audio + text
    if text_confidence > 0.7 and text_lang != whisper_lang:
        # High-confidence text detection disagrees with Whisper
        return text_lang, text_confidence, "text_override"
    else:
        # Trust Whisper's audio-based detection
        return whisper_lang, text_confidence, "whisper_confirmed"


# STEP 3: Translation Decision Logic
def decide_translation(detected_lang, target_lang, text):
    # Check for noise/silence
    if is_noise(text):
        return "KEEP", "Non-speech/Noise"
    
    # Simple rule: Translate anything not in target language
    if detected_lang.lower() == target_lang.lower():
        return "KEEP", f"Already in target language ({detected_lang})"
    else:
        return "TRANSLATE", f"Source: {detected_lang} → Target: {target_lang}"


# STEP 4: Process All Segments
def process_video(video_path, target_language):
    # Extract audio
    audio_data = extract_audio(video_path)
    
    # Transcribe with per-segment language detection
    segments, global_info = transcribe_audio(audio_data, source_lang_hint="auto")
    
    # Process each segment independently
    for segment in segments:
        text = segment.text
        
        # Detect language (hybrid approach)
        detected_lang, confidence, method = detect_segment_language(
            segment, text, fasttext_model
        )
        
        # Decide: TRANSLATE or KEEP
        action, reason = decide_translation(detected_lang, target_language, text)
        
        # Log decision
        log(f"SEG[{segment.id}] lang={detected_lang} action={action} reason={reason}")
        
        # Execute action
        if action == "TRANSLATE":
            translated_text = translate(text, detected_lang, target_language)
            dubbed_audio = tts(translated_text, target_language, segment.gender)
            replace_audio_segment(segment.start, segment.end, dubbed_audio)
        else:
            # Keep original audio
            pass
    
    # Merge all segments
    final_video = merge_audio_video(video_path, dubbed_audio_timeline)
    return final_video
```

## Key Differences from Previous Logic

### ❌ OLD (BROKEN)
```python
# Used global language hint for all segments
whisper_hint = global_info.language  # Same for ALL segments!

# Fell back to global hint for short text
if len(text) < 3:
    detected_lang = global_info.language  # ❌ Global bias

# Weak decision logic
if detected_lang == target_lang:
    action = "KEEP"
else:
    action = "TRANSLATE"  # But detection was biased!
```

### ✅ NEW (FIXED)
```python
# Use per-segment language from Whisper
whisper_lang = segment.segment_language  # Different for each segment!

# Trust Whisper's audio detection for short text
if len(text) < 3:
    detected_lang = segment.segment_language  # ✅ Per-segment

# Strict decision logic
if detected_lang == target_lang:
    action = "KEEP"
else:
    action = "TRANSLATE"  # Detection is now accurate!
```

## Example Execution Flow

### Input Video
```
[0-5s]   English:  "Hello, welcome"
[5-10s]  Hindi:    "नमस्ते"
[10-15s] French:   "Bonjour"
[15-20s] German:   "Guten Tag"
[20-25s] English:  "Thank you"
```

### Target Language: Hindi

### Processing Steps

#### Segment 1: [0-5s] "Hello, welcome"
```
1. Whisper per-segment: "en"
2. Text-based (fastText): "en" (conf=0.95)
3. Hybrid decision: "en" (whisper_confirmed)
4. Translation decision: "en" != "hi" → TRANSLATE
5. Action: Translate "Hello, welcome" to Hindi
```

#### Segment 2: [5-10s] "नमस्ते"
```
1. Whisper per-segment: "hi"
2. Text-based (fastText): "hi" (conf=0.98)
3. Hybrid decision: "hi" (whisper_confirmed)
4. Translation decision: "hi" == "hi" → KEEP
5. Action: Keep original audio
```

#### Segment 3: [10-15s] "Bonjour"
```
1. Whisper per-segment: "fr"  ✅ (Previously was "en" due to global bias)
2. Text-based (fastText): "fr" (conf=0.92)
3. Hybrid decision: "fr" (whisper_confirmed)
4. Translation decision: "fr" != "hi" → TRANSLATE
5. Action: Translate "Bonjour" to Hindi
```

#### Segment 4: [15-20s] "Guten Tag"
```
1. Whisper per-segment: "de"  ✅ (Previously was "en" due to global bias)
2. Text-based (fastText): "de" (conf=0.89)
3. Hybrid decision: "de" (whisper_confirmed)
4. Translation decision: "de" != "hi" → TRANSLATE
5. Action: Translate "Guten Tag" to Hindi
```

#### Segment 5: [20-25s] "Thank you"
```
1. Whisper per-segment: "en"
2. Text-based (fastText): "en" (conf=0.94)
3. Hybrid decision: "en" (whisper_confirmed)
4. Translation decision: "en" != "hi" → TRANSLATE
5. Action: Translate "Thank you" to Hindi
```

### Final Output
```
[0-5s]   Hindi: "नमस्ते, स्वागत है"      (Translated from English)
[5-10s]  Hindi: "नमस्ते"                 (Original Hindi kept)
[10-15s] Hindi: "नमस्कार"                (Translated from French) ✅
[15-20s] Hindi: "नमस्ते"                 (Translated from German) ✅
[20-25s] Hindi: "धन्यवाद"                (Translated from English)
```

## Defensive Checks

### 1. Timestamp Matching
```python
# Match segments by timestamp with tolerance
for seg in segments:
    if abs(seg.start - sentence.start) < 0.1:  # 100ms tolerance
        whisper_lang = seg.segment_language
        break
```

### 2. Graceful Fallbacks
```python
# Fallback chain for language detection
try:
    # Try per-segment language
    lang = segment.segment_language
except:
    try:
        # Fallback to global language
        lang = global_info.language
    except:
        # Last resort: assume source language hint
        lang = source_lang_hint
```

### 3. Error Handling
```python
# Handle text-based LID failures
try:
    text_lang, confidence = fasttext_model.predict(text)
except Exception as e:
    logger.warning(f"Text LID failed: {e}")
    # Fallback to Whisper's audio detection
    text_lang = whisper_lang
    confidence = 0.6
```

### 4. Noise Detection
```python
# Detect noise/silence with Unicode support
def is_noise(text):
    if not text.strip():
        return True
    if len(text.strip()) < 2:
        return True
    # Check for actual characters (Latin, Devanagari, Arabic, CJK)
    if not re.search(r'[a-zA-Z\u0900-\u0D7F\u0600-\u06FF\u4E00-\u9FFF]', text):
        return True
    return False
```

## Summary

### Core Principle
**Every segment is processed independently based on its own detected language, not the global video language.**

### Key Changes
1. Capture `segment.language` from Whisper (not just `global_info.language`)
2. Use hybrid detection: Whisper audio + text validation
3. Strict rule: `if detected_lang != target_lang: TRANSLATE`
4. No global bias, no assumptions, no exceptions

### Result
All segments in all languages are correctly identified and translated to the target language.
