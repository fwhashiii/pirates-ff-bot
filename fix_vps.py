import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('149.28.122.244', username='root', password='Q}m2Hkj#D{L*g[jy', timeout=15)

commands = [
    "pip3 install 'discord.py[voice]==2.4.0' PyNaCl --upgrade --quiet",
    "pip3 install yt-dlp --upgrade --quiet",
    "cd /root/bot && git pull",
    "systemctl restart pirates-music",
    "sleep 3 && journalctl -u pirates-music -n 10 --no-pager",
]

for cmd in commands:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(out[-500:])
    if err and "WARNING" not in err and "already" not in err.lower():
        print(f"ERR: {err[-200:]}")

ssh.close()
print("\nDone!")
