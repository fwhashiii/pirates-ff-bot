"""
🛡️ Moderation Cog — Kick, ban, mute, warn, purge + Anti-Spam + Word Filter
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import time
import os
import re

log = logging.getLogger("cog.mod")

# Simple in-memory warn store (use a DB for persistence)
_warnings: dict[int, list[dict]] = {}

# ── Anti-spam tracking ────────────────────────────────────
_spam_tracker: dict[int, list[float]] = defaultdict(list)

SPAM_MAX_MESSAGES = 5
SPAM_WINDOW_SECS  = 5
SPAM_MUTE_MINUTES = 10
SPAM_DELETE_MSGS  = True

# ── Word filter ───────────────────────────────────────────
# Mute duration for banned words (minutes)
FILTER_MUTE_MINUTES = 30

# Banned words list — add/remove as needed
# Using partial match so variations like l33tspeak are caught too
BANNED_WORDS = [
    # Racial slurs (common variations covered by regex)
    r"\bn[i!1][g9][g9][ae3]r?\b",
    r"\bn[i!1][g9]{2}[ae3]?\b",
    r"\bc[o0][o0]n\b",
    r"\bsp[i!1][c]k?\b",
    r"\bch[i!1]nk\b",
    r"\bk[i!1]ke\b",
    r"\bw[e3]tb[a@]ck\b",
    r"\bbeaner\b",
    r"\bz[i!1][p]p[e3]rh[e3][a@]d\b",
    r"\bs[a@]nd[n][i!1][g9]{2}[ae3]r?\b",
    r"\bh[a@][j][i!1]\b",
    r"\bt[o0][w][e3]lh[e3][a@]d\b",
    r"\bcr[a@]ck[e3]r\b",
    r"\bh[o0]nk[e3]y\b",
    r"\btr[a@][s][h][y]?\s*[a@][s][s]\b",
    # Harassment / hate
    r"\bf[a@][g9]{1,2}[o0]?t?\b",
    r"\bf[a@][g9]\b",
    r"\br[e3]t[a@]rd\b",
    r"\bk[i!1]ll\s+your\s*self\b",
    r"\bkys\b",
    r"\bg[o0]\s*k[i!1]ll\s*your\s*self\b",
    r"\bkill\s*ur\s*self\b",
    r"\bkill\s*yourself\b",
    r"\bslit\s*your\s*wrists\b",
    r"\bh[a@]ng\s*your\s*self\b",
    r"\bh[a@]ngself\b",
    r"\bsuicide\s*yourself\b",
    r"\btr[a@]nny\b",
    r"\bsh[e3]m[a@][l][e3]\b",
    r"\bsl[u][t]\b",
    r"\bwh[o0]r[e3]\b",
    r"\bc[u][n][t]\b",
    r"\bd[i!1]k[e3]\b",
]

# Compile all patterns once for performance
_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in BANNED_WORDS]


def contains_banned_word(text: str) -> str | None:
    """Returns the matched pattern string if a banned word is found, else None."""
    # Normalize common l33tspeak substitutions
    normalized = text.lower()
    normalized = normalized.replace("@", "a").replace("3", "e").replace("1", "i") \
                           .replace("0", "o").replace("$", "s").replace("!", "i") \
                           .replace("9", "g").replace("+", "t")
    for pattern in _compiled_patterns:
        if pattern.search(normalized) or pattern.search(text):
            return pattern.pattern
    return None


def mod_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_messages
    return app_commands.check(predicate)


class ModerationCog(commands.Cog, name="Moderation"):
    """Server moderation tools for staff."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Combined message listener (spam + word filter) ────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, and staff
        if message.author.bot:
            return
        if not message.guild:
            return
        if message.author.guild_permissions.manage_messages:
            return  # Staff exempt from both filters

        # ── 1. Word filter check ──────────────────────────
        matched = contains_banned_word(message.content)
        if matched:
            member = message.author
            guild  = message.guild

            # Delete the offending message
            try:
                await message.delete()
            except discord.Forbidden:
                pass

            # Apply timeout
            try:
                until = datetime.utcnow() + timedelta(minutes=FILTER_MUTE_MINUTES)
                await member.timeout(until, reason="Auto-mute: banned word used")
            except discord.Forbidden:
                pass

            # Issue warning (escalates automatically)
            count = await self.issue_warning(
                guild, member,
                reason=f"Used banned word/phrase in #{message.channel.name}",
                auto=True,
            )

            # Public notice in channel
            embed = discord.Embed(
                title="🚫 Banned Word Detected",
                description=(
                    f"{member.mention} used prohibited language and has received **Warning {count}/3**.\n\n"
                    f"{'🔨 They have been **permanently banned**.' if count >= 3 else '⚠️ One more warning results in a permanent ban.' if count == 2 else '⚠️ Keep it clean or face further action.'}"
                ),
                color=0xFF0000 if count >= 3 else 0xFF4500 if count == 2 else 0xFFD700,
                timestamp=datetime.utcnow(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Word Filter • Free Fire Squad Bot")
            try:
                await message.channel.send(embed=embed, delete_after=20)
            except discord.Forbidden:
                pass
            return
        # ── 2. Anti-spam check ────────────────────────────
        uid = message.author.id
        now = time.time()

        _spam_tracker[uid].append(now)
        _spam_tracker[uid] = [
            t for t in _spam_tracker[uid]
            if now - t <= SPAM_WINDOW_SECS
        ]

        if len(_spam_tracker[uid]) >= SPAM_MAX_MESSAGES:
            _spam_tracker[uid] = []
            member = message.author
            guild  = message.guild

            if SPAM_DELETE_MSGS:
                try:
                    await message.channel.purge(
                        limit=SPAM_MAX_MESSAGES + 2,
                        check=lambda m: m.author == member,
                    )
                except discord.Forbidden:
                    pass

            try:
                until = datetime.utcnow() + timedelta(minutes=SPAM_MUTE_MINUTES)
                await member.timeout(until, reason="Auto-mute: spam detected")
            except discord.Forbidden:
                pass

            count = await self.issue_warning(guild, member, reason="Spamming messages", auto=True)

            embed = discord.Embed(
                title="🔇 Spammer Detected!",
                description=(
                    f"{member.mention} sent too many messages too fast — **Warning {count}/3** issued.\n\n"
                    f"{'🔨 They have been **permanently banned**.' if count >= 3 else '⚠️ One more warning = permanent ban.' if count == 2 else 'Slow down and keep it chill! 🔥'}"
                ),
                color=0xFF0000 if count >= 3 else 0xFF4500,
                timestamp=datetime.utcnow(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Anti-Spam System • Free Fire Squad Bot")

            try:
                await message.channel.send(embed=embed, delete_after=15)
            except discord.Forbidden:
                pass

            await self.log_action(
                guild, f"Auto-Mute ({SPAM_MUTE_MINUTES}m) — Spam",
                member, self.bot.user, "Spam detected by anti-spam system"
            )

    async def issue_warning(self, guild: discord.Guild, member: discord.Member, reason: str, auto: bool = False) -> int:
        """
        Central warning issuer. Returns the new warning count.
        Escalation:
          Warning 1 → DM notice
          Warning 2 → 1 hour mute + DM
          Warning 3 → permanent ban + public announcement
        """
        uid = member.id
        if uid not in _warnings:
            _warnings[uid] = []

        _warnings[uid].append({
            "reason": reason,
            "by": "Auto-Mod" if auto else "Staff",
            "time": str(datetime.utcnow()),
        })
        count = len(_warnings[uid])

        issuer = "🤖 Auto-Mod" if auto else "Staff"

        if count == 1:
            # ── Warning 1: DM only ────────────────────────
            await self.log_action(guild, "Warning #1", member, issuer, reason)
            try:
                dm = discord.Embed(
                    title="⚠️ Warning #1 — Free Fire Squad",
                    description=(
                        f"You have received **Warning 1/3** in **{guild.name}**.\n\n"
                        f"**Reason:** {reason}\n\n"
                        f"⚠️ **2 more warnings will result in a permanent ban.**\n"
                        f"Please follow the server rules."
                    ),
                    color=0xFFD700,
                )
                await member.send(embed=dm)
            except discord.Forbidden:
                pass

        elif count == 2:
            # ── Warning 2: 1 hour mute + DM ──────────────
            try:
                until = datetime.utcnow() + timedelta(hours=1)
                await member.timeout(until, reason=f"Warning #2: {reason}")
            except discord.Forbidden:
                pass

            await self.log_action(guild, "Warning #2 + Mute (1h)", member, issuer, reason)

            try:
                dm = discord.Embed(
                    title="⚠️ Warning #2 — Muted 1 Hour",
                    description=(
                        f"You have received **Warning 2/3** in **{guild.name}**.\n\n"
                        f"**Reason:** {reason}\n\n"
                        f"You have been **muted for 1 hour**.\n"
                        f"🚨 **One more warning = permanent ban.** This is your final chance."
                    ),
                    color=0xFF4500,
                )
                await member.send(embed=dm)
            except discord.Forbidden:
                pass

        elif count >= 3:
            # ── Warning 3: Auto-ban ───────────────────────
            # DM them before banning so they receive it
            try:
                dm = discord.Embed(
                    title="🔨 Banned — Free Fire Squad",
                    description=(
                        f"You have been **permanently banned** from **{guild.name}**.\n\n"
                        f"**Reason:** {reason}\n"
                        f"**Warnings received:** {count}\n\n"
                        f"You reached 3 warnings and have been automatically banned."
                    ),
                    color=0xFF0000,
                )
                await member.send(embed=dm)
            except discord.Forbidden:
                pass

            try:
                await member.ban(
                    reason=f"Auto-ban: 3 warnings reached. Last reason: {reason}",
                    delete_message_days=1,
                )
            except discord.Forbidden:
                pass

            # Clear warnings after ban
            _warnings.pop(uid, None)
            await self.log_action(guild, "🔨 AUTO-BAN (3 warnings)", member, issuer, reason)

        return count
        """Send a log embed to the mod-log channel."""
        import os
        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        if not log_ch_id:
            return
        channel = guild.get_channel(log_ch_id)
        if not channel:
            return
        embed = discord.Embed(
            title=f"🛡️ Mod Action: {action}",
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Target",    value=str(target),    inline=True)
        embed.add_field(name="Moderator", value=str(moderator), inline=True)
        embed.add_field(name="Reason",    value=reason or "No reason given", inline=False)
        await channel.send(embed=embed)

    # ── /kick ─────────────────────────────────────────────
    @app_commands.command(name="kick", description="Kick a member 👢")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @mod_only()
    async def slash_kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 **{member}** has been kicked. Reason: {reason}")
        await self.log_action(interaction.guild, "Kick", member, interaction.user, reason)

    # ── /ban ──────────────────────────────────────────────
    @app_commands.command(name="ban", description="Ban a member 🔨")
    @app_commands.describe(member="Member to ban", reason="Reason for ban", delete_days="Days of messages to delete (0–7)")
    @mod_only()
    async def slash_ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given", delete_days: int = 1):
        delete_days = max(0, min(delete_days, 7))
        await member.ban(reason=reason, delete_message_days=delete_days)
        await interaction.response.send_message(f"🔨 **{member}** has been banned. Reason: {reason}")
        await self.log_action(interaction.guild, "Ban", member, interaction.user, reason)

    # ── /unban ────────────────────────────────────────────
    @app_commands.command(name="unban", description="Unban a user by ID 🔓")
    @app_commands.describe(user_id="The user's Discord ID")
    @mod_only()
    async def slash_unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"🔓 **{user}** has been unbanned.")
            await self.log_action(interaction.guild, "Unban", user, interaction.user, "Manual unban")
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Could not unban: {e}", ephemeral=True)

    # ── /mute ─────────────────────────────────────────────
    @app_commands.command(name="mute", description="Timeout (mute) a member ⏱️")
    @app_commands.describe(member="Member to mute", minutes="Duration in minutes", reason="Reason")
    @mod_only()
    async def slash_mute(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason given"):
        until = datetime.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=reason)
        await interaction.response.send_message(
            f"🔇 **{member}** has been muted for **{minutes} minutes**. Reason: {reason}"
        )
        await self.log_action(interaction.guild, f"Mute ({minutes}m)", member, interaction.user, reason)

    # ── /unmute ───────────────────────────────────────────
    @app_commands.command(name="unmute", description="Remove timeout from a member 🔊")
    @app_commands.describe(member="Member to unmute")
    @mod_only()
    async def slash_unmute(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 **{member}** has been unmuted.")
        await self.log_action(interaction.guild, "Unmute", member, interaction.user, "Manual unmute")

    # ── /warn ─────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member ⚠️")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @mod_only()
    async def slash_warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
        count = await self.issue_warning(interaction.guild, member, reason=reason, auto=False)

        color = 0xFFD700 if count == 1 else 0xFF4500 if count == 2 else 0xFF0000
        status = (
            "⚠️ Warning issued."                          if count == 1 else
            "⚠️ Second warning — muted for 1 hour."       if count == 2 else
            "🔨 Third warning — **permanently banned**."
        )

        embed = discord.Embed(
            title=f"⚠️ Warning #{count}/3 — {member.display_name}",
            description=f"{status}\n\n**Reason:** {reason}",
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Issued by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    # ── /warnings ─────────────────────────────────────────
    @app_commands.command(name="warnings", description="View warnings for a member 📋")
    @app_commands.describe(member="Member to check")
    @mod_only()
    async def slash_warnings(self, interaction: discord.Interaction, member: discord.Member):
        warns = _warnings.get(member.id, [])
        if not warns:
            await interaction.response.send_message(f"✅ **{member}** has no warnings.", ephemeral=True)
            return
        embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=0xFFD700)
        for i, w in enumerate(warns, 1):
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Reason:** {w['reason']}\n**By:** {w['by']}\n**Time:** {w['time']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /clearwarnings ────────────────────────────────────
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member 🧹")
    @app_commands.describe(member="Member to clear warnings for")
    @mod_only()
    async def slash_clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        _warnings.pop(member.id, None)
        await interaction.response.send_message(f"🧹 Cleared all warnings for **{member}**.", ephemeral=True)

    # ── /purge ────────────────────────────────────────────
    @app_commands.command(name="purge", description="Delete multiple messages 🗑️")
    @app_commands.describe(amount="Number of messages to delete (1–100)")
    @mod_only()
    async def slash_purge(self, interaction: discord.Interaction, amount: int = 10):
        amount = max(1, min(amount, 100))
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages.", ephemeral=True)
        await self.log_action(
            interaction.guild, f"Purge ({len(deleted)} msgs)",
            interaction.channel, interaction.user, "Manual purge"
        )

    # ── /antispam ─────────────────────────────────────────
    @app_commands.command(name="antispam", description="View or adjust anti-spam settings 🛡️")
    @app_commands.describe(
        max_messages="Max messages before mute (default 5)",
        window_secs="Time window in seconds (default 5)",
        mute_minutes="Mute duration in minutes (default 10)"
    )
    @mod_only()
    async def slash_antispam(
        self,
        interaction: discord.Interaction,
        max_messages: int = None,
        window_secs: int = None,
        mute_minutes: int = None,
    ):
        global SPAM_MAX_MESSAGES, SPAM_WINDOW_SECS, SPAM_MUTE_MINUTES

        if max_messages:  SPAM_MAX_MESSAGES = max_messages
        if window_secs:   SPAM_WINDOW_SECS  = window_secs
        if mute_minutes:  SPAM_MUTE_MINUTES = mute_minutes

        embed = discord.Embed(
            title="🛡️ Anti-Spam Settings",
            color=0x00BFFF,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="📨 Max Messages",   value=str(SPAM_MAX_MESSAGES), inline=True)
        embed.add_field(name="⏱️ Window",         value=f"{SPAM_WINDOW_SECS}s", inline=True)
        embed.add_field(name="🔇 Mute Duration",  value=f"{SPAM_MUTE_MINUTES}m", inline=True)
        embed.add_field(
            name="ℹ️ How it works",
            value=f"If a user sends **{SPAM_MAX_MESSAGES}+ messages** within **{SPAM_WINDOW_SECS} seconds**, they get auto-muted for **{SPAM_MUTE_MINUTES} minutes**.",
            inline=False,
        )
        embed.set_footer(text="Staff only • Changes apply immediately")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Error handler ─────────────────────────────────────
    @slash_kick.error
    @slash_ban.error
    @slash_mute.error
    @slash_warn.error
    @slash_purge.error
    async def mod_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "🚫 You need **Manage Messages** permission to use this command.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
