#!/bin/bash
set -e

read -p "Enter domain name (e.g., jagjeevan.me): " DOMAIN
read -p "Enter email address for Let's Encrypt notifications: " EMAIL

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "Error: Domain and email cannot be empty."
  exit 1
fi

echo "Installing Certbot and enabling HTTPS for $DOMAIN ..."

sudo apt update -y
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL

sudo systemctl reload nginx

sudo certbot renew --dry-run

echo "SSL successfully enabled for https://$DOMAIN/"
