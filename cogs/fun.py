"""
🎲 Fun Cog — Trivia, 8-ball, coin flip, dice, and Free Fire mini-games
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime


FF_TRIVIA = [
    {"q": "What is the maximum number of players in a Free Fire Battle Royale match?",
     "a": "50", "options": ["30", "50", "100", "60"]},
    {"q": "Which character has the ability 'Jai' that reloads the gun after knocking an enemy?",
     "a": "Jai", "options": ["Jai", "Alok", "Chrono", "Kelly"]},
    {"q": "What is the name of the in-game currency used to buy items in Free Fire?",
     "a": "Diamonds", "options": ["Coins", "Gems", "Diamonds", "Gold"]},
    {"q": "Which map was the original map in Free Fire?",
     "a": "Bermuda", "options": ["Kalahari", "Purgatory", "Bermuda", "Alpine"]},
    {"q": "What does 'Booyah' mean in Free Fire?",
     "a": "Victory/Win", "options": ["Good game", "Victory/Win", "Nice kill", "Squad wipe"]},
    {"q": "Which character's ability creates a force field that blocks bullets?",
     "a": "Chrono", "options": ["Alok", "Skyler", "Chrono", "Wukong"]},
    {"q": "What is the name of the Clash Squad ranked mode currency?",
     "a": "CS Tokens", "options": ["Battle Points", "CS Tokens", "Diamonds", "Gold"]},
    {"q": "How many zones does the safe zone shrink to in a standard BR match?",
     "a": "Multiple (shrinks continuously)", "options": ["3", "5", "Multiple (shrinks continuously)", "10"]},
    {"q": "Which weapon is known as the 'one-shot' shotgun in Free Fire?",
     "a": "M1887", "options": ["SPAS12", "M1887", "MAG-7", "M1014"]},
    {"q": "What company developed Free Fire?",
     "a": "Garena / 111 Dots Studio", "options": ["Tencent", "Garena / 111 Dots Studio", "Activision", "NetEase"]},
]

EIGHT_BALL_RESPONSES = [
    "🔮 It is certain.", "🔮 Without a doubt.", "🔮 Yes, definitely!",
    "🔮 You may rely on it.", "🔮 As I see it, yes.", "🔮 Most likely.",
    "🔮 Outlook good.", "🔮 Signs point to yes.", "🔮 Reply hazy, try again.",
    "🔮 Ask again later.", "🔮 Better not tell you now.", "🔮 Cannot predict now.",
    "🔮 Don't count on it.", "🔮 My reply is no.", "🔮 My sources say no.",
    "🔮 Outlook not so good.", "🔮 Very doubtful.",
]

BOOYAH_GIFS = [
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif",
]


class FunCog(commands.Cog, name="Fun"):
    """Games, trivia, and fun commands for the squad."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_trivia: dict[int, dict] = {}  # channel_id → question

    # ── /trivia ───────────────────────────────────────────
    @app_commands.command(name="trivia", description="Test your Free Fire knowledge! 🎯")
    async def slash_trivia(self, interaction: discord.Interaction):
        q = random.choice(FF_TRIVIA)
        options = q["options"][:]
        random.shuffle(options)
        letters = ["🇦", "🇧", "🇨", "🇩"]

        embed = discord.Embed(
            title="🎯 Free Fire Trivia!",
            description=f"**{q['q']}**",
            color=0xFFD700,
            timestamp=datetime.utcnow(),
        )
        option_text = "\n".join(
            f"{letters[i]} {opt}" for i, opt in enumerate(options)
        )
        embed.add_field(name="Options", value=option_text, inline=False)
        embed.set_footer(text="Reply with the letter of your answer!")

        # Store answer for this channel
        self._active_trivia[interaction.channel_id] = {
            "answer": q["a"],
            "options": options,
            "letters": letters,
            "asker": interaction.user.id,
        }

        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Check trivia answers from chat messages."""
        if message.author.bot:
            return
        trivia = self._active_trivia.get(message.channel.id)
        if not trivia:
            return

        content = message.content.strip().upper()
        letter_map = {l: opt for l, opt in zip(["A", "B", "C", "D"], trivia["options"])}
        # Accept letter or full answer
        chosen = letter_map.get(content, content)

        if trivia["answer"].lower() in chosen.lower() or chosen.lower() in trivia["answer"].lower():
            del self._active_trivia[message.channel.id]
            embed = discord.Embed(
                title="✅ Correct! BOOYAH!",
                description=f"{message.author.mention} got it right!\n**Answer:** {trivia['answer']}",
                color=0x00FF7F,
            )
            await message.channel.send(embed=embed)

    # ── /8ball ────────────────────────────────────────────
    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question 🔮")
    @app_commands.describe(question="Your yes/no question")
    async def slash_8ball(self, interaction: discord.Interaction, question: str):
        response = random.choice(EIGHT_BALL_RESPONSES)
        embed = discord.Embed(color=0x9B59B6)
        embed.add_field(name="❓ Question", value=question,  inline=False)
        embed.add_field(name="🔮 Answer",   value=response,  inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /coinflip ─────────────────────────────────────────
    @app_commands.command(name="coinflip", description="Flip a coin 🪙")
    async def slash_coinflip(self, interaction: discord.Interaction):
        result = random.choice(["🪙 Heads!", "🪙 Tails!"])
        await interaction.response.send_message(result)

    # ── /dice ─────────────────────────────────────────────
    @app_commands.command(name="dice", description="Roll a dice 🎲")
    @app_commands.describe(sides="Number of sides (default 6)")
    async def slash_dice(self, interaction: discord.Interaction, sides: int = 6):
        sides = max(2, min(sides, 100))
        result = random.randint(1, sides)
        await interaction.response.send_message(
            f"🎲 You rolled a **{result}** (d{sides})"
        )

    # ── /rps ──────────────────────────────────────────────
    @app_commands.command(name="rps", description="Rock Paper Scissors vs the bot ✊")
    @app_commands.choices(choice=[
        app_commands.Choice(name="✊ Rock",     value="rock"),
        app_commands.Choice(name="✋ Paper",    value="paper"),
        app_commands.Choice(name="✌️ Scissors", value="scissors"),
    ])
    async def slash_rps(self, interaction: discord.Interaction, choice: str):
        bot_choice = random.choice(["rock", "paper", "scissors"])
        icons = {"rock": "✊", "paper": "✋", "scissors": "✌️"}

        if choice == bot_choice:
            result, color = "🤝 It's a tie!", 0xFFD700
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            result, color = "🏆 You win! BOOYAH!", 0x00FF7F
        else:
            result, color = "💀 Bot wins! Better luck next time!", 0xFF4500

        embed = discord.Embed(title="✊ Rock Paper Scissors", color=color)
        embed.add_field(name="Your choice", value=icons[choice],    inline=True)
        embed.add_field(name="Bot's choice", value=icons[bot_choice], inline=True)
        embed.add_field(name="Result",       value=result,           inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /booyah ───────────────────────────────────────────
    @app_commands.command(name="booyah", description="Celebrate a win! 🏆")
    async def slash_booyah(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏆 BOOYAH!",
            description=f"{interaction.user.mention} just got a **BOOYAH!** 🔥🔥🔥",
            color=0xFFD700,
            timestamp=datetime.utcnow(),
        )
        embed.set_image(url=random.choice(BOOYAH_GIFS))
        await interaction.response.send_message(embed=embed)

    # ── /squad ────────────────────────────────────────────
    @app_commands.command(name="squad", description="Randomly pick a squad from online members 🎮")
    async def slash_squad(self, interaction: discord.Interaction):
        guild = interaction.guild
        humans = [m for m in guild.members if not m.bot and m.status != discord.Status.offline]
        if len(humans) < 4:
            await interaction.response.send_message(
                "⚠️ Not enough online members to form a squad (need 4).", ephemeral=True
            )
            return
        squad = random.sample(humans, 4)
        embed = discord.Embed(
            title="🎮 Random Squad Picked!",
            description="\n".join(f"• {m.mention}" for m in squad),
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Good luck squad! Get that Booyah! 🏆")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(FunCog(bot))
