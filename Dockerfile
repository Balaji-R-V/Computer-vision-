# Dockerfile for Aegis-OS Computer Vision Application
FROM python:3.10-slim

# Prevent Python from writing bytecode and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=5050
ENV AEGIS_ENGINE_MODE=aws_rekognition
ENV AWS_DEFAULT_REGION=ap-south-1
ENV AWS_REKOGNITION_COLLECTION=aegis-rekognition-collection

# Install required system dependencies for OpenCV, FFmpeg, and PyTorch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project code and model files
COPY . /app/

# Ensure required storage directories exist
RUN mkdir -p static/uploads static/outputs logs

EXPOSE 5050

CMD ["python", "server.py"]
