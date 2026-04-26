"""
📡 Live & Updates Cog
- /golive  — announce you're streaming
- /endlive — mark stream as ended
- /update  — staff post a game/server update
- Auto-posts Free Fire update news to #game-updates
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import feedparser
import logging

log = logging.getLogger("cog.live")

# Track active streams: {user_id: message_id}
_active_streams: dict[int, int] = {}

# Track posted update URLs so we don't double-post
_posted_updates: set[str] = set()

# RSS feeds for game updates
UPDATE_FEEDS = [
    "https://freefireinfo.in/feed/",
    "https://gamingonphone.com/feed/",
]

PLATFORM_COLORS = {
    "YouTube":  0xFF0000,
    "Twitch":   0x9146FF,
    "TikTok":   0x000000,
    "Facebook": 0x1877F2,
    "Other":    0xFF4500,
}

PLATFORM_ICONS = {
    "YouTube":  "▶️",
    "Twitch":   "🟣",
    "TikTok":   "🎵",
    "Facebook": "📘",
    "Other":    "📡",
}


class LiveCog(commands.Cog, name="Live"):
    """Live stream announcements and game update feeds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_feed_task.start()

    def cog_unload(self):
        self.update_feed_task.cancel()

    def get_channel_by_name(self, guild: discord.Guild, name: str):
        return discord.utils.get(guild.text_channels, name=name)

    # ── /golive ───────────────────────────────────────────
    @app_commands.command(name="golive", description="Announce you're going live! 🔴")
    @app_commands.describe(
        platform="Where are you streaming?",
        title="Stream title",
        link="Your stream link",
        game="What are you playing? (default: Free Fire)",
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="▶️ YouTube",  value="YouTube"),
        app_commands.Choice(name="🟣 Twitch",   value="Twitch"),
        app_commands.Choice(name="🎵 TikTok",   value="TikTok"),
        app_commands.Choice(name="📘 Facebook", value="Facebook"),
        app_commands.Choice(name="📡 Other",    value="Other"),
    ])
    async def slash_golive(
        self,
        interaction: discord.Interaction,
        platform: str,
        title: str,
        link: str,
        game: str = "Free Fire 🔥",
    ):
        guild = interaction.guild
        live_ch = self.get_channel_by_name(guild, "🔴│live-now")
        if not live_ch:
            live_ch = interaction.channel

        icon = PLATFORM_ICONS.get(platform, "📡")
        color = PLATFORM_COLORS.get(platform, 0xFF4500)

        embed = discord.Embed(
            title=f"🔴 {interaction.user.display_name} is LIVE!",
            description=f"**{title}**\n\n[🔗 Watch Now]({link})",
            color=color,
            url=link,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(name=f"{icon} Platform", value=platform, inline=True)
        embed.add_field(name="🎮 Game",          value=game,     inline=True)
        embed.add_field(name="🔗 Link",          value=f"[Click here]({link})", inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="React 👀 to tune in! • Free Fire Squad")

        # Post in live channel
        msg = await live_ch.send(
            content="@here 🔴 **Someone just went LIVE!**",
            embed=embed,
        )
        await msg.add_reaction("👀")
        await msg.add_reaction("🔥")
        await msg.add_reaction("🏆")

        _active_streams[interaction.user.id] = msg.id

        await interaction.response.send_message(
            f"✅ Your stream has been announced in {live_ch.mention}! BOOYAH! 🏆",
            ephemeral=True,
        )

    # ── /endlive ──────────────────────────────────────────
    @app_commands.command(name="endlive", description="Mark your stream as ended 📴")
    async def slash_endlive(self, interaction: discord.Interaction):
        guild = interaction.guild
        live_ch = self.get_channel_by_name(guild, "🔴│live-now")
        if not live_ch:
            await interaction.response.send_message("⚠️ Live channel not found.", ephemeral=True)
            return

        msg_id = _active_streams.pop(interaction.user.id, None)
        if msg_id:
            try:
                msg = await live_ch.fetch_message(msg_id)
                # Edit the embed to show stream ended
                embed = msg.embeds[0] if msg.embeds else None
                if embed:
                    ended_embed = discord.Embed(
                        title=f"📴 {interaction.user.display_name}'s stream has ended",
                        description=embed.description,
                        color=0x7F8C8D,
                        timestamp=datetime.utcnow(),
                    )
                    ended_embed.set_author(
                        name=interaction.user.display_name,
                        icon_url=interaction.user.display_avatar.url,
                    )
                    ended_embed.set_footer(text="Stream ended • Thanks for watching!")
                    await msg.edit(content="📴 **Stream ended**", embed=ended_embed)
            except Exception:
                pass

        await interaction.response.send_message(
            "📴 Your stream has been marked as ended. Thanks for streaming! 🔥",
            ephemeral=True,
        )

    # ── /update ───────────────────────────────────────────
    @app_commands.command(name="update", description="Post a server or game update 📣")
    @app_commands.describe(
        title="Update title",
        description="What's the update?",
        category="Type of update",
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="🎮 Game Update",    value="Game Update"),
        app_commands.Choice(name="🏆 Event",          value="Event"),
        app_commands.Choice(name="🛡️ Server Update",  value="Server Update"),
        app_commands.Choice(name="📢 Announcement",   value="Announcement"),
        app_commands.Choice(name="⚠️ Maintenance",    value="Maintenance"),
    ])
    async def slash_update(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        category: str = "Announcement",
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        guild = interaction.guild
        update_ch = self.get_channel_by_name(guild, "🔔│game-updates")
        if not update_ch:
            update_ch = interaction.channel

        color_map = {
            "Game Update":    0x00BFFF,
            "Event":          0xFFD700,
            "Server Update":  0x9B59B6,
            "Announcement":   0xFF4500,
            "Maintenance":    0xFF0000,
        }

        embed = discord.Embed(
            title=f"📣 {category}: {title}",
            description=description,
            color=color_map.get(category, 0xFF4500),
            timestamp=datetime.utcnow(),
        )
        embed.set_author(
            name=f"Posted by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_footer(text="Free Fire Squad • Stay updated 🔥")

        await update_ch.send(content="🔔 **New Update!**", embed=embed)
        await interaction.response.send_message(
            f"✅ Update posted in {update_ch.mention}!", ephemeral=True
        )

    # ── /livestatus ───────────────────────────────────────
    @app_commands.command(name="livestatus", description="See who's currently live 🔴")
    async def slash_livestatus(self, interaction: discord.Interaction):
        if not _active_streams:
            await interaction.response.send_message(
                "📴 Nobody is live right now. Be the first to go live with `/golive`!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🔴 Currently Live",
            color=0xFF0000,
            timestamp=datetime.utcnow(),
        )
        for uid in _active_streams:
            member = interaction.guild.get_member(uid)
            if member:
                embed.add_field(
                    name=member.display_name,
                    value="🔴 Live now",
                    inline=True,
                )
        embed.set_footer(text="Use /golive to announce your stream!")
        await interaction.response.send_message(embed=embed)

    # ── Auto-post game updates every hour ─────────────────
    @tasks.loop(hours=1)
    async def update_feed_task(self):
        for guild in self.bot.guilds:
            ch = self.get_channel_by_name(guild, "🔔│game-updates")
            if not ch:
                continue
            for feed_url in UPDATE_FEEDS[:1]:
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:2]:
                        url = entry.get("link", "")
                        if url and url not in _posted_updates:
                            _posted_updates.add(url)
                            embed = discord.Embed(
                                title=entry.get("title", "Free Fire Update"),
                                url=url,
                                description=(entry.get("summary", "")[:250] + "…") if entry.get("summary") else "",
                                color=0x00BFFF,
                                timestamp=datetime.utcnow(),
                            )
                            embed.set_author(name="🔔 Free Fire Update")
                            embed.set_footer(text="freefireinfo.in")
                            await ch.send(embed=embed)
                except Exception as e:
                    log.error(f"Update feed error: {e}")

    @update_feed_task.before_loop
    async def before_update_feed(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LiveCog(bot))
