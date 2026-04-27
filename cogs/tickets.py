"""
🎫 Ticketing System — Fixed duplicate ticket bug
Uses a single button instead of select menu to prevent double-fire
"""

import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import logging
from datetime import datetime

log = logging.getLogger("cog.tickets")

_active_tickets: dict[int, dict] = {}
_creating: set[int] = set()

TICKET_CATEGORIES = {
    "🛡️ Report a Member":   ("report",   0xFF4500, "Report someone for breaking server rules"),
    "🔇 Appeal a Mute/Ban": ("appeal",   0xFF0000, "Appeal a moderation action against you"),
    "🤝 Staff Application": ("staffapp", 0x9B59B6, "Apply to become a moderator or staff"),
    "💬 Server Suggestion": ("suggest",  0x2ECC71, "Suggest improvements for the server"),
    "❓ General Help":      ("general",  0x00BFFF, "Any other questions for staff"),
}


async def create_ticket(interaction: discord.Interaction, category_key: str):
    """Core ticket creation — called once per interaction."""
    member = interaction.user
    guild  = interaction.guild

    if member.id in _creating:
        return
    _creating.add(member.id)

    try:
        category_name = next(k for k, v in TICKET_CATEGORIES.items() if v[0] == category_key)
        color         = next(v[1] for v in TICKET_CATEGORIES.values() if v[0] == category_key)

        # Check for existing ticket
        tickets_cat = discord.utils.get(guild.categories, name="🎫 TICKETS")
        if tickets_cat:
            for ch in tickets_cat.text_channels:
                if member in ch.members:
                    await interaction.edit_original_response(
                        content=f"⚠️ You already have an open ticket: {ch.mention}"
                    )
                    return

        if not tickets_cat:
            tickets_cat = await guild.create_category("🎫 TICKETS")

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
            ticket_name, category=tickets_cat, overwrites=overwrites,
            topic=f"{category_name} | Opened by {member}",
        )

        _active_tickets[ticket_ch.id] = {
            "user_id":    member.id,
            "category":   category_name,
            "claimed_by": None,
            "opened_at":  str(datetime.utcnow()),
        }

        embed = discord.Embed(
            title=category_name,
            description=(
                f"Hey {member.mention}! Your ticket has been created.\n\n"
                f"Describe your issue and staff will assist you shortly.\n\n"
                f"Use the buttons below to manage this ticket."
            ),
            color=color,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name=f"Ticket by {member.display_name}", icon_url=member.display_avatar.url)
        embed.set_footer(text="PIRATES Support")

        staff_pings = []
        for rn in ["🛡️ Moderator", "⚔️ Captain"]:
            r = discord.utils.get(guild.roles, name=rn)
            if r: staff_pings.append(r.mention)

        await ticket_ch.send(
            content=f"{member.mention} {' '.join(staff_pings)}",
            embed=embed, view=TicketControlView(),
        )

        await interaction.edit_original_response(content=f"✅ Ticket created: {ticket_ch.mention}")

        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        log_ch = guild.get_channel(log_ch_id)
        if log_ch:
            e = discord.Embed(title="🎫 Ticket Opened", color=color, timestamp=datetime.utcnow())
            e.add_field(name="User",     value=f"{member} ({member.id})", inline=True)
            e.add_field(name="Category", value=category_name,             inline=True)
            e.add_field(name="Channel",  value=ticket_ch.mention,         inline=True)
            await log_ch.send(embed=e)

    except Exception as ex:
        log.error(f"Ticket creation error: {ex}")
        try:
            await interaction.edit_original_response(content="❌ Failed to create ticket. Try again.")
        except Exception:
            pass
    finally:
        _creating.discard(member.id)


# ── Category selection modal ──────────────────────────────
class TicketCategoryModal(ui.Modal, title="Open a Support Ticket"):
    category = ui.TextInput(
        label="Category",
        placeholder="report / appeal / staffapp / suggest / general",
        min_length=4,
        max_length=10,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        val = self.category.value.strip().lower()
        valid = {v[0] for v in TICKET_CATEGORIES.values()}
        if val not in valid:
            await interaction.response.send_message(
                f"❌ Invalid category. Use one of: {', '.join(valid)}", ephemeral=True
            )
            return
        await interaction.response.send_message("🎫 Creating your ticket...", ephemeral=True)
        await create_ticket(interaction, val)


# ── Open Ticket button ────────────────────────────────────
class OpenTicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🎫 Open a Ticket",
        style=discord.ButtonStyle.success,
        custom_id="open_ticket_btn",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
        # Show category selection as ephemeral message with select
        embed = discord.Embed(
            title="Select a Category",
            description=(
                "**report** — Report a member\n"
                "**appeal** — Appeal a mute/ban\n"
                "**staffapp** — Staff application\n"
                "**suggest** — Server suggestion\n"
                "**general** — General help"
            ),
            color=0xFF4500,
        )
        await interaction.response.send_message(embed=embed, view=CategorySelectView(), ephemeral=True)


class CategorySelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.select(
        placeholder="Choose a category...",
        options=[
            discord.SelectOption(label=name, value=data[0], description=data[2], emoji=name.split()[0])
            for name, data in TICKET_CATEGORIES.items()
        ],
    )
    async def select_category(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.send_message("🎫 Creating your ticket...", ephemeral=True)
        await create_ticket(interaction, select.values[0])


# ── Ticket control buttons ────────────────────────────────
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
        await interaction.response.send_message(f"✋ **{interaction.user.display_name}** claimed this ticket.")
        button.disabled = True
        await interaction.message.edit(view=self)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        data = _active_tickets.get(interaction.channel_id)
        is_owner = data and data["user_id"] == interaction.user.id
        if not interaction.user.guild_permissions.manage_messages and not is_owner:
            await interaction.response.send_message("🚫 You can't close this ticket.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Closing in 5 seconds...")
        await save_transcript(interaction.channel, interaction.guild)
        import asyncio
        await asyncio.sleep(5)
        _active_tickets.pop(interaction.channel_id, None)
        await interaction.channel.delete(reason=f"Closed by {interaction.user}")

    @ui.button(label="📄 Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript")
    async def transcript(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        txt = await build_transcript(interaction.channel)
        import io
        file = discord.File(fp=io.StringIO(txt), filename=f"transcript-{interaction.channel.name}.txt")
        await interaction.followup.send("📄 Transcript:", file=file, ephemeral=True)


async def build_transcript(channel):
    lines = [f"=== Transcript: {channel.name} ===\n"]
    async for msg in channel.history(limit=500, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[{ts}] {msg.author.display_name}: {msg.content or '[embed]'}")
    return "\n".join(lines)


async def save_transcript(channel, guild):
    log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
    log_ch = guild.get_channel(log_ch_id)
    if not log_ch:
        return
    txt = await build_transcript(channel)
    import io
    file = discord.File(fp=io.StringIO(txt), filename=f"transcript-{channel.name}.txt")
    data = _active_tickets.get(channel.id, {})
    e = discord.Embed(title="🎫 Ticket Closed", color=0x7F8C8D, timestamp=datetime.utcnow())
    e.add_field(name="Channel",  value=channel.name,              inline=True)
    e.add_field(name="Category", value=data.get("category", "?"), inline=True)
    e.add_field(name="Opened",   value=data.get("opened_at", "?"), inline=True)
    await log_ch.send(embed=e, file=file)


class TicketsCog(commands.Cog, name="Tickets"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Only register persistent views once
        bot.add_view(OpenTicketView())
        bot.add_view(TicketControlView())

    @commands.Cog.listener()
    async def on_ready(self):
        await self._post_ticket_panel()

    async def _post_ticket_panel(self):
        for guild in self.bot.guilds:
            support_ch = discord.utils.get(guild.text_channels, name="🎫┃ꜱᴜᴘᴘᴏʀᴛ")
            if not support_ch:
                continue

            # Only post if no panel exists yet
            history = [m async for m in support_ch.history(limit=5)]
            for msg in history:
                if msg.author == self.bot.user and msg.components:
                    return  # already posted

            await support_ch.purge(limit=10, check=lambda m: m.author == self.bot.user)

            embed = discord.Embed(
                title="🎫 PIRATES Support Center",
                description=(
                    "Need help or want to reach staff? Click the button below.\n\n"
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
            await support_ch.send(embed=embed, view=OpenTicketView())
            log.info(f"Posted ticket panel in {guild.name}")

    @app_commands.command(name="closeticket", description="Close the current ticket 🔒")
    async def slash_closeticket(self, interaction: discord.Interaction):
        data = _active_tickets.get(interaction.channel_id)
        if not data:
            await interaction.response.send_message("⚠️ Not a ticket channel.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_messages and data["user_id"] != interaction.user.id:
            await interaction.response.send_message("🚫 You can't close this ticket.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Closing in 5 seconds...")
        await save_transcript(interaction.channel, interaction.guild)
        import asyncio
        await asyncio.sleep(5)
        _active_tickets.pop(interaction.channel_id, None)
        await interaction.channel.delete(reason=f"Closed by {interaction.user}")

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
            embed.add_field(
                name=ch.name if ch else f"#{ch_id}",
                value=f"**User:** {member.mention if member else 'Unknown'}\n**Category:** {data['category']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
