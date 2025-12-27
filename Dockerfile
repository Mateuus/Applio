# syntax=docker/dockerfile:1
FROM python:3.10-bullseye

# Expose ports
# 6969 - Gradio interface (opcional)
# 8000 - FastAPI API (produção)
EXPOSE 6969 8000

# Set up working directory
WORKDIR /app

# Install system dependencies, clean up cache to keep image size small
# PortAudio is needed for sounddevice (audio I/O)
# libsndfile1 is needed for soundfile (audio file I/O)
RUN apt update && \
    apt install -y -qq \
        ffmpeg \
        curl \
        portaudio19-dev \
        libportaudio2 \
        python3-dev \
        build-essential \
        libsndfile1 \
        libsndfile1-dev \
        libasound2-dev \
        libffi-dev \
        libssl-dev && \
    apt clean && rm -rf /var/lib/apt/lists/*

# Copy application files into the container
COPY . .

# Remove any existing .venv if copied (shouldn't happen with .dockerignore, but just in case)
RUN rm -rf /app/.venv

# Create a virtual environment in the app directory
RUN python3 -m venv /app/.venv

# Install dependencies using the venv's pip directly
RUN /app/.venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch with CUDA support first (large package, better to install early)
RUN /app/.venv/bin/pip install --no-cache-dir torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128

# Install API requirements first (FastAPI, uvicorn, etc.)
RUN if [ -f "api/requirements.txt" ]; then /app/.venv/bin/pip install --no-cache-dir -r api/requirements.txt; fi

# Install essential dependencies that might be missing
# These are critical for the API to work
RUN /app/.venv/bin/pip install --no-cache-dir \
    tensorboard \
    tensorboardX \
    numpy==1.26.4 \
    requests \
    tqdm \
    wget \
    ffmpeg-python \
    faiss-cpu==1.7.3 \
    librosa==0.11.0 \
    scipy==1.11.1 \
    soundfile==0.12.1 \
    noisereduce \
    pedalboard \
    stftpitchshift \
    soxr \
    numba \
    omegaconf \
    torchcrepe==0.0.23 \
    torchfcpe \
    einops \
    transformers==4.44.2 \
    matplotlib==3.7.2 \
    gradio==5.23.1 \
    python-multipart \
    edge-tts==7.2.0 \
    pypresence \
    beautifulsoup4 \
    webrtcvad \
    PyYAML \
    regex \
    gdown

# Install sounddevice after system libraries are installed
# This ensures it can find PortAudio libraries
RUN /app/.venv/bin/pip install --no-cache-dir --force-reinstall sounddevice

# Install main requirements.txt (will skip already installed packages)
# The requirements.txt has platform conditionals, but pip will handle them correctly on Linux
RUN if [ -f "requirements.txt" ]; then /app/.venv/bin/pip install --no-cache-dir -r requirements.txt || true; fi

# Verify critical packages are installed
RUN echo "Verifying critical packages..." && \
    /app/.venv/bin/python3 -c "import fastapi; print('✓ fastapi')" && \
    /app/.venv/bin/python3 -c "import tensorboard; print('✓ tensorboard')" && \
    /app/.venv/bin/python3 -c "import torch; print('✓ torch')" && \
    /app/.venv/bin/python3 -c "import numpy; print('✓ numpy')" && \
    /app/.venv/bin/python3 -c "import librosa; print('✓ librosa')" && \
    /app/.venv/bin/python3 -c "import soundfile; print('✓ soundfile')" && \
    /app/.venv/bin/python3 -c "import sounddevice; print('✓ sounddevice')" && \
    /app/.venv/bin/python3 -c "import gradio; print('✓ gradio')" && \
    /app/.venv/bin/python3 -c "import regex; print('✓ regex')" && \
    /app/.venv/bin/python3 -c "import gdown; print('✓ gdown')" && \
    /app/.venv/bin/python3 -c "import whisper; print('✓ whisper')" && \
    /app/.venv/bin/python3 -c "import edge_tts; print('✓ edge_tts')" && \
    /app/.venv/bin/python3 -c "import faiss; print('✓ faiss')" && \
    /app/.venv/bin/python3 -c "import torchcrepe; print('✓ torchcrepe')" && \
    /app/.venv/bin/python3 -c "import torchfcpe; print('✓ torchfcpe')" && \
    /app/.venv/bin/python3 -c "import noisereduce; print('✓ noisereduce')" && \
    /app/.venv/bin/python3 -c "import pedalboard; print('✓ pedalboard')" && \
    /app/.venv/bin/python3 -c "import soxr; print('✓ soxr')" && \
    /app/.venv/bin/python3 -c "import webrtcvad; print('✓ webrtcvad')" && \
    /app/.venv/bin/python3 -c "import matplotlib; print('✓ matplotlib')" && \
    /app/.venv/bin/python3 -c "import transformers; print('✓ transformers')" && \
    /app/.venv/bin/python3 -c "import scipy; print('✓ scipy')" && \
    /app/.venv/bin/python3 -c "import pyannote.audio; print('✓ pyannote.audio')" 2>/dev/null || echo "⚠ pyannote.audio (opcional - requer token)" && \
    /app/.venv/bin/python3 -c "import omegaconf; print('✓ omegaconf')" && \
    /app/.venv/bin/python3 -c "import numba; print('✓ numba')" && \
    /app/.venv/bin/python3 -c "import einops; print('✓ einops')" && \
    echo "All critical packages verified!"

# Create necessary directories
RUN mkdir -p /app/logs /app/api/logs /app/outputs /app/uploads

# Define volumes for persistent storage
VOLUME ["/app/logs/", "/app/api/logs/", "/app/outputs/", "/app/uploads/", "/app/rvc/models/"]

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Run the app
# Por padrão, roda a API FastAPI (produção)
# Para rodar a interface Gradio, use: docker run ... /app/.venv/bin/python3 app.py
ENTRYPOINT ["/app/.venv/bin/python3"]
CMD ["api/app.py", "--host", "0.0.0.0", "--port", "8000"]
