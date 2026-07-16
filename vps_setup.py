"""
Run this script to set up the music bot on the Vultr VPS.
It uses paramiko (SSH library) to connect and run commands.
"""
import subprocess, sys

# Install paramiko if needed
subprocess.run([sys.executable, "-m", "pip", "install", "paramiko", "--quiet"])

import paramiko, time

HOST = "149.28.122.244"
USER = "root"
PASS = "Q}m2Hkj#D{L*g[jy"

# Your music bot token from .env
import os
from dotenv import load_dotenv
load_dotenv()
MUSIC_TOKEN = os.getenv("MUSIC_BOT_TOKEN", "")
GUILD_ID = os.getenv("GUILD_ID", "1478801553585475886")

def run(ssh, cmd, timeout=60):
    print(f"\n$ {cmd[:80]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[-500:])
    if err and "WARNING" not in err: print(f"ERR: {err[-200:]}")
    return out

print("Connecting to VPS...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=15)
print("Connected!")

# Update and install
run(ssh, "apt-get update -y", 120)
run(ssh, "apt-get install -y python3 python3-pip ffmpeg git screen", 180)
run(ssh, "python3 --version")
run(ssh, "ffmpeg -version 2>&1 | head -1")

# Clone repo
run(ssh, "rm -rf /root/bot && git clone https://github.com/fwhashiii/pirates-ff-bot.git /root/bot", 60)

# Install Python packages
run(ssh, "cd /root/bot && pip3 install -r requirements.txt --quiet", 180)
run(ssh, "pip3 install audioop-lts yt-dlp --upgrade --quiet", 60)

# Create .env
env_content = f"""MUSIC_BOT_TOKEN={MUSIC_TOKEN}
GUILD_ID={GUILD_ID}
PREFIX=!
"""
run(ssh, f"cat > /root/bot/.env << 'EOF'\n{env_content}\nEOF")

# Create systemd service
service = """[Unit]
Description=PIRATES Music Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bot
ExecStart=/usr/bin/python3 music_bot.py
Restart=always
RestartSec=10
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
"""
run(ssh, f"cat > /etc/systemd/system/pirates-music.service << 'EOF'\n{service}\nEOF")
run(ssh, "systemctl daemon-reload")
run(ssh, "systemctl enable pirates-music")
run(ssh, "systemctl start pirates-music")
time.sleep(3)
run(ssh, "systemctl status pirates-music --no-pager")

print("\n✅ Music bot is running on VPS!")
print(f"   Server: {HOST}")
print("   To check status: systemctl status pirates-music")
print("   To see logs: journalctl -u pirates-music -f")

ssh.close()
