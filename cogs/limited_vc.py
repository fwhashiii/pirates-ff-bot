"""
🎮 Limited VC Cog — Sets user limits on existing voice channels
Matches by name (case-insensitive, ignores emojis) on startup.
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger("cog.limited_vc")

# Partial name match (case-insensitive) → user limit
# Order matters — assigned 2, 4, 6, 8
VC_LIMITS = [
    ("squad lobby",  2),
    ("game room 1",  4),
    ("game room 2",  6),
    ("ranked grind", 8),
]


def _match(channel_name: str, keyword: str) -> bool:
    return keyword.lower() in channel_name.lower()


class LimitedVCCog(commands.Cog, name="LimitedVC"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._apply_limits(guild)

    async def _apply_limits(self, guild: discord.Guild):
        for keyword, limit in VC_LIMITS:
            channel = next(
                (ch for ch in guild.voice_channels if _match(ch.name, keyword)), None
            )
            if channel:
                if channel.user_limit != limit:
                    await channel.edit(user_limit=limit, reason="Auto limit applied by bot")
                log.info(f"'{channel.name}' → limit {limit} ✅")
            else:
                log.warning(f"No VC matching '{keyword}' found in {guild.name}")

    # ── /setlimit — change a VC's user limit on the fly ──
    @app_commands.command(name="setlimit", description="Change the user limit on a voice channel 🔢")
    @app_commands.describe(channel="The voice channel to update", limit="Max users (0 = unlimited, max 99)")
    @app_commands.default_permissions(manage_channels=True)
    async def slash_setlimit(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        limit: int,
    ):
        if limit < 0 or limit > 99:
            await interaction.response.send_message(
                "⚠️ Limit must be between 0 (unlimited) and 99.", ephemeral=True
            )
            return
        await channel.edit(user_limit=limit)
        label = f"**{limit}**" if limit > 0 else "**unlimited**"
        await interaction.response.send_message(
            f"✅ {channel.mention} user limit set to {label}.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LimitedVCCog(bot))
