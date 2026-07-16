"""
🔑 Temp VC Access Cog
Commands: /grantvcaccess /revokevcaccess /listvcaccess
Grants non-admin users temporary view/join access to the admin VC.
They cannot manage channels, mute others, or do any mod actions.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
import logging

log = logging.getLogger("cog.temp_vc_access")

# In-memory store: {(guild_id, member_id, channel_id): expiry datetime}
_temp_access: dict[tuple, datetime] = {}

# Default admin VC name to look for (case-insensitive partial match)
DEFAULT_VC_NAME = "admin"


def staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_channels
    return app_commands.check(predicate)


def _find_vc(guild: discord.Guild, name: str) -> discord.VoiceChannel | None:
    """Find a voice channel by partial name match (case-insensitive)."""
    name_lower = name.lower()
    for ch in guild.voice_channels:
        if name_lower in ch.name.lower():
            return ch
    return None


class TempVCAccessCog(commands.Cog, name="TempVCAccess"):
    """Grant temporary access to the admin voice channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.expiry_checker.start()

    def cog_unload(self):
        self.expiry_checker.cancel()

    # ── Background task: check for expired access every minute ──
    @tasks.loop(minutes=1)
    async def expiry_checker(self):
        now = datetime.now(timezone.utc)
        expired = [key for key, expiry in _temp_access.items() if now >= expiry]

        for key in expired:
            guild_id, member_id, channel_id = key
            guild = self.bot.get_guild(guild_id)
            if not guild:
                _temp_access.pop(key, None)
                continue

            member = guild.get_member(member_id)
            channel = guild.get_channel(channel_id)

            if member and channel:
                try:
                    await channel.set_permissions(
                        member,
                        overwrite=None,
                        reason="Temp VC access expired",
                    )
                    log.info(f"Temp VC access expired for {member} in #{channel.name}")

                    # Disconnect them if they're currently in the VC
                    if member.voice and member.voice.channel == channel:
                        await member.move_to(None, reason="Temp VC access expired")

                    # DM the member
                    try:
                        embed = discord.Embed(
                            title="🔑 Temp VC Access Expired",
                            description=(
                                f"Your temporary access to **{channel.name}** in **{guild.name}** has expired.\n"
                                f"Contact staff if you need it extended."
                            ),
                            color=0xFF4500,
                            timestamp=now,
                        )
                        embed.set_footer(text="PIRATES • Temp VC Access")
                        await member.send(embed=embed)
                    except discord.Forbidden:
                        pass

                except (discord.Forbidden, discord.HTTPException) as e:
                    log.error(f"Failed to remove temp VC access for {member_id}: {e}")

            _temp_access.pop(key, None)

    @expiry_checker.before_loop
    async def before_expiry_checker(self):
        await self.bot.wait_until_ready()

    # ── /grantvcaccess ────────────────────────────────────
    @app_commands.command(
        name="grantvcaccess",
        description="Grant a member temporary access to the admin VC 🔑",
    )
    @app_commands.describe(
        member="The member to grant access to",
        duration="How long in minutes (default: 60)",
        vc_name="Name of the VC to grant access to (default: admin VC)",
    )
    @staff_only()
    async def slash_grant(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: int = 1440,
        vc_name: str = DEFAULT_VC_NAME,
    ):
        await interaction.response.defer(ephemeral=True)

        # Validate duration
        if duration < 1 or duration > 1440:
            await interaction.followup.send(
                "⚠️ Duration must be between 1 and 1440 minutes (24 hours).",
                ephemeral=True,
            )
            return

        # Find the VC
        channel = _find_vc(interaction.guild, vc_name)
        if not channel:
            await interaction.followup.send(
                f"❌ Could not find a voice channel matching **\"{vc_name}\"**.\n"
                f"Use the `vc_name` parameter to specify the exact channel name.",
                ephemeral=True,
            )
            return

        # Don't grant to admins (they already have access)
        if member.guild_permissions.administrator:
            await interaction.followup.send(
                f"⚠️ {member.mention} is already an admin — no need to grant access.",
                ephemeral=True,
            )
            return

        expiry = datetime.now(timezone.utc) + timedelta(minutes=duration)
        key = (interaction.guild.id, member.id, channel.id)

        # Set permission overwrite — view + connect ONLY, no mod perms
        overwrite = discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
            speak=True,
            stream=False,
            use_voice_activation=True,
            # Explicitly deny mod-level perms
            manage_channels=False,
            manage_permissions=False,
            mute_members=False,
            deafen_members=False,
            move_members=False,
            priority_speaker=False,
        )

        try:
            await channel.set_permissions(member, overwrite=overwrite, reason=f"Temp VC access granted by {interaction.user} for {duration}m")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to manage that channel's permissions.",
                ephemeral=True,
            )
            return

        _temp_access[key] = expiry

        # DM the member
        try:
            dm_embed = discord.Embed(
                title="🔑 Temp VC Access Granted",
                description=(
                    f"You've been granted **temporary access** to **{channel.name}** in **{interaction.guild.name}**.\n\n"
                    f"⏱️ **Expires in:** {duration} minute{'s' if duration != 1 else ''}\n"
                    f"📅 **Expires at:** <t:{int(expiry.timestamp())}:F>\n\n"
                    f"You can join the channel now. Access will be removed automatically when it expires."
                ),
                color=0x00FF7F,
                timestamp=datetime.now(timezone.utc),
            )
            dm_embed.set_footer(text="PIRATES • Temp VC Access")
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # DMs closed, no problem

        # Confirm to staff
        confirm_embed = discord.Embed(
            title="✅ Temp VC Access Granted",
            color=0x00FF7F,
            timestamp=datetime.now(timezone.utc),
        )
        confirm_embed.add_field(name="👤 Member",   value=member.mention,                              inline=True)
        confirm_embed.add_field(name="🔊 Channel",  value=channel.mention,                             inline=True)
        confirm_embed.add_field(name="⏱️ Duration", value=f"{duration} minute{'s' if duration != 1 else ''}", inline=True)
        confirm_embed.add_field(name="📅 Expires",  value=f"<t:{int(expiry.timestamp())}:R>",          inline=True)
        confirm_embed.set_footer(text=f"Granted by {interaction.user} • PIRATES")
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

        # Log to mod-log
        await self._log_action(
            interaction.guild,
            f"🔑 Temp VC Access Granted ({duration}m)",
            member,
            interaction.user,
            f"Channel: {channel.name} | Expires: <t:{int(expiry.timestamp())}:F>",
        )

    # ── /revokevcaccess ───────────────────────────────────
    @app_commands.command(
        name="revokevcaccess",
        description="Revoke a member's temporary VC access early 🔒",
    )
    @app_commands.describe(
        member="The member to revoke access from",
        vc_name="Name of the VC (default: admin VC)",
    )
    @staff_only()
    async def slash_revoke(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        vc_name: str = DEFAULT_VC_NAME,
    ):
        await interaction.response.defer(ephemeral=True)

        channel = _find_vc(interaction.guild, vc_name)
        if not channel:
            await interaction.followup.send(
                f"❌ Could not find a voice channel matching **\"{vc_name}\"**.",
                ephemeral=True,
            )
            return

        key = (interaction.guild.id, member.id, channel.id)

        if key not in _temp_access:
            await interaction.followup.send(
                f"⚠️ {member.mention} doesn't have active temp access to **{channel.name}**.",
                ephemeral=True,
            )
            return

        # Remove permission overwrite
        try:
            await channel.set_permissions(
                member,
                overwrite=None,
                reason=f"Temp VC access revoked by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to manage that channel's permissions.",
                ephemeral=True,
            )
            return

        # Disconnect if in VC
        if member.voice and member.voice.channel == channel:
            try:
                await member.move_to(None, reason="Temp VC access revoked")
            except discord.Forbidden:
                pass

        _temp_access.pop(key, None)

        # DM the member
        try:
            dm_embed = discord.Embed(
                title="🔒 Temp VC Access Revoked",
                description=(
                    f"Your temporary access to **{channel.name}** in **{interaction.guild.name}** has been revoked by staff."
                ),
                color=0xFF4500,
                timestamp=datetime.now(timezone.utc),
            )
            dm_embed.set_footer(text="PIRATES • Temp VC Access")
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        await interaction.followup.send(
            f"✅ Revoked temp VC access for {member.mention} in **{channel.name}**.",
            ephemeral=True,
        )

        await self._log_action(
            interaction.guild,
            "🔒 Temp VC Access Revoked",
            member,
            interaction.user,
            f"Channel: {channel.name} | Revoked early",
        )

    # ── /listvcaccess ─────────────────────────────────────
    @app_commands.command(
        name="listvcaccess",
        description="List all active temporary VC access grants 📋",
    )
    @staff_only()
    async def slash_list(self, interaction: discord.Interaction):
        guild_entries = {
            key: expiry
            for key, expiry in _temp_access.items()
            if key[0] == interaction.guild.id
        }

        if not guild_entries:
            await interaction.response.send_message(
                "📋 No active temporary VC access grants.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📋 Active Temp VC Access Grants",
            color=0x00BFFF,
            timestamp=datetime.now(timezone.utc),
        )

        for (guild_id, member_id, channel_id), expiry in guild_entries.items():
            member = interaction.guild.get_member(member_id)
            channel = interaction.guild.get_channel(channel_id)
            member_str = member.mention if member else f"<@{member_id}>"
            channel_str = channel.mention if channel else f"<#{channel_id}>"
            embed.add_field(
                name=f"{member_str}",
                value=f"Channel: {channel_str}\nExpires: <t:{int(expiry.timestamp())}:R>",
                inline=True,
            )

        embed.set_footer(text="PIRATES • Temp VC Access")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Shared log helper ─────────────────────────────────
    async def _log_action(
        self,
        guild: discord.Guild,
        action: str,
        target: discord.Member,
        moderator: discord.Member,
        reason: str,
    ):
        import os
        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        if not log_ch_id:
            return
        channel = guild.get_channel(log_ch_id)
        if not channel:
            return
        embed = discord.Embed(
            title=f"🛡️ {action}",
            color=0x00BFFF,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Target",    value=str(target),    inline=True)
        embed.add_field(name="Moderator", value=str(moderator), inline=True)
        embed.add_field(name="Details",   value=reason,         inline=False)
        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TempVCAccessCog(bot))
