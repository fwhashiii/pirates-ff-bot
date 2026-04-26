"""
╔══════════════════════════════════════════════════════════╗
║         🔥 FREE FIRE SQUAD BOT — Main Entry Point 🔥     ║
║         Built for friends, gaming & the Booyah life      ║
╚══════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands, tasks
import os
import sys
import traceback
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
import logging

load_dotenv()

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("FreeFire-Bot")

OWNER_ID = 815646767311224953  # fwpirate

# ── Intents ───────────────────────────────────────────────
intents = discord.Intents.all()

# ── Bot Setup ─────────────────────────────────────────────
bot = commands.Bot(
    command_prefix=os.getenv("PREFIX", "!"),
    intents=intents,
    help_command=None,
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


# ── Owner DM alert ────────────────────────────────────────
async def notify_owner(message: str, color: int = 0xFF0000):
    try:
        owner = await bot.fetch_user(OWNER_ID)
        embed = discord.Embed(
            title="🤖 Bot Status Alert",
            description=message,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="PIRATES Bot Monitor")
        await owner.send(embed=embed)
    except Exception as e:
        log.error(f"Failed to notify owner: {e}")


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
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"Synced {len(synced)} slash command(s) to guild instantly.")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")

    # Notify owner bot is online
    await notify_owner("✅ **Pirate bot is online!**\nAll systems running.", color=0x00FF7F)


@bot.event
async def on_disconnect():
    log.warning("Bot disconnected from Discord")


@bot.event
async def on_resumed():
    log.info("Bot reconnected to Discord")
    await notify_owner("🔄 **Bot reconnected** after a disconnect.", color=0xFFD700)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 You don't have permission to use that command.")
    else:
        log.error(f"Unhandled error: {error}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Catch slash command errors and notify owner."""
    error_msg = str(error)
    log.error(f"Slash command error in /{interaction.command.name if interaction.command else 'unknown'}: {error_msg}")
    await notify_owner(
        f"⚠️ **Slash Command Error**\n"
        f"Command: `/{interaction.command.name if interaction.command else 'unknown'}`\n"
        f"User: {interaction.user}\n"
        f"Error: ```{error_msg[:500]}```"
    )
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ Something went wrong. Staff have been notified.", ephemeral=True)
    except Exception:
        pass


# ── Load Cogs ─────────────────────────────────────────────
async def load_cogs():
    failed = []
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            log.info(f"Loaded cog: {cog}")
        except Exception as e:
            log.error(f"Failed to load cog {cog}: {e}")
            failed.append(f"`{cog}`: {e}")

    if failed:
        await notify_owner(
            f"⚠️ **Failed to load {len(failed)} cog(s):**\n" + "\n".join(failed)
        )


# ── Run ───────────────────────────────────────────────────
async def main():
    async with bot:
        await load_cogs()
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    except Exception as e:
        log.critical(f"Bot crashed: {e}")
        log.critical(traceback.format_exc())
