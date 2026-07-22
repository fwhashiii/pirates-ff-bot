"""
🎮 Player Cog — Real Free Fire stats via HL Gaming Official API
/stats  /rank  /lfg  /profile  /ffuid  /guild
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import aiohttp
import os
import logging

log = logging.getLogger("cog.player")

# ── HL Gaming Official API ────────────────────────────────
FF_API_BASE   = "https://proapis.hlgamingofficial.com/main/games/freefire/account/api"
FF_STATS_BASE = "https://proapis.hlgamingofficial.com/main/games/freefire/stats/api"
FF_API_KEY    = os.getenv("FF_API_KEY", "")
FF_USER_UID   = os.getenv("FF_USER_UID", "")   # Your developer UID from HL Gaming

# Supported regions
REGIONS = ["ind", "sg", "br", "us", "id", "tw", "th", "vn", "me", "pk", "ru", "eu", "na", "sa"]

# Rank point → rank name mapping (BR)
def br_rank_name(points: int) -> str:
    if points >= 6000: return "Heroic"
    if points >= 4800: return "Grandmaster"
    if points >= 3600: return "Master"
    if points >= 2400: return "Diamond"
    if points >= 1200: return "Platinum"
    if points >= 600:  return "Gold"
    if points >= 300:  return "Silver"
    return "Bronze"

RANK_COLORS = {
    "Bronze":      0xCD7F32,
    "Silver":      0xBDC3C7,
    "Gold":        0xF1C40F,
    "Platinum":    0x95A5A6,
    "Diamond":     0x00BFFF,
    "Master":      0xFFD700,
    "Grandmaster": 0xFF6B35,
    "Heroic":      0xE91E63,
}

RANK_IMAGES = {
    "Bronze":      "https://static.wikia.nocookie.net/freefire/images/5/5b/Bronze.png",
    "Silver":      "https://static.wikia.nocookie.net/freefire/images/4/4e/Silver.png",
    "Gold":        "https://static.wikia.nocookie.net/freefire/images/8/8e/Gold.png",
    "Platinum":    "https://static.wikia.nocookie.net/freefire/images/b/b5/Platinum.png",
    "Diamond":     "https://static.wikia.nocookie.net/freefire/images/3/3e/Diamond.png",
    "Master":      "https://static.wikia.nocookie.net/freefire/images/6/6e/Master.png",
    "Grandmaster": "https://static.wikia.nocookie.net/freefire/images/9/9e/Grandmaster.png",
    "Heroic":      "https://static.wikia.nocookie.net/freefire/images/2/2e/Heroic.png",
}

RANK_ROLE_MAP = {
    "Bronze":       "🌱 Bronze",
    "Silver":       "🔰 Silver",
    "Gold":         "🥉 Gold",
    "Platinum":     "🥈 Platinum",
    "Diamond":      "💠 Diamond",
    "Master":       "🥇 Master",
    "Grandmaster":  "🏆 Grandmaster",
    "Heroic":       "💎 Heroic",
}


async def fetch_ff_player(uid: str, region: str) -> dict | None:
    """Fetch full player data from HL Gaming API."""
    if not FF_API_KEY or not FF_USER_UID:
        return None
    params = {
        "sectionName": "AllData",
        "PlayerUid":   uid,
        "region":      region.lower(),
        "useruid":     FF_USER_UID,
        "api":         FF_API_KEY,
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
    """Fetch player game stats (solo/duo/squad) from HL Gaming API."""
    if not FF_API_KEY or not FF_USER_UID:
        return None
    params = {
        "sectionName": "playerStats",
        "PlayerUid":   uid,
        "region":      region.lower(),
        "useruid":     FF_USER_UID,
        "api":         FF_API_KEY,
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


class PlayerCog(commands.Cog, name="Player"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /stats ────────────────────────────────────────────
    @app_commands.command(name="stats", description="Look up real Free Fire stats by UID 📊")
    @app_commands.describe(
        uid="Free Fire player UID",
        region="Player region (ind, sg, br, us, pk, id, etc.)"
    )
    async def slash_stats(self, interaction: discord.Interaction, uid: str, region: str = "sg"):
        await interaction.response.defer()

        if not FF_API_KEY:
            await interaction.followup.send(
                "⚠️ FF_API_KEY not configured. Add it to `.env` — get a free key at https://www.hlgamingofficial.com/p/api.html",
                ephemeral=True,
            )
            return

        data = await fetch_ff_player(uid, region)
        if not data or "result" not in data:
            await interaction.followup.send("❌ Player not found. Check the UID and region.", ephemeral=True)
            return

        result  = data["result"]
        info    = result.get("AccountInfo", {})
        social  = result.get("socialinfo", {})
        guild   = result.get("GuildInfo", {})

        name        = info.get("AccountName", "Unknown")
        level       = info.get("AccountLevel", "?")
        likes       = fmt_num(info.get("AccountLikes", 0))
        br_points   = info.get("BrRankPoint", 0)
        cs_points   = info.get("CsRankPoint", 0)
        br_max      = info.get("BrMaxRank", 0)
        br_rank     = br_rank_name(br_points)
        cs_rank     = br_rank_name(cs_points)
        region_code = info.get("AccountRegion", region).upper()
        version     = info.get("ReleaseVersion", "?")
        language    = social.get("AccountLanguage", "?").replace("Language_", "")
        pref_mode   = social.get("AccountPreferMode", "?").replace("Prefermode_", "").upper()
        signature   = social.get("AccountSignature", "")
        guild_name  = guild.get("GuildName", "No Guild")
        guild_level = guild.get("GuildLevel", "?")
        guild_members = guild.get("GuildMember", "?")

        color = RANK_COLORS.get(br_rank, 0xFF4500)

        embed = discord.Embed(
            title=f"📊 {name}",
            description=f"*{signature}*" if signature else "",
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=RANK_IMAGES.get(br_rank, "https://i.imgur.com/8QfKFqA.png"))
        embed.add_field(name="🌍 Region",        value=region_code,                    inline=True)
        embed.add_field(name="⭐ Level",          value=str(level),                     inline=True)
        embed.add_field(name="❤️ Likes",          value=likes,                          inline=True)
        embed.add_field(name="🏅 BR Rank",        value=f"{br_rank} ({fmt_num(br_points)} pts)", inline=True)
        embed.add_field(name="⚔️ CS Rank",        value=f"{cs_rank} ({fmt_num(cs_points)} pts)", inline=True)
        embed.add_field(name="🏆 Peak BR Rank",   value=br_rank_name(br_max),           inline=True)
        embed.add_field(name="🎮 Preferred Mode", value=pref_mode,                      inline=True)
        embed.add_field(name="🌐 Language",       value=language,                       inline=True)
        embed.add_field(name="📦 Version",        value=version,                        inline=True)
        if guild_name != "No Guild":
            embed.add_field(
                name="🏰 Guild",
                value=f"{guild_name} (Lvl {guild_level} • {guild_members} members)",
                inline=False,
            )
        embed.set_footer(text=f"UID: {uid} • Data via HL Gaming Official API")
        await interaction.followup.send(embed=embed)

        # Also try to fetch game stats
        stats_data = await fetch_ff_stats(uid, region)
        if stats_data and "result" in stats_data:
            ps = stats_data["result"].get("playerStats", {})
            squad = ps.get("quadstats", {})
            duo   = ps.get("duostats", {})
            solo  = ps.get("solostats", {})

            def stat_line(mode_data: dict) -> str:
                if not mode_data:
                    return "No data"
                g = mode_data.get("gamesplayed", 0)
                w = mode_data.get("wins", 0)
                k = mode_data.get("kills", 0)
                wr = round((w / g * 100), 1) if g else 0
                kd = round(k / max((g - w), 1), 2)
                return f"Games: {fmt_num(g)} | Wins: {fmt_num(w)} ({wr}%) | Kills: {fmt_num(k)} | K/D: {kd}"

            stats_embed = discord.Embed(
                title=f"🎮 {name} — Game Stats",
                color=color,
                timestamp=datetime.utcnow(),
            )
            stats_embed.add_field(name="👤 Solo",  value=stat_line(solo),  inline=False)
            stats_embed.add_field(name="👥 Duo",   value=stat_line(duo),   inline=False)
            stats_embed.add_field(name="👨‍👩‍👧‍👦 Squad", value=stat_line(squad), inline=False)

            if squad:
                d = squad.get("detailedstats", {})
                hs    = d.get("headshotkills", 0)
                total = squad.get("kills", 1)
                hs_pct = round((hs / total * 100), 1) if total else 0
                stats_embed.add_field(name="🎯 Headshot %", value=f"{hs_pct}%",                             inline=True)
                stats_embed.add_field(name="💥 Most Kills", value=fmt_num(d.get("highestkills", 0)),         inline=True)
                stats_embed.add_field(name="🤝 Revives",    value=fmt_num(d.get("revives", 0)),              inline=True)

            stats_embed.set_footer(text=f"UID: {uid} • Data via HL Gaming Official API")
            await interaction.followup.send(embed=stats_embed)

    # ── /ffuid — look up player by UID only ───────────────
    @app_commands.command(name="ffuid", description="Quick lookup of a Free Fire player by UID 🔎")
    @app_commands.describe(uid="Free Fire UID", region="Region code (default: sg)")
    async def slash_ffuid(self, interaction: discord.Interaction, uid: str, region: str = "sg"):
        await interaction.response.defer()
        if not FF_API_KEY:
            await interaction.followup.send("⚠️ FF_API_KEY not set in .env", ephemeral=True)
            return

        data = await fetch_ff_player(uid, region)
        if not data or "result" not in data:
            await interaction.followup.send("❌ Player not found.", ephemeral=True)
            return

        info  = data["result"].get("AccountInfo", {})
        guild = data["result"].get("GuildInfo", {})
        name  = info.get("AccountName", "Unknown")
        level = info.get("AccountLevel", "?")
        br_r  = br_rank_name(info.get("BrRankPoint", 0))
        likes = fmt_num(info.get("AccountLikes", 0))

        embed = discord.Embed(
            title=f"🔎 {name}",
            color=RANK_COLORS.get(br_r, 0xFF4500),
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=RANK_IMAGES.get(br_r, ""))
        embed.add_field(name="🆔 UID",    value=uid,                                      inline=True)
        embed.add_field(name="⭐ Level",  value=str(level),                               inline=True)
        embed.add_field(name="🏅 Rank",   value=br_r,                                     inline=True)
        embed.add_field(name="❤️ Likes",  value=likes,                                    inline=True)
        embed.add_field(name="🌍 Region", value=info.get("AccountRegion", region).upper(), inline=True)
        if guild.get("GuildName"):
            embed.add_field(name="🏰 Guild", value=guild["GuildName"], inline=True)
        embed.set_footer(text="Data via HL Gaming Official API")
        await interaction.followup.send(embed=embed)

    # ── /rank ─────────────────────────────────────────────
    @app_commands.command(name="rank", description="Set your Free Fire rank role 🏅")
    @app_commands.describe(rank="Your current rank in Free Fire")
    @app_commands.choices(rank=[
        app_commands.Choice(name="🌱 Bronze",      value="Bronze"),
        app_commands.Choice(name="🔰 Silver",      value="Silver"),
        app_commands.Choice(name="🥉 Gold",        value="Gold"),
        app_commands.Choice(name="🥈 Platinum",    value="Platinum"),
        app_commands.Choice(name="💠 Diamond",     value="Diamond"),
        app_commands.Choice(name="🥇 Master",      value="Master"),
        app_commands.Choice(name="🏆 Grandmaster", value="Grandmaster"),
        app_commands.Choice(name="💎 Heroic",      value="Heroic"),
    ])
    async def slash_rank(self, interaction: discord.Interaction, rank: str):
        guild  = interaction.guild
        member = interaction.user

        rank_role_names = list(RANK_ROLE_MAP.values())
        roles_to_remove = [r for r in member.roles if r.name in rank_role_names]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Rank update")

        target_role_name = RANK_ROLE_MAP.get(rank)
        target_role = discord.utils.get(guild.roles, name=target_role_name)

        if target_role:
            await member.add_roles(target_role, reason="Rank self-assign")
            embed = discord.Embed(
                title="🏅 Rank Updated!",
                description=f"{member.mention} is now ranked **{rank}**!",
                color=RANK_COLORS.get(rank, 0xFFD700),
            )
            embed.set_thumbnail(url=RANK_IMAGES.get(rank, ""))
            embed.set_footer(text="Keep grinding! 🔥")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                f"⚠️ Role `{target_role_name}` not found. Ask an admin to create it.",
                ephemeral=True,
            )

    # ── /lfg ──────────────────────────────────────────────
    @app_commands.command(name="lfg", description="Looking for group — find squadmates 🔍")
    @app_commands.describe(
        mode="Game mode",
        rank="Your rank",
        slots="Players needed (1–3)",
        note="Extra info (mic, region, etc.)"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Battle Royale",  value="Battle Royale"),
        app_commands.Choice(name="Clash Squad",    value="Clash Squad"),
        app_commands.Choice(name="Ranked BR",      value="Ranked BR"),
        app_commands.Choice(name="Ranked CS",      value="Ranked CS"),
        app_commands.Choice(name="Custom Room",    value="Custom Room"),
    ])
    async def slash_lfg(
        self,
        interaction: discord.Interaction,
        mode: str,
        rank: str = "Any",
        slots: int = 3,
        note: str = "",
    ):
        slots = max(1, min(slots, 3))
        embed = discord.Embed(title="🔍 Looking for Group!", color=0x00FF7F, timestamp=datetime.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🎮 Mode",  value=mode,         inline=True)
        embed.add_field(name="🏅 Rank",  value=rank,         inline=True)
        embed.add_field(name="👥 Slots", value=f"{slots}/3", inline=True)
        if note:
            embed.add_field(name="📝 Note", value=note, inline=False)
        embed.set_footer(text="React ✅ to join • DM the player above")
        await interaction.response.send_message(embed=embed)
        sent = await interaction.original_response()
        await sent.add_reaction("✅")

    # ── /profile ──────────────────────────────────────────
    @app_commands.command(name="profile", description="View a member's server profile 👤")
    @app_commands.describe(member="The member to view (leave blank for yourself)")
    async def slash_profile(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        roles  = [r.mention for r in target.roles if r.name != "@everyone"]

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            color=target.color if target.color.value else 0xFF4500,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="📛 Username", value=str(target),                                            inline=True)
        embed.add_field(name="🆔 ID",       value=str(target.id),                                         inline=True)
        embed.add_field(name="📅 Joined",   value=target.joined_at.strftime("%b %d, %Y") if target.joined_at else "?", inline=True)
        embed.add_field(name="🎂 Account",  value=target.created_at.strftime("%b %d, %Y"),                inline=True)
        embed.add_field(name="🎭 Roles",    value=" ".join(roles[-5:]) if roles else "None",               inline=False)
        embed.set_footer(text="PIRATES Free Fire Server")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))
