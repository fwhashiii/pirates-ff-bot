"""
🎵 PIRATES Music Bot — Standalone
Run separately from the main bot: python music_bot.py
"""

import discord
from discord.ext import commands
import asyncio
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("MusicBot")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix="m!",
    intents=intents,
    help_command=None,
)


async def announce_failure(reason: str = "unknown error"):
    """Send a failure message to the announcements channel in EN/AR/SO."""
    try:
        channel_id = int(os.getenv("ANNOUNCEMENTS_CHANNEL_ID", 0))
        if not channel_id:
            return
        channel = bot.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="⚠️ Music Bot Issue",
            color=0xFF4500,
        )
        embed.add_field(
            name="🇬🇧 English",
            value="The music bot is currently experiencing issues and will be back shortly. Sorry for the inconvenience!",
            inline=False,
        )
        embed.add_field(
            name="🇸🇦 العربية",
            value="بوت الموسيقى يواجه مشكلة حالياً وسيعود قريباً. نعتذر عن الإزعاج!",
            inline=False,
        )
        embed.add_field(
            name="🇸🇴 Soomaali",
            value="Botka muusikada ayaa hadda la kulma dhibaato waxaana dib u soo noqon doona dhawaan. Raali noqo!",
            inline=False,
        )
        embed.set_footer(text="PIRATES Music Bot • Auto-restart in progress")
        await channel.send(content="@everyone", embed=embed)
        log.info("Sent failure announcement to channel")
    except Exception as e:
        log.error(f"Failed to send failure announcement: {e}")

@bot.event
async def on_ready():
    log.info(f"Music Bot logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="music 🎵 | /play",
        )
    )

    # Force-disconnect from any lingering voice sessions (fixes error 4006)
    for guild in bot.guilds:
        if guild.voice_client:
            try:
                await guild.voice_client.disconnect(force=True)
                log.info(f"Cleared stale voice session in {guild.name}")
            except Exception:
                pass

    try:
        guild_id = int(os.getenv("GUILD_ID", 0))
        if guild_id:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            log.info(f"Synced {len(synced)} music commands to guild instantly.")
        else:
            synced = await bot.tree.sync()
            log.info(f"Synced {len(synced)} music commands globally.")
    except Exception as e:
        log.error(f"Sync failed: {e}")


@bot.event
async def on_resumed():
    log.info("Music bot reconnected — clearing stale voice sessions")
    for guild in bot.guilds:
        if guild.voice_client:
            try:
                await guild.voice_client.disconnect(force=True)
            except Exception:
                pass


@bot.event
async def on_disconnect():
    log.warning("Music bot disconnected from Discord")
    # Give it a moment — if it's a brief disconnect it'll reconnect on its own
    await asyncio.sleep(10)
    # If still not connected, announce the issue
    if not bot.is_ready():
        await announce_failure("disconnected from Discord")


async def main():
    async with bot:
        await bot.load_extension("cogs.music")
        token = os.getenv("MUSIC_BOT_TOKEN")
        if not token or token == "your_music_bot_token_here":
            print("❌ MUSIC_BOT_TOKEN not set in .env")
            print("   Add your music bot token to .env as MUSIC_BOT_TOKEN=")
            return
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
