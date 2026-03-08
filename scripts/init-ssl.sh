#!/usr/bin/env bash
# One-time SSL certificate acquisition via Let's Encrypt.
# Run on the VM AFTER DNS A record for archist.work points to this server.
# Usage: bash scripts/init-ssl.sh

set -euo pipefail

DOMAIN="archist.work"
EMAIL="${1:-}"  # Usage: bash init-ssl.sh your@email.com

if [ -z "$EMAIL" ]; then
  echo "Usage: bash scripts/init-ssl.sh <your-email>"
  exit 1
fi

cd ~/ai-arch-assistant

echo ">>> Step 1: Start nginx on HTTP only (for ACME challenge)..."
# Temporarily use the HTTP-only config so nginx can start without certs
docker compose -f docker-compose.prod.yml up -d nginx

echo ">>> Step 2: Obtain certificate for $DOMAIN..."
docker compose -f docker-compose.prod.yml run --rm certbot \
  certonly --webroot \
  --webroot-path /var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN" \
  -d "www.$DOMAIN"

echo ">>> Step 3: Reload nginx with HTTPS config..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "=== SSL ready ==="
echo "Visit https://$DOMAIN to verify."
