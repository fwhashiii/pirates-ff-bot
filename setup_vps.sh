#!/bin/bash
# PIRATES Music Bot VPS Setup Script
set -e

echo "=== Updating system ==="
apt-get update -y && apt-get upgrade -y

echo "=== Installing dependencies ==="
apt-get install -y python3 python3-pip python3-venv ffmpeg git screen curl

echo "=== Cloning bot repo ==="
cd /root
git clone https://github.com/fwhashiii/pirates-ff-bot.git bot
cd bot

echo "=== Installing Python packages ==="
pip3 install -r requirements.txt
pip3 install audioop-lts yt-dlp --upgrade

echo "=== Creating .env file ==="
cat > .env << 'ENVEOF'
MUSIC_BOT_TOKEN=REPLACE_WITH_TOKEN
GUILD_ID=1478801553585475886
PREFIX=!
ENVEOF

echo "=== Creating systemd service ==="
cat > /etc/systemd/system/pirates-music.service << 'SVCEOF'
[Unit]
Description=PIRATES Music Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bot
ExecStart=/usr/bin/python3 music_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable pirates-music
echo "=== Setup complete! Edit /root/bot/.env then run: systemctl start pirates-music ==="
