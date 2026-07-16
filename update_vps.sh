#!/bin/bash
# ─────────────────────────────────────────────────────────
# update_vps.sh — Push latest code to VPS and restart bots
# Run from your LOCAL machine: bash update_vps.sh
# ─────────────────────────────────────────────────────────

VPS_IP="149.28.122.244"
VPS_USER="root"
BOT_DIR="/root/bot"

echo "📦 Uploading latest bot files to VPS..."

# Upload the updated music cog
scp freefire_bot/cogs/music.py ${VPS_USER}@${VPS_IP}:${BOT_DIR}/cogs/music.py
scp freefire_bot/music_bot.py  ${VPS_USER}@${VPS_IP}:${BOT_DIR}/music_bot.py
scp freefire_bot/youtube_cookies.txt ${VPS_USER}@${VPS_IP}:${BOT_DIR}/youtube_cookies.txt

echo "🔄 Restarting music bot service..."
ssh ${VPS_USER}@${VPS_IP} "
  # Update yt-dlp to latest version
  pip3 install -U yt-dlp

  # Restart the service
  systemctl restart pirates-music
  sleep 3
  systemctl status pirates-music --no-pager -l | tail -20
"

echo "✅ Done!"
