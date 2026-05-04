import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('149.28.122.244', username='root', password='Q}m2Hkj#D{L*g[jy', timeout=15)

test_script = '''
import yt_dlp

opts = {
    "format": "bestaudio/best",
    "quiet": False,
    "cookiefile": "/root/bot/youtube_cookies.txt",
}

url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=False)
    print("Title:", info.get("title"))
    print("Format:", info.get("format"))
    print("SUCCESS!")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/test_direct.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_direct.py 2>&1 | tail -8', timeout=30)
print(stdout.read().decode())
ssh.close()
