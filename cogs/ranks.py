"""
🏅 Ranks Cog — Auto-assign Bronze on join, auto-upgrade based on time in server
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
import logging

log = logging.getLogger("cog.ranks")

# ── Rank progression by hours in server ──────────────────
# (hours_required, role_name, color)
RANK_LADDER = [
    (0,    "🌱 Bronze",      0xCD7F32),
    (12,   "🔰 Silver",      0xBDC3C7),
    (24,   "🥉 Gold",        0xF1C40F),
    (72,   "🥈 Platinum",    0x95A5A6),
    (168,  "💠 Diamond",     0x00BFFF),   # 7 days
    (336,  "🥇 Master",      0xFFD700),   # 14 days
    (720,  "🏆 Grandmaster", 0xFF6B35),   # 30 days
    (1440, "💎 Heroic",      0xE91E63),   # 60 days
]

RANK_NAMES = [r[1] for r in RANK_LADDER]


def get_earned_rank(joined_at: datetime) -> tuple[str, int]:
    """Return the highest rank a member has earned based on join date."""
    now = datetime.now(timezone.utc)
    hours = (now - joined_at).total_seconds() / 3600
    earned = RANK_LADDER[0]
    for hours_req, name, color in RANK_LADDER:
        if hours >= hours_req:
            earned = (hours_req, name, color)
    return earned[1], earned[2]


class RanksCog(commands.Cog, name="Ranks"):
    """Auto rank assignment and progression based on server time."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rank_check_task.start()

    def cog_unload(self):
        self.rank_check_task.cancel()

    # ── Give Bronze on join ───────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.assign_rank(member, announce=False)

    # ── Check all members every 30 minutes ───────────────
    @tasks.loop(minutes=30)
    async def rank_check_task(self):
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                if member.joined_at is None:
                    continue
                await self.assign_rank(member, announce=True)

    @rank_check_task.before_loop
    async def before_rank_check(self):
        await self.bot.wait_until_ready()

    # ── Core rank assignment logic ────────────────────────
    async def assign_rank(self, member: discord.Member, announce: bool = True):
        """Assign the correct rank role. If upgraded, post in general chat."""
        guild = member.guild
        if member.joined_at is None:
            return

        earned_name, earned_color = get_earned_rank(member.joined_at)

        # Find what rank they currently hold
        current_rank = None
        for role in member.roles:
            if role.name in RANK_NAMES:
                current_rank = role.name
                break

        # Already on the right rank — nothing to do
        if current_rank == earned_name:
            return

        # Remove all existing rank roles
        roles_to_remove = [r for r in member.roles if r.name in RANK_NAMES]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason="Rank progression")
            except discord.Forbidden:
                return

        # Add new rank role
        new_role = discord.utils.get(guild.roles, name=earned_name)
        if not new_role:
            log.warning(f"Rank role '{earned_name}' not found in {guild.name}")
            return

        try:
            await member.add_roles(new_role, reason="Rank progression")
        except discord.Forbidden:
            return

        # Announce upgrade if they had a previous rank (not first join)
        if announce and current_rank is not None:
            await self.announce_rank_up(member, current_rank, earned_name, earned_color)

    # ── Rank-up announcement ──────────────────────────────
    async def announce_rank_up(
        self,
        member: discord.Member,
        old_rank: str,
        new_rank: str,
        color: int,
    ):
        guild = member.guild
        # Post in general-chat
        channel = discord.utils.get(guild.text_channels, name="💬│general-chat")
        if not channel:
            channel = discord.utils.get(guild.text_channels, name="👋│welcome")
        if not channel:
            return

        hours = round((datetime.now(timezone.utc) - member.joined_at).total_seconds() / 3600, 1)

        embed = discord.Embed(
            title="🎉 Rank Up!",
            description=(
                f"{member.mention} has been promoted!\n\n"
                f"**{old_rank}** → **{new_rank}**\n\n"
                f"⏱️ {hours} hours in the server\n"
                f"Keep grinding! 🔥"
            ),
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Free Fire Squad • Rank Progression")
        await channel.send(embed=embed)

    # ── /myrank ───────────────────────────────────────────
    @app_commands.command(name="myrank", description="Check your current rank and progress 🏅")
    async def slash_myrank(self, interaction: discord.Interaction):
        member = interaction.user
        if member.joined_at is None:
            await interaction.response.send_message("⚠️ Can't determine your join date.", ephemeral=True)
            return

        hours = round((datetime.now(timezone.utc) - member.joined_at).total_seconds() / 3600, 1)
        earned_name, earned_color = get_earned_rank(member.joined_at)

        # Find next rank
        next_rank = None
        hours_until_next = None
        for hours_req, name, color in RANK_LADDER:
            if hours_req > hours:
                next_rank = name
                hours_until_next = round(hours_req - hours, 1)
                break

        embed = discord.Embed(
            title=f"🏅 {member.display_name}'s Rank",
            color=earned_color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🏅 Current Rank",    value=earned_name,   inline=True)
        embed.add_field(name="⏱️ Hours in Server", value=f"{hours}h",   inline=True)

        if next_rank:
            embed.add_field(
                name="⬆️ Next Rank",
                value=f"{next_rank}\nin **{hours_until_next}** more hours",
                inline=False,
            )
        else:
            embed.add_field(name="👑 Status", value="Max rank achieved! BOOYAH! 🏆", inline=False)

        # Progress bar
        current_idx = next((i for i, (_, n, _) in enumerate(RANK_LADDER) if n == earned_name), 0)
        if current_idx < len(RANK_LADDER) - 1:
            current_hrs_req = RANK_LADDER[current_idx][0]
            next_hrs_req    = RANK_LADDER[current_idx + 1][0]
            progress = (hours - current_hrs_req) / (next_hrs_req - current_hrs_req)
            filled = int(progress * 10)
            bar = "█" * filled + "░" * (10 - filled)
            embed.add_field(name="📊 Progress", value=f"`[{bar}]` {int(progress*100)}%", inline=False)

        embed.set_footer(text="Ranks auto-upgrade based on time in server")
        await interaction.response.send_message(embed=embed)

    # ── /rankinfo ─────────────────────────────────────────
    @app_commands.command(name="rankinfo", description="See all rank requirements 📋")
    async def slash_rankinfo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏅 Free Fire Squad — Rank Requirements",
            description="Ranks are automatically assigned based on how long you've been in the server.",
            color=0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        for hours_req, name, color in RANK_LADDER:
            if hours_req == 0:
                embed.add_field(name=name, value="On join",          inline=True)
            elif hours_req < 24:
                embed.add_field(name=name, value=f"{hours_req}h",    inline=True)
            else:
                days = hours_req // 24
                embed.add_field(name=name, value=f"{days} day{'s' if days > 1 else ''}", inline=True)
        embed.set_footer(text="Use /myrank to check your progress")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RanksCog(bot))
