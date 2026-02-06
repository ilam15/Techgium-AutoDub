# AutoDub - AI Video Dubbing Pipeline 🎥🎙️

AutoDub is a comprehensive, automated video dubbing solution that utilizes state-of-the-art AI models to transcribe, translate, and dub videos into multiple languages while preserving background audio. It features a robust Python/FastAPI backend and a modern React/Vite frontend.

## 🚀 Features

*   **Automated Dubbing Pipeline**: End-to-end processing from video input to dubbed output.
*   **Multi-Source Input**: Support for direct file uploads and YouTube URL downloads.
*   **Advanced AI Stack**:
    *   **ASR (Speech-to-Text)**: Uses `Faster-Whisper` for highly accurate transcription.
    *   **Diarization**: `Pyannote Audio` for distinguishing between multiple speakers.
    *   **Translation**: `NLLB` (No Language Left Behind) and `DeepTranslator` for context-aware translation.
    *   **TTS (Text-to-Speech)**: Supports `Edge-TTS`, `Kokoro`, and `Misaki` for natural-sounding voice generation with gender control.
*   **Audio Engineering**:
    *   **Background Recovery**: Extracts and preserves original background music/noise using `Audio Separator` (UVR).
    *   **Audio Ducking**: Automatically lowers background audio during speech segments.
*   **Performance**:
    *   **Model Warmup**: Intelligent pre-loading of AI models for reduced latency.
    *   **Concurrency**: Async request handling with semaphore-based traffic control.
    *   **Checks**: Built-in health checks for FFmpeg, Disk Space, and Model availability.

---

## 🏗️ Architecture

### Tech Stack

**Backend**
*   **Framework**: FastAPI (Python 3.11+)
*   **Audio Processing**: FFmpeg (via `static-ffmpeg` or system path), Librosa, Soundfile
*   **ML/AI Libraries**: Torch, Transformers, CTranslate2, HuggingFace Hub
*   **Utilities**: Pydantic, Loguru, yt-dlp

**Frontend**
*   **Framework**: React 19 + Vite 7
*   **Styling**: Tailwind CSS v4
*   **State/Routing**: React Router 7
*   **Networking**: Axios

### Pipeline Logic

1.  **Input Handling**: Verification of video format and duration (max 10 mins default).
2.  **Audio Extraction**: FFmpeg extracts audio tracks from the source video.
3.  **Vocal Separation**: Splits audio into "Vocals" and "Background" stems (if `recover_bg` is enabled).
4.  **Transcription & Diarization**:
    *   Whisper generates timestamped text.
    *   Speaker separation assigns text segments to specific speakers.
5.  **Translation**: Text is translated to the target language (e.g., Hindi, Spanish) while preserving speaker identity.
6.  **Speech Synthesis (TTS)**: Generates new audio segments matching the duration and gender of the original speaker.
7.  **Final Mix**: Merges the new dubbed vocals with the preserved background track and the original video stream.

---

## 🛠️ Installation & Setup

### Prerequisites
*   **OS**: Windows / Linux / macOS
*   **Python**: v3.11 Recommended
*   **Node.js**: v18+
*   **FFmpeg**: Must be installed and added to system PATH.

### 1. Backend Setup

Navigate to the backend directory:
```bash
cd Techgium-AutoDub/BackEnd
```

Create and activate a virtual environment:
```bash
# Windows
python -m venv venv311
.\venv311\Scripts\activate

# Linux/Mac
python3 -m venv venv311
source venv311/bin/activate
```

Install dependencies:
```bash
cd autodub
pip install -r requirements.txt
```

> **Note**: This will install heavy libraries like PyTorch and CUDA-enabled versions of CTranslate2 if supported.

### 2. Frontend Setup

Navigate to the frontend directory:
```bash
cd Techgium-AutoDub/FrontEnd
```

Install Node dependencies:
```bash
npm install
```

---

## 🖥️ Usage

### Running the Backend
You can use the provided batch script (Windows) or run manually.

**Using Batch Script:**
```bash
cd Techgium-AutoDub/BackEnd
run_backend.bat
```

**Manual Start:**
```bash
cd Techgium-AutoDub/BackEnd/autodub
python -m src.main
```
The server will start at `http://0.0.0.0:8000`.

### Running the Frontend
Start the development server:
```bash
cd Techgium-AutoDub/FrontEnd
npm run dev
```
Access the UI at `http://localhost:5173` (or the port shown in terminal).

---

## 🔌 API Reference

### Core Endpoints

#### `POST /api/v1/dub_video`
Initiates the dubbing process.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `file` | File | Video file to upload (optional if `youtube_url` provided). |
| `youtube_url` | String | YouTube link to download and dub. |
| `source_lang` | String | Source language code (default: "Automatic"). |
| `target_lang` | String | Target language (e.g., "Hindi", "Spanish"). |
| `gender` | String | Preferred voice gender ("Male"/"Female"). |
| `recover_bg` | Boolean | If `true`, preserves background music using separation models. |

#### `POST /api/v1/youtube/info`
Get metadata for a YouTube video.

#### `GET /health/deep`
Performs a deep system check (FFmpeg, Disk, Model Status).

---

## 📂 Project Structure

```
Techgium-AutoDub/
├── BackEnd/
│   ├── autodub/
│   │   ├── src/
│   │   │   ├── api/            # Route definitions
│   │   │   ├── core/           # Config & Logging
│   │   │   ├── engines/        # TTS & Translation logic
│   │   │   ├── services/       # YouTube & external services
│   │   │   ├── main.py         # Entry point
│   │   │   └── main_pipeline.py# Orchestrator
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── run_backend.bat
├── FrontEnd/
│   ├── src/                    # React components
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## ⚠️ Common Issues

1.  **FFmpeg Not Found**: Ensure `ffmpeg` is in your `PATH`. Run `ffmpeg -version` in cmd to verify.
2.  **Torch/CUDA Errors**: If you lack a GPU, ensure you install the CPU-only versions of torch or configure `settings.DEVICE = "cpu"`.
3.  **Model Download**: On first run, models (Whisper, NLLB) will be downloaded to `~/.cache/huggingface`. Ensure you have a stable internet connection.

---

**Developed for Techgium**
