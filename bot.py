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
from datetime import datetime, timezone, time as dt_time
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
    "cogs.welcome",
    "cogs.help",
    "cogs.ranks",
    "cogs.live",
    "cogs.sensitivity",
    "cogs.translate",
    "cogs.tickets",
    "cogs.polls",
    "cogs.leaderboard",
    "cogs.stats_dashboard",
    "cogs.roles",
    "cogs.tournaments",
    "cogs.clips",
    "cogs.antiraid",
    "cogs.growth",
    "cogs.temp_vc_access",
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

    # Start daily status report
    if not daily_status.is_running():
        daily_status.start()

    # Start heartbeat monitor
    if not heartbeat.is_running():
        heartbeat.start()


# ── Heartbeat — checks bot is still responsive every 10 min ──
@tasks.loop(minutes=10)
async def heartbeat():
    """Silent check — if this stops firing, something is wrong."""
    log.debug("Heartbeat OK")


@heartbeat.error
async def heartbeat_error(error):
    await notify_owner(f"💔 **Heartbeat failed** — bot may be unresponsive!\nError: `{error}`")


# ── Daily status DM ───────────────────────────────────────
@tasks.loop(time=dt_time(hour=9, minute=0))  # 9:00 AM UTC daily
async def daily_status():
    import psutil, time
    try:
        owner = await bot.fetch_user(OWNER_ID)
        guild_id = int(os.getenv("GUILD_ID", 0))
        guild = bot.get_guild(guild_id)

        latency = round(bot.latency * 1000)
        process = psutil.Process()
        uptime_seconds = int(time.time() - process.create_time())
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        mem_mb = round(process.memory_info().rss / 1024 / 1024, 1)

        embed = discord.Embed(
            title="📊 Daily Bot Status Report",
            description="Here's your daily summary for **Pirate bot**",
            color=0x00BFFF,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="🏓 Latency",    value=f"{latency}ms",                                    inline=True)
        embed.add_field(name="⏱️ Uptime",      value=f"{hours}h {minutes}m {seconds}s",                inline=True)
        embed.add_field(name="💾 Memory",      value=f"{mem_mb} MB",                                   inline=True)
        embed.add_field(name="👥 Members",     value=str(guild.member_count) if guild else "?",        inline=True)
        embed.add_field(name="🔧 Cogs",        value=str(len(bot.cogs)),                               inline=True)
        embed.add_field(name="⚡ Commands",    value=str(len(bot.tree.get_commands())),                inline=True)
        embed.add_field(name="✅ Status",      value="All systems operational",                        inline=False)
        embed.set_footer(text="PIRATES Bot • Daily Report • 9:00 AM UTC")
        await owner.send(embed=embed)
        log.info("Daily status report sent to owner")
    except Exception as e:
        log.error(f"Daily status report failed: {e}")


@bot.event
async def on_disconnect():
    log.warning("Bot disconnected from Discord")


@bot.event
async def on_resumed():
    log.info("Bot reconnected to Discord")
    await notify_owner("🔄 **Bot reconnected** after a disconnect.", color=0xFFD700)


@bot.command(name="sync")
async def prefix_sync(ctx):
    """Owner-only: force re-sync slash commands to the guild."""
    if ctx.author.id != OWNER_ID:
        return
    try:
        guild = discord.Object(id=int(os.getenv("GUILD_ID", 0)))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        await ctx.send(f"✅ Synced {len(synced)} command(s) to guild.")
        log.info(f"Manual sync: {len(synced)} commands synced by {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Sync failed: {e}")
        log.error(f"Manual sync failed: {e}")


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
    """Catch slash command errors — only notify owner for serious ones."""
    error_msg = str(error)
    cmd_name = interaction.command.name if interaction.command else "unknown"
    log.error(f"Slash command error in /{cmd_name}: {error_msg}")

    # Only DM owner for serious errors, not user mistakes
    serious = not isinstance(error, (
        discord.app_commands.CommandNotFound,
        discord.app_commands.CheckFailure,
        discord.app_commands.MissingPermissions,
        discord.app_commands.BotMissingPermissions,
        discord.app_commands.CommandOnCooldown,
    ))

    if serious:
        await notify_owner(
            f"⚠️ **Slash Command Error**\n"
            f"Command: `/{cmd_name}`\n"
            f"User: {interaction.user}\n"
            f"Error: ```{error_msg[:500]}```"
        )

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ Something went wrong. Try again.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Something went wrong. Try again.", ephemeral=True)
    except Exception:
        pass


async def log_command_usage(interaction: discord.Interaction):
    """Log every slash command use to #⚙️│BOT-LOG."""
    try:
        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        if not log_ch_id:
            return
        channel = bot.get_channel(log_ch_id)
        if not channel:
            return
        cmd_name = interaction.command.name if interaction.command else "unknown"
        options = ""
        if interaction.data and interaction.data.get("options"):
            opts = interaction.data["options"]
            options = " ".join(f"`{o['name']}:{o.get('value','')}`" for o in opts[:5])
        embed = discord.Embed(
            description=(
                f"**/{cmd_name}** {options}\n"
                f"👤 {interaction.user.mention} (`{interaction.user}`)\n"
                f"📍 {interaction.channel.mention if interaction.channel else 'DM'}"
            ),
            color=0x00BFFF,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(
            name=f"{interaction.user.display_name} used /{cmd_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await channel.send(embed=embed)
    except Exception as e:
        log.debug(f"Command log error: {e}")


@bot.tree.interaction_check
async def global_interaction_check(interaction: discord.Interaction) -> bool:
    asyncio.create_task(log_command_usage(interaction))
    return True


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
