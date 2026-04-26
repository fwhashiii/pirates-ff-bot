"""
🎮 Player Cog — Stats, LFG, rank roles, and player profiles
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import random


# Simulated rank data (replace with real API if available)
FF_RANKS = ["Bronze", "Silver", "Gold", "Platinum", "Diamond",
            "Master", "Grandmaster", "Heroic"]

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

# Official Free Fire rank badge images
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


class PlayerCog(commands.Cog, name="Player"):
    """Player stats, rank roles, and squad finder."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /stats ────────────────────────────────────────────
    @app_commands.command(name="stats", description="Show your Free Fire stats card 📊")
    @app_commands.describe(
        username="Your Free Fire in-game name",
        region="Your region (e.g. NA, SEA, SA, IND)"
    )
    async def slash_stats(
        self,
        interaction: discord.Interaction,
        username: str,
        region: str = "SEA",
    ):
        await interaction.response.defer()

        # Simulated stats — swap with a real FF stats API if you have one
        kd     = round(random.uniform(1.0, 8.5), 2)
        wins   = random.randint(50, 3000)
        games  = wins + random.randint(200, 5000)
        wr     = round((wins / games) * 100, 1)
        kills  = random.randint(500, 25000)
        rank   = random.choice(FF_RANKS)
        level  = random.randint(40, 80)
        cs_rank = random.choice(FF_RANKS)

        embed = discord.Embed(
            title=f"📊 {username} — Free Fire Stats",
            color=RANK_COLORS.get(rank, 0xFF4500),
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=RANK_IMAGES.get(rank, "https://i.imgur.com/8QfKFqA.png"))
        embed.add_field(name="🌍 Region",      value=region.upper(), inline=True)
        embed.add_field(name="⭐ Level",        value=str(level),     inline=True)
        embed.add_field(name="🏅 BR Rank",      value=rank,           inline=True)
        embed.add_field(name="🎯 Clash Squad",  value=cs_rank,        inline=True)
        embed.add_field(name="💀 K/D Ratio",    value=str(kd),        inline=True)
        embed.add_field(name="🏆 Win Rate",     value=f"{wr}%",       inline=True)
        embed.add_field(name="🔫 Total Kills",  value=f"{kills:,}",   inline=True)
        embed.add_field(name="🎮 Games Played", value=f"{games:,}",   inline=True)
        embed.add_field(name="🥇 Total Wins",   value=f"{wins:,}",    inline=True)
        embed.set_footer(
            text="⚠️ Stats are simulated — connect a real API for live data",
            icon_url=interaction.user.display_avatar.url,
        )
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
        guild = interaction.guild
        member = interaction.user

        # Remove existing rank roles
        rank_role_names = list(RANK_ROLE_MAP.values())
        roles_to_remove = [r for r in member.roles if r.name in rank_role_names]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Rank update")

        # Add new rank role
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
                f"⚠️ Role `{target_role_name}` not found. Run the setup script first.",
                ephemeral=True,
            )

    # ── /lfg ──────────────────────────────────────────────
    @app_commands.command(name="lfg", description="Looking for group — find squadmates 🔍")
    @app_commands.describe(
        mode="Game mode you want to play",
        rank="Your rank",
        slots="How many players you need (1–3)",
        note="Any extra info (mic required, region, etc.)"
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
        embed = discord.Embed(
            title="🔍 Looking for Group!",
            color=0x00FF7F,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(name="🎮 Mode",    value=mode,         inline=True)
        embed.add_field(name="🏅 Rank",    value=rank,         inline=True)
        embed.add_field(name="👥 Slots",   value=f"{slots}/3", inline=True)
        if note:
            embed.add_field(name="📝 Note", value=note, inline=False)
        embed.set_footer(text="React ✅ to join • DM the player above")
        msg = await interaction.response.send_message(embed=embed)
        # Add join reaction
        sent = await interaction.original_response()
        await sent.add_reaction("✅")

    # ── /profile ──────────────────────────────────────────
    @app_commands.command(name="profile", description="View a member's server profile 👤")
    @app_commands.describe(member="The member to view (leave blank for yourself)")
    async def slash_profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None,
    ):
        target = member or interaction.user
        roles = [r.mention for r in target.roles if r.name != "@everyone"]

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            color=target.color if target.color.value else 0xFF4500,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="📛 Username",   value=str(target),                          inline=True)
        embed.add_field(name="🆔 ID",         value=str(target.id),                       inline=True)
        embed.add_field(name="📅 Joined",     value=target.joined_at.strftime("%b %d, %Y") if target.joined_at else "Unknown", inline=True)
        embed.add_field(name="🎂 Account",    value=target.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name="🎭 Roles",      value=" ".join(roles[-5:]) if roles else "None", inline=False)
        embed.set_footer(text="Free Fire Squad Server")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))
