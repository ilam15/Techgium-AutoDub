FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV USE_GPU=true

# Optimization: Use a faster mirror and set retry limits to fix network/DNS hiccups
RUN (echo "nameserver 8.8.8.8" > /etc/resolv.conf || true) && \
    echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries && \
    apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng1 \
    libsndfile1 \
    libsndfile1-dev \
    build-essential \
    cmake \
    git \
    pkg-config \
    wget \
    curl \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .

# Use BuildKit cache mounts to speed up re-builds significantly
RUN --mount=type=cache,target=/root/.cache/pip \
    (echo "nameserver 8.8.8.8" > /etc/resolv.conf || true) && \
    pip install --timeout 1000 --retries 10 --index-url https://pypi.org/simple pip numpy==1.26.4

# Install heavy dependencies separately to maximize Docker caching
# Added DNS fallback and explicit index URLs to fix name resolution issues on Windows
RUN --mount=type=cache,target=/root/.cache/pip \
    (echo "nameserver 8.8.8.8" > /etc/resolv.conf || true) && \
    pip install --timeout 1000 --retries 10 \
    --index-url https://pypi.org/simple \
    --extra-index-url https://pypi.python.org/simple \
    ctranslate2==4.5.0 \
    onnxruntime==1.23.2 \
    scipy==1.15.3

# Final pass for the rest of requirements
RUN (echo "nameserver 8.8.8.8" > /etc/resolv.conf || true) && \
    pip install --no-cache-dir --timeout 1000 --retries 10 \
    --index-url https://pypi.org/simple \
    -r requirements.txt

# Copy application code
COPY . .

# Create necessary folders
RUN mkdir -p temp audio_data engine/lid

CMD ["python", "src/main.py"]