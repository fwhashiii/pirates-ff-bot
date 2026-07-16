"""
📊 Server Stats Dashboard Cog
Auto-updating channels showing live server stats
Commands: /setupstats /serverstats
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
import logging
import os

log = logging.getLogger("cog.stats")

OWNER_ID = 815646767311224953


class StatsDashboardCog(commands.Cog, name="Stats"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._stat_channels: dict[int, dict] = {}  # {guild_id: {members, online, bots}}
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    @tasks.loop(minutes=10)
    async def update_stats(self):
        """Update stat channels every 10 minutes."""
        for guild in self.bot.guilds:
            await self._update_guild_stats(guild)

    async def _update_guild_stats(self, guild: discord.Guild):
        """Update stat voice channels for a guild."""
        total = guild.member_count
        online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots

        # Look for stat channels by name pattern
        for vc in guild.voice_channels:
            name = vc.name.lower()
            try:
                if "members:" in name or "👥" in name:
                    await vc.edit(name=f"👥 Members: {humans}")
                elif "online:" in name or "🟢" in name:
                    await vc.edit(name=f"🟢 Online: {online}")
                elif "bots:" in name or "🤖" in name:
                    await vc.edit(name=f"🤖 Bots: {bots}")
            except discord.Forbidden:
                pass
            except Exception as e:
                log.error(f"Stat channel update error: {e}")

    # ── /setupstats ───────────────────────────────────────
    @app_commands.command(name="setupstats", description="Create live stat channels 📊")
    async def slash_setupstats(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("🚫 Need Manage Channels permission.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        guild = interaction.guild

        # Create or find stats category
        cat = discord.utils.get(guild.categories, name="📊 SERVER STATS")
        if not cat:
            cat = await guild.create_category(
                "📊 SERVER STATS",
                overwrites={guild.default_role: discord.PermissionOverwrite(connect=False)},
            )

        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots
        online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)

        created = []
        for name in [f"👥 Members: {humans}", f"🟢 Online: {online}", f"🤖 Bots: {bots}"]:
            existing = discord.utils.get(cat.voice_channels, name=name.split(":")[0] + ":")
            if not existing:
                vc = await guild.create_voice_channel(
                    name,
                    category=cat,
                    overwrites={guild.default_role: discord.PermissionOverwrite(connect=False)},
                )
                created.append(vc.name)

        await interaction.followup.send(
            f"✅ Stats dashboard created in **{cat.name}**!\nChannels update every 10 minutes."
        )

    # ── /serverstats ──────────────────────────────────────
    @app_commands.command(name="serverstats", description="Show detailed server statistics 📈")
    async def slash_serverstats(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        bots = sum(1 for m in guild.members if m.bot)
        humans = total - bots
        online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
        in_vc = sum(len(vc.members) for vc in guild.voice_channels)
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        roles = len(guild.roles)
        boosts = guild.premium_subscription_count
        boost_level = guild.premium_tier

        embed = discord.Embed(
            title=f"📊 {guild.name} — Server Stats",
            color=0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="👥 Total Members", value=str(total), inline=True)
        embed.add_field(name="👤 Humans", value=str(humans), inline=True)
        embed.add_field(name="🤖 Bots", value=str(bots), inline=True)
        embed.add_field(name="🟢 Online", value=str(online), inline=True)
        embed.add_field(name="🎙️ In Voice", value=str(in_vc), inline=True)
        embed.add_field(name="💬 Text Channels", value=str(text_channels), inline=True)
        embed.add_field(name="🔊 Voice Channels", value=str(voice_channels), inline=True)
        embed.add_field(name="🎭 Roles", value=str(roles), inline=True)
        embed.add_field(name="🚀 Boosts", value=f"{boosts} (Level {boost_level})", inline=True)
        embed.add_field(name="📅 Created", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.set_footer(text="PIRATES Server Stats")
        await interaction.response.send_message(embed=embed)

    # ── /userinfo ─────────────────────────────────────────
    @app_commands.command(name="userinfo", description="Show info about a member 👤")
    @app_commands.describe(member="Member to look up")
    async def slash_userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        roles = [r.mention for r in reversed(target.roles) if r.name != "@everyone"]

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            color=target.color if target.color.value else 0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🆔 User ID", value=str(target.id), inline=True)
        embed.add_field(name="📛 Username", value=str(target), inline=True)
        embed.add_field(name="🤖 Bot", value="Yes" if target.bot else "No", inline=True)
        embed.add_field(name="📅 Account Created", value=f"<t:{int(target.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="📥 Joined Server", value=f"<t:{int(target.joined_at.timestamp())}:D>" if target.joined_at else "Unknown", inline=True)
        embed.add_field(name="🎮 Status", value=str(target.status).title(), inline=True)
        if roles:
            embed.add_field(name=f"🎭 Roles ({len(roles)})", value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else ""), inline=False)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsDashboardCog(bot))
