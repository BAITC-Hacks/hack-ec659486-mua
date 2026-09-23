#!/usr/bin/env bash
# Один раз на VPS (Ubuntu 22.04 / 24.04 / 26.04), под root:
#   scp deploy/vps-bootstrap.sh root@IP:/root/ && ssh root@IP bash /root/vps-bootstrap.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get -y upgrade
apt-get install -y ca-certificates curl git ufw rsync docker.io docker-compose-v2 docker-buildx
systemctl enable --now docker

# swap 2G: на 2 ГБ RAM сборка образа frontend (next build) ловит OOM без него
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf && sysctl -q -p /etc/sysctl.d/99-swap.conf

# firewall: только ssh, http, https
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

mkdir -p /opt/app
IP=$(curl -fsS -4 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
echo
echo "VPS готов. DNS: A-запись домена -> $IP"
echo "Дальше с ноутбука:  deploy/deploy.sh root@$IP"
