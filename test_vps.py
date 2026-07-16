import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('149.28.122.244', username='root', password='Q}m2Hkj#D{L*g[jy', timeout=15)

# Test yt-dlp directly
cmd = """python3 -c "
import yt_dlp
opts = {
    'format': 'bestaudio/best',
    'quiet': False,
    'default_search': 'ytsearch',
    'extractor_args': {'youtube': {'player_client': ['android']}},
    'http_headers': {'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip'},
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info('ytsearch:free fire music', download=False)
    if 'entries' in info and info['entries']:
        print('SUCCESS:', info['entries'][0]['title'])
        print('URL:', info['entries'][0]['url'][:60])
    else:
        print('NO RESULTS')
" 2>&1 | tail -20"""

stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
ssh.close()
