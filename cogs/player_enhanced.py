"""
🎮 Player Cog — Enhanced Free Fire stats
New: /compare /guild /detailed /topplayers
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import aiohttp
import os
import logging

log = logging.getLogger("cog.player_enhanced")

FF_API_BASE   = "https://proapis.hlgamingofficial.com/main/games/freefire/account/api"
FF_STATS_BASE = "https://proapis.hlgamingofficial.com/main/games/freefire/stats/api"
FF_API_KEY    = os.getenv("FF_API_KEY", "")
FF_USER_UID   = os.getenv("FF_USER_UID", "")

def br_rank_name(points: int) -> str:
    if points >= 6000: return "Heroic"
    if points >= 4800: return "Grandmaster"
    if points >= 3600: return "Master"
    if points >= 2400: return "Diamond"
    if points >= 1200: return "Platinum"
    if points >= 600:  return "Gold"
    if points >= 300:  return "Silver"
    return "Bronze"

def rank_progress_bar(points: int) -> str:
    """Generate a progress bar showing progress to next rank."""
    thresholds = [0, 300, 600, 1200, 2400, 3600, 4800, 6000, 10000]
    rank_names = ["Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master", "Grandmaster", "Heroic", "Heroic"]
    
    for i, threshold in enumerate(thresholds):
        if points < thresholds[i + 1]:
            current_rank = rank_names[i]
            next_rank = rank_names[i + 1]
            progress = points - threshold
            needed = thresholds[i + 1] - threshold
            pct = min(100, int((progress / needed) * 100))
            filled = "█" * (pct // 10)
            empty = "░" * (10 - pct // 10)
            return f"`{filled}{empty}` {pct}% to {next_rank}"
    return "`██████████` MAX"

RANK_COLORS = {
    "Bronze": 0xCD7F32, "Silver": 0xBDC3C7, "Gold": 0xF1C40F,
    "Platinum": 0x95A5A6, "Diamond": 0x00BFFF, "Master": 0xFFD700,
    "Grandmaster": 0xFF6B35, "Heroic": 0xE91E63,
}

async def fetch_ff_player(uid: str, region: str) -> dict | None:
    if not FF_API_KEY or not FF_USER_UID:
        return None
    params = {
        "sectionName": "AllData",
        "PlayerUid": uid,
        "region": region.lower(),
        "useruid": FF_USER_UID,
        "api": FF_API_KEY,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FF_API_BASE, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        log.error(f"FF API error: {e}")
    return None

async def fetch_ff_stats(uid: str, region: str) -> dict | None:
    if not FF_API_KEY or not FF_USER_UID:
        return None
    params = {
        "sectionName": "playerStats",
        "PlayerUid": uid,
        "region": region.lower(),
        "useruid": FF_USER_UID,
        "api": FF_API_KEY,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FF_STATS_BASE, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        log.error(f"FF Stats API error: {e}")
    return None

def fmt_num(n) -> str:
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)

def days_since(timestamp: int) -> str:
    """Convert unix timestamp to readable time ago."""
    try:
        if not timestamp or timestamp == 0:
            return "Unknown"
        dt = datetime.fromtimestamp(timestamp)
        delta = datetime.now() - dt
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            return "Recently"
    except Exception:
        return "Unknown"


class PlayerEnhancedCog(commands.Cog, name="PlayerEnhanced"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /detailed — full detailed stats ──────────────────
    @app_commands.command(name="detailed", description="Detailed Free Fire account breakdown 📊")
    @app_commands.describe(uid="Free Fire UID", region="Region")
    async def slash_detailed(self, interaction: discord.Interaction, uid: str, region: str = "sg"):
        await interaction.response.defer()
        if not FF_API_KEY:
            await interaction.followup.send("⚠️ API not configured", ephemeral=True)
            return

        data = await fetch_ff_player(uid, region)
        if not data or "result" not in data:
            await interaction.followup.send("❌ Player not found", ephemeral=True)
            return

        result = data["result"]
        info = result.get("AccountInfo", {})
        credit = result.get("creditScoreInfo", {})
        pet = result.get("petInfo", {})
        guild = result.get("GuildInfo", {})

        name = info.get("AccountName", "Unknown")
        br_points = info.get("BrRankPoint", 0)
        br_rank = br_rank_name(br_points)
        created = info.get("AccountCreateTime", 0)
        last_login = info.get("AccountLastLogin", 0)
        credit_score = credit.get("creditScore", 0)
        pet_level = pet.get("level", 0)
        pet_id = pet.get("id", 0)

        embed = discord.Embed(
            title=f"📊 {name} — Detailed Stats",
            color=RANK_COLORS.get(br_rank, 0xFF4500),
            timestamp=datetime.utcnow(),
        )

        # Account Info
        embed.add_field(name="🆔 UID", value=uid, inline=True)
        embed.add_field(name="⭐ Level", value=str(info.get("AccountLevel", "?")), inline=True)
        embed.add_field(name="🌍 Region", value=info.get("AccountRegion", region).upper(), inline=True)
        
        # Rank Progress
        embed.add_field(name="🏅 BR Rank", value=f"{br_rank} ({fmt_num(br_points)} pts)", inline=False)
        embed.add_field(name="📈 Progress", value=rank_progress_bar(br_points), inline=False)

        # Credit & Pet
        credit_color = "🟢" if credit_score >= 90 else "🟡" if credit_score >= 70 else "🔴"
        embed.add_field(name=f"{credit_color} Credit Score", value=str(credit_score), inline=True)
        if pet_level:
            embed.add_field(name="🐾 Pet", value=f"Level {pet_level}", inline=True)

        # Account Age & Last Seen
        if created and created > 0:
            account_age = days_since(created)
            embed.add_field(name="📅 Account Age", value=account_age, inline=True)
        
        if last_login and last_login > 0:
            last_seen = days_since(last_login)
            embed.add_field(name="🕐 Last Seen", value=last_seen, inline=True)

        # Guild
        if guild.get("GuildName"):
            embed.add_field(
                name="🏰 Guild",
                value=f"{guild['GuildName']} (Lvl {guild.get('GuildLevel', '?')} • {guild.get('GuildMember', '?')} members)",
                inline=False,
            )

        embed.set_footer(text=f"UID: {uid}")
        await interaction.followup.send(embed=embed)

    # ── /compare — compare two players ───────────────────
    @app_commands.command(name="compare", description="Compare two Free Fire players side-by-side ⚖️")
    @app_commands.describe(
        uid1="First player UID",
        uid2="Second player UID",
        region="Region (same for both)"
    )
    async def slash_compare(self, interaction: discord.Interaction, uid1: str, uid2: str, region: str = "sg"):
        await interaction.response.defer()
        if not FF_API_KEY:
            await interaction.followup.send("⚠️ API not configured", ephemeral=True)
            return

        data1 = await fetch_ff_player(uid1, region)
        data2 = await fetch_ff_player(uid2, region)

        if not data1 or not data2:
            await interaction.followup.send("❌ One or both players not found", ephemeral=True)
            return

        info1 = data1["result"].get("AccountInfo", {})
        info2 = data2["result"].get("AccountInfo", {})

        name1 = info1.get("AccountName", "Player 1")
        name2 = info2.get("AccountName", "Player 2")
        
        lvl1 = info1.get("AccountLevel", 0)
        lvl2 = info2.get("AccountLevel", 0)
        
        br1 = info1.get("BrRankPoint", 0)
        br2 = info2.get("BrRankPoint", 0)
        
        likes1 = info1.get("AccountLikes", 0)
        likes2 = info2.get("AccountLikes", 0)

        embed = discord.Embed(
            title="⚖️ Player Comparison",
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )

        embed.add_field(name="👤 Players", value=f"{name1}\n🆚\n{name2}", inline=False)
        embed.add_field(name="⭐ Level", value=f"{lvl1}\n🆚\n{lvl2}", inline=True)
        embed.add_field(name="🏅 BR Points", value=f"{fmt_num(br1)}\n🆚\n{fmt_num(br2)}", inline=True)
        embed.add_field(name="❤️ Likes", value=f"{fmt_num(likes1)}\n🆚\n{fmt_num(likes2)}", inline=True)

        # Winner determination
        winner = None
        if br1 > br2:
            winner = f"🏆 {name1} has higher BR rank!"
        elif br2 > br1:
            winner = f"🏆 {name2} has higher BR rank!"
        else:
            winner = "🤝 Tied!"

        embed.add_field(name="Result", value=winner, inline=False)
        embed.set_footer(text=f"UIDs: {uid1} vs {uid2}")
        await interaction.followup.send(embed=embed)

    # ── /guild — lookup guild stats ───────────────────────
    @app_commands.command(name="guild", description="Look up Free Fire guild info 🏰")
    @app_commands.describe(captain_uid="Guild captain's UID", region="Region")
    async def slash_guild(self, interaction: discord.Interaction, captain_uid: str, region: str = "sg"):
        await interaction.response.defer()
        if not FF_API_KEY:
            await interaction.followup.send("⚠️ API not configured", ephemeral=True)
            return

        data = await fetch_ff_player(captain_uid, region)
        if not data or "result" not in data:
            await interaction.followup.send("❌ Player/Guild not found", ephemeral=True)
            return

        result = data["result"]
        guild = result.get("GuildInfo", {})
        captain = result.get("captainBasicInfo", {})

        if not guild.get("GuildName"):
            await interaction.followup.send("❌ Player is not in a guild", ephemeral=True)
            return

        guild_name = guild.get("GuildName", "Unknown")
        guild_level = guild.get("GuildLevel", "?")
        guild_members = guild.get("GuildMember", "?")
        guild_capacity = guild.get("GuildCapacity", "?")
        captain_name = captain.get("nickname", "Unknown")
        captain_level = captain.get("level", "?")

        embed = discord.Embed(
            title=f"🏰 {guild_name}",
            color=0xFFD700,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="⭐ Guild Level", value=str(guild_level), inline=True)
        embed.add_field(name="👥 Members", value=f"{guild_members}/{guild_capacity}", inline=True)
        embed.add_field(name="👑 Captain", value=f"{captain_name} (Lvl {captain_level})", inline=True)
        embed.set_footer(text=f"Captain UID: {captain_uid}")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerEnhancedCog(bot))
