"""
🏆 Leaderboard & XP System Cog
Tracks messages, VC time, and gives XP/levels
Commands: /leaderboard /rank /givexp /resetxp
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
import logging
import json
import os

log = logging.getLogger("cog.leaderboard")

# In-memory XP store (persisted to file)
_XP_FILE = os.path.join(os.path.dirname(__file__), "..", "xp_data.json")
_xp: dict[str, dict] = {}  # {guild_id: {user_id: {xp, level, messages, vc_minutes}}}
_vc_start: dict[int, dict] = {}  # {guild_id: {user_id: join_timestamp}}

XP_PER_MESSAGE = 10
XP_PER_VC_MINUTE = 5
XP_COOLDOWN = 60  # seconds between XP gains from messages
_last_xp: dict[str, float] = {}


def _load_xp():
    global _xp
    try:
        if os.path.exists(_XP_FILE):
            with open(_XP_FILE, "r") as f:
                _xp = json.load(f)
    except Exception:
        _xp = {}


def _save_xp():
    try:
        with open(_XP_FILE, "w") as f:
            json.dump(_xp, f)
    except Exception as e:
        log.error(f"Failed to save XP: {e}")


def _get_user(guild_id: int, user_id: int) -> dict:
    gid, uid = str(guild_id), str(user_id)
    if gid not in _xp:
        _xp[gid] = {}
    if uid not in _xp[gid]:
        _xp[gid][uid] = {"xp": 0, "level": 1, "messages": 0, "vc_minutes": 0}
    return _xp[gid][uid]


def _xp_for_level(level: int) -> int:
    return 100 * (level ** 2)


def _add_xp(guild_id: int, user_id: int, amount: int) -> tuple[bool, int]:
    """Add XP and return (leveled_up, new_level)."""
    data = _get_user(guild_id, user_id)
    data["xp"] += amount
    leveled_up = False
    while data["xp"] >= _xp_for_level(data["level"]):
        data["xp"] -= _xp_for_level(data["level"])
        data["level"] += 1
        leveled_up = True
    return leveled_up, data["level"]


class LeaderboardCog(commands.Cog, name="Leaderboard"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        _load_xp()
        self.save_xp_loop.start()

    def cog_unload(self):
        self.save_xp_loop.cancel()
        _save_xp()

    @tasks.loop(minutes=5)
    async def save_xp_loop(self):
        _save_xp()

    # ── Message XP ────────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        key = f"{message.guild.id}:{message.author.id}"
        import time
        now = time.time()
        if now - _last_xp.get(key, 0) < XP_COOLDOWN:
            return
        _last_xp[key] = now

        data = _get_user(message.guild.id, message.author.id)
        data["messages"] += 1
        leveled_up, new_level = _add_xp(message.guild.id, message.author.id, XP_PER_MESSAGE)

        if leveled_up:
            embed = discord.Embed(
                description=f"🎉 {message.author.mention} leveled up to **Level {new_level}**!",
                color=0xFF4500,
            )
            await message.channel.send(embed=embed, delete_after=10)

    # ── VC XP ─────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        import time
        gid = member.guild.id

        if after.channel and not before.channel:
            # Joined VC
            if gid not in _vc_start:
                _vc_start[gid] = {}
            _vc_start[gid][member.id] = time.time()

        elif before.channel and not after.channel:
            # Left VC
            if gid in _vc_start and member.id in _vc_start[gid]:
                minutes = int((time.time() - _vc_start[gid].pop(member.id)) / 60)
                if minutes > 0:
                    data = _get_user(gid, member.id)
                    data["vc_minutes"] += minutes
                    _add_xp(gid, member.id, minutes * XP_PER_VC_MINUTE)

    # ── /rank ─────────────────────────────────────────────
    @app_commands.command(name="rank", description="Check your rank and XP 🏅")
    @app_commands.describe(member="Member to check (default: yourself)")
    async def slash_rank(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        data = _get_user(interaction.guild.id, target.id)
        level = data["level"]
        xp = data["xp"]
        needed = _xp_for_level(level)
        progress = int((xp / needed) * 20)
        bar = "█" * progress + "░" * (20 - progress)

        # Get rank position
        gid = str(interaction.guild.id)
        all_users = _xp.get(gid, {})
        sorted_users = sorted(all_users.items(), key=lambda x: (x[1].get("level", 1), x[1].get("xp", 0)), reverse=True)
        rank_pos = next((i + 1 for i, (uid, _) in enumerate(sorted_users) if uid == str(target.id)), "?")

        embed = discord.Embed(
            title=f"🏅 {target.display_name}'s Rank",
            color=0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏆 Server Rank", value=f"#{rank_pos}", inline=True)
        embed.add_field(name="⭐ Level", value=str(level), inline=True)
        embed.add_field(name="✨ XP", value=f"{xp}/{needed}", inline=True)
        embed.add_field(name="💬 Messages", value=str(data.get("messages", 0)), inline=True)
        embed.add_field(name="🎙️ VC Time", value=f"{data.get('vc_minutes', 0)} min", inline=True)
        embed.add_field(name="📊 Progress", value=f"`{bar}`", inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /leaderboard ──────────────────────────────────────
    @app_commands.command(name="leaderboard", description="Show the server leaderboard 🏆")
    @app_commands.describe(category="What to rank by")
    @app_commands.choices(category=[
        app_commands.Choice(name="XP & Level", value="xp"),
        app_commands.Choice(name="Messages", value="messages"),
        app_commands.Choice(name="VC Time", value="vc"),
    ])
    async def slash_leaderboard(self, interaction: discord.Interaction, category: str = "xp"):
        gid = str(interaction.guild.id)
        all_users = _xp.get(gid, {})

        if not all_users:
            await interaction.response.send_message("❌ No data yet. Start chatting to earn XP!", ephemeral=True)
            return

        if category == "xp":
            sorted_users = sorted(all_users.items(), key=lambda x: (x[1].get("level", 1), x[1].get("xp", 0)), reverse=True)
            title = "🏆 XP Leaderboard"
        elif category == "messages":
            sorted_users = sorted(all_users.items(), key=lambda x: x[1].get("messages", 0), reverse=True)
            title = "💬 Message Leaderboard"
        else:
            sorted_users = sorted(all_users.items(), key=lambda x: x[1].get("vc_minutes", 0), reverse=True)
            title = "🎙️ VC Time Leaderboard"

        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title=title, color=0xFF4500, timestamp=datetime.now(timezone.utc))

        for i, (uid, data) in enumerate(sorted_users[:10]):
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"

            if category == "xp":
                value = f"Level {data.get('level', 1)} • {data.get('xp', 0)} XP"
            elif category == "messages":
                value = f"{data.get('messages', 0)} messages"
            else:
                value = f"{data.get('vc_minutes', 0)} minutes"

            embed.add_field(name=f"{medal} {name}", value=value, inline=False)

        embed.set_footer(text=f"Top {min(10, len(sorted_users))} members")
        await interaction.response.send_message(embed=embed)

    # ── /givexp ───────────────────────────────────────────
    @app_commands.command(name="givexp", description="Give XP to a member (Staff only) ⭐")
    @app_commands.describe(member="Member to give XP to", amount="Amount of XP")
    async def slash_givexp(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return
        leveled_up, new_level = _add_xp(interaction.guild.id, member.id, amount)
        msg = f"✅ Gave **{amount} XP** to {member.mention}."
        if leveled_up:
            msg += f" They leveled up to **Level {new_level}**! 🎉"
        await interaction.response.send_message(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
