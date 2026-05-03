"""
📣 Server Growth Cog
- Bump reminder every 2 hours
- Invite tracker (who invited who, top inviters)
- Member milestone announcements (50, 100, 250, 500, 1000)
- /tempvcaccess — give a member 24h access to admin VC
Commands: /invites /topinviters /tempvcaccess /revokevcaccess
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import asyncio
import logging
import json
import os

log = logging.getLogger("cog.growth")

OWNER_ID = 815646767311224953

# Milestones to announce
MILESTONES = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]

# Invite tracking
_invites: dict[int, dict] = {}          # {guild_id: {code: invite_obj}}
_invite_uses: dict[str, dict] = {}      # {guild_id: {user_id: {invites, invited_by}}}
_INVITE_FILE = os.path.join(os.path.dirname(__file__), "..", "invite_data.json")

# Temp VC access tracking
_temp_vc_access: dict[int, list] = defaultdict(list)  # {guild_id: [{user_id, expires_at}]}

TEMP_VC_ROLE_NAME = "🎙️ VIP VC Access"
ADMIN_VC_NAMES = ["👑 OWNER VC", "⚔️ CAPTAIN VC", "🛡️ MOD VC", "🔒 STAFF LOUNGE", "admin", "staff vc"]


def _load_invites():
    global _invite_uses
    try:
        if os.path.exists(_INVITE_FILE):
            with open(_INVITE_FILE, "r") as f:
                _invite_uses = json.load(f)
    except Exception:
        _invite_uses = {}


def _save_invites():
    try:
        with open(_INVITE_FILE, "w") as f:
            json.dump(_invite_uses, f)
    except Exception as e:
        log.error(f"Failed to save invite data: {e}")


class GrowthCog(commands.Cog, name="Growth"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        _load_invites()
        self.bump_reminder.start()
        self.check_temp_vc.start()
        self._last_bump: dict[int, datetime] = {}
        self._prev_member_count: dict[int, int] = {}

    def cog_unload(self):
        self.bump_reminder.cancel()
        self.check_temp_vc.cancel()
        _save_invites()

    # ── Cache invites on ready ────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                _invites[guild.id] = {inv.code: inv for inv in invites}
                self._prev_member_count[guild.id] = guild.member_count
            except Exception:
                pass

    # ── Track invite usage ────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        gid = str(guild.id)

        # Check milestones
        count = guild.member_count
        if count in MILESTONES:
            await self._announce_milestone(guild, count)

        # Track invite
        try:
            new_invites = await guild.invites()
            new_inv_map = {inv.code: inv for inv in new_invites}
            old_inv_map = _invites.get(guild.id, {})

            inviter = None
            for code, inv in new_inv_map.items():
                old = old_inv_map.get(code)
                if old and inv.uses > old.uses:
                    inviter = inv.inviter
                    break

            _invites[guild.id] = new_inv_map

            if gid not in _invite_uses:
                _invite_uses[gid] = {}

            uid = str(member.id)
            _invite_uses[gid][uid] = {
                "invited_by": str(inviter.id) if inviter else None,
                "invited_by_name": str(inviter) if inviter else "Unknown",
                "joined_at": datetime.now(timezone.utc).isoformat(),
            }

            if inviter:
                inv_uid = str(inviter.id)
                if inv_uid not in _invite_uses[gid]:
                    _invite_uses[gid][inv_uid] = {"invites": 0}
                _invite_uses[gid][inv_uid]["invites"] = _invite_uses[gid][inv_uid].get("invites", 0) + 1

            _save_invites()

        except Exception as e:
            log.error(f"Invite tracking error: {e}")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild:
            if invite.guild.id not in _invites:
                _invites[invite.guild.id] = {}
            _invites[invite.guild.id][invite.code] = invite

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild and invite.guild.id in _invites:
            _invites[invite.guild.id].pop(invite.code, None)

    # ── Milestone announcement ────────────────────────────
    async def _announce_milestone(self, guild: discord.Guild, count: int):
        ch = discord.utils.find(
            lambda c: any(x in c.name.lower() for x in ["general", "chat", "announce", "welcome"]),
            guild.text_channels,
        )
        if not ch:
            return

        milestones_text = {
            10: "We're just getting started! 🔥",
            25: "The crew is growing! ⚓",
            50: "50 pirates aboard! 🏴‍☠️",
            100: "100 members! This is huge! 🎉",
            250: "250 strong! PIRATES is rising! 💪",
            500: "500 members! We're a force to be reckoned with! 🚀",
            1000: "1000 PIRATES! LEGENDARY! 👑",
            2500: "2500 members! The seas belong to us! 🌊",
            5000: "5000 PIRATES! UNSTOPPABLE! 🏆",
        }

        embed = discord.Embed(
            title=f"🎉 {count} Members!",
            description=milestones_text.get(count, f"We've reached **{count} members**!"),
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="PIRATES • Growing Strong")
        await ch.send(content="@everyone", embed=embed)

    # ── Bump reminder ─────────────────────────────────────
    @tasks.loop(minutes=30)
    async def bump_reminder(self):
        for guild in self.bot.guilds:
            last = self._last_bump.get(guild.id)
            if last and (datetime.now(timezone.utc) - last) >= timedelta(hours=2):
                bump_ch = discord.utils.find(
                    lambda c: "bump" in c.name.lower() or "disboard" in c.name.lower(),
                    guild.text_channels,
                )
                if bump_ch:
                    try:
                        await bump_ch.send(
                            embed=discord.Embed(
                                title="📣 Time to Bump!",
                                description="It's been 2 hours! Use `/bump` to bump the server on Disboard and help us grow!\n\nMore members = more games = more fun 🏴‍☠️",
                                color=0xFF4500,
                            )
                        )
                        self._last_bump[guild.id] = datetime.now(timezone.utc)
                    except Exception:
                        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Detect Disboard bump confirmation
        if message.author.id == 302050872383242240:  # Disboard bot ID
            if message.embeds and "bump done" in str(message.embeds[0].description or "").lower():
                if message.guild:
                    self._last_bump[message.guild.id] = datetime.now(timezone.utc)
                    log.info(f"Bump detected in {message.guild.name}")

    # ── Temp VC access checker ────────────────────────────
    @tasks.loop(minutes=5)
    async def check_temp_vc(self):
        now = datetime.now(timezone.utc)
        for guild in self.bot.guilds:
            entries = _temp_vc_access.get(guild.id, [])
            expired = [e for e in entries if datetime.fromisoformat(e["expires_at"]) <= now]
            for entry in expired:
                member = guild.get_member(entry["user_id"])
                if member:
                    role = discord.utils.get(guild.roles, name=TEMP_VC_ROLE_NAME)
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Temp VC access expired")
                            log.info(f"Removed temp VC access from {member} in {guild.name}")
                            try:
                                await member.send(
                                    embed=discord.Embed(
                                        title="⏰ VIP VC Access Expired",
                                        description=f"Your temporary VIP VC access in **{guild.name}** has expired.",
                                        color=0xFF4500,
                                    )
                                )
                            except Exception:
                                pass
                        except Exception as e:
                            log.error(f"Failed to remove temp VC role: {e}")
            _temp_vc_access[guild.id] = [e for e in entries if datetime.fromisoformat(e["expires_at"]) > now]

    # ── /tempvcaccess ─────────────────────────────────────
    @app_commands.command(name="tempvcaccess", description="Give a member 24h access to the admin VC 🎙️")
    @app_commands.describe(
        member="Member to give access to",
        hours="How many hours (default: 24, max: 48)",
    )
    async def slash_tempvcaccess(self, interaction: discord.Interaction, member: discord.Member, hours: int = 24):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("🚫 Need Manage Roles permission.", ephemeral=True)
            return

        hours = max(1, min(hours, 48))
        guild = interaction.guild

        # Get or create the temp VC role
        role = discord.utils.get(guild.roles, name=TEMP_VC_ROLE_NAME)
        if not role:
            role = await guild.create_role(
                name=TEMP_VC_ROLE_NAME,
                color=discord.Color.gold(),
                reason="Temp VIP VC access role",
            )
            # Give this role access to admin VCs
            for vc in guild.voice_channels:
                if any(x.lower() in vc.name.lower() for x in ADMIN_VC_NAMES):
                    try:
                        await vc.set_permissions(role, connect=True, speak=True, view_channel=True)
                        log.info(f"Gave {TEMP_VC_ROLE_NAME} access to {vc.name}")
                    except Exception:
                        pass

        # Give the role to the member
        await member.add_roles(role, reason=f"Temp VC access granted by {interaction.user} for {hours}h")

        expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        _temp_vc_access[guild.id].append({
            "user_id": member.id,
            "expires_at": expires_at.isoformat(),
            "granted_by": interaction.user.id,
        })

        embed = discord.Embed(
            title="🎙️ VIP VC Access Granted",
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="👤 Member", value=member.mention, inline=True)
        embed.add_field(name="⏱️ Duration", value=f"{hours} hours", inline=True)
        embed.add_field(name="⏰ Expires", value=f"<t:{int(expires_at.timestamp())}:R>", inline=True)
        embed.add_field(name="✅ Access", value="Admin/Staff voice channels", inline=False)
        embed.set_footer(text=f"Granted by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        # DM the member
        try:
            await member.send(
                embed=discord.Embed(
                    title="🎙️ VIP VC Access Granted!",
                    description=(
                        f"You've been given **temporary VIP VC access** in **{guild.name}**!\n\n"
                        f"⏱️ Duration: **{hours} hours**\n"
                        f"⏰ Expires: <t:{int(expires_at.timestamp())}:R>\n\n"
                        f"You can now join the admin/staff voice channels.\n"
                        f"*Note: You cannot kick, ban, or use any mod commands.*"
                    ),
                    color=0xFFD700,
                )
            )
        except Exception:
            pass

    # ── /revokevcaccess ───────────────────────────────────
    @app_commands.command(name="revokevcaccess", description="Revoke a member's VIP VC access 🚫")
    @app_commands.describe(member="Member to revoke access from")
    async def slash_revokevcaccess(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("🚫 Need Manage Roles permission.", ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, name=TEMP_VC_ROLE_NAME)
        if not role or role not in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} doesn't have VIP VC access.", ephemeral=True)
            return

        await member.remove_roles(role, reason=f"VIP VC access revoked by {interaction.user}")
        _temp_vc_access[interaction.guild.id] = [
            e for e in _temp_vc_access.get(interaction.guild.id, [])
            if e["user_id"] != member.id
        ]

        await interaction.response.send_message(f"✅ VIP VC access revoked from {member.mention}.")

    # ── /invites ──────────────────────────────────────────
    @app_commands.command(name="invites", description="Check how many people you've invited 📨")
    @app_commands.describe(member="Member to check (default: yourself)")
    async def slash_invites(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        gid = str(interaction.guild.id)
        uid = str(target.id)
        data = _invite_uses.get(gid, {}).get(uid, {})
        invite_count = data.get("invites", 0)
        invited_by = data.get("invited_by_name", "Unknown")

        embed = discord.Embed(
            title=f"📨 {target.display_name}'s Invites",
            color=0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="📨 Invites", value=str(invite_count), inline=True)
        embed.add_field(name="👤 Invited By", value=invited_by, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /topinviters ──────────────────────────────────────
    @app_commands.command(name="topinviters", description="Show top inviters 🏆")
    async def slash_topinviters(self, interaction: discord.Interaction):
        gid = str(interaction.guild.id)
        data = _invite_uses.get(gid, {})

        sorted_inviters = sorted(
            [(uid, d.get("invites", 0)) for uid, d in data.items() if d.get("invites", 0) > 0],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        if not sorted_inviters:
            await interaction.response.send_message("❌ No invite data yet.", ephemeral=True)
            return

        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title="📨 Top Inviters", color=0xFF4500, timestamp=datetime.now(timezone.utc))

        for i, (uid, count) in enumerate(sorted_inviters):
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            embed.add_field(name=f"{medal} {name}", value=f"**{count}** invites", inline=False)

        embed.set_footer(text=f"Total tracked: {len(sorted_inviters)} inviters")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(GrowthCog(bot))
