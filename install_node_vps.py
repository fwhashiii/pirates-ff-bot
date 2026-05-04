import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('149.28.122.244', username='root', password='Q}m2Hkj#D{L*g[jy', timeout=15)

print("Installing Node.js on VPS...")
stdin, stdout, stderr = ssh.exec_command(
    'curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs && node --version',
    timeout=120
)
print(stdout.read().decode())
print(stderr.read().decode()[-200:])

print("Restarting music bot...")
stdin, stdout, stderr = ssh.exec_command('systemctl restart pirates-music && sleep 3 && journalctl -u pirates-music -n 3 --no-pager')
print(stdout.read().decode())
ssh.close()
print("Done!")
