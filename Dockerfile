# Dockerfile for Aegis-OS Computer Vision Application (AWS Rekognition Cloud Edition)
FROM python:3.10-slim

# Prevent Python from writing bytecode and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=5050
ENV AEGIS_ENGINE_MODE=aws_rekognition
ENV AWS_DEFAULT_REGION=ap-south-1
ENV AWS_REKOGNITION_COLLECTION=aegis-rekognition-collection

# Install minimal runtime packages (ffmpeg for video decoding)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install lightweight python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . /app/

# Ensure required storage directories exist
RUN mkdir -p static/uploads static/outputs logs

EXPOSE 5050

CMD ["python", "server.py"]
