# Techgium AutoDub - Complete Tech Stack Reference

## 📚 Technology Stack Breakdown

---

## 🎨 Frontend Technologies

### **Core Framework**

| Technology | Version | Purpose | Documentation |
|------------|---------|---------|---------------|
| **React** | 19.2.0 | UI Library | https://react.dev/ |
| **React DOM** | 19.2.0 | DOM Rendering | https://react.dev/ |
| **Vite** | 7.2.4 | Build Tool & Dev Server | https://vitejs.dev/ |

**Why React?**
- Component-based architecture for reusability
- Virtual DOM for efficient rendering
- Large ecosystem and community support
- Excellent developer experience

**Why Vite?**
- Lightning-fast HMR (Hot Module Replacement)
- Optimized build with Rollup
- Native ES modules support
- Better performance than Create React App

---

### **Routing & Navigation**

| Technology | Version | Purpose |
|------------|---------|---------|
| **React Router DOM** | 7.11.0 | Client-side routing |

**Features Used:**
- `BrowserRouter` - HTML5 history API routing
- `Routes` & `Route` - Route configuration
- `useNavigate` - Programmatic navigation
- `useLocation` - Access location state

**Routes:**
```javascript
/ → Landing Page
/login → Login (overlay)
/register → Register (overlay)
/input → Video Upload Page
/preview → Results Preview Page
```

---

### **HTTP Client**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Axios** | 1.13.2 | HTTP requests to backend |

**Why Axios over Fetch?**
- Automatic JSON transformation
- Request/response interceptors
- Better error handling
- Progress tracking for uploads
- Browser and Node.js support

**Usage Example:**
```javascript
const formData = new FormData();
formData.append('file', videoFile);
formData.append('source_lang', sourceLang);
formData.append('target_lang', targetLang);

const response = await axios.post(
  'http://localhost:8000/api/v1/dub_video',
  formData,
  {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      const percentCompleted = Math.round(
        (progressEvent.loaded * 100) / progressEvent.total
      );
      setUploadProgress(percentCompleted);
    }
  }
);
```

---

### **Styling**

| Technology | Version | Purpose |
|------------|---------|---------|
| **TailwindCSS** | 4.1.18 | Utility-first CSS framework |
| **@tailwindcss/vite** | 4.1.18 | Vite integration |
| **PostCSS** | 8.5.6 | CSS processing |
| **Autoprefixer** | 10.4.23 | CSS vendor prefixes |

**TailwindCSS Features Used:**
- Utility classes for rapid development
- Responsive design utilities
- Dark mode support
- Custom color palettes
- Glassmorphism effects

**Custom Styles:**
```css
/* Glassmorphism */
.glass {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

/* Gradient backgrounds */
.gradient-bg {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
```

---

### **UI Components & Utilities**

| Technology | Version | Purpose |
|------------|---------|---------|
| **React Toastify** | 11.0.5 | Toast notifications |

**Features:**
- Success/error/info notifications
- Customizable positioning
- Auto-dismiss
- Progress bar
- Stacking support

---

### **Development Tools**

| Technology | Version | Purpose |
|------------|---------|---------|
| **ESLint** | 9.39.1 | Code linting |
| **eslint-plugin-react-hooks** | 7.0.1 | React Hooks linting |
| **eslint-plugin-react-refresh** | 0.4.24 | React Refresh linting |
| **@eslint/js** | 9.39.1 | ESLint JavaScript config |

---

## 🔧 Backend Technologies

### **Web Framework**

| Technology | Version | Purpose | Documentation |
|------------|---------|---------|---------------|
| **FastAPI** | Latest | Modern Python web framework | https://fastapi.tiangolo.com/ |
| **Uvicorn** | Latest | ASGI server | https://www.uvicorn.org/ |

**Why FastAPI?**
- Automatic API documentation (Swagger/OpenAPI)
- Type hints and validation with Pydantic
- Async support for high performance
- Easy dependency injection
- WebSocket support (future feature)

**Key Features Used:**
- `@app.post()` - Route decorators
- `UploadFile` - File upload handling
- `BackgroundTasks` - Async cleanup
- `CORSMiddleware` - Cross-origin requests
- `StaticFiles` - Serve generated videos

---

### **Data Validation**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Pydantic** | Latest | Data validation |
| **pydantic-settings** | Latest | Settings management |

**Usage:**
```python
class Settings(BaseSettings):
    APP_NAME: str = "AutoDub Engine"
    MAX_FILE_SIZE: int = 500 * 1024 * 1024
    DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"
    
    class Config:
        env_file = ".env"
```

---

### **File Handling**

| Technology | Version | Purpose |
|------------|---------|---------|
| **python-multipart** | Latest | Multipart form data parsing |

---

## 🤖 AI/ML Technologies

### **Automatic Speech Recognition (ASR)**

| Technology | Version | Purpose | Model |
|------------|---------|---------|-------|
| **Faster Whisper** | 1.0.3 | Speech-to-text | OpenAI Whisper Large V3 Turbo |
| **CTranslate2** | 4.5.0 | Optimized inference | - |

**Model Details:**
- **Name:** `deepdml/faster-whisper-large-v3-turbo-ct2`
- **Size:** ~1.5GB
- **Languages:** 99+ languages
- **Accuracy:** State-of-the-art
- **Speed:** 4x faster than original Whisper

**Features:**
- Automatic language detection
- Word-level timestamps
- Speaker-aware transcription
- GPU acceleration support

**Usage:**
```python
model = WhisperModel(
    "deepdml/faster-whisper-large-v3-turbo-ct2",
    device="cuda",
    compute_type="float16"
)

segments, info = model.transcribe(
    audio,
    language="en",
    word_timestamps=True
)
```

---

### **Speaker Diarization**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Pyannote Audio** | Latest | Speaker identification |

**Model:** `pyannote/speaker-diarization-3.1`

**Features:**
- Multi-speaker detection
- Speaker turn segmentation
- Gender detection
- Overlap handling

**Requirements:**
- Hugging Face token (free)
- Accept model license on HF

**Usage:**
```python
from pyannote.audio import Pipeline

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=hf_token
)

diarization = pipeline(audio_file)
```

---

### **Neural Machine Translation**

| Technology | Version | Purpose | Model |
|------------|---------|---------|-------|
| **Transformers** | Latest | Model loading | Hugging Face |
| **Deep Translator** | 1.11.4 | Translation API wrapper | - |

**Primary Model:** NLLB-200 (No Language Left Behind)
- **Full Name:** `facebook/nllb-200-distilled-600M`
- **Size:** 600M parameters (distilled version)
- **Languages:** 200+ languages
- **Quality:** High-quality neural translation

**Fallback:** Google Translate (via Deep Translator)

**Features:**
- Batch translation
- Low-resource language support
- Context preservation
- GPU acceleration

**Usage:**
```python
from transformers import pipeline

translator = pipeline(
    "translation",
    model="facebook/nllb-200-distilled-600M",
    device=0  # GPU
)

result = translator(
    text,
    src_lang="eng_Latn",
    tgt_lang="hin_Deva"
)
```

---

### **Text-to-Speech (TTS)**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Kokoro TTS** | 0.8.4+ | High-quality TTS |
| **Edge TTS** | Latest | Fallback TTS |

**Primary: Kokoro TTS**
- **Model:** `hexgrad/Kokoro-82M`
- **Quality:** Near-human quality
- **Languages:** 20+ languages
- **Voices:** Multiple per language
- **Speed Control:** Elastic timing

**Fallback: Microsoft Edge TTS**
- **Languages:** 100+ languages
- **Voices:** 400+ voices
- **Quality:** Good
- **Free:** No API key required

**Features:**
- Gender-specific voices
- Prosody preservation
- Speed adjustment
- Emotion control (Kokoro)

---

### **Supporting ML Libraries**

| Technology | Version | Purpose |
|------------|---------|---------|
| **PyTorch** | 2.1.1+ | Deep learning framework |
| **Hugging Face Hub** | Latest | Model downloading |
| **NLTK** | 3.8.1 | Natural language processing |
| **Spacy** | Latest | Advanced NLP |
| **Phonemizer** | Latest | Text to phoneme conversion |
| **Num2Words** | Latest | Number to word conversion |

---

## 🎵 Audio/Video Processing

### **FFmpeg**

| Technology | Version | Purpose |
|------------|---------|---------|
| **static-ffmpeg** | Latest | FFmpeg binary bundling |

**Why FFmpeg?**
- Industry standard for media processing
- Supports 100+ formats
- Hardware acceleration
- Stream processing
- Lossless operations

**Key Operations:**
1. **Audio Extraction**
```bash
ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 -f wav pipe:1
```

2. **Video Muxing (Zero Re-encode)**
```bash
ffmpeg -i video.mp4 -i audio.wav -map 0:v:0 -map 1:a:0 -c:v copy -shortest -movflags +faststart output.mp4
```

**Performance:**
- Audio extraction: 0.8s for 10min video
- Video muxing: 1.5s (vs 120s+ with re-encoding)

---

### **Audio Processing**

| Technology | Version | Purpose |
|------------|---------|---------|
| **audio-separator** | Latest | Vocal/background separation |
| **Librosa** | 0.10.2.post1 | Audio analysis |
| **Soundfile** | 0.13.1 | Audio file I/O |
| **Pydub** | Latest | Audio manipulation |

**Audio Separator:**
- **Model:** MDX-Net
- **Purpose:** Separate vocals from music
- **Quality:** High-quality separation
- **Speed:** ~30s for 10min audio

**Librosa:**
- Audio feature extraction
- Tempo detection
- Pitch shifting
- Time stretching

**Usage:**
```python
import librosa
import soundfile as sf

# Load audio
audio, sr = librosa.load('audio.wav', sr=16000)

# Time stretch
stretched = librosa.effects.time_stretch(audio, rate=1.2)

# Save
sf.write('output.wav', stretched, sr)
```

---

## 🗃️ Data & File Handling

### **Subtitle Processing**

| Technology | Version | Purpose |
|------------|---------|---------|
| **pysrt** | 1.1.2 | SRT file parsing |

**Features:**
- Parse SRT files
- Modify timestamps
- Add/remove subtitles
- Encoding support

**Usage:**
```python
import pysrt

subs = pysrt.open('subtitles.srt')
for sub in subs:
    print(f"{sub.start} --> {sub.end}: {sub.text}")

subs.save('output.srt', encoding='utf-8')
```

---

### **Language Data**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Misaki** | Latest | Japanese/Chinese text processing |

**Variants:**
- `misaki[zh]` - Chinese support
- `misaki[ja]` - Japanese support

---

## 🔧 Utilities & Tools

### **Logging**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Loguru** | Latest | Advanced logging |

**Features:**
- Colored output
- Automatic rotation
- Async logging
- Exception catching
- Structured logging

**Usage:**
```python
from loguru import logger

logger.add(
    "logs/app_{time}.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO"
)

logger.info("Processing request {request_id}", request_id=trace_id)
```

---

### **Progress Tracking**

| Technology | Version | Purpose |
|------------|---------|---------|
| **tqdm** | Latest | Progress bars |

**Usage:**
```python
from tqdm import tqdm

for item in tqdm(items, desc="Processing"):
    process(item)
```

---

### **Async Operations**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Click** | 8.1.7+ | CLI utilities |
| **Gradio** | 5.6.0+ | Web UI (optional) |

---

## 🐍 Python Environment

### **Version Requirements**

| Component | Version |
|-----------|---------|
| **Python** | 3.11+ |
| **pip** | Latest |
| **venv** | Built-in |

### **Virtual Environment**

```bash
# Create
python -m venv venv311

# Activate (Windows)
.\venv311\Scripts\activate

# Activate (Linux/Mac)
source venv311/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🖥️ System Requirements

### **Minimum Requirements**

| Component | Specification |
|-----------|---------------|
| **CPU** | 4 cores, 2.5GHz+ |
| **RAM** | 8GB |
| **Storage** | 20GB free space |
| **OS** | Windows 10+, Ubuntu 20.04+, macOS 11+ |

### **Recommended Requirements**

| Component | Specification |
|-----------|---------------|
| **CPU** | 8+ cores, 3.0GHz+ |
| **RAM** | 16GB+ |
| **GPU** | NVIDIA GPU with 8GB+ VRAM |
| **CUDA** | 11.8+ |
| **Storage** | 50GB+ SSD |

### **GPU Acceleration**

**Supported:**
- NVIDIA GPUs with CUDA support
- Compute Capability 6.0+ (Pascal or newer)

**Performance Boost:**
- Whisper: 4-6x faster
- Translation: 3-4x faster
- TTS: 2-3x faster
- **Overall:** 3-5x faster pipeline

**CUDA Installation:**
```bash
# Check CUDA
nvidia-smi

# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

---

## 📦 Complete Dependency List

### **Backend (requirements.txt)**

```txt
# Web Framework
fastapi
uvicorn
pydantic-settings
python-multipart

# AI/ML Models
faster-whisper==1.0.3
torch>=2.1.1
transformers
CTranslate2==4.5.0
kokoro>=0.8.4
edge-tts

# Audio/Video Processing
static-ffmpeg
audio-separator
librosa==0.10.2.post1
soundfile==0.13.1
pydub

# NLP
nltk==3.8.1
spacy
phonemizer
num2words

# Translation
deep_translator==1.11.4

# Utilities
pysrt>=1.1.2
click>=8.1.7
tqdm
loguru
huggingface-hub

# Optional
gradio>=5.6.0
misaki[zh]
misaki[ja]
```

### **Frontend (package.json)**

```json
{
  "dependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "react-router-dom": "^7.11.0",
    "axios": "^1.13.2",
    "@tailwindcss/vite": "^4.1.18",
    "react-toastify": "^11.0.5"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.1.1",
    "vite": "^7.2.4",
    "tailwindcss": "^4.1.18",
    "postcss": "^8.5.6",
    "autoprefixer": "^10.4.23",
    "eslint": "^9.39.1",
    "@eslint/js": "^9.39.1",
    "eslint-plugin-react-hooks": "^7.0.1",
    "eslint-plugin-react-refresh": "^0.4.24",
    "globals": "^16.5.0"
  }
}
```

---

## 🔗 External Services & APIs

### **Hugging Face**

**Purpose:** Model hosting and diarization

**Required:**
- Free account
- Access token
- Accept model licenses

**Models Used:**
- `deepdml/faster-whisper-large-v3-turbo-ct2`
- `pyannote/speaker-diarization-3.1`
- `facebook/nllb-200-distilled-600M`
- `hexgrad/Kokoro-82M`

**Get Token:**
1. Sign up at https://huggingface.co/
2. Go to Settings → Access Tokens
3. Create token with read permissions
4. Add to `.env`: `HF_TOKEN=your_token`

---

## 🌐 Browser Compatibility

### **Supported Browsers**

| Browser | Minimum Version |
|---------|-----------------|
| **Chrome** | 90+ |
| **Firefox** | 88+ |
| **Safari** | 14+ |
| **Edge** | 90+ |

### **Required Features**

- ES6+ JavaScript
- Fetch API
- FormData API
- HTML5 Video
- CSS Grid & Flexbox

---

## 📊 Technology Comparison

### **Why These Choices?**

| Decision | Alternative | Reason for Choice |
|----------|-------------|-------------------|
| **FastAPI** vs Flask | Flask | Better async, auto docs, type safety |
| **React** vs Vue | Vue | Larger ecosystem, better for complex UIs |
| **Vite** vs Webpack | Webpack | Faster dev server, better DX |
| **Whisper** vs Google Speech | Google | Offline, no API costs, better accuracy |
| **NLLB** vs Google Translate | Google | More languages, offline, free |
| **Kokoro** vs Azure TTS | Azure | Free, high quality, customizable |
| **FFmpeg** vs MoviePy | MoviePy | Much faster, more features |

---

## 🔮 Future Technology Additions

**Planned:**
- **Redis** - Caching and job queue
- **PostgreSQL** - User data and history
- **Docker** - Containerization
- **Kubernetes** - Orchestration
- **Celery** - Distributed task queue
- **WebSocket** - Real-time progress
- **S3/Azure Blob** - Cloud storage
- **Prometheus** - Metrics
- **Grafana** - Monitoring dashboards

---

**Document Version:** 1.0.0  
**Last Updated:** January 28, 2026  
**Maintained by:** Techgium Team
