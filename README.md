# 🔥 Free Fire Squad — Discord Bot & Server Setup

A complete Discord server + bot for Free Fire players and friends.

---

## ⚡ Quick Start (3 steps)

### Step 1 — Create your Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → name it `Free Fire Squad Bot`
3. Go to **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
   - ✅ Presence Intent
5. copy your token (keep it secret!)Click **Reset Token** → 
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot Permissions: `Administrator`
7. Copy the generated URL → open it → invite the bot to your server

---

### Step 2 — Configure the bot

```bash
# Install dependencies
pip install -r requirements.txt

# Copy the example env file
copy .env.example .env      # Windows
# cp .env.example .env      # Mac/Linux
```

Open `.env` and fill in:

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here        # Right-click server → Copy Server ID
OPENAI_API_KEY=optional_for_ai      # Leave blank if you don't have one
```

**How to get your Server ID:**
- Open Discord → Settings → Advanced → Enable **Developer Mode**
- Right-click your server icon → **Copy Server ID**

---

### Step 3 — Run setup then start the bot

```bash
# Build the entire server (channels, roles, categories) — run ONCE
python setup_server.py

# Start the bot
python bot.py
```

That's it! 🎉

---

## 🏗️ What Gets Created

### Channels
| Category | Channels |
|----------|----------|
| 📋 INFO & RULES | announcements, rules, about-server, bot-commands |
| 🔥 FREE FIRE HQ | ff-news, events, patch-notes, esports, tips-and-tricks, map-callouts |
| 👥 COMMUNITY | welcome, general-chat, memes, clips-and-highlights, fan-art, trading-post |
| 🎮 GAMING | lfg, stats-flex, rank-grind, custom-rooms, other-games |
| 🤖 AI & BOTS | ai-assistant, player-stats, bot-fun, music |
| 🎙️ VOICE | Squad Lobby, Game Room 1 & 2, Ranked Grind, Chill Zone |
| 🛡️ STAFF | staff-chat, mod-log, bot-log (staff only) |

### Roles
| Role | Purpose |
|------|---------|
| 👑 Owner | Full admin |
| ⚔️ Admin | Server admin |
| 🛡️ Moderator | Moderation tools |
| 💎 Heroic → 🌱 Bronze | Free Fire rank roles (self-assign with `/rank`) |
| 🎮 Gamer | General gaming role |
| 🔥 Free Fire Fan | FF enthusiast role |
| 👋 New Member | Auto-assigned on join |

---

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/news` | Latest Free Fire news (auto-posts every 30 min) |
| `/events` | Active in-game events & esports schedule |
| `/patchnotes` | Latest patch highlights |
| `/stats [username]` | Player stats card |
| `/rank [rank]` | Self-assign your rank role |
| `/lfg [mode]` | Looking for group post |
| `/profile` | View member profile |
| `/ask [question]` | AI assistant (Booyah Bot) |
| `/tip` | Random pro tip |
| `/build [playstyle]` | Character build recommendation |
| `/trivia` | Free Fire trivia game |
| `/8ball` | Magic 8-ball |
| `/coinflip` | Flip a coin |
| `/dice` | Roll a dice |
| `/rps` | Rock Paper Scissors |
| `/booyah` | Celebrate a win |
| `/squad` | Pick a random squad |
| `/giveaway` | Start a giveaway (staff) |
| `/poll` | Create a poll |
| `/customroom` | Post a custom room code |
| `/schedule` | Post a gaming session |
| `/kick /ban /mute /warn /purge` | Moderation (staff) |
| `/help` | Show all commands |
| `/ping` | Bot latency |
| `/serverinfo` | Server info |

---

## 🤖 AI Assistant (Optional)

Add your OpenAI API key to `.env` for full AI responses:
```env
OPENAI_API_KEY=sk-...
```

Without it, the bot uses built-in keyword-based answers. Still works great!

Get a key at [platform.openai.com](https://platform.openai.com)

---

## 📰 Auto News

The bot automatically posts Free Fire news to `#📰│ff-news` every **30 minutes**.
Make sure `NEWS_CHANNEL_ID` is set in `.env` (the setup script does this automatically).

---

## 🔧 Troubleshooting

**Bot not responding to slash commands?**
- Wait 1–2 minutes after first run for commands to sync globally
- Make sure the bot has `applications.commands` scope

**"Guild not found" error?**
- Double-check `GUILD_ID` in `.env`
- Make sure Developer Mode is on in Discord settings

**News not posting?**
- Check `NEWS_CHANNEL_ID` is set in `.env`
- Run `setup_server.py` first — it sets this automatically
