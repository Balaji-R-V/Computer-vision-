#!/bin/bash
# ==============================================================================
# Aegis-OS Automated GCP Compute Engine VM Deployment Script
# Target OS: Ubuntu 22.04 / 24.04 LTS on GCP Compute Engine
# ==============================================================================

set -e

echo "[Deploy] Starting Aegis-OS GCP VM Preparation and Deployment..."

# 1. Update package list & install system prerequisites
echo "[Deploy] Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y build-essential curl git ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev nginx ufw

# 2. Setup 4GB Swap Space (prevents OOM memory crash when loading YOLO PyTorch models)
if [ ! -f /swapfile ]; then
    echo "[Deploy] Creating 4GB Swapfile..."
    sudo fallocate -l 4G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "[Deploy] Swapfile enabled."
fi

# 3. Install Docker & Docker Compose plugin
if ! command -v docker &> /dev/null; then
    echo "[Deploy] Installing Docker Engine..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "[Deploy] Docker installed."
fi

# 4. Create required data directories & environment config
mkdir -p static/uploads static/outputs logs

if [ ! -f .env ]; then
    echo "[Deploy] Creating default .env configuration file..."
    cat <<EOT > .env
# Aegis-OS Dual Vision Engine Deployment Config
AEGIS_ENGINE_MODE=aws_rekognition
AWS_DEFAULT_REGION=ap-south-1
AWS_REKOGNITION_COLLECTION=aegis-rekognition-collection
HOST=0.0.0.0
PORT=5050
# Enter your AWS credentials below:
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
EOT
    echo "[Deploy] .env initialized for Mumbai (ap-south-1) AWS Rekognition."
fi

# 5. Build and Launch with Docker Compose
echo "[Deploy] Building and starting Docker container..."
sudo docker compose --env-file .env build
sudo docker compose --env-file .env up -d

# 6. Configure Nginx Reverse Proxy
echo "[Deploy] Configuring Nginx reverse proxy..."
if [ -f /etc/letsencrypt/live/aicv.devops-in22labs.com/fullchain.pem ]; then
    sudo cp nginx.conf /etc/nginx/sites-available/aegis
    echo "[Deploy] Activated SSL configuration."
else
    sudo cp nginx_http.conf /etc/nginx/sites-available/aegis
    echo "[Deploy] Activated HTTP proxy configuration."
fi
sudo ln -sf /etc/nginx/sites-available/aegis /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# 7. Configure firewall (allow HTTP, HTTPS, and port 5050)
echo "[Deploy] Configuring local firewall rules..."
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 5050/tcp
echo "y" | sudo ufw enable || true

echo ""
echo "=========================================================================="
echo "DEPLOYMENT COMPLETE"
echo "Aegis-OS is running on your GCP Virtual Machine."
echo "Access via browser: http://$(curl -s ifconfig.me)"
echo "Internal Port: http://$(curl -s ifconfig.me):5050"
echo "Check status with: sudo docker compose ps"
echo "View logs with:   sudo docker compose logs -f"
echo "To enable SSL:    bash setup_ssl.sh"
echo "=========================================================================="
