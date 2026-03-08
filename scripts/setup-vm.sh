#!/usr/bin/env bash
# First-time VM setup script.
# Run as root (or with sudo) on a fresh Ubuntu 24.04 Droplet.
# Usage: bash scripts/setup-vm.sh <deploy-username>

set -euo pipefail

DEPLOY_USER="${1:-deployer}"

echo ">>> Installing Docker..."
apt-get update -q
apt-get install -y -q ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -q
apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo ">>> Creating deploy user: $DEPLOY_USER"
id "$DEPLOY_USER" &>/dev/null || useradd -m -s /bin/bash "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"
mkdir -p /home/"$DEPLOY_USER"/.ssh
chmod 700 /home/"$DEPLOY_USER"/.ssh
touch /home/"$DEPLOY_USER"/.ssh/authorized_keys
chmod 600 /home/"$DEPLOY_USER"/.ssh/authorized_keys
chown -R "$DEPLOY_USER":"$DEPLOY_USER" /home/"$DEPLOY_USER"/.ssh

echo ">>> Cloning repository..."
sudo -u "$DEPLOY_USER" git clone https://github.com/yimingc-1010/ai-arch-assistant.git \
  /home/"$DEPLOY_USER"/ai-arch-assistant 2>/dev/null || echo "(repo already exists, skip)"

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Paste the GitHub Actions public SSH key into /home/$DEPLOY_USER/.ssh/authorized_keys"
echo "  2. Copy .env to /home/$DEPLOY_USER/ai-arch-assistant/.env"
echo "  3. Run: bash scripts/init-ssl.sh"
