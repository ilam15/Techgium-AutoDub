# 🎯 YOUR HUGGING FACE TOKEN

Your token has been configured in the system!

## Token Details
```
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
```

## ⚠️ IMPORTANT: Keep This Token Secret!
- Do NOT share this token publicly
- Do NOT commit it to GitHub
- This token gives access to your Hugging Face account

## How to Use

### Quick Start (Recommended)
Simply run this file instead of `RUN_APP.bat`:
```
START_WITH_DIARIZATION.bat
```

This will:
1. ✅ Set your HF token automatically
2. ✅ Start the backend with speaker diarization enabled
3. ✅ Show you confirmation when models load

### Manual Setup (Alternative)
If you prefer to set it manually each time:

**Windows Command Prompt:**
```batch
set HF_TOKEN=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
```

**PowerShell:**
```powershell
$env:HF_TOKEN="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"
```

Then run `RUN_APP.bat` as usual.

## What to Expect When It Works

### Console Output:
```
Loading speaker models...
Pyannote loaded successfully.
Gender classification model loaded.
INFO: Uvicorn running on http://0.0.0.0:8000
```

### When Processing a Video:
```
Diarizing audio: temp_audio.wav
Found 2 speakers.
Identifying speaker genders...
Speaker SPEAKER_00 pitch: 142.35Hz -> Male
Speaker SPEAKER_01 pitch: 218.67Hz -> Female
```

## Troubleshooting

### "Error loading pyannote"
→ Make sure you accepted the model terms:
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

### "Invalid token"
→ Check that you copied the entire token including `hf_`

### Still says "No HF token provided"
→ Make sure you're using `START_WITH_DIARIZATION.bat` instead of `RUN_APP.bat`

## Next Steps

1. **Close** any currently running backend
2. **Run** `START_WITH_DIARIZATION.bat`
3. **Upload** a video with multiple speakers
4. **Watch** the console for speaker detection messages
5. **Enjoy** automatic voice switching!

---

**Token Status:** ✅ Configured and Ready
**Created:** 2026-01-16
