#!/bin/bash
# ==============================================================================
# Automated Let's Encrypt SSL Setup for Aegis-OS
# Domain: aicv.devops-in22labs.com
# ==============================================================================

set -e

DOMAIN="aicv.devops-in22labs.com"
EMAIL="admin@devops-in22labs.com"

echo "[SSL] Installing Certbot and Let's Encrypt Nginx plugin..."
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

echo "[SSL] Ensuring HTTPS port 443 is open in firewall..."
sudo ufw allow 443/tcp || true

echo "[SSL] Requesting and applying Let's Encrypt SSL Certificate for $DOMAIN..."
sudo certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect

echo "[SSL] Applying Aegis-OS Nginx SSL configuration..."
if [ -f nginx.conf ]; then
    sudo cp nginx.conf /etc/nginx/sites-available/aegis
    sudo ln -sf /etc/nginx/sites-available/aegis /etc/nginx/sites-enabled/default
fi

echo "[SSL] Reloading Nginx with SSL configuration..."
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "=========================================================================="
echo "SSL CERTIFICATE INSTALLED & ACTIVE"
echo "Your live secure web portal is now online at:"
echo "https://$DOMAIN"
echo "=========================================================================="
