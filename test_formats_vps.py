import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('149.28.122.244', username='root', password='Q}m2Hkj#D{L*g[jy', timeout=15)

test_script = '''
import yt_dlp

# First get the video ID
opts = {
    "quiet": True,
    "default_search": "ytsearch",
    "cookiefile": "/root/bot/youtube_cookies.txt",
    "extract_flat": True,
}

with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info("ytsearch:free fire music", download=False)
    if "entries" in info and info["entries"]:
        vid_id = info["entries"][0]["id"]
        print("Video ID:", vid_id)
        
        # Now list formats
        opts2 = {
            "quiet": True,
            "cookiefile": "/root/bot/youtube_cookies.txt",
            "listformats": False,
        }
        with yt_dlp.YoutubeDL(opts2) as ydl2:
            info2 = ydl2.extract_info(f"https://www.youtube.com/watch?v={vid_id}", download=False)
            formats = info2.get("formats", [])
            audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
            print(f"Audio-only formats: {len(audio_formats)}")
            for f in audio_formats[:3]:
                print(f"  {f.get('format_id')} - {f.get('ext')} - {f.get('abr')}kbps - url: {f.get('url','')[:40]}")
            if not audio_formats:
                print("No audio-only formats, trying any format...")
                for f in formats[:3]:
                    print(f"  {f.get('format_id')} - {f.get('ext')} - acodec:{f.get('acodec')} vcodec:{f.get('vcodec')}")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/test_fmt.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_fmt.py 2>&1', timeout=30)
print(stdout.read().decode())
ssh.close()
