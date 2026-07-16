#!/bin/bash
# ─────────────────────────────────────────────────────────
# vps_fix_music.sh — Run this DIRECTLY on the VPS terminal
# Fixes YouTube streaming issues and restarts the music bot
# ─────────────────────────────────────────────────────────

BOT_DIR="/root/bot"

echo "=== 1. Updating yt-dlp to latest version ==="
pip3 install -U yt-dlp
echo ""

echo "=== 2. Checking ffmpeg ==="
ffmpeg -version 2>&1 | head -1
echo ""

echo "=== 3. Checking cookies file ==="
if [ -f "$BOT_DIR/youtube_cookies.txt" ]; then
    echo "✅ Cookies file exists: $(wc -l < $BOT_DIR/youtube_cookies.txt) lines"
    head -3 "$BOT_DIR/youtube_cookies.txt"
else
    echo "❌ Cookies file NOT found at $BOT_DIR/youtube_cookies.txt"
fi
echo ""

echo "=== 4. Testing YouTube extraction (tv_embedded client) ==="
python3 - <<'PYEOF'
import yt_dlp, os

cookie_file = "/root/bot/youtube_cookies.txt"

opts = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": False,
    "no_warnings": False,
    "extractor_args": {
        "youtube": {
            "player_client": ["tv_embedded", "android"],
            "player_skip": ["webpage", "configs"],
        }
    },
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version",
    },
}

if os.path.exists(cookie_file):
    opts["cookiefile"] = cookie_file
    print(f"Using cookies: {cookie_file}")
else:
    print("No cookies file found, trying without")

try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info("ytsearch1:never gonna give you up", download=False)
        if "entries" in info:
            info = info["entries"][0]
        print(f"\n✅ SUCCESS!")
        print(f"   Title: {info.get('title')}")
        print(f"   URL: {info.get('url', 'N/A')[:80]}...")
        print(f"   Duration: {info.get('duration')}s")
except Exception as e:
    print(f"\n❌ FAILED: {e}")
PYEOF

echo ""
echo "=== 5. Restarting music bot ==="
systemctl restart pirates-music
sleep 3
systemctl status pirates-music --no-pager | tail -15

echo ""
echo "=== 6. Live logs (last 20 lines) ==="
journalctl -u pirates-music -n 20 --no-pager
