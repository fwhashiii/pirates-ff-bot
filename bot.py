"""
╔══════════════════════════════════════════════════════════╗
║         🔥 FREE FIRE SQUAD BOT — Main Entry Point 🔥     ║
║         Built for friends, gaming & the Booyah life      ║
╚══════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import logging

load_dotenv()

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("FreeFire-Bot")

# ── Intents ───────────────────────────────────────────────
intents = discord.Intents.all()

# ── Bot Setup ─────────────────────────────────────────────
bot = commands.Bot(
    command_prefix=os.getenv("PREFIX", "!"),
    intents=intents,
    help_command=None,          # We use a custom /help
    case_insensitive=True,
)

# ── Cogs to load ──────────────────────────────────────────
COGS = [
    "cogs.news",
    "cogs.player",
    "cogs.fun",
    "cogs.moderation",
    "cogs.ai_assistant",
    "cogs.events",
    "cogs.welcome",
    "cogs.help",
    "cogs.ranks",
    "cogs.live",
    "cogs.voice_monitor",
    "cogs.sensitivity",
    "cogs.translate",
    "cogs.tickets",
]

# ── Bot Events ────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="Free Fire 🔥 | /help",
        )
    )
    try:
        guild = discord.Object(id=int(os.getenv("GUILD_ID", 0)))
        # Sync to guild instantly (no 1-hour wait)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"Synced {len(synced)} slash command(s) to guild instantly.")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 You don't have permission to use that command.")
    else:
        log.error(f"Unhandled error: {error}")


# ── Load Cogs ─────────────────────────────────────────────
async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            log.info(f"Loaded cog: {cog}")
        except Exception as e:
            log.error(f"Failed to load cog {cog}: {e}")


# ── Run ───────────────────────────────────────────────────
async def main():
    async with bot:
        await load_cogs()
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
