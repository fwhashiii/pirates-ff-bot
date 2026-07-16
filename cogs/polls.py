"""
📊 Polls & Suggestions Cog
Commands: /poll /suggest /giveaway /remind
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import re
from datetime import datetime, timezone, timedelta
import logging

log = logging.getLogger("cog.polls")

OWNER_ID = 815646767311224953


class PollsCog(commands.Cog, name="Polls"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._reminders: list = []

    # ── /poll ─────────────────────────────────────────────
    @app_commands.command(name="poll", description="Create a poll 📊")
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
        duration="Duration in minutes (default: 60)",
    )
    async def slash_poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        duration: int = 60,
    ):
        options = [o for o in [option1, option2, option3, option4] if o]
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]

        embed = discord.Embed(
            title=f"📊 {question}",
            color=0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        for i, opt in enumerate(options):
            embed.add_field(name=f"{emojis[i]} {opt}", value="\u200b", inline=False)

        embed.set_footer(text=f"Poll by {interaction.user.display_name} • Ends in {duration} min")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()

        for i in range(len(options)):
            await msg.add_reaction(emojis[i])

        # End poll after duration
        await asyncio.sleep(duration * 60)
        try:
            msg = await interaction.channel.fetch_message(msg.id)
            results = {}
            for reaction in msg.reactions:
                if str(reaction.emoji) in emojis:
                    idx = emojis.index(str(reaction.emoji))
                    if idx < len(options):
                        results[options[idx]] = reaction.count - 1  # subtract bot's reaction

            if results:
                winner = max(results, key=results.get)
                result_embed = discord.Embed(
                    title=f"📊 Poll Results: {question}",
                    color=0x00FF7F,
                    timestamp=datetime.now(timezone.utc),
                )
                for opt, votes in sorted(results.items(), key=lambda x: x[1], reverse=True):
                    bar = "█" * votes + "░" * max(0, 10 - votes)
                    result_embed.add_field(
                        name=f"{'🏆 ' if opt == winner else ''}{opt}",
                        value=f"`{bar}` **{votes} votes**",
                        inline=False,
                    )
                result_embed.set_footer(text=f"Winner: {winner}")
                await interaction.channel.send(embed=result_embed)
        except Exception as e:
            log.error(f"Poll end error: {e}")

    # ── /suggest ──────────────────────────────────────────
    @app_commands.command(name="suggest", description="Submit a suggestion 💡")
    @app_commands.describe(suggestion="Your suggestion for the server")
    async def slash_suggest(self, interaction: discord.Interaction, suggestion: str):
        # Find suggestions channel
        suggest_ch = discord.utils.get(interaction.guild.text_channels, name="💡┃suggestions")
        if not suggest_ch:
            suggest_ch = discord.utils.get(interaction.guild.text_channels, name="suggestions")
        if not suggest_ch:
            await interaction.response.send_message("❌ No suggestions channel found. Ask staff to create one.", ephemeral=True)
            return

        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        msg = await suggest_ch.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        await interaction.response.send_message("✅ Your suggestion has been submitted!", ephemeral=True)

    # ── /giveaway ─────────────────────────────────────────
    @app_commands.command(name="giveaway", description="Start a giveaway 🎁")
    @app_commands.describe(
        prize="What are you giving away?",
        duration="Duration in minutes",
        winners="Number of winners (default: 1)",
    )
    async def slash_giveaway(
        self,
        interaction: discord.Interaction,
        prize: str,
        duration: int,
        winners: int = 1,
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration)

        embed = discord.Embed(
            title="🎁 GIVEAWAY",
            description=(
                f"**Prize:** {prize}\n\n"
                f"React with 🎉 to enter!\n\n"
                f"**Winners:** {winners}\n"
                f"**Ends:** <t:{int(end_time.timestamp())}:R>"
            ),
            color=0xFF4500,
            timestamp=end_time,
        )
        embed.set_footer(text=f"Hosted by {interaction.user.display_name} • Ends at")

        await interaction.response.send_message("🎁 Giveaway started!")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("🎉")

        await asyncio.sleep(duration * 60)

        try:
            msg = await interaction.channel.fetch_message(msg.id)
            reaction = discord.utils.get(msg.reactions, emoji="🎉")
            if not reaction:
                await interaction.channel.send("❌ No one entered the giveaway.")
                return

            users = [u async for u in reaction.users() if not u.bot]
            if not users:
                await interaction.channel.send("❌ No valid entries.")
                return

            actual_winners = random.sample(users, min(winners, len(users)))
            winner_mentions = " ".join(w.mention for w in actual_winners)

            result_embed = discord.Embed(
                title="🎉 Giveaway Ended!",
                description=f"**Prize:** {prize}\n\n**Winner(s):** {winner_mentions}",
                color=0x00FF7F,
                timestamp=datetime.now(timezone.utc),
            )
            await interaction.channel.send(
                content=f"🎉 Congratulations {winner_mentions}!",
                embed=result_embed,
            )
        except Exception as e:
            log.error(f"Giveaway end error: {e}")

    # ── /remind ───────────────────────────────────────────
    @app_commands.command(name="remind", description="Set a reminder ⏰")
    @app_commands.describe(
        time="Time (e.g. 30m, 2h, 1d)",
        reminder="What to remind you about",
    )
    async def slash_remind(self, interaction: discord.Interaction, time: str, reminder: str):
        # Parse time
        match = re.match(r"(\d+)(m|h|d)", time.lower())
        if not match:
            await interaction.response.send_message("❌ Invalid time format. Use: `30m`, `2h`, `1d`", ephemeral=True)
            return

        amount, unit = int(match.group(1)), match.group(2)
        seconds = amount * {"m": 60, "h": 3600, "d": 86400}[unit]

        if seconds > 7 * 86400:
            await interaction.response.send_message("❌ Max reminder time is 7 days.", ephemeral=True)
            return

        end_time = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        await interaction.response.send_message(
            f"⏰ I'll remind you about **{reminder}** <t:{int(end_time.timestamp())}:R>!",
            ephemeral=True,
        )

        await asyncio.sleep(seconds)
        try:
            await interaction.user.send(
                embed=discord.Embed(
                    title="⏰ Reminder!",
                    description=reminder,
                    color=0xFF4500,
                    timestamp=datetime.now(timezone.utc),
                ).set_footer(text="PIRATES Bot Reminder")
            )
        except discord.Forbidden:
            try:
                await interaction.channel.send(
                    f"⏰ {interaction.user.mention} — Reminder: **{reminder}**"
                )
            except Exception:
                pass

    # ── /reroll ───────────────────────────────────────────
    @app_commands.command(name="reroll", description="Reroll a giveaway winner 🔄")
    @app_commands.describe(message_id="The giveaway message ID")
    async def slash_reroll(self, interaction: discord.Interaction, message_id: str):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return
        try:
            msg = await interaction.channel.fetch_message(int(message_id))
            reaction = discord.utils.get(msg.reactions, emoji="🎉")
            if not reaction:
                await interaction.response.send_message("❌ No 🎉 reactions found.", ephemeral=True)
                return
            users = [u async for u in reaction.users() if not u.bot]
            if not users:
                await interaction.response.send_message("❌ No valid entries.", ephemeral=True)
                return
            winner = random.choice(users)
            await interaction.response.send_message(f"🎉 New winner: {winner.mention}! Congratulations!")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PollsCog(bot))
