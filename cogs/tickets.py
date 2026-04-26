"""
🎫 Ticketing System
- Bot posts a ticket panel in #support with category buttons
- Member clicks a category → private ticket channel created
- Staff can claim, close, and transcript tickets
- Closed tickets get saved as a transcript
"""

import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import logging
from datetime import datetime

log = logging.getLogger("cog.tickets")

# Active tickets: {channel_id: {user_id, category, claimed_by}}
_active_tickets: dict[int, dict] = {}

TICKET_CATEGORIES = {
    "🛡️ Report a Member":    ("report",    0xFF4500, "Report someone for breaking server rules"),
    "🔇 Appeal a Mute/Ban":  ("appeal",    0xFF0000, "Appeal a moderation action against you"),
    "🤝 Staff Application":  ("staffapp",  0x9B59B6, "Apply to become a moderator or staff"),
    "💬 Server Suggestion":  ("suggest",   0x2ECC71, "Suggest improvements for the server"),
    "❓ General Help":       ("general",   0x00BFFF, "Any other questions for staff"),
}


class TicketCategorySelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=data[0], description=data[2], emoji=name.split()[0])
            for name, data in TICKET_CATEGORIES.items()
        ]
        super().__init__(
            placeholder="📋 Select a ticket category...",
            options=options,
            custom_id="ticket_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        category_key = self.values[0]
        category_name = next(k for k, v in TICKET_CATEGORIES.items() if v[0] == category_key)
        color = next(v[1] for v in TICKET_CATEGORIES.values() if v[0] == category_key)

        guild  = interaction.guild
        member = interaction.user

        # Check if member already has an open ticket
        for ch_id, data in _active_tickets.items():
            if data["user_id"] == member.id:
                ch = guild.get_channel(ch_id)
                if ch:
                    await interaction.response.send_message(
                        f"⚠️ You already have an open ticket: {ch.mention}",
                        ephemeral=True,
                    )
                    return

        # Find or create tickets category
        tickets_cat = discord.utils.get(guild.categories, name="🎫 TICKETS")
        if not tickets_cat:
            tickets_cat = await guild.create_category("🎫 TICKETS")

        # Create private ticket channel
        ticket_name = f"ticket-{category_key}-{member.display_name[:12].lower().replace(' ', '-')}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        for rn in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
            r = discord.utils.get(guild.roles, name=rn)
            if r:
                overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

        ticket_ch = await guild.create_text_channel(
            ticket_name,
            category=tickets_cat,
            overwrites=overwrites,
            topic=f"{category_name} | Opened by {member}",
        )

        _active_tickets[ticket_ch.id] = {
            "user_id":    member.id,
            "category":   category_name,
            "claimed_by": None,
            "opened_at":  str(datetime.utcnow()),
        }

        # Post ticket info embed
        embed = discord.Embed(
            title=f"{category_name}",
            description=(
                f"Hey {member.mention}! Your ticket has been created.\n\n"
                f"**Please describe your issue in detail** and a staff member will assist you shortly.\n\n"
                f"Use the buttons below to manage this ticket."
            ),
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name=f"Ticket by {member.display_name}", icon_url=member.display_avatar.url)
        embed.set_footer(text="Free Fire Squad • PIRATES Support")

        # Ping staff
        staff_pings = []
        for rn in ["🛡️ Moderator", "⚔️ Captain"]:
            r = discord.utils.get(guild.roles, name=rn)
            if r:
                staff_pings.append(r.mention)

        await ticket_ch.send(
            content=f"{member.mention} {' '.join(staff_pings)}",
            embed=embed,
            view=TicketControlView(),
        )

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {ticket_ch.mention}",
            ephemeral=True,
        )

        # Log
        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        log_ch = guild.get_channel(log_ch_id)
        if log_ch:
            log_emb = discord.Embed(
                title="🎫 Ticket Opened",
                color=color,
                timestamp=datetime.utcnow(),
            )
            log_emb.add_field(name="User",     value=f"{member} ({member.id})", inline=True)
            log_emb.add_field(name="Category", value=category_name,             inline=True)
            log_emb.add_field(name="Channel",  value=ticket_ch.mention,         inline=True)
            await log_ch.send(embed=log_emb)


class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="✋ Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return
        data = _active_tickets.get(interaction.channel_id)
        if data:
            data["claimed_by"] = interaction.user.id
        await interaction.response.send_message(
            f"✋ **{interaction.user.display_name}** has claimed this ticket.",
        )
        button.disabled = True
        await interaction.message.edit(view=self)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            # Allow the ticket owner to close their own ticket
            data = _active_tickets.get(interaction.channel_id)
            if not data or data["user_id"] != interaction.user.id:
                await interaction.response.send_message("🚫 You can't close this ticket.", ephemeral=True)
                return

        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await save_transcript(interaction.channel, interaction.guild)
        import asyncio
        await asyncio.sleep(5)
        _active_tickets.pop(interaction.channel_id, None)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

    @ui.button(label="📄 Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript")
    async def transcript(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        txt = await build_transcript(interaction.channel)
        file = discord.File(
            fp=__import__("io").StringIO(txt),
            filename=f"transcript-{interaction.channel.name}.txt",
        )
        await interaction.followup.send("📄 Transcript:", file=file, ephemeral=True)


async def build_transcript(channel: discord.TextChannel) -> str:
    lines = [f"=== Transcript: {channel.name} ===\n"]
    async for msg in channel.history(limit=500, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = msg.content or "[embed/attachment]"
        lines.append(f"[{ts}] {msg.author.display_name}: {content}")
    return "\n".join(lines)


async def save_transcript(channel: discord.TextChannel, guild: discord.Guild):
    """Save transcript to staff log channel."""
    log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
    log_ch = guild.get_channel(log_ch_id)
    if not log_ch:
        return
    txt = await build_transcript(channel)
    file = discord.File(
        fp=__import__("io").StringIO(txt),
        filename=f"transcript-{channel.name}.txt",
    )
    data = _active_tickets.get(channel.id, {})
    embed = discord.Embed(
        title="🎫 Ticket Closed",
        color=0x7F8C8D,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="Channel",  value=channel.name,              inline=True)
    embed.add_field(name="Category", value=data.get("category", "?"), inline=True)
    embed.add_field(name="Opened",   value=data.get("opened_at", "?"), inline=True)
    await log_ch.send(embed=embed, file=file)


class TicketsCog(commands.Cog, name="Tickets"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(TicketPanelView())
        bot.add_view(TicketControlView())

    @commands.Cog.listener()
    async def on_ready(self):
        await self._post_ticket_panel()

    async def _post_ticket_panel(self):
        for guild in self.bot.guilds:
            # Find support channel
            support_ch = discord.utils.get(guild.text_channels, name="🎫┃ꜱᴜᴘᴘᴏʀᴛ")
            if not support_ch:
                support_ch = discord.utils.get(guild.text_channels, name="🎫│support")
            if not support_ch:
                continue

            # Check if panel already posted
            history = [m async for m in support_ch.history(limit=5)]
            for msg in history:
                if msg.author == self.bot.user and msg.components:
                    return

            await support_ch.purge(limit=5, check=lambda m: m.author == self.bot.user)

            embed = discord.Embed(
                title="🎫 PIRATES Support Center",
                description=(
                    "Need help or want to reach staff? Open a ticket below.\n\n"
                    "**Select a category:**\n\n"
                    "🛡️ **Report a Member** — Someone breaking server rules\n"
                    "🔇 **Appeal a Mute/Ban** — Contest a moderation action\n"
                    "🤝 **Staff Application** — Apply to join the mod team\n"
                    "💬 **Server Suggestion** — Ideas to improve the server\n"
                    "❓ **General Help** — Anything else\n\n"
                    "*Tickets are private — only you and staff can see them.*"
                ),
                color=0xFF4500,
            )
            embed.set_footer(text="PIRATES Community Server • Response time: < 24 hours")
            await support_ch.send(embed=embed, view=TicketPanelView())
            log.info(f"Posted ticket panel in {guild.name}")

    # ── /ticket ───────────────────────────────────────────
    @app_commands.command(name="ticket", description="Open a support ticket 🎫")
    async def slash_ticket(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Open a Ticket",
            description="Select a category to open a support ticket.",
            color=0xFF4500,
        )
        await interaction.response.send_message(embed=embed, view=TicketPanelView(), ephemeral=True)

    # ── /closeticket ──────────────────────────────────────
    @app_commands.command(name="closeticket", description="Close the current ticket 🔒")
    async def slash_closeticket(self, interaction: discord.Interaction):
        data = _active_tickets.get(interaction.channel_id)
        if not data:
            await interaction.response.send_message("⚠️ This is not a ticket channel.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_messages and data["user_id"] != interaction.user.id:
            await interaction.response.send_message("🚫 You can't close this ticket.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await save_transcript(interaction.channel, interaction.guild)
        import asyncio
        await asyncio.sleep(5)
        _active_tickets.pop(interaction.channel_id, None)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

    # ── /tickets ──────────────────────────────────────────
    @app_commands.command(name="tickets", description="View all open tickets 📋")
    async def slash_tickets(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return
        if not _active_tickets:
            await interaction.response.send_message("✅ No open tickets.", ephemeral=True)
            return
        embed = discord.Embed(title="🎫 Open Tickets", color=0xFF4500, timestamp=datetime.utcnow())
        for ch_id, data in _active_tickets.items():
            ch = interaction.guild.get_channel(ch_id)
            member = interaction.guild.get_member(data["user_id"])
            claimed = interaction.guild.get_member(data["claimed_by"]) if data["claimed_by"] else None
            embed.add_field(
                name=ch.name if ch else f"#{ch_id}",
                value=(
                    f"**User:** {member.mention if member else 'Unknown'}\n"
                    f"**Category:** {data['category']}\n"
                    f"**Claimed:** {claimed.display_name if claimed else 'Unclaimed'}"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
