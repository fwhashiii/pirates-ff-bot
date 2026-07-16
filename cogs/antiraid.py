"""
🛡️ Anti-Raid Protection Cog
Detects and stops raids automatically:
- Mass join detection (many accounts joining at once)
- New account detection (accounts < 7 days old)
- Mass mention detection
- Invite link spam
- Lockdown mode
Commands: /antiraid /lockdown /unlockdown /raidstatus
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import asyncio
import logging
import time

log = logging.getLogger("cog.antiraid")

OWNER_ID = 815646767311224953

# ── Config ────────────────────────────────────────────────
RAID_JOIN_THRESHOLD = 5       # joins within window = raid
RAID_JOIN_WINDOW    = 10      # seconds
MIN_ACCOUNT_AGE     = 7       # days — accounts younger than this get flagged
MASS_MENTION_LIMIT  = 5       # mentions in one message = violation
INVITE_PATTERN      = r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[a-zA-Z0-9]+"

# ── State ─────────────────────────────────────────────────
_join_tracker: dict[int, list[float]] = defaultdict(list)  # {guild_id: [timestamps]}
_raid_mode: dict[int, bool] = {}                            # {guild_id: bool}
_locked_channels: dict[int, list[int]] = defaultdict(list) # {guild_id: [channel_ids]}


class AntiRaidCog(commands.Cog, name="AntiRaid"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _notify_staff(self, guild: discord.Guild, title: str, description: str, color: int = 0xFF0000):
        """Send alert to mod-log channel and owner."""
        import os
        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        if log_ch_id:
            ch = guild.get_channel(log_ch_id)
            if ch:
                embed = discord.Embed(title=f"🛡️ {title}", description=description, color=color, timestamp=datetime.now(timezone.utc))
                embed.set_footer(text="Anti-Raid System • PIRATES")
                await ch.send(embed=embed)

        # Also DM owner
        try:
            owner = await self.bot.fetch_user(OWNER_ID)
            embed = discord.Embed(title=f"🚨 {title}", description=f"**Server:** {guild.name}\n\n{description}", color=color, timestamp=datetime.now(timezone.utc))
            await owner.send(embed=embed)
        except Exception:
            pass

    async def _enable_raid_mode(self, guild: discord.Guild, reason: str):
        """Lock all channels and enable raid mode."""
        if _raid_mode.get(guild.id):
            return  # Already in raid mode

        _raid_mode[guild.id] = True
        locked = []

        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(guild.default_role)
            if overwrite.send_messages is not False:
                try:
                    overwrite.send_messages = False
                    await channel.set_permissions(guild.default_role, overwrite=overwrite, reason=f"RAID MODE: {reason}")
                    locked.append(channel.id)
                except Exception:
                    pass

        _locked_channels[guild.id] = locked
        log.warning(f"RAID MODE ENABLED in {guild.name}: {reason}")

        await self._notify_staff(
            guild,
            "🚨 RAID MODE ACTIVATED",
            f"**Reason:** {reason}\n\n"
            f"**{len(locked)} channels locked.**\n"
            f"Use `/unlockdown` to restore access when safe.",
            color=0xFF0000,
        )

        # Post warning in all channels
        for ch_id in locked[:3]:  # Only first 3 to avoid spam
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    await ch.send(
                        embed=discord.Embed(
                            title="🚨 RAID MODE ACTIVE",
                            description="The server is under attack. All channels are temporarily locked.\nStaff are handling the situation.",
                            color=0xFF0000,
                        )
                    )
                except Exception:
                    pass

    # ── Mass join detection ───────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        now = time.time()

        # Track joins
        _join_tracker[guild.id].append(now)
        _join_tracker[guild.id] = [t for t in _join_tracker[guild.id] if now - t <= RAID_JOIN_WINDOW]

        # Check for raid
        if len(_join_tracker[guild.id]) >= RAID_JOIN_THRESHOLD:
            await self._enable_raid_mode(
                guild,
                f"{len(_join_tracker[guild.id])} accounts joined in {RAID_JOIN_WINDOW} seconds"
            )

        # Check account age
        account_age = (datetime.now(timezone.utc) - member.created_at).days
        if account_age < MIN_ACCOUNT_AGE:
            log.info(f"New account joined: {member} (age: {account_age} days)")

            # Kick if in raid mode
            if _raid_mode.get(guild.id):
                try:
                    await member.send(
                        embed=discord.Embed(
                            title="❌ Kicked — Account Too New",
                            description=f"**{guild.name}** is currently under a raid attack.\nNew accounts are being automatically removed for safety.\nPlease try joining again later.",
                            color=0xFF0000,
                        )
                    )
                except Exception:
                    pass
                try:
                    await member.kick(reason=f"Anti-raid: account only {account_age} days old during raid")
                    await self._notify_staff(guild, "New Account Kicked", f"{member.mention} (`{member}`) was kicked — account age: {account_age} days")
                except Exception:
                    pass
            else:
                # Just flag it
                await self._notify_staff(
                    guild,
                    "⚠️ New Account Joined",
                    f"{member.mention} (`{member}`)\nAccount age: **{account_age} days**\nThis may be a bot or alt account.",
                    color=0xFFD700,
                )

    # ── Mass mention detection ────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.author.guild_permissions.manage_messages:
            return

        import re

        # Mass mention check
        mention_count = len(message.mentions) + len(message.role_mentions)
        if mention_count >= MASS_MENTION_LIMIT:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                until = datetime.now(timezone.utc) + timedelta(minutes=30)
                await message.author.timeout(until, reason="Mass mention detected")
            except Exception:
                pass
            await self._notify_staff(
                message.guild,
                "⚠️ Mass Mention Detected",
                f"{message.author.mention} mentioned **{mention_count} users/roles** in one message.\nUser has been muted for 30 minutes.",
                color=0xFF4500,
            )
            return

        # Invite link detection (non-staff)
        if re.search(INVITE_PATTERN, message.content, re.IGNORECASE):
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.channel.send(
                    f"🚫 {message.author.mention} — Posting invite links is not allowed!",
                    delete_after=10,
                )
            except Exception:
                pass
            await self._notify_staff(
                message.guild,
                "⚠️ Invite Link Blocked",
                f"{message.author.mention} tried to post an invite link in {message.channel.mention}.",
                color=0xFF4500,
            )

    # ── /lockdown ─────────────────────────────────────────
    @app_commands.command(name="lockdown", description="Lock all channels (emergency) 🔒")
    @app_commands.describe(reason="Reason for lockdown")
    async def slash_lockdown(self, interaction: discord.Interaction, reason: str = "Manual lockdown by staff"):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("🚫 Need Manage Channels permission.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        await self._enable_raid_mode(interaction.guild, reason)
        await interaction.followup.send(f"🔒 **Lockdown activated!** Reason: {reason}\nUse `/unlockdown` to restore access.")

    # ── /unlockdown ───────────────────────────────────────
    @app_commands.command(name="unlockdown", description="Unlock all channels 🔓")
    async def slash_unlockdown(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("🚫 Need Manage Channels permission.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        _raid_mode[guild.id] = False
        restored = 0

        for ch_id in _locked_channels.get(guild.id, []):
            ch = guild.get_channel(ch_id)
            if ch:
                try:
                    overwrite = ch.overwrites_for(guild.default_role)
                    overwrite.send_messages = None  # Reset to default
                    await ch.set_permissions(guild.default_role, overwrite=overwrite, reason=f"Lockdown lifted by {interaction.user}")
                    restored += 1
                except Exception:
                    pass

        _locked_channels[guild.id] = []
        _join_tracker[guild.id] = []

        await self._notify_staff(
            guild,
            "✅ Lockdown Lifted",
            f"Lockdown removed by {interaction.user.mention}.\n{restored} channels restored.",
            color=0x00FF7F,
        )
        await interaction.followup.send(f"🔓 **Lockdown lifted!** {restored} channels restored.")

    # ── /raidstatus ───────────────────────────────────────
    @app_commands.command(name="raidstatus", description="Check anti-raid status 🛡️")
    async def slash_raidstatus(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        guild = interaction.guild
        in_raid = _raid_mode.get(guild.id, False)
        recent_joins = len(_join_tracker.get(guild.id, []))
        locked = len(_locked_channels.get(guild.id, []))

        embed = discord.Embed(
            title="🛡️ Anti-Raid Status",
            color=0xFF0000 if in_raid else 0x00FF7F,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="🚨 Raid Mode", value="**ACTIVE** 🔴" if in_raid else "Inactive 🟢", inline=True)
        embed.add_field(name="🔒 Locked Channels", value=str(locked), inline=True)
        embed.add_field(name="👥 Recent Joins", value=f"{recent_joins} in last {RAID_JOIN_WINDOW}s", inline=True)
        embed.add_field(name="⚙️ Settings", value=(
            f"Join threshold: **{RAID_JOIN_THRESHOLD}** in **{RAID_JOIN_WINDOW}s**\n"
            f"Min account age: **{MIN_ACCOUNT_AGE} days**\n"
            f"Mass mention limit: **{MASS_MENTION_LIMIT}**"
        ), inline=False)
        embed.set_footer(text="PIRATES Anti-Raid System")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /antiraid ─────────────────────────────────────────
    @app_commands.command(name="antiraid", description="Configure anti-raid settings 🛡️")
    @app_commands.describe(enabled="Enable or disable anti-raid")
    async def slash_antiraid(self, interaction: discord.Interaction, enabled: bool):
        if interaction.user.id != OWNER_ID and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🚫 Owner/Admin only.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛡️ Anti-Raid System",
            description=(
                f"Anti-raid protection is **always active**.\n\n"
                f"**Current protections:**\n"
                f"✅ Mass join detection ({RAID_JOIN_THRESHOLD} joins/{RAID_JOIN_WINDOW}s)\n"
                f"✅ New account detection (<{MIN_ACCOUNT_AGE} days old)\n"
                f"✅ Mass mention blocking (>{MASS_MENTION_LIMIT} mentions)\n"
                f"✅ Invite link blocking\n"
                f"✅ Auto-lockdown on raid detection\n"
                f"✅ Owner DM alerts\n\n"
                f"Use `/lockdown` for manual lockdown\n"
                f"Use `/unlockdown` to restore access"
            ),
            color=0x00FF7F,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaidCog(bot))
