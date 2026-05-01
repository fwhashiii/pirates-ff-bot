"""
📸 Clips & Highlights Cog
Auto-detects video clips and highlights them
Commands: /highlight /tophighlights
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import logging

log = logging.getLogger("cog.clips")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif"}
CLIP_CHANNEL_NAMES = ["clips", "highlights", "🎬", "📸", "gameplay"]


class ClipsCog(commands.Cog, name="Clips"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._highlights: dict[int, list] = {}  # {guild_id: [message_ids]}

    def _is_clip(self, message: discord.Message) -> bool:
        """Check if message contains a video clip."""
        for attachment in message.attachments:
            ext = "." + attachment.filename.rsplit(".", 1)[-1].lower() if "." in attachment.filename else ""
            if ext in VIDEO_EXTENSIONS:
                return True
        # Check for video links
        content = message.content.lower()
        if any(x in content for x in ["youtube.com/watch", "youtu.be/", "tiktok.com", "streamable.com", "medal.tv"]):
            return True
        return False

    def _is_clips_channel(self, channel: discord.TextChannel) -> bool:
        """Check if channel is a clips/highlights channel."""
        name = channel.name.lower()
        return any(x in name for x in CLIP_CHANNEL_NAMES)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Auto-react to clips in clips channels
        if self._is_clips_channel(message.channel) and self._is_clip(message):
            try:
                await message.add_reaction("🔥")
                await message.add_reaction("👍")
                await message.add_reaction("😮")
            except Exception:
                pass

    @app_commands.command(name="highlight", description="Highlight a clip in the highlights channel ⭐")
    @app_commands.describe(message_id="Message ID of the clip to highlight")
    async def slash_highlight(self, interaction: discord.Interaction, message_id: str):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        try:
            msg = await interaction.channel.fetch_message(int(message_id))
        except Exception:
            await interaction.response.send_message("❌ Message not found.", ephemeral=True)
            return

        # Find highlights channel
        highlights_ch = None
        for ch in interaction.guild.text_channels:
            if "highlight" in ch.name.lower() or "clip" in ch.name.lower():
                highlights_ch = ch
                break

        if not highlights_ch:
            await interaction.response.send_message("❌ No highlights channel found. Create a channel with 'highlights' or 'clips' in the name.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⭐ Highlighted Clip",
            description=msg.content or "Check out this clip!",
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(name=msg.author.display_name, icon_url=msg.author.display_avatar.url)
        embed.add_field(name="📍 Original", value=f"[Jump to message]({msg.jump_url})", inline=True)
        embed.add_field(name="📅 Posted", value=f"<t:{int(msg.created_at.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"Highlighted by {interaction.user.display_name}")

        files = []
        for attachment in msg.attachments:
            ext = "." + attachment.filename.rsplit(".", 1)[-1].lower() if "." in attachment.filename else ""
            if ext in VIDEO_EXTENSIONS:
                try:
                    f = await attachment.to_file()
                    files.append(f)
                except Exception:
                    pass

        await highlights_ch.send(embed=embed, files=files if files else None)
        await interaction.response.send_message(f"⭐ Clip highlighted in {highlights_ch.mention}!", ephemeral=True)

    @app_commands.command(name="setupclips", description="Set up the clips channel with auto-reactions 🎬")
    async def slash_setupclips(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("🚫 Need Manage Channels permission.", ephemeral=True)
            return

        guild = interaction.guild
        clips_ch = discord.utils.get(guild.text_channels, name="🎬┃clips")
        if not clips_ch:
            clips_ch = await guild.create_text_channel(
                "🎬┃clips",
                topic="Share your best Free Fire clips! Bot will auto-react 🔥",
            )

        highlights_ch = discord.utils.get(guild.text_channels, name="⭐┃highlights")
        if not highlights_ch:
            highlights_ch = await guild.create_text_channel(
                "⭐┃highlights",
                topic="The best clips from the server, curated by staff",
            )

        embed = discord.Embed(
            title="🎬 Clips Channel Setup!",
            description=(
                f"**Clips channel:** {clips_ch.mention}\n"
                f"**Highlights channel:** {highlights_ch.mention}\n\n"
                f"The bot will automatically react 🔥👍😮 to any video clips posted in {clips_ch.mention}.\n"
                f"Staff can use `/highlight <message_id>` to feature clips in {highlights_ch.mention}."
            ),
            color=0xFF4500,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ClipsCog(bot))
