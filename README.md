# 🎬 Techgium AutoDub

> **AI-Powered Multilingual Video Dubbing Platform**

Transform your videos into any language with state-of-the-art AI dubbing technology. Preserve speaker identity, maintain audio quality, and reach global audiences effortlessly.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19.2.0-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ Features

- 🎙️ **Automatic Speech Recognition** - Transcribe audio with 99+ language support
- 👥 **Speaker Diarization** - Identify and separate multiple speakers
- 🌍 **Neural Translation** - Translate to 200+ languages with NLLB-200
- 🗣️ **High-Quality TTS** - Natural-sounding voices with Kokoro TTS
- 🎵 **Background Music Recovery** - Preserve original background audio
- ⚡ **Lightning Fast** - GPU-accelerated processing (3-5x faster)
- 🎯 **Zero Video Re-encoding** - Maintain original video quality
- 🔒 **Privacy First** - All processing happens locally

---

## 🚀 Quick Start

### **Prerequisites**

- Python 3.11+
- Node.js 18+
- FFmpeg
- 8GB+ RAM (16GB recommended)
- NVIDIA GPU with CUDA (optional, for acceleration)

### **Installation**

#### 1. Clone Repository
```bash
git clone https://github.com/ilam15/Techgium-AutoDub.git
cd Techgium-AutoDub
```

#### 2. Backend Setup
```bash
cd BackEnd/Multilingual-Dubbing-main/Multilingual-Dubbing-main

# Create virtual environment
python -m venv venv311
.\venv311\Scripts\activate  # Windows
# source venv311/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
echo HF_TOKEN=your_huggingface_token > .env
echo USE_GPU=true >> .env

# Start server
.\START_PRODUCTION_API.bat  # Windows
# uvicorn api.main:app --host 0.0.0.0 --port 8000  # Linux/Mac
```

#### 3. Frontend Setup
```bash
cd ../../../FrontEnd

# Install dependencies
npm install

# Start development server
npm run dev
```

#### 4. Access Application
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| **[PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)** | Complete project documentation with architecture, workflow, and deployment |
| **[QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)** | Quick setup guide and troubleshooting |
| **[TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)** | Detailed technical architecture with diagrams |
| **[TECH_STACK_REFERENCE.md](TECH_STACK_REFERENCE.md)** | Comprehensive tech stack breakdown |

---

## 🎯 How It Works

```
1. Upload Video → 2. Extract Audio → 3. Transcribe (ASR) → 
4. Identify Speakers → 5. Translate Text → 6. Generate Speech (TTS) → 
7. Mix Audio → 8. Merge with Video → 9. Download Dubbed Video
```

**Processing Time:**
- 1-minute video: ~10 seconds
- 10-minute video: ~60 seconds (GPU) / ~150 seconds (CPU)

---

## 🛠️ Tech Stack

### **Frontend**
- React 19.2.0 + Vite 7.2.4
- TailwindCSS 4.1.18
- React Router DOM 7.11.0
- Axios

### **Backend**
- FastAPI (Python 3.11)
- Faster Whisper (ASR)
- Pyannote Audio (Diarization)
- NLLB-200 (Translation)
- Kokoro TTS / Edge TTS
- FFmpeg (Media Processing)

### **AI Models**
- **ASR:** OpenAI Whisper Large V3 Turbo
- **Diarization:** Pyannote 3.1
- **Translation:** Facebook NLLB-200 (600M)
- **TTS:** Kokoro-82M / Microsoft Edge TTS

---

## 📊 Performance

### **Benchmarks (10-minute 1080p video)**

| Stage | GPU | CPU |
|-------|-----|-----|
| Audio Extraction | 0.8s | 0.8s |
| ASR (Whisper) | 15s | 60s |
| Diarization | 12s | 45s |
| Translation | 4s | 4s |
| TTS Generation | 18s | 35s |
| Video Muxing | 1.5s | 1.5s |
| **Total** | **~55s** | **~150s** |

### **Optimizations**
- ⚡ Zero video re-encoding (120s → 1.5s)
- 🚀 Audio streaming to memory (5.2s → 0.8s)
- 🔄 Parallel ASR + Diarization (30-40% faster)
- 💾 Model pooling (3-5s saved per request)
- 🎯 GPU acceleration (4-10x speedup)

---

## 🌍 Supported Languages

**50+ Languages Including:**

- 🇬🇧 English
- 🇪🇸 Spanish
- 🇫🇷 French
- 🇩🇪 German
- 🇮🇹 Italian
- 🇮🇳 Hindi, Tamil, Telugu, Kannada, Malayalam
- 🇨🇳 Chinese (Simplified/Traditional)
- 🇯🇵 Japanese
- 🇰🇷 Korean
- 🇸🇦 Arabic
- 🇷🇺 Russian
- 🇵🇹 Portuguese
- And many more...

---

## 🎬 Usage Example

### **Via Web Interface**

1. Navigate to http://localhost:5173
2. Click "Get Started"
3. Upload your video
4. Select source and target languages
5. Choose voice gender
6. Click "Dub Video"
7. Preview and download result

### **Via API**

```bash
curl -X POST http://localhost:8000/api/v1/dub_video \
  -F "file=@video.mp4" \
  -F "source_lang=English" \
  -F "target_lang=Hindi" \
  -F "gender=Male" \
  -F "recover_bg=false"
```

**Response:**
```json
{
  "status": "success",
  "request_id": "abc123",
  "video_url": "http://localhost:8000/static/output_abc123.mp4",
  "detected_language": "English",
  "metrics": {
    "total_pipeline": 55.3
  }
}
```

---

## 🔧 Configuration

### **Environment Variables (.env)**

```env
# Hugging Face Token (required for diarization)
HF_TOKEN=your_token_here

# GPU Usage
USE_GPU=true

# Model Settings
WHISPER_MODEL_NAME=deepdml/faster-whisper-large-v3-turbo-ct2
KOKORO_MODEL_ID=hexgrad/Kokoro-82M

# API Limits
MAX_FILE_SIZE=524288000  # 500MB
MAX_VIDEO_DURATION=3600  # 1 hour
```

### **Get Hugging Face Token**

1. Create account at https://huggingface.co/
2. Go to Settings → Access Tokens
3. Create token with read permissions
4. Accept model licenses for pyannote models

---

## 🏗️ Project Structure

```
Techgium-AutoDub/
├── BackEnd/
│   └── Multilingual-Dubbing-main/
│       ├── api/              # FastAPI application
│       ├── core/             # Configuration & models
│       ├── engine/           # Processing engines
│       ├── main_pipeline.py  # Pipeline orchestrator
│       ├── app.py            # Legacy pipeline
│       └── requirements.txt  # Python dependencies
│
├── FrontEnd/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── App.jsx           # Main app
│   │   └── main.jsx          # Entry point
│   ├── package.json          # Node dependencies
│   └── vite.config.js        # Vite configuration
│
└── Documentation/
    ├── PROJECT_DOCUMENTATION.md
    ├── QUICK_START_GUIDE.md
    ├── TECHNICAL_ARCHITECTURE.md
    └── TECH_STACK_REFERENCE.md
```

---

## 🛡️ Error Handling

The system includes robust fallback mechanisms:

| Failure | Fallback Strategy |
|---------|-------------------|
| GPU OOM | Clear cache → Retry on CPU |
| Diarization Error | Single speaker fallback |
| Kokoro TTS Down | Auto-switch to Edge TTS |
| Translation Fail | Return original subtitles |
| Background Separation Fail | Continue with voice-only |
| Network Error | Exponential backoff retry |

---

## 🔐 Security

- ✅ File size validation (500MB max)
- ✅ Duration validation (1 hour max)
- ✅ Sandbox isolation per request
- ✅ Automatic cleanup after processing
- ✅ CORS protection
- ✅ No sensitive data in logs

---

## 🚧 Known Limitations

- Maximum file size: 500MB
- Maximum duration: 1 hour
- GPU required for optimal performance
- Some languages have limited TTS voice options
- Background music separation may not be perfect

---

## 🔮 Roadmap

- [ ] Real-time progress updates via WebSocket
- [ ] Batch video processing
- [ ] Cloud storage integration (S3/Azure)
- [ ] User authentication & history
- [ ] Custom voice cloning
- [ ] Subtitle editing interface
- [ ] Multi-speaker TTS with different voices
- [ ] API rate limiting
- [ ] Kubernetes deployment
- [ ] Mobile app

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenAI Whisper** - State-of-the-art speech recognition
- **Pyannote Audio** - Speaker diarization by Hervé Bredin
- **Meta NLLB** - No Language Left Behind translation
- **Kokoro TTS** - High-quality open-source TTS
- **FFmpeg** - The backbone of media processing
- **FastAPI** - Modern Python web framework
- **React** - UI library

---

## 📞 Support

- **Documentation:** See docs folder
- **Issues:** [GitHub Issues](https://github.com/ilam15/Techgium-AutoDub/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ilam15/Techgium-AutoDub/discussions)

---

## 📈 Stats

- **Languages Supported:** 200+
- **Processing Speed:** 3-5x real-time (GPU)
- **Model Size:** ~8GB total
- **Accuracy:** State-of-the-art
- **Cost:** Free and open-source

---

## 🎉 Quick Test

Try with a sample video:

```bash
# Download sample
curl -o sample.mp4 https://example.com/sample-video.mp4

# Process via API
curl -X POST http://localhost:8000/api/v1/dub_video \
  -F "file=@sample.mp4" \
  -F "source_lang=Automatic" \
  -F "target_lang=Spanish" \
  -F "gender=Male"
```

---

<div align="center">

**Made with ❤️ by Techgium Team**

[Website](https://techgium.com) • [GitHub](https://github.com/ilam15/Techgium-AutoDub) • [Documentation](PROJECT_DOCUMENTATION.md)

**Star ⭐ this repo if you find it useful!**

</div>