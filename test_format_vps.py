import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('149.28.122.244', username='root', password='Q}m2Hkj#D{L*g[jy', timeout=15)

# Write a test script to the VPS
test_script = '''
import yt_dlp

opts = {
    "format": "bestaudio",
    "quiet": False,
    "default_search": "ytsearch",
    "cookiefile": "/root/bot/youtube_cookies.txt",
}

with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info("ytsearch:free fire music", download=False)
    if "entries" in info and info["entries"]:
        e = info["entries"][0]
        print("SUCCESS:", e["title"])
        print("URL:", e["url"][:60])
    else:
        print("NO RESULTS")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/test_yt.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_yt.py 2>&1 | tail -8', timeout=30)
print(stdout.read().decode())
ssh.close()
