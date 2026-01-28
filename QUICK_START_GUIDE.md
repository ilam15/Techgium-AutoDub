# Techgium AutoDub - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### **Backend Setup**

1. **Navigate to Backend Directory**
```bash
cd c:\Users\ilams\OneDrive\Desktop\Autodub\Techgium-AutoDub\BackEnd\Multilingual-Dubbing-main\Multilingual-Dubbing-main
```

2. **Activate Virtual Environment**
```bash
.\venv311\Scripts\activate
```

3. **Start the API Server**
```bash
.\START_PRODUCTION_API.bat
```

✅ Backend running at: `http://localhost:8000`

---

### **Frontend Setup**

1. **Navigate to Frontend Directory**
```bash
cd c:\Users\ilams\OneDrive\Desktop\Autodub\Techgium-AutoDub\FrontEnd
```

2. **Start Development Server**
```bash
npm run dev
```

✅ Frontend running at: `http://localhost:5173`

---

## 🎬 How to Use

### **Step 1: Open the Application**
- Navigate to `http://localhost:5173` in your browser

### **Step 2: Upload Video**
- Click "Get Started" or navigate to `/input`
- Drag and drop your video file or click to browse
- Supported formats: MP4, AVI, MOV, MKV

### **Step 3: Configure Settings**
- **Source Language**: Select or use "Automatic" detection
- **Target Language**: Choose from 50+ languages
- **Gender**: Select Male or Female voice
- **Background Music**: Toggle to preserve background audio

### **Step 4: Process**
- Click "Dub Video"
- Wait for processing (typically 1-2 minutes for a 10-minute video)

### **Step 5: Preview & Download**
- View original and dubbed videos side-by-side
- Download the dubbed video

---

## 🛠️ Tech Stack Summary

### **Frontend**
- React 19.2.0 + Vite 7.2.4
- TailwindCSS 4.1.18
- React Router DOM 7.11.0
- Axios for API calls

### **Backend**
- FastAPI (Python 3.11)
- Faster Whisper (ASR)
- Pyannote (Speaker Diarization)
- NLLB-200 (Translation)
- Kokoro TTS / Edge TTS
- FFmpeg (Media Processing)

---

## 📊 Processing Pipeline

```
Video Upload → Audio Extraction → ASR + Diarization → 
Translation → TTS Generation → Audio Mixing → 
Video Muxing → Dubbed Video
```

**Average Processing Time:**
- 1-minute video: ~10 seconds
- 10-minute video: ~60 seconds (GPU) / ~150 seconds (CPU)

---

## 🔧 Common Issues & Solutions

### **Issue: Backend won't start**
**Solution:**
```bash
# Ensure virtual environment is activated
.\venv311\Scripts\activate

# Check if all dependencies are installed
pip install -r requirements.txt

# Verify FFmpeg is installed
ffmpeg -version
```

### **Issue: Frontend can't connect to backend**
**Solution:**
- Ensure backend is running at `http://localhost:8000`
- Check CORS settings in `api/main.py`
- Verify API URL in frontend config

### **Issue: GPU not being used**
**Solution:**
- Check `.env` file: `USE_GPU=true`
- Verify CUDA installation: `nvidia-smi`
- Check PyTorch CUDA: `python -c "import torch; print(torch.cuda.is_available())"`

### **Issue: Out of memory**
**Solution:**
- Reduce video resolution before upload
- Close other GPU-intensive applications
- Set `USE_GPU=false` to use CPU mode

---

## 📁 Important Files

### **Backend**
- `api/main.py` - API entry point
- `api/routes.py` - API endpoints
- `main_pipeline.py` - Processing pipeline
- `core/config.py` - Configuration
- `.env` - Environment variables

### **Frontend**
- `src/App.jsx` - Main app component
- `src/components/InputPage/InputPage.jsx` - Upload page
- `src/components/PreviewPage/PreviewPage.jsx` - Results page
- `package.json` - Dependencies

---

## 🌐 API Endpoints

### **Health Check**
```bash
curl http://localhost:8000/health
```

### **Dub Video**
```bash
curl -X POST http://localhost:8000/api/v1/dub_video \
  -F "file=@video.mp4" \
  -F "source_lang=English" \
  -F "target_lang=Hindi" \
  -F "gender=Male" \
  -F "recover_bg=false"
```

---

## 📝 Environment Variables

Create `.env` file in backend directory:

```env
# Required for speaker diarization
HF_TOKEN=your_huggingface_token

# GPU usage (true/false)
USE_GPU=true
```

**Get HF Token:**
1. Create account at https://huggingface.co/
2. Go to Settings → Access Tokens
3. Create new token with read permissions

---

## 🎯 Supported Languages

**Popular Languages:**
- English, Spanish, French, German, Italian
- Hindi, Tamil, Telugu, Kannada, Malayalam
- Chinese, Japanese, Korean
- Arabic, Russian, Portuguese

**Total:** 50+ languages supported

---

## 📈 Performance Tips

1. **Use GPU**: 3-4x faster than CPU
2. **Smaller Videos**: Process in chunks if very long
3. **Disable Background Recovery**: Faster if music not needed
4. **Close Other Apps**: Free up RAM and VRAM
5. **Use SSD**: Faster file I/O

---

## 🔐 Security Notes

- Maximum file size: 500MB
- Maximum duration: 1 hour
- Files are automatically cleaned up after processing
- Each request is isolated in its own sandbox

---

## 📞 Need Help?

- **Full Documentation**: See `PROJECT_DOCUMENTATION.md`
- **GitHub Issues**: Report bugs and feature requests
- **Code Comments**: Inline documentation in source files

---

## 🎉 Quick Test

**Test with a sample video:**

1. Download a short video (1-2 minutes)
2. Upload to the application
3. Select: English → Hindi, Male voice
4. Process and preview
5. Download the result

**Expected time:** 10-20 seconds for a 1-minute video

---

**Happy Dubbing! 🎬🌍**
