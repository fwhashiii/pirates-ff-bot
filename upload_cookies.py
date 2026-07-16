import paramiko, os

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('149.28.122.244', username='root', password='Q}m2Hkj#D{L*g[jy', timeout=15)

# Upload cookies file
sftp = ssh.open_sftp()
sftp.put('youtube_cookies.txt', '/root/bot/youtube_cookies.txt')
sftp.close()
print('✅ Cookies uploaded to /root/bot/youtube_cookies.txt')

# Update and restart
stdin, stdout, stderr = ssh.exec_command('cd /root/bot && git pull && systemctl restart pirates-music && sleep 3 && journalctl -u pirates-music -n 5 --no-pager')
print(stdout.read().decode())
ssh.close()
print('Done!')
