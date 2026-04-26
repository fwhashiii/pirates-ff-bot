"""
📖 Help Cog — Custom /help command with Free Fire theme
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime


COMMANDS_INFO = {
    "🔥 Free Fire": [
        ("/news [count]",       "Latest Free Fire news articles"),
        ("/events",             "Active in-game events & esports"),
        ("/patchnotes",         "Latest patch highlights"),
        ("/tip",                "Random pro tip"),
        ("/build [playstyle]",  "Character build recommendation"),
    ],
    "🎮 Player": [
        ("/stats [username]",   "View player stats card"),
        ("/rank [rank]",        "Set your rank role"),
        ("/lfg [mode]",         "Post a Looking for Group request"),
        ("/profile [member]",   "View a member's server profile"),
    ],
    "🤖 AI Assistant": [
        ("/ask [question]",     "Ask Booyah Bot anything about FF"),
    ],
    "🎲 Fun & Games": [
        ("/trivia",             "Free Fire trivia question"),
        ("/8ball [question]",   "Magic 8-ball answer"),
        ("/coinflip",           "Flip a coin"),
        ("/dice [sides]",       "Roll a dice"),
        ("/rps [choice]",       "Rock Paper Scissors vs bot"),
        ("/booyah",             "Celebrate a win!"),
        ("/squad",              "Pick a random squad from online members"),
    ],
    "🎯 Events": [
        ("/giveaway [prize]",   "Start a giveaway (staff)"),
        ("/poll [question]",    "Create a poll"),
        ("/customroom [code]",  "Post a custom room code"),
        ("/schedule [title]",   "Post a gaming session schedule"),
    ],
    "🛡️ Moderation": [
        ("/kick [member]",      "Kick a member (mod+)"),
        ("/ban [member]",       "Ban a member (mod+)"),
        ("/mute [member]",      "Timeout a member (mod+)"),
        ("/warn [member]",      "Warn a member (mod+)"),
        ("/purge [amount]",     "Delete messages (mod+)"),
    ],
}


class HelpCog(commands.Cog, name="Help"):
    """Custom help command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all bot commands 📖")
    @app_commands.describe(category="Filter by category (optional)")
    @app_commands.choices(category=[
        app_commands.Choice(name="🔥 Free Fire",    value="🔥 Free Fire"),
        app_commands.Choice(name="🎮 Player",       value="🎮 Player"),
        app_commands.Choice(name="🤖 AI Assistant", value="🤖 AI Assistant"),
        app_commands.Choice(name="🎲 Fun & Games",  value="🎲 Fun & Games"),
        app_commands.Choice(name="🎯 Events",       value="🎯 Events"),
        app_commands.Choice(name="🛡️ Moderation",   value="🛡️ Moderation"),
    ])
    async def slash_help(self, interaction: discord.Interaction, category: str = None):
        if category and category in COMMANDS_INFO:
            # Single category
            embed = discord.Embed(
                title=f"📖 Commands — {category}",
                color=0xFF4500,
                timestamp=datetime.utcnow(),
            )
            cmds = COMMANDS_INFO[category]
            value = "\n".join(f"`{cmd}` — {desc}" for cmd, desc in cmds)
            embed.add_field(name="Commands", value=value, inline=False)
        else:
            # Full help
            embed = discord.Embed(
                title="🔥 Free Fire Squad Bot — Commands",
                description="Use `/help [category]` to filter. All commands use slash `/`.",
                color=0xFF4500,
                timestamp=datetime.utcnow(),
            )
            for cat, cmds in COMMANDS_INFO.items():
                value = "\n".join(f"`{cmd}` — {desc}" for cmd, desc in cmds)
                embed.add_field(name=cat, value=value, inline=False)

        embed.set_thumbnail(url="https://i.imgur.com/8QfKFqA.png")
        embed.set_footer(
            text=f"Free Fire Squad Bot • Requested by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Check bot latency 🏓")
    async def slash_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = 0x00FF7F if latency < 100 else 0xFFD700 if latency < 200 else 0xFF4500
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=color,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="View server information 🏠")
    async def slash_serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"🏠 {guild.name}",
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="👑 Owner",       value=str(guild.owner),                    inline=True)
        embed.add_field(name="👥 Members",     value=str(guild.member_count),             inline=True)
        embed.add_field(name="📁 Channels",    value=str(len(guild.channels)),            inline=True)
        embed.add_field(name="🎭 Roles",       value=str(len(guild.roles)),               inline=True)
        embed.add_field(name="🌍 Region",      value="Global",                            inline=True)
        embed.add_field(name="📅 Created",     value=guild.created_at.strftime("%b %d, %Y"), inline=True)
        embed.set_footer(text="Free Fire Squad Server")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
