"""
╔══════════════════════════════════════════════════════════════╗
║   🔥 FREE FIRE SQUAD — Discord Server Auto-Setup Script 🔥   ║
║   Run this ONCE to build your entire server automatically    ║
╚══════════════════════════════════════════════════════════════╝

HOW TO USE:
  1. pip install -r requirements.txt
  2. Copy .env.example → .env and fill in your bot token + guild ID
  3. python setup_server.py
  4. python bot.py   ← runs the bot after setup
"""

import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))

# ── Color palette ─────────────────────────────────────────
COLORS = {
    "gold":    0xFFD700,
    "red":     0xFF4500,
    "blue":    0x00BFFF,
    "green":   0x00FF7F,
    "purple":  0x9B59B6,
    "gray":    0x95A5A6,
    "dark":    0x2C2F33,
    "white":   0xFFFFFF,
}

# ══════════════════════════════════════════════════════════
#  SERVER STRUCTURE
#  Each category holds a list of (channel_name, type, topic)
#  type: "text" | "voice" | "announcement" | "forum"
# ══════════════════════════════════════════════════════════
SERVER_STRUCTURE = [
    {
        "category": "📋 INFO & RULES",
        "channels": [
            ("📢│announcements",  "announcement", "Official server announcements"),
            ("📜│rules",          "text",         "Read before doing anything else"),
            ("🎮│about-server",   "text",         "What this server is about"),
            ("✅│verify",         "text",         "Verify your Free Fire account to access the server"),
            ("🤖│bot-commands",   "text",         "Use bot commands here"),
        ],
    },
    {
        "category": "📡 LIVE & UPDATES",
        "channels": [
            ("🔴│live-now",         "text",   "Post when you go live — streams, YouTube, TikTok"),
            ("📺│stream-clips",     "text",   "Share your best stream moments"),
            ("🔔│game-updates",     "text",   "Auto-posted Free Fire game updates and patches"),
            ("📣│content-creators", "text",   "Follow our squad's content creators"),
            ("🎥│youtube-drops",    "text",   "New YouTube video notifications"),
            ("📱│tiktok-clips",     "text",   "TikTok Free Fire clips"),
        ],
    },
    {
        "category": "🔥 FREE FIRE HQ",
        "channels": [
            ("📰│ff-news",        "text",   "Auto-posted Free Fire news & updates"),
            ("🗓️│events",         "text",   "In-game events, tournaments & giveaways"),
            ("📋│patch-notes",    "text",   "Latest patch notes and balance changes"),
            ("🏆│esports",        "text",   "Competitive scene, FFWS, EWC updates"),
            ("💡│tips-and-tricks","text",   "Share your best strategies"),
            ("🗺️│map-callouts",   "text",   "Map strategies and drop spots"),
        ],
    },
    {
        "category": "👥 COMMUNITY",
        "channels": [
            ("👋│welcome",        "text",   "New members land here"),
            ("💬│general-chat",   "text",   "Talk about anything"),
            ("😂│memes",          "text",   "Free Fire memes only"),
            ("📸│clips-and-highlights", "text", "Post your best plays"),
            ("🎨│fan-art",        "text",   "Share your Free Fire artwork"),
            ("🛒│trading-post",   "text",   "Trade items, accounts, tips"),
        ],
    },
    {
        "category": "🎮 GAMING",
        "channels": [
            ("🔍│lfg",            "text",   "Looking for group — find squadmates"),
            ("📊│stats-flex",     "text",   "Show off your stats and rank"),
            ("🏅│rank-grind",     "text",   "Ranked mode discussion"),
            ("🎯│custom-rooms",   "text",   "Custom room codes and scrims"),
            ("🕹️│other-games",    "text",   "Other games the squad plays"),
        ],
    },
    {
        "category": "🤖 AI & BOTS",
        "channels": [
            ("🤖│ai-assistant",   "text",   "Ask the AI anything — game tips, builds, lore"),
            ("📈│player-stats",   "text",   "Use /stats to look up player info"),
            ("🎲│bot-fun",        "text",   "Games, trivia, and bot entertainment"),
            ("🎵│music",          "text",   "Music bot commands"),
        ],
    },
    {
        "category": "🎙️ VOICE CHANNELS",
        "channels": [
            ("🔥 Squad Lobby",    "voice",  ""),
            ("🎮 Game Room 1",    "voice",  ""),
            ("🎮 Game Room 2",    "voice",  ""),
            ("🎯 Ranked Grind",   "voice",  ""),
            ("🎵 Chill Zone",     "voice",  ""),
            ("📢 Announcements",  "voice",  ""),
        ],
    },
    {
        "category": "🛡️ STAFF",
        "channels": [
            ("🛡️│staff-chat",        "text",         "Staff only"),
            ("📋│mod-log",           "text",         "Moderation log"),
            ("⚙️│bot-log",           "text",         "Bot activity log"),
            ("👑 Owner VC",          "voice_owner",  ""),
            ("⚔️ Captain VC",        "voice_captain",""),
            ("🛡️ Mod VC",            "voice_mod",    ""),
            ("🔒 Staff Lounge",      "voice_staff",  ""),
        ],
    },
]

# ══════════════════════════════════════════════════════════
#  ROLES
#  (name, color_hex, hoist, mentionable, permissions_preset)
#  permissions_preset: "admin" | "mod" | "member" | "muted" | "bot"
# ══════════════════════════════════════════════════════════
ROLES = [
    # Staff
    {"name": "👑 Owner",          "color": 0xFFD700, "hoist": True,  "mentionable": False, "preset": "admin"},
    {"name": "⚔️ Captain",        "color": 0xFF4500, "hoist": True,  "mentionable": True,  "preset": "admin"},
    {"name": "🛡️ Moderator",      "color": 0x00BFFF, "hoist": True,  "mentionable": True,  "preset": "mod"},
    # Game ranks
    {"name": "💎 Heroic",         "color": 0xE91E63, "hoist": True,  "mentionable": True,  "preset": "member"},
    {"name": "🏆 Grandmaster",    "color": 0xFF6B35, "hoist": True,  "mentionable": True,  "preset": "member"},
    {"name": "🥇 Master",         "color": 0xFFD700, "hoist": True,  "mentionable": True,  "preset": "member"},
    {"name": "💠 Diamond",        "color": 0x00BFFF, "hoist": True,  "mentionable": True,  "preset": "member"},
    {"name": "🥈 Platinum",       "color": 0x95A5A6, "hoist": True,  "mentionable": True,  "preset": "member"},
    {"name": "🥉 Gold",           "color": 0xF1C40F, "hoist": False, "mentionable": False, "preset": "member"},
    {"name": "🔰 Silver",         "color": 0xBDC3C7, "hoist": False, "mentionable": False, "preset": "member"},
    {"name": "🌱 Bronze",         "color": 0xCD7F32, "hoist": False, "mentionable": False, "preset": "member"},
    # Community
    {"name": "🎮 Player",          "color": 0x9B59B6, "hoist": False, "mentionable": False, "preset": "member"},
    {"name": "🔥 Free Fire Fan",  "color": 0xFF4500, "hoist": False, "mentionable": False, "preset": "member"},
    {"name": "🤖 Bot",            "color": 0x2ECC71, "hoist": True,  "mentionable": False, "preset": "bot"},
    {"name": "🎮 New Player",     "color": 0x7F8C8D, "hoist": False, "mentionable": False, "preset": "member"},
    {"name": "🔇 Muted",          "color": 0x2C2F33, "hoist": False, "mentionable": False, "preset": "muted"},
]

# ══════════════════════════════════════════════════════════
#  WELCOME MESSAGE (posted to #welcome on setup)
# ══════════════════════════════════════════════════════════
WELCOME_TEXT = """
🔥 **Welcome to Free Fire Squad!** 🔥

The ultimate hangout for Free Fire players, fans, and friends.

**Get started:**
> 📜 Read <#RULES_PLACEHOLDER> before chatting
> 🏅 Grab your rank role in <#BOT_COMMANDS_PLACEHOLDER>
> 💬 Introduce yourself in <#GENERAL_PLACEHOLDER>
> 🤖 Try `/help` to see all bot commands

**Quick commands:**
> `/news` — Latest Free Fire news
> `/events` — Active in-game events
> `/stats` — Look up player stats
> `/ask` — Ask the AI assistant anything
> `/lfg` — Find squadmates
> `/trivia` — Free Fire trivia game

**BOOYAH! 🏆**
"""

RULES_TEXT = """
📜 **Server Rules — Read Before Playing**

**1. Respect everyone** — No toxicity, harassment, or hate speech.
**2. Keep it Free Fire** — Stay on topic in game channels.
**3. No spam** — Don't flood chats or ping staff unnecessarily.
**4. No NSFW content** — Keep it clean, this is a gaming server.
**5. No self-promotion** — Don't advertise without staff permission.
**6. English in main channels** — So everyone can follow along.
**7. No cheating discussion** — Hacks, exploits, and cheats are banned topics.
**8. Listen to staff** — Their word is final.

Breaking rules = warning → mute → kick → ban.

**Have fun and get that Booyah! 🏆**
"""


# ══════════════════════════════════════════════════════════
#  SETUP CLIENT
# ══════════════════════════════════════════════════════════
class SetupClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.done = False

    async def on_ready(self):
        if self.done:
            return
        self.done = True

        guild = self.get_guild(GUILD_ID)
        if not guild:
            print(f"❌ Guild {GUILD_ID} not found. Check your GUILD_ID in .env")
            await self.close()
            return

        print(f"\n🔥 Setting up server: {guild.name}")
        print("=" * 50)

        # ── 1. Create Roles ───────────────────────────────
        print("\n📋 Creating roles...")
        existing_roles = {r.name: r for r in guild.roles}
        created_roles = {}

        for role_data in ROLES:
            name = role_data["name"]
            if name in existing_roles:
                print(f"   ⏭️  Role exists: {name}")
                created_roles[name] = existing_roles[name]
                continue

            perms = build_permissions(role_data["preset"])
            role = await guild.create_role(
                name=name,
                color=discord.Color(role_data["color"]),
                hoist=role_data["hoist"],
                mentionable=role_data["mentionable"],
                permissions=perms,
                reason="Free Fire Bot Setup",
            )
            created_roles[name] = role
            print(f"   ✅ Created role: {name}")
            await asyncio.sleep(0.5)

        # ── 2. Create Categories & Channels ───────────────
        print("\n📁 Creating categories and channels...")
        existing_categories = {c.name: c for c in guild.categories}
        channel_map = {}  # name → channel object

        for section in SERVER_STRUCTURE:
            cat_name = section["category"]

            if cat_name in existing_categories:
                category = existing_categories[cat_name]
                print(f"   ⏭️  Category exists: {cat_name}")
            else:
                # Staff category — restrict to mod+ roles
                overwrites = {}
                if "STAFF" in cat_name:
                    overwrites = build_staff_overwrites(guild, created_roles)

                category = await guild.create_category(
                    cat_name,
                    overwrites=overwrites,
                    reason="Free Fire Bot Setup",
                )
                print(f"   📁 Created category: {cat_name}")
                await asyncio.sleep(0.5)

            existing_channels = {c.name: c for c in category.channels}

            for (ch_name, ch_type, topic) in section["channels"]:
                if ch_name in existing_channels:
                    print(f"      ⏭️  Channel exists: {ch_name}")
                    channel_map[ch_name] = existing_channels[ch_name]
                    continue

                if ch_type == "voice":
                    ch = await guild.create_voice_channel(
                        ch_name, category=category, reason="Free Fire Bot Setup"
                    )
                elif ch_type == "voice_owner":
                    ow = {
                        guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
                    }
                    for rn in ["👑 Owner"]:
                        r = discord.utils.get(guild.roles, name=rn)
                        if r: ow[r] = discord.PermissionOverwrite(connect=True, view_channel=True, speak=True)
                    ch = await guild.create_voice_channel(ch_name, category=category, overwrites=ow, reason="Free Fire Bot Setup")
                elif ch_type == "voice_captain":
                    ow = {
                        guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
                    }
                    for rn in ["👑 Owner", "⚔️ Captain"]:
                        r = discord.utils.get(guild.roles, name=rn)
                        if r: ow[r] = discord.PermissionOverwrite(connect=True, view_channel=True, speak=True)
                    ch = await guild.create_voice_channel(ch_name, category=category, overwrites=ow, reason="Free Fire Bot Setup")
                elif ch_type == "voice_mod":
                    ow = {
                        guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
                    }
                    for rn in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
                        r = discord.utils.get(guild.roles, name=rn)
                        if r: ow[r] = discord.PermissionOverwrite(connect=True, view_channel=True, speak=True)
                    ch = await guild.create_voice_channel(ch_name, category=category, overwrites=ow, reason="Free Fire Bot Setup")
                elif ch_type == "voice_staff":
                    ow = {
                        guild.default_role: discord.PermissionOverwrite(connect=False, view_channel=False),
                    }
                    for rn in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
                        r = discord.utils.get(guild.roles, name=rn)
                        if r: ow[r] = discord.PermissionOverwrite(connect=True, view_channel=True, speak=True)
                    ch = await guild.create_voice_channel(ch_name, category=category, overwrites=ow, reason="Free Fire Bot Setup")
                else:
                    # announcement and text both use create_text_channel
                    ch = await guild.create_text_channel(
                        ch_name,
                        category=category,
                        topic=topic,
                        reason="Free Fire Bot Setup",
                    )

                channel_map[ch_name] = ch
                print(f"      ✅ Created channel: {ch_name}")
                await asyncio.sleep(0.4)

        # ── 3. Post Welcome & Rules messages ──────────────
        print("\n💬 Posting welcome and rules messages...")
        await post_starter_messages(guild, channel_map)

        # ── 4. Update .env with channel IDs ───────────────
        print("\n⚙️  Saving channel IDs to .env ...")
        update_env_channel_ids(channel_map)

        print("\n" + "=" * 50)
        print("✅ SERVER SETUP COMPLETE!")
        print("=" * 50)
        print("\nNext steps:")
        print("  1. Assign the '👑 Owner' role to yourself")
        print("  2. Run:  python bot.py   to start the bot")
        print("  3. Use /help in Discord to see all commands")
        print("\nBOOYAH! 🏆\n")

        await self.close()


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════
def build_permissions(preset: str) -> discord.Permissions:
    if preset == "admin":
        return discord.Permissions(administrator=True)
    if preset == "mod":
        return discord.Permissions(
            kick_members=True,
            ban_members=True,
            manage_messages=True,
            manage_channels=True,
            mute_members=True,
            deafen_members=True,
            move_members=True,
            read_messages=True,
            send_messages=True,
        )
    if preset == "muted":
        return discord.Permissions(
            read_messages=True,
            send_messages=False,
            speak=False,
        )
    if preset == "bot":
        return discord.Permissions(
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            manage_messages=True,
        )
    # default member
    return discord.Permissions(
        read_messages=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        add_reactions=True,
        connect=True,
        speak=True,
    )


def build_staff_overwrites(guild, roles):
    """Make staff channels invisible to regular members."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
    }
    for role_name in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
        if role_name in roles:
            overwrites[roles[role_name]] = discord.PermissionOverwrite(read_messages=True)
    return overwrites


async def post_starter_messages(guild, channel_map):
    """Post welcome and rules messages if channels are fresh."""
    # Rules
    rules_ch = channel_map.get("📜│rules")
    if rules_ch:
        history = [m async for m in rules_ch.history(limit=1)]
        if not history:
            await rules_ch.send(RULES_TEXT)
            print("   ✅ Posted rules")

    # Welcome
    welcome_ch = channel_map.get("👋│welcome")
    if welcome_ch:
        history = [m async for m in welcome_ch.history(limit=1)]
        if not history:
            await welcome_ch.send(WELCOME_TEXT)
            print("   ✅ Posted welcome message")


def update_env_channel_ids(channel_map):
    """Write discovered channel IDs back into .env."""
    mapping = {
        "NEWS_CHANNEL_ID":    "📰│ff-news",
        "WELCOME_CHANNEL_ID": "👋│welcome",
        "LOG_CHANNEL_ID":     "⚙️│bot-log",
    }

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        print("   ⚠️  .env not found — skipping channel ID update")
        return

    with open(env_path, "r") as f:
        lines = f.readlines()

    updated = []
    for line in lines:
        replaced = False
        for env_key, ch_name in mapping.items():
            if line.startswith(env_key + "="):
                ch = channel_map.get(ch_name)
                if ch:
                    updated.append(f"{env_key}={ch.id}\n")
                    replaced = True
                    break
        if not replaced:
            updated.append(line)

    with open(env_path, "w") as f:
        f.writelines(updated)
    print("   ✅ Channel IDs saved to .env")


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set in .env")
        exit(1)
    if not GUILD_ID:
        print("❌ GUILD_ID not set in .env")
        exit(1)

    client = SetupClient()
    client.run(TOKEN)
