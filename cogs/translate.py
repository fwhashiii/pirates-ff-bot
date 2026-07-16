"""
🌍 Auto-Translate Cog
- When someone sends a non-English message in general channels,
  the bot DMs the translation ONLY to members who have a different
  language set in their verification profile.
- No public translation posted — completely silent to others.
- Members can toggle their personal translation on/off with /mytranslate
- /translate command for manual one-off translations
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime

log = logging.getLogger("cog.translate")

try:
    from deep_translator import GoogleTranslator
    from langdetect import detect, LangDetectException
    _translate_available = True
except ImportError:
    _translate_available = False
    log.warning("deep-translator or langdetect not installed")

# Members who have opted OUT of auto-translate DMs
_opted_out: set[int] = set()

# Channels where auto-translate is active
AUTO_TRANSLATE_CHANNEL_NAMES = [
    "💬│general-chat",
    "💬┃ɢᴇɴᴇʀᴀʟ-ᴄʜᴀᴛ",
    "🔍│lfg",
    "🔍┃ʟꜰɢ",
    "😂│memes",
    "😂┃ᴍᴇᴍᴇꜱ",
]

LANG_MAP = {
    "english": "en",
    "arabic":  "ar",
    "somali":  "so",
    "other":   "en",
}

LANG_FLAGS = {
    "en": "🇬🇧",
    "ar": "🇸🇦",
    "so": "🇸🇴",
}


def translate_text(text: str, target: str = "en", source: str = "auto") -> str | None:
    if not _translate_available:
        return None
    try:
        return GoogleTranslator(source=source, target=target).translate(text)
    except Exception as e:
        log.error(f"Translation error: {e}")
        return None


def detect_language(text: str) -> str:
    if not _translate_available:
        return "en"
    try:
        return detect(text)
    except LangDetectException:
        return "en"


class TranslateCog(commands.Cog, name="Translate"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_channels: set[int] = set()

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            for name in AUTO_TRANSLATE_CHANNEL_NAMES:
                ch = discord.utils.get(guild.text_channels, name=name)
                if ch:
                    self._active_channels.add(ch.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        if len(message.content.strip()) < 5:
            return
        if message.channel.id not in self._active_channels:
            return
        if not _translate_available:
            return

        # Detect the language of the message
        detected = detect_language(message.content)
        if detected == "en":
            return  # Already English — nothing to do

        src_flag = LANG_FLAGS.get(detected, "🌍")

        # Get verified member data from the verify cog
        verify_cog = self.bot.cogs.get("Verify")
        verified_data = getattr(verify_cog, '_verified', {}) if verify_cog else {}
        # Also import directly
        try:
            from cogs.verify import _verified as global_verified
        except Exception:
            global_verified = {}

        all_verified = {**global_verified}

        # Find all members in this guild who:
        # 1. Have a different language set
        # 2. Haven't opted out
        # 3. Are not the message author
        guild = message.guild
        translation_cache: dict[str, str] = {}  # target_lang → translated text

        for member in guild.members:
            if member.bot:
                continue
            if member.id == message.author.id:
                continue
            if member.id in _opted_out:
                continue
            if not member.status == discord.Status.online and not member.status == discord.Status.idle:
                continue  # Only DM online/idle members to avoid spam

            # Get their language
            member_data = all_verified.get(member.id, {})
            member_lang_name = member_data.get("language", "English").lower()
            member_lang_code = LANG_MAP.get(member_lang_name, "en")

            # Skip if they speak the same language as the message
            if member_lang_code == detected:
                continue

            # Translate to their language (cache to avoid duplicate API calls)
            if member_lang_code not in translation_cache:
                translated = translate_text(message.content, target=member_lang_code, source=detected)
                if translated:
                    translation_cache[member_lang_code] = translated

            translated = translation_cache.get(member_lang_code)
            if not translated:
                continue

            tgt_flag = LANG_FLAGS.get(member_lang_code, "🌍")

            # DM the translation silently
            try:
                embed = discord.Embed(
                    description=(
                        f"**{src_flag} Message from {message.author.display_name}** "
                        f"in [#{message.channel.name}]({message.jump_url}):\n"
                        f"> {message.content[:500]}\n\n"
                        f"**{tgt_flag} Translation ({member_lang_name.title()}):**\n"
                        f"{translated[:500]}"
                    ),
                    color=0x00BFFF,
                    timestamp=datetime.utcnow(),
                )
                embed.set_author(
                    name=message.author.display_name,
                    icon_url=message.author.display_avatar.url,
                )
                embed.set_footer(text="Use /mytranslate to turn off these DMs")
                await member.send(embed=embed)
            except discord.Forbidden:
                pass  # DMs closed

    # ── /translate ────────────────────────────────────────
    @app_commands.command(name="translate", description="Translate text to any language 🌍")
    @app_commands.describe(
        text="Text to translate",
        to_language="Target language",
    )
    @app_commands.choices(to_language=[
        app_commands.Choice(name="🇬🇧 English", value="en"),
        app_commands.Choice(name="🇸🇦 Arabic",  value="ar"),
        app_commands.Choice(name="🇸🇴 Somali",  value="so"),
    ])
    async def slash_translate(
        self,
        interaction: discord.Interaction,
        text: str,
        to_language: str = "en",
    ):
        await interaction.response.defer(ephemeral=True)
        if not _translate_available:
            await interaction.followup.send("⚠️ Translation library not installed.", ephemeral=True)
            return

        detected  = detect_language(text)
        translated = translate_text(text, target=to_language, source=detected)
        if not translated:
            await interaction.followup.send("⚠️ Translation failed.", ephemeral=True)
            return

        src_flag = LANG_FLAGS.get(detected, "🌍")
        tgt_flag = LANG_FLAGS.get(to_language, "🌍")

        embed = discord.Embed(
            title=f"{src_flag} → {tgt_flag} Translation",
            color=0x00BFFF,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name=f"{src_flag} Original",   value=text[:1000],       inline=False)
        embed.add_field(name=f"{tgt_flag} Translated", value=translated[:1000], inline=False)
        embed.set_footer(text="Only you can see this")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /mytranslate ──────────────────────────────────────
    @app_commands.command(name="mytranslate", description="Toggle auto-translation DMs on/off 🔔")
    async def slash_mytranslate(self, interaction: discord.Interaction):
        uid = interaction.user.id
        if uid in _opted_out:
            _opted_out.discard(uid)
            await interaction.response.send_message(
                "✅ Auto-translation DMs **enabled**. You'll receive translations of foreign messages.",
                ephemeral=True,
            )
        else:
            _opted_out.add(uid)
            await interaction.response.send_message(
                "🔕 Auto-translation DMs **disabled**. Use `/mytranslate` again to re-enable.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(TranslateCog(bot))
