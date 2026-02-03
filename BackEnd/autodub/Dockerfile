# Production ML Stage
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 as base

# 1. System Dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    ffmpeg \
    libespeak-ng1 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# 2. App Environment
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 3. Codebase
COPY . .

# 4. Model Pre-download (Optional for fast start)
# RUN python3 -c "import faster_whisper; faster_whisper.WhisperModel('deepdml/faster-whisper-large-v3-turbo-ct2')"

# 5. Runtime
ENV USE_GPU=true
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
