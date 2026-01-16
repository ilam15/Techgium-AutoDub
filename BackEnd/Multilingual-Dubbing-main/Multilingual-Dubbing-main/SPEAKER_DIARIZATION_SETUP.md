# Speaker Diarization & Gender Classification Setup

## Overview
Your system is **fully configured** to automatically:
1. ✅ Segment audio by speaker turns using `pyannote-audio`
2. ✅ Identify gender (Male/Female) for each speaker using pitch analysis
3. ✅ Assign correct dubbing voices automatically for multi-speaker videos

## Current Status
- **Gender Detection**: ✅ Working (pitch-based F0 analysis)
- **Speaker Diarization**: ⚠️ Requires Hugging Face Token

## How to Enable Full Multi-Speaker Detection

### Step 1: Get Your Hugging Face Token

1. **Create Account**: Go to [https://huggingface.co/join](https://huggingface.co/join)
2. **Generate Token**: 
   - Visit [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
   - Click "New token"
   - Name it "AutoDub" 
   - Select "Read" access
   - Copy the token (starts with `hf_...`)

### Step 2: Accept Model Terms

Visit these pages and click "Agree and access repository":
- [https://huggingface.co/pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [https://huggingface.co/pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

### Step 3: Provide the Token

**Option A: Environment Variable (Recommended)**
```batch
set HF_TOKEN=hf_your_token_here
```
Run this in the command prompt **before** starting the backend.

**Option B: Pass via API**
When making requests to your backend, include the token in the form data:
```javascript
formData.append('hf_token', 'hf_your_token_here');
```

### Step 4: Restart Backend
Close the current backend window and run:
```batch
RUN_APP.bat
```

## What You'll See When It Works

### Console Output:
```
Loading speaker models...
Pyannote loaded successfully.
Gender classification model loaded.
Diarizing audio: temp_audio.wav
Found 2 speakers.
Identifying speaker genders...
Speaker SPEAKER_00 pitch: 142.35Hz -> Male
Speaker SPEAKER_01 pitch: 218.67Hz -> Female
```

### Processing Flow:
1. **Audio Extraction**: Video → Audio file
2. **Speaker Diarization**: Identifies "Speaker A talks 0:00-0:05, Speaker B talks 0:05-0:10"
3. **Gender Classification**: Analyzes pitch for each speaker
4. **Subtitle Assignment**: Each subtitle gets speaker + gender tags
5. **TTS Generation**: Automatically uses Male voice for Speaker A, Female voice for Speaker B
6. **Video Assembly**: Dubbed audio merged back with video

## Technical Details

### Models Used:
- **Diarization**: `pyannote/speaker-diarization-3.1` (requires token)
- **Gender Detection**: Pitch analysis via `librosa.pyin()` (F0 > 165Hz = Female)

### SRT Format:
```srt
1
00:00:00,000 --> 00:00:03,500
<S:SPEAKER_00|G:Male> Hello, how are you?

2
00:00:03,500 --> 00:00:06,000
<S:SPEAKER_01|G:Female> I'm doing great, thanks!
```

### Voice Selection:
The system automatically selects from `lang_data.py`:
- **Male**: `male_voice_list[Language]`
- **Female**: `female_voice_list[Language]`

## Troubleshooting

### "No HF token provided"
→ Set the `HF_TOKEN` environment variable or pass it via API

### "Error loading pyannote"
→ Make sure you accepted the model terms on Hugging Face

### "Diarization pipeline not available"
→ Token is missing or invalid

### Still using same voice for everyone
→ Check console for "Found X speakers" - if it says "Found 1 speakers", diarization isn't working

## Without Token (Current Fallback)
The system will:
- ✅ Detect gender per sentence using pitch
- ❌ NOT track speaker identity across sentences
- Result: Voice may switch inconsistently even for the same person

## Files Modified for This Feature
- `speaker_detection.py` - Core diarization & gender logic
- `app.py` - Integration with subtitle generation
- `api.py` - Token handling
- `microsoft_tts.py` - Automatic voice selection

---

**Ready to test?** Just provide your HF token and process a multi-speaker video!
