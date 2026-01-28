# Techgium AutoDub - Technical Architecture

## 🏗️ System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          CLIENT LAYER (Browser)                             │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     React Frontend (Vite)                             │  │
│  │                                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  │
│  │  │ Landing  │  │  Input   │  │ Preview  │  │   Auth   │             │  │
│  │  │   Page   │  │   Page   │  │   Page   │  │  Pages   │             │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │  │
│  │                                                                        │  │
│  │  Dependencies: React Router, Axios, TailwindCSS, React Toastify      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP/REST API
                                    │ (JSON + Multipart Form Data)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                        APPLICATION LAYER (FastAPI)                          │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         API Gateway                                   │  │
│  │                        (api/main.py)                                  │  │
│  │                                                                        │  │
│  │  • CORS Middleware                                                    │  │
│  │  • Request Validation                                                 │  │
│  │  • Static File Serving                                                │  │
│  │  • Health Checks                                                      │  │
│  │  • Process Time Tracking                                              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      Route Handler                                    │  │
│  │                      (api/routes.py)                                  │  │
│  │                                                                        │  │
│  │  POST /api/v1/dub_video                                               │  │
│  │  • File Upload Handling                                               │  │
│  │  • Parameter Extraction                                               │  │
│  │  • Background Task Scheduling                                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                      BUSINESS LOGIC LAYER                                   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                   Production Pipeline                                 │  │
│  │                  (main_pipeline.py)                                   │  │
│  │                                                                        │  │
│  │  Orchestrates:                                                        │  │
│  │  1. Request Context Creation                                          │  │
│  │  2. Audio Extraction                                                  │  │
│  │  3. ASR + Diarization (Parallel)                                      │  │
│  │  4. Speaker Alignment                                                 │  │
│  │  5. Translation                                                       │  │
│  │  6. TTS Generation                                                    │  │
│  │  7. Audio Mixing                                                      │  │
│  │  8. Video Muxing                                                      │  │
│  │  9. Cleanup                                                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                    ┌───────────────┼───────────────┐                        │
│                    │               │               │                        │
│                    ▼               ▼               ▼                        │
│  ┌──────────────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   ASR Transcriber    │  │  Translation │  │  TTS Generator│             │
│  │ (engine/asr/)        │  │   Service    │  │ (engine/tts/) │             │
│  │                      │  │ (engine/     │  │               │             │
│  │ • Whisper Model      │  │  translation)│  │ • Kokoro TTS  │             │
│  │ • Language Detection │  │              │  │ • Edge TTS    │             │
│  │ • Segment Extraction │  │ • NLLB-200   │  │ • Speed Ctrl  │             │
│  └──────────────────────┘  │ • Batching   │  └──────────────┘             │
│                             │ • Caching    │                                │
│  ┌──────────────────────┐  └──────────────┘  ┌──────────────┐             │
│  │  Audio Processor     │                     │ Media Engine │             │
│  │ (engine/audio/)      │                     │(media_engine)│             │
│  │                      │                     │              │             │
│  │ • Extraction         │                     │ • FFmpeg     │             │
│  │ • Vocal Separation   │                     │ • Streaming  │             │
│  │ • Mixing             │                     │ • Muxing     │             │
│  └──────────────────────┘                     └──────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                         MODEL LAYER (Singleton)                             │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      Model Manager                                    │  │
│  │                     (core/models.py)                                  │  │
│  │                                                                        │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│  │  │ Whisper Model  │  │  Pyannote      │  │   NLLB-200     │         │  │
│  │  │                │  │  Diarization   │  │  Translation   │         │  │
│  │  │ • Large V3     │  │                │  │                │         │  │
│  │  │ • Turbo CT2    │  │ • Speaker ID   │  │ • 200 langs    │         │  │
│  │  │ • GPU/CPU      │  │ • Gender Det.  │  │ • Distilled    │         │  │
│  │  └────────────────┘  └────────────────┘  └────────────────┘         │  │
│  │                                                                        │  │
│  │  Features:                                                            │  │
│  │  • Lazy Loading                                                       │  │
│  │  • Idle Timeout (5 min)                                               │  │
│  │  • GPU Memory Management                                              │  │
│  │  • Automatic CPU Fallback                                             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                      INFRASTRUCTURE LAYER                                   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        FFmpeg                                         │  │
│  │                                                                        │  │
│  │  • Audio Extraction (pipe to memory)                                  │  │
│  │  • Video Stream Copy (zero re-encode)                                 │  │
│  │  • Audio/Video Muxing                                                 │  │
│  │  • Format Conversion                                                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                   Audio Separator                                     │  │
│  │                                                                        │  │
│  │  • Vocal/Background Separation                                        │  │
│  │  • MDX-Net Model                                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    PyTorch + CUDA                                     │  │
│  │                                                                        │  │
│  │  • GPU Acceleration                                                   │  │
│  │  • Model Inference                                                    │  │
│  │  • Memory Management                                                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                         STORAGE LAYER                                       │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                   File System                                         │  │
│  │                                                                        │  │
│  │  /temp/requests/{request_id}/  (Sandbox per request)                 │  │
│  │  ├── input_video.mp4                                                  │  │
│  │  ├── extracted_audio.wav                                              │  │
│  │  ├── vocals.wav                                                       │  │
│  │  ├── background.wav                                                   │  │
│  │  ├── original.srt                                                     │  │
│  │  ├── translated.srt                                                   │  │
│  │  ├── dubbed_audio.wav                                                 │  │
│  │  └── [auto-deleted after processing]                                  │  │
│  │                                                                        │  │
│  │  /output_{request_id}.mp4  (Final output)                            │  │
│  │                                                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Diagram

```
┌──────────┐
│  User    │
│ Browser  │
└────┬─────┘
     │
     │ 1. Upload Video + Config
     ▼
┌─────────────────┐
│  InputPage.jsx  │
│  (React)        │
└────┬────────────┘
     │
     │ 2. POST /api/v1/dub_video
     │    (FormData: file, source_lang, target_lang, gender)
     ▼
┌──────────────────┐
│  API Gateway     │
│  (FastAPI)       │
└────┬─────────────┘
     │
     │ 3. Validate & Create Request Context
     ▼
┌──────────────────────┐
│ Production Pipeline  │
│ (main_pipeline.py)   │
└────┬─────────────────┘
     │
     │ 4. Extract Audio (FFmpeg pipe)
     ▼
┌──────────────────┐
│  Audio Data      │
│  (NumPy array)   │
└────┬─────────────┘
     │
     ├─────────────────────────────┐
     │                             │
     │ 5a. ASR (Whisper)           │ 5b. Diarization (Pyannote)
     ▼                             ▼
┌──────────────┐            ┌──────────────┐
│ Transcription│            │ Speaker Turns│
│  Segments    │            │  + Genders   │
└────┬─────────┘            └────┬─────────┘
     │                           │
     └───────────┬───────────────┘
                 │
                 │ 6. Merge & Align
                 ▼
         ┌───────────────┐
         │  Aligned SRT  │
         │  (original)   │
         └───┬───────────┘
             │
             │ 7. Translate (NLLB-200)
             ▼
         ┌───────────────┐
         │ Translated SRT│
         └───┬───────────┘
             │
             │ 8. TTS Generation (Kokoro/Edge)
             ▼
         ┌───────────────┐
         │ Dubbed Audio  │
         └───┬───────────┘
             │
             │ 9. Mix with Background (if enabled)
             ▼
         ┌───────────────┐
         │  Final Audio  │
         └───┬───────────┘
             │
             │ 10. Mux with Video (FFmpeg -c:v copy)
             ▼
         ┌───────────────┐
         │  Dubbed Video │
         │  (output.mp4) │
         └───┬───────────┘
             │
             │ 11. Return URL
             ▼
     ┌──────────────────┐
     │  JSON Response   │
     │  {               │
     │   video_url,     │
     │   metrics,       │
     │   request_id     │
     │  }               │
     └────┬─────────────┘
          │
          │ 12. Display in Preview
          ▼
     ┌──────────────┐
     │ PreviewPage  │
     │  (React)     │
     └──────────────┘
```

---

## 🧩 Component Interaction Diagram

```
Frontend Components:
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  LandingPage.jsx                                           │
│  ├── Navbar.jsx                                            │
│  ├── HeroSection.jsx                                       │
│  ├── FeaturesSection.jsx                                   │
│  ├── AIDubbingSection.jsx                                  │
│  ├── WhyDubbify.jsx                                        │
│  ├── SolutionsGrid.jsx                                     │
│  └── Footer.jsx                                            │
│                                                            │
│  InputPage.jsx                                             │
│  └── Axios → POST /api/v1/dub_video                        │
│                                                            │
│  PreviewPage.jsx                                           │
│  └── Receives video_url from navigation state              │
│                                                            │
│  Authentication/                                           │
│  ├── Login.jsx                                             │
│  └── Register.jsx                                          │
│                                                            │
└────────────────────────────────────────────────────────────┘

Backend Components:
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  api/                                                      │
│  ├── main.py (FastAPI app, middleware, static files)      │
│  └── routes.py (POST /dub_video endpoint)                 │
│                                                            │
│  core/                                                     │
│  ├── config.py (Settings, environment vars)               │
│  ├── context.py (Request sandbox management)              │
│  ├── models.py (Model manager singleton)                  │
│  ├── logger.py (Structured logging)                       │
│  └── exceptions.py (Custom exceptions)                    │
│                                                            │
│  engine/                                                   │
│  ├── asr/transcriber.py (Whisper wrapper)                 │
│  ├── audio/processor.py (FFmpeg, audio-separator)         │
│  ├── translation/translator.py (NLLB wrapper)             │
│  └── tts/generator.py (Kokoro/Edge TTS)                   │
│                                                            │
│  main_pipeline.py (Orchestrates all engines)              │
│  media_engine.py (FFmpeg operations)                      │
│  speaker_detection.py (Pyannote wrapper)                  │
│  clean_up.py (Background cleanup tasks)                   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Security Layers                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Input Validation                                    │
│     • File size limit: 500MB                            │
│     • Duration limit: 1 hour                            │
│     • File type validation                              │
│     • Language code validation                          │
│                                                         │
│  2. CORS Protection                                     │
│     • Configurable allowed origins                      │
│     • Credentials support                               │
│                                                         │
│  3. Sandbox Isolation                                   │
│     • Each request in isolated directory                │
│     • Unique request ID (UUID)                          │
│     • Automatic cleanup after processing                │
│                                                         │
│  4. Resource Limits                                     │
│     • Model idle timeout (5 min)                        │
│     • GPU memory management                             │
│     • Concurrent request handling                       │
│                                                         │
│  5. Error Handling                                      │
│     • Graceful degradation                              │
│     • No sensitive data in error messages               │
│     • Structured logging with trace IDs                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## ⚡ Performance Optimization Strategy

```
┌─────────────────────────────────────────────────────────┐
│            Performance Optimizations                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Zero Video Re-encoding                              │
│     FFmpeg -c:v copy → 10min video: 1.5s vs 120s+       │
│                                                         │
│  2. Audio Streaming                                     │
│     Pipe to memory → 0.8s vs 5.2s file I/O              │
│                                                         │
│  3. Model Pooling                                       │
│     Singleton pattern → 3-5s saved per request          │
│                                                         │
│  4. Parallel Processing                                 │
│     ASR + Diarization concurrent → 30-40% faster        │
│                                                         │
│  5. GPU Acceleration                                    │
│     CUDA support → 4-10x speedup                        │
│                                                         │
│  6. Translation Caching                                 │
│     In-memory cache → 20-30% faster on similar content  │
│                                                         │
│  7. Batched Operations                                  │
│     ID-based translation batching → Reduced overhead    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🛡️ Reliability & Fallback Mechanisms

```
┌──────────────────────────────────────────────────────────┐
│              Fallback Strategy Matrix                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  GPU OOM                                                 │
│  └─→ Clear cache → Retry on CPU                         │
│                                                          │
│  Diarization Failure                                     │
│  └─→ Single speaker fallback (SPEAKER_00)               │
│                                                          │
│  Kokoro TTS Unavailable                                  │
│  └─→ Auto-switch to Edge TTS                            │
│                                                          │
│  Translation Error                                       │
│  └─→ Return original subtitles                          │
│                                                          │
│  Background Separation Failure                           │
│  └─→ Continue with voice-only                           │
│                                                          │
│  Network Error                                           │
│  └─→ Exponential backoff retry (3 attempts)             │
│                                                          │
│  CUDA Initialization Failure                             │
│  └─→ Automatic CPU mode fallback                        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 📊 Monitoring & Observability

```
┌──────────────────────────────────────────────────────────┐
│              Logging & Metrics                           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Request Tracing                                         │
│  • Unique trace_id per request                          │
│  • All logs tagged with trace_id                        │
│  • End-to-end request tracking                          │
│                                                          │
│  Performance Metrics                                     │
│  • Per-stage timing                                     │
│  • Total pipeline duration                              │
│  • Resource usage tracking                              │
│                                                          │
│  Error Tracking                                          │
│  • Full stack traces                                    │
│  • Stage identification                                 │
│  • Structured error messages                            │
│                                                          │
│  Health Monitoring                                       │
│  • /health endpoint                                     │
│  • /ready endpoint                                      │
│  • Model availability checks                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

**Document Version:** 1.0.0  
**Last Updated:** January 28, 2026  
**Maintained by:** Techgium Team
