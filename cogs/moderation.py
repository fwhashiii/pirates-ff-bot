"""
🛡️ Moderation Cog — Kick, ban, mute, warn, purge + Anti-Spam + Word Filter
"""

import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import datetime, timedelta, timezone
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

# ── Message history buffer (for split-message bypass detection) ──
# Stores last 3 messages per user per channel: {(user_id, channel_id): [msg1, msg2, msg3]}
from collections import deque
_msg_buffer: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=5))

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
    # ── Racial slurs ──────────────────────────────────────
    r"\bn[i!1][g9][g9][ae3]r?\b",
    r"\bn[i!1][g9]{2}[ae3]?\b",
    r"\bc[o0][o0]n\b",
    r"\bsp[i!1][c]k?\b",
    r"\bch[i!1]nk\b",
    r"\bk[i!1]ke\b",
    r"\bw[e3]tb[a@]ck\b",
    r"\bbeaner\b",
    r"\bs[a@]nd[n][i!1][g9]{2}[ae3]r?\b",
    r"\bh[a@][j][i!1]\b",
    r"\bt[o0][w][e3]lh[e3][a@]d\b",
    r"\bcr[a@]ck[e3]r\b",
    r"\bh[o0]nk[e3]y\b",
    # ── Harassment / hate ─────────────────────────────────
    r"\bf[a@][g9]{1,2}[o0]?t?\b",
    r"\br[e3]t[a@]rd\b",
    r"\bkys\b",
    r"\bkill\s*your\s*self\b",
    r"\bkill\s*ur\s*self\b",
    r"\bslit\s*your\s*wrists\b",
    r"\bh[a@]ng\s*your\s*self\b",
    r"\btr[a@]nny\b",
    r"\bsl[u][t]\b",
    r"\bwh[o0]r[e3]\b",
    r"\bc[u][n][t]\b",
    # ── Discord TOS violations ────────────────────────────
    # Doxxing / personal info sharing
    r"\bdox\b",
    r"\bdoxx\b",
    r"\bpost\s*(your|their|his|her)\s*(address|ip|location|phone)",
    r"\bip\s*grab",
    r"\bip\s*logger",
    r"\bip\s*stresser",
    # NSFW / explicit content
    r"\bcp\b",
    r"\bchild\s*porn",
    r"\bkiddie\s*porn",
    r"\bloli\b",
    r"\bshota\b",
    # Scams / phishing
    r"\bfree\s*nitro\b",
    r"\bnitro\s*giveaway\b",
    r"\bdiscord\s*nitro\s*free\b",
    r"\bsteam\s*gift\s*card\s*free\b",
    r"\bclick\s*this\s*link\s*for\s*free",
    r"\bdiscord\.gift\b",
    r"\bsteamcommunity\.com\.[\w]+",
    # Threats
    r"\bi\s*will\s*kill\s*you\b",
    r"\bi\s*will\s*find\s*you\b",
    r"\bim\s*going\s*to\s*kill\b",
    r"\bimma\s*kill\b",
    r"\bswat\s*you\b",
    r"\bswatting\b",
    # ── Illegal content ───────────────────────────────────
    r"\bbuy\s*(drugs|weed|cocaine|meth|heroin)\b",
    r"\bsell\s*(drugs|weed|cocaine|meth|heroin)\b",
    r"\bhow\s*to\s*make\s*(bomb|explosive|weapon)\b",

    # ── Arabic slurs & harassment (English + Arabic script) ──
    # Transliterated (Latin)
    r"\bkahba\b",
    r"\bsharmuta\b",
    r"\bsharmouta\b",
    r"\bkuss\b",
    r"\bkuss\s*ummak\b",
    r"\bkuss\s*ukhtk\b",
    r"\bibn\s*el\s*sharmouta\b",
    r"\bweld\s*el\s*sharmouta\b",
    r"\bhaywaan\b",
    r"\bkalb\b",
    r"\bklab\b",
    r"\bkhanzeer\b",
    r"\byel3an\s*(ummak|abuk|deenak)\b",
    r"\bla3nat\b",
    # Arabic script
    r"قحبة",       # kahba - whore
    r"شرموطة",     # sharmuta - slut
    r"شرموطه",     # sharmuta variant
    r"كس",         # kuss - vulgar
    r"كس امك",     # kuss ummak
    r"كس اختك",    # kuss ukhtk
    r"ابن الشرموطة", # ibn el sharmuta
    r"ولد الشرموطة", # weld el sharmuta
    r"حيوان",      # haywaan - animal
    r"كلب",        # kalb - dog
    r"كلاب",       # klab - dogs
    r"خنزير",      # khanzeer - pig
    r"يلعن امك",   # yel3an ummak
    r"يلعن ابوك",  # yel3an abuk
    r"يلعن دينك",  # yel3an deenak
    r"لعنة",       # la3na - curse
    r"عاهرة",      # aahira - prostitute
    r"زبالة",      # zbala - garbage (used as insult)
    r"منيوك",      # manyuk - vulgar insult
    r"أنت غبي",    # anta ghabi - you're stupid (aggressive)
    r"روح انيك",   # go f*** yourself

    # ── Somali slurs & harassment ─────────────────────────
    r"\bdhilo\b",
    r"\bgaalo\b",
    r"\bgaal\b",
    r"\bqaniis\b",
    r"\bkacsi\b",
    r"\bkufsiga\b",
    r"\bwaryaa\s*dhilo\b",
    r"\bnaag\s*xun\b",
    r"\bina\s*dhilo\b",
    r"\bcun\b",
    r"\bhooyo\b",
    r"\baabo\b",
    r"\bwaryaa\s*cun\b",
    r"\bcun\s*iska\b",
    r"\bhooyada\s*was\b",
    r"\bhoyada\s*was\b",
    r"\bhooyo\s*was\b",
    r"\bhoyo\s*was\b",
    r"\babhaa\s*was\b",
    r"\babahaa\s*was\b",
    r"\baabbaha\s*was\b",
    r"\bhooyada\b",
    r"\bhoyada\b",
    r"\babhaa\b",
    r"\babahaa\b",
    # "was" combined with Somali words = bad word
    r"\bwas\s*(hooyo|aabo|abahaa|hooyada|naag|wiil|nin|gabar)\b",
    r"\b(hooyo|aabo|abahaa|hooyada|naag|wiil|nin|gabar)\s*was\b",
    r"\bwas\s*ku\b",
    r"\bwas\s*la\b",
]

# Compile all patterns once for performance
_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in BANNED_WORDS]


def contains_banned_word(text: str) -> str | None:
    """Returns the matched pattern string if a banned word is found, else None."""
    # Normalize common l33tspeak substitutions for Latin text
    normalized = text.lower()
    normalized = normalized.replace("@", "a").replace("3", "e").replace("1", "i") \
                           .replace("0", "o").replace("$", "s").replace("!", "i") \
                           .replace("9", "g").replace("+", "t")
    for pattern in _compiled_patterns:
        # Check original (catches Arabic script), normalized (catches l33tspeak), and lowercase
        if pattern.search(text) or pattern.search(normalized):
            return pattern.pattern
    return None


def mod_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_messages
    return app_commands.check(predicate)


class ViolationTicketView(ui.View):
    """Buttons for violation tickets — close and ban."""

    def __init__(self, violator_id: int):
        super().__init__(timeout=None)
        self.violator_id = violator_id

    @ui.button(label="✅ Restore Access", style=discord.ButtonStyle.success, custom_id="vt_restore")
    async def restore(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        await interaction.response.defer()

        guild = interaction.guild
        member = None

        # Try to get member from stored violator_id
        if self.violator_id:
            member = guild.get_member(self.violator_id)

        # Fallback: parse from channel topic
        if not member and interaction.channel.topic:
            import re
            match = re.search(r"Opened by (.+)#(\d+)", interaction.channel.topic)
            if not match:
                # Try to find by channel name
                ch_name = interaction.channel.name  # violation-username
                parts = ch_name.split("-")
                if len(parts) >= 2:
                    name_part = "-".join(parts[1:])
                    for m in guild.members:
                        if m.display_name.lower().replace(" ", "-")[:12] == name_part[:12]:
                            member = m
                            break

        if not member:
            await interaction.followup.send("⚠️ Could not find the member. Use `/restoreaccess @member` instead.", ephemeral=True)
            return

        # Clear all channel overrides
        restored = 0
        for channel in guild.channels:
            overwrite = channel.overwrites_for(member)
            if overwrite.read_messages is False or overwrite.send_messages is False or overwrite.connect is False:
                try:
                    await channel.set_permissions(member, overwrite=None, reason=f"Access restored by {interaction.user}")
                    restored += 1
                except Exception:
                    pass

        # Give back New Player role
        role = discord.utils.get(guild.roles, name="🎮 New Player")
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="Access restored")
            except Exception:
                pass

        # Remove timeout (unmute)
        try:
            await member.timeout(None, reason=f"Unmuted by {interaction.user} via restore access")
        except Exception:
            pass

        _warnings.pop(member.id, None)

        await interaction.followup.send(f"✅ Access restored for {member.mention} — {restored} overrides cleared. Closing ticket in 5 seconds...")
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Violation resolved by {interaction.user}")

    @ui.button(label="🔨 Ban & Close", style=discord.ButtonStyle.danger, custom_id="vt_ban")
    async def ban_close(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("🚫 You need Ban Members permission.", ephemeral=True)
            return
        guild = interaction.guild
        member = guild.get_member(self.violator_id)
        if member:
            try:
                await member.ban(reason=f"Banned by {interaction.user} via violation ticket", delete_message_days=1)
            except Exception:
                pass
        await interaction.response.send_message(f"🔨 {member.mention if member else 'User'} has been banned. Closing ticket...")
        import asyncio
        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Violation banned by {interaction.user}")

    @ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.secondary, custom_id="vt_close")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


class ModerationCog(commands.Cog, name="Moderation"):
    """Server moderation tools for staff."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(ViolationTicketView(0))  # register persistent view

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

        # ── 1. Word filter check (single + last 5 messages combined) ──
        buf_key = (message.author.id, message.channel.id)
        _msg_buffer[buf_key].append(message.content)
        combined_text = " ".join(_msg_buffer[buf_key])

        matched = contains_banned_word(message.content) or contains_banned_word(combined_text)
        if matched:
            member = message.author
            guild  = message.guild

            # Delete the offending message
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

            # Clear their message buffer
            _msg_buffer.pop(buf_key, None)

            # Apply timeout
            try:
                until = datetime.now(timezone.utc) + timedelta(minutes=FILTER_MUTE_MINUTES)
                await member.timeout(until, reason="Auto-mute: banned word used")
            except discord.Forbidden:
                pass

            # Revoke all channel access immediately — no warnings
            await self.revoke_access(guild, member)

            # Auto-open a ticket with the violation details
            await self.auto_violation_ticket(guild, member, message.content, matched, 1)

            # Public notice in channel
            embed = discord.Embed(
                title="🚫 Violation Detected",
                description=(
                    f"{member.mention} violated server rules and has had their **access revoked**.\n\n"
                    f"A staff member will review their case in the violation ticket."
                ),
                color=0xFF0000,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Auto-Mod • PIRATES")
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
                until = datetime.now(timezone.utc) + timedelta(hours=1)
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
            # ── Warning 3: Revoke access, lock to ticket ──
            try:
                dm = discord.Embed(
                    title="🔒 Access Revoked — Free Fire Squad",
                    description=(
                        f"Your access to **{guild.name}** has been **revoked**.\n\n"
                        f"**Reason:** {reason}\n"
                        f"**Warnings received:** {count}\n\n"
                        f"You can only access your violation ticket. "
                        f"A staff member will review your case."
                    ),
                    color=0xFF0000,
                )
                await member.send(embed=dm)
            except discord.Forbidden:
                pass

            # Remove all roles except @everyone
            try:
                roles_to_remove = [r for r in member.roles if r.name != "@everyone" and not r.managed]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Access revoked: 3 warnings")
            except discord.Forbidden:
                pass

            # Deny access to all channels except their violation ticket
            try:
                for channel in guild.channels:
                    # Skip the violation ticket channel
                    if hasattr(channel, 'topic') and channel.topic and str(member.id) in str(channel.topic):
                        continue
                    if channel.name.startswith(f"violation-{member.display_name[:12].lower().replace(' ', '-')}"):
                        continue
                    try:
                        await channel.set_permissions(
                            member,
                            read_messages=False,
                            send_messages=False,
                            connect=False,
                            reason="Access revoked: 3 warnings",
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            except Exception as e:
                log.error(f"Failed to revoke channel access: {e}")

            _warnings.pop(uid, None)
            await self.log_action(guild, "🔒 ACCESS REVOKED (3 warnings)", member, issuer, reason)

        return count

    async def revoke_access(self, guild: discord.Guild, member: discord.Member):
        """Immediately revoke all channel access — member can only see their violation ticket."""
        try:
            roles_to_remove = [r for r in member.roles if r.name != "@everyone" and not r.managed]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Access revoked: rule violation")
        except discord.Forbidden:
            pass

        for channel in guild.channels:
            if channel.name.startswith(f"violation-{member.display_name[:12].lower().replace(' ', '-')}"):
                continue
            try:
                await channel.set_permissions(
                    member,
                    read_messages=False,
                    send_messages=False,
                    connect=False,
                    reason="Access revoked: rule violation",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        try:
            dm = discord.Embed(
                title="🔒 Access Revoked — PIRATES",
                description=(
                    f"Your access to **{guild.name}** has been **revoked** due to a rule violation.\n\n"
                    f"You can only access your violation ticket.\n"
                    f"A staff member will review your case shortly."
                ),
                color=0xFF0000,
            )
            await member.send(embed=dm)
        except discord.Forbidden:
            pass

        await self.log_action(guild, "🔒 ACCESS REVOKED", member, self.bot.user, "Rule/TOS violation")

    async def auto_violation_ticket(
        self,
        guild: discord.Guild,
        member: discord.Member,
        original_message: str,
        matched_pattern: str,
        warning_count: int,
    ):
        """Auto-create a ticket channel when a TOS/rule violation is detected."""
        try:
            # Find or create tickets category
            tickets_cat = discord.utils.get(guild.categories, name="🎫 TICKETS")
            if not tickets_cat:
                tickets_cat = await guild.create_category("🎫 TICKETS")

            ticket_name = f"violation-{member.display_name[:12].lower().replace(' ', '-')}"

            # Check if violation ticket already open for this user
            for ch in tickets_cat.text_channels:
                if ch.name == ticket_name:
                    # Update existing ticket
                    await ch.send(
                        f"⚠️ **New violation detected** — Warning #{warning_count}/3\n"
                        f"Message: ```{original_message[:500]}```"
                    )
                    return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=True),  # can see and respond in ticket
            }
            for rn in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
                r = discord.utils.get(guild.roles, name=rn)
                if r:
                    overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

            ticket_ch = await guild.create_text_channel(
                ticket_name,
                category=tickets_cat,
                overwrites=overwrites,
                topic=f"Auto-violation ticket | {member} | Warning {warning_count}/3",
            )

            # Determine violation type
            if any(x in matched_pattern for x in ["nitro", "gift", "steam", "click"]):
                vtype = "🎣 Scam/Phishing"
            elif any(x in matched_pattern for x in ["dox", "ip", "address"]):
                vtype = "🔍 Doxxing Attempt"
            elif any(x in matched_pattern for x in ["kill", "swat", "find you"]):
                vtype = "⚠️ Threat"
            elif any(x in matched_pattern for x in ["drug", "bomb", "weapon"]):
                vtype = "🚨 Illegal Content"
            elif any(x in matched_pattern for x in ["cp", "child", "loli", "shota"]):
                vtype = "🚫 CSAM / TOS Violation"
            else:
                vtype = "🚫 Hate Speech / Slur"

            # Ping staff
            staff_pings = []
            for rn in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
                r = discord.utils.get(guild.roles, name=rn)
                if r: staff_pings.append(r.mention)

            embed = discord.Embed(
                title="🚨 Auto-Violation Ticket",
                color=0xFF0000,
                timestamp=datetime.utcnow(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="👤 Violator",      value=f"{member.mention} (`{member}`)", inline=True)
            embed.add_field(name="🆔 User ID",        value=str(member.id),                  inline=True)
            embed.add_field(name="⚠️ Warning Count",  value=f"{warning_count}/3",            inline=True)
            embed.add_field(name="🏷️ Violation Type", value=vtype,                           inline=True)
            embed.add_field(name="📅 Time",           value=f"<t:{int(datetime.utcnow().timestamp())}:F>", inline=True)
            embed.add_field(
                name="💬 Offending Message",
                value=f"```{original_message[:900]}```",
                inline=False,
            )
            embed.add_field(
                name="⚖️ Suggested Actions",
                value=(
                    f"`/warn @{member.display_name}` — Issue manual warning\n"
                    f"`/mute @{member.display_name} 60` — Mute for 1 hour\n"
                    f"`/ban @{member.display_name}` — Permanent ban\n"
                    f"`/restoreaccess @{member.display_name}` — Restore access\n"
                    f"Use the **🔒 Close Ticket** button below when resolved."
                ),
                inline=False,
            )
            embed.set_footer(text="Auto-Mod System • PIRATES")

            await ticket_ch.send(
                content=f"🚨 **Auto-violation detected!** {' '.join(staff_pings)}",
                embed=embed,
                view=ViolationTicketView(member.id),
            )

        except Exception as e:
            log.error(f"Auto violation ticket error: {e}")

    async def log_action(self, guild: discord.Guild, action: str, target, moderator, reason: str):
        """Send a log embed to the mod-log channel."""
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
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
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

    # ── /restoreaccess ────────────────────────────────────
    @app_commands.command(name="restoreaccess", description="Restore a member's channel access 🔓")
    @app_commands.describe(member="Member to restore access for")
    @mod_only()
    async def slash_restoreaccess(self, interaction: discord.Interaction, member: discord.Member):
        guild = interaction.guild
        await interaction.response.defer(ephemeral=True)

        # Remove all channel-specific permission overwrites for this member
        restored = 0
        for channel in guild.channels:
            overwrite = channel.overwrites_for(member)
            if overwrite.read_messages is False or overwrite.send_messages is False:
                try:
                    await channel.set_permissions(member, overwrite=None, reason=f"Access restored by {interaction.user}")
                    restored += 1
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Give back New Player role
        new_player = discord.utils.get(guild.roles, name="🎮 New Player")
        if new_player and new_player not in member.roles:
            try:
                await member.add_roles(new_player, reason="Access restored")
            except discord.Forbidden:
                pass

        # Remove timeout (unmute)
        try:
            await member.timeout(None, reason=f"Unmuted by {interaction.user}")
        except discord.Forbidden:
            pass

        # Clear warnings
        _warnings.pop(member.id, None)

        await interaction.followup.send(
            f"✅ Access restored for **{member.display_name}** — {restored} channel overrides cleared.",
            ephemeral=True,
        )
        await self.log_action(guild, "🔓 Access Restored", member, interaction.user, "Manual restore by staff")

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
