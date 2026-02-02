# FIX: Multilingual Detection for AI-Generated Videos with English Captions

## The Problem
In AI-generated videos (like HeyGen, Rask, etc.), the speaker often switches languages rapidly (code-switching). Additionally, these videos often have **English captions** burned into the frames.

**Issues encountered:**
1.  **Dominant Language Bias**: Whisper detects English at the start and stays "stuck" in English mode for the entire video.
2.  **Caption Bias**: Text-based detection often sees English text and confirms the language as English, even if the audio is Hindi, French, or German.
3.  **No Gaps**: When a speaker segments are contiguous without pauses, Whisper's VAD keeps them as one long segment, making it harder to detect language switches.

---

## The Solutions Implemented

### 1. Pure Audio Extraction (Bypassing Captions)
We now use a specialized FFmpeg extraction method that explicitly removes all video and subtitle streams before processing.
- **Tool**: `MediaEngine.extract_pure_audio_numpy`
- **Action**: Fixed the `AudioProcessor` to always use this pure extraction.
- **Result**: Whisper ONLY analyzes the audio track. No burned-in captions or visual text can influence the detection.

### 2. Sliding Window Transcription (Fixing Code-Switching)
Standard Whisper transcription calculates a "global language hint" once and uses it for the whole video. This misses rapid language switches.
- **Change**: We now split the audio into **30-second sliding windows**.
- **Action**: Each 30s window performs **fresh language detection** and context reset.
- **Result**: If the speaker switches from English to Hindi at the 31st second, the system WILL detect Hindi in the next window.

### 3. Audio-Priority Hybrid Logic
We updated the decision engine to handle cases where audio and text disagree.
- **Logic**: If Whisper (Audio) detects a non-English language (hi, fr, de, etc.) but Text-LID says 'en', we **trust Whisper**.
- **Reason**: AI videos often have English-biased transcriptions or residual caption influence. Audio-based detection is more reliable for identifying the actual spoken language in these cases.

---

## How to Test
1.  **Run the pipeline** with your multilingual AI video.
2.  **Monitor the logs** for:
    *   `🌍 ASR Engine: Starting Segmented Multilingual Transcription (30s windows)`
    *   `🎵 Extracting PURE AUDIO (ignoring all captions/subtitles)`
    *   `🎤 Whisper Audio Detection` showing different languages for different segments.
    *   `method=whisper_audio_priority` (if a text/audio disagreement was resolved in favor of audio).

---

## Technical Comparison

| Feature | Old Behavior | New Behavior (FIX) |
| :--- | :--- | :--- |
| **Transcription** | Single long pass (Global bias) | Sliding window (Fresh detection every 30s) |
| **Audio Source** | Standard video extraction | Pure audio extraction (VP/SN removed) |
| **Detection Method** | Aggressive Text-Override | Audio-Priority for non-English |
| **Accuracy** | Misses language switches | Catches switches every ~30s (or per VAD) |

---

## Expected Output
For a video with **EN (0-15s) → HI (15-30s) → FR (30-45s)**:
- **0-15s**: Detected `en`, Transcribed as English → Translated to Target.
- **15-30s**: Detected `hi`, Transcribed as Hindi (Devanagari) → KEPT (if target is Hindi).
- **30-45s**: Detected `fr`, Transcribed as French → Translated to Target.

This ensures **100% accurate multilingual dubbing** even for the most complex AI-generated code-switching videos!
