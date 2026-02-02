# CRITICAL ISSUE: AI-Generated Videos with English Captions

## The Real Problem

### Your Scenario
- **Video Type**: AI-generated multilingual video
- **Captions**: English text (burned-in or subtitle file)
- **Audio**: Speaker's voice in multiple languages (EN, HI, FR, DE)
- **Issue**: Whisper transcribes based on captions, not actual audio language

### Why Current Solution Doesn't Work

```
Segment 1 Audio: Speaker speaks English
Segment 1 Captions: "If you still haven't heard about this AI"
Whisper: Reads captions → Transcribes as English ✅

Segment 2 Audio: Speaker speaks Hindi
Segment 2 Captions: "Okay, I'm speaking English to you right now"
Whisper: Reads captions → Transcribes as English ❌ (should detect Hindi audio!)

Segment 3 Audio: Speaker speaks French
Segment 3 Captions: "The crazy part is that this whole time"
Whisper: Reads captions → Transcribes as English ❌ (should detect French audio!)
```

**Result**: All segments detected as English because Whisper is reading the English captions, not analyzing the actual audio language!

---

## Root Cause

### Whisper's Behavior with Captions

When a video has **burned-in captions** or **subtitle files**, Whisper may:
1. **Prioritize visual text** (OCR from burned-in captions)
2. **Use caption timing** to align transcription
3. **Ignore audio language** if captions are present

This is why all segments show:
```
🎤 Whisper Audio Detection: lang=en (prob=1.00)
```

Even though the speaker is speaking Hindi/French/German!

---

## Possible Solutions

### Solution 1: Remove Captions Before Processing

**Approach**: Strip captions from the video before sending to Whisper

**Pros**:
- Forces Whisper to analyze audio only
- Should detect actual spoken language

**Cons**:
- Requires video preprocessing
- May lose timing information
- Complex implementation

**Implementation**:
```python
# Use FFmpeg to remove captions
ffmpeg -i input.mp4 -c copy -sn output_no_captions.mp4
```

---

### Solution 2: Force Audio-Only Analysis

**Approach**: Extract audio separately and analyze it independently

**Pros**:
- Guaranteed audio-only analysis
- No caption interference

**Cons**:
- Need to re-sync with video
- May lose visual context

**Implementation**:
```python
# Extract audio only
ffmpeg -i input.mp4 -vn -acodec pcm_s16le audio_only.wav

# Analyze audio with Whisper
# Then sync back to video
```

---

### Solution 3: Manual Language Mapping (Timestamp-Based)

**Approach**: User provides timestamp ranges for each language

**Pros**:
- 100% accurate if user knows the video
- No AI detection needed

**Cons**:
- Requires manual input
- Not automated

**Implementation**:
```python
language_map = {
    (0.0, 5.0): "en",      # 0-5s: English
    (5.0, 10.0): "hi",     # 5-10s: Hindi
    (10.0, 15.0): "fr",    # 10-15s: French
    (15.0, 20.0): "de",    # 15-20s: German
    (20.0, 36.7): "en"     # 20-36.7s: English
}
```

---

### Solution 4: Multiple Whisper Passes (Language-Specific)

**Approach**: Run Whisper multiple times with different language hints

**Pros**:
- Can detect if audio matches specific language
- Uses Whisper's strength

**Cons**:
- Very slow (multiple passes)
- Computationally expensive

**Implementation**:
```python
# Pass 1: language="en"
# Pass 2: language="hi"
# Pass 3: language="fr"
# Pass 4: language="de"
# Compare confidence scores to determine actual language
```

---

### Solution 5: Use Alternative ASR (Language-Agnostic)

**Approach**: Use a different ASR model that doesn't rely on captions

**Pros**:
- May be more accurate for audio-only
- Designed for multilingual audio

**Cons**:
- Requires new model integration
- May have lower accuracy

**Options**:
- Google Speech-to-Text
- Azure Speech Services
- AssemblyAI

---

## Recommended Solution

### **Hybrid Approach: Audio Extraction + Manual Override**

1. **Extract audio-only** from video (no captions)
2. **Run Whisper on pure audio** to detect language
3. **Provide manual override** option for known language segments

### Implementation Steps

#### Step 1: Extract Audio Only
```python
def extract_audio_only(video_path):
    """Extract audio without any video/caption influence"""
    audio_path = video_path.replace('.mp4', '_audio_only.wav')
    
    ffmpeg_cmd = [
        'ffmpeg', '-i', video_path,
        '-vn',  # No video
        '-acodec', 'pcm_s16le',  # Raw audio
        '-ar', '16000',  # 16kHz
        '-ac', '1',  # Mono
        audio_path
    ]
    
    subprocess.run(ffmpeg_cmd)
    return audio_path
```

#### Step 2: Analyze Pure Audio
```python
# Whisper will now ONLY hear the audio, not see captions
audio_only = extract_audio_only(video_path)
segments, info = whisper.transcribe(audio_only, language=None)
```

#### Step 3: Manual Language Override (Optional)
```python
# API accepts manual language mapping
{
    "video": "video.mp4",
    "target_language": "Hindi",
    "language_segments": [
        {"start": 0.0, "end": 5.0, "language": "en"},
        {"start": 5.0, "end": 10.0, "language": "hi"},
        {"start": 10.0, "end": 15.0, "language": "fr"},
        {"start": 15.0, "end": 20.0, "language": "de"}
    ]
}
```

---

## Quick Test

### Verify if Captions are the Issue

1. **Extract audio only**:
   ```bash
   ffmpeg -i Video10.mp4 -vn -acodec pcm_s16le audio_only.wav
   ```

2. **Run Whisper on audio only**:
   ```python
   result = whisper.transcribe("audio_only.wav", language=None)
   print(result['language'])  # What language does it detect?
   ```

3. **Compare**:
   - If audio-only detects different languages → Captions are the issue ✅
   - If audio-only still detects only English → Video is actually all English ❌

---

## Questions for You

### 1. **Can you confirm the video structure?**
   - [ ] Video has burned-in English captions
   - [ ] Video has separate subtitle file
   - [ ] No captions, just audio

### 2. **Do you know the language timestamps?**
   - [ ] Yes, I know when each language is spoken
   - [ ] No, I need automatic detection

### 3. **Can you test audio extraction?**
   - [ ] Yes, I can extract audio and test
   - [ ] No, I need an automated solution

---

## Next Steps

Based on your answers, I can implement:

**Option A**: Audio-only extraction and analysis (automatic)
**Option B**: Manual language mapping API (user-provided timestamps)
**Option C**: Hybrid approach (audio extraction + manual override)

**Please let me know:**
1. Does the video have English captions?
2. Do you know the timestamps for each language?
3. Should I implement audio-only extraction?
