#!/bin/bash
# ==============================================================================
# Automated Let's Encrypt SSL Setup for Aegis-OS
# Domain: aicv.devops-in22labs.com
# ==============================================================================

set -e

DOMAIN="aicv.devops-in22labs.com"
EMAIL="admin@devops-in22labs.com"

echo "🔐 Installing Certbot and Let's Encrypt Nginx plugin..."
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

echo "🛡️ Ensuring HTTPS port 443 is open in firewall..."
sudo ufw allow 443/tcp || true

echo "🌐 Requesting and applying Let's Encrypt SSL Certificate for $DOMAIN..."
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect

echo "🔄 Reloading Nginx with SSL configuration..."
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "=========================================================================="
echo "🎉 SSL CERTIFICATE INSTALLED & ACTIVE!"
echo "Your live secure web portal is now online at:"
echo "👉 https://$DOMAIN"
echo "=========================================================================="
