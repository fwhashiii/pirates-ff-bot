"""
🎯 Events Cog — Giveaways, polls, and custom room management
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
from datetime import datetime, timedelta


class EventsCog(commands.Cog, name="Events"):
    """Giveaways, polls, and custom room management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /giveaway ─────────────────────────────────────────
    @app_commands.command(name="giveaway", description="Start a giveaway 🎁")
    @app_commands.describe(
        prize="What are you giving away?",
        minutes="How long to run (minutes)",
        winners="Number of winners"
    )
    async def slash_giveaway(
        self,
        interaction: discord.Interaction,
        prize: str,
        minutes: int = 5,
        winners: int = 1,
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 You need Manage Messages permission.", ephemeral=True)
            return

        minutes = max(1, min(minutes, 1440))  # max 24 hours
        winners = max(1, min(winners, 10))
        end_time = datetime.utcnow() + timedelta(minutes=minutes)

        embed = discord.Embed(
            title="🎁 GIVEAWAY!",
            description=(
                f"**Prize:** {prize}\n\n"
                f"React with 🎉 to enter!\n\n"
                f"**Winners:** {winners}\n"
                f"**Ends:** <t:{int(end_time.timestamp())}:R>"
            ),
            color=0xFFD700,
            timestamp=end_time,
        )
        embed.set_author(name=f"Hosted by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Ends at")

        await interaction.response.send_message("🎁 Giveaway started!")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("🎉")

        # Wait for giveaway to end
        await asyncio.sleep(minutes * 60)

        # Fetch updated message
        msg = await interaction.channel.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")

        if reaction and reaction.count > 1:
            users = [u async for u in reaction.users() if not u.bot]
            if users:
                chosen = random.sample(users, min(winners, len(users)))
                winner_mentions = ", ".join(w.mention for w in chosen)
                await interaction.channel.send(
                    f"🎉 Congratulations {winner_mentions}! You won **{prize}**! BOOYAH! 🏆"
                )
                return

        await interaction.channel.send(f"😔 Not enough entries for the **{prize}** giveaway.")

    # ── /poll ─────────────────────────────────────────────
    @app_commands.command(name="poll", description="Create a quick poll 📊")
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
    )
    async def slash_poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
    ):
        options = [o for o in [option1, option2, option3, option4] if o]
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]

        embed = discord.Embed(
            title=f"📊 {question}",
            description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)),
            color=0x00BFFF,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(
            name=f"Poll by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_footer(text="Vote by reacting below!")

        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])

    # ── /customroom ───────────────────────────────────────
    @app_commands.command(name="customroom", description="Post a custom room code 🎮")
    @app_commands.describe(
        code="Room code",
        password="Room password",
        mode="Game mode",
        note="Any extra info"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Battle Royale",  value="Battle Royale"),
        app_commands.Choice(name="Clash Squad",    value="Clash Squad"),
        app_commands.Choice(name="Lone Wolf",      value="Lone Wolf"),
        app_commands.Choice(name="Training",       value="Training"),
    ])
    async def slash_customroom(
        self,
        interaction: discord.Interaction,
        code: str,
        password: str = "None",
        mode: str = "Battle Royale",
        note: str = "",
    ):
        embed = discord.Embed(
            title="🎮 Custom Room Open!",
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(
            name=f"Hosted by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(name="🔑 Room Code",  value=f"||{code}||",     inline=True)
        embed.add_field(name="🔒 Password",   value=f"||{password}||", inline=True)
        embed.add_field(name="🎯 Mode",       value=mode,              inline=True)
        if note:
            embed.add_field(name="📝 Note",   value=note,              inline=False)
        embed.set_footer(text="Click the spoiler tags to reveal • Good luck!")
        await interaction.response.send_message(embed=embed)

    # ── /schedule ─────────────────────────────────────────
    @app_commands.command(name="schedule", description="Post a gaming session schedule 📅")
    @app_commands.describe(
        title="Session title",
        date="Date and time (e.g. Saturday 8PM EST)",
        game="Game mode",
        note="Extra details"
    )
    async def slash_schedule(
        self,
        interaction: discord.Interaction,
        title: str,
        date: str,
        game: str = "Free Fire BR",
        note: str = "",
    ):
        embed = discord.Embed(
            title=f"📅 {title}",
            color=0x9B59B6,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(
            name=f"Organized by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(name="🕐 When",  value=date, inline=True)
        embed.add_field(name="🎮 Game",  value=game, inline=True)
        if note:
            embed.add_field(name="📝 Details", value=note, inline=False)
        embed.set_footer(text="React ✅ if you're in! • Free Fire Squad")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
