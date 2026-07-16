"""
🤖 AI Assistant Cog — Powered by OpenAI GPT
Answers Free Fire questions, gives tips, and chats with members
"""

import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
from datetime import datetime

log = logging.getLogger("cog.ai")

# OpenAI is optional — bot works without it
try:
    from openai import AsyncOpenAI
    _openai_available = True
except ImportError:
    _openai_available = False

SYSTEM_PROMPT = """You are Booyah Bot, the AI assistant for a Free Fire gaming Discord server.
You are enthusiastic, friendly, and an expert on Free Fire (the mobile battle royale game by Garena).
You help players with:
- Character abilities and best builds
- Weapon stats and loadout recommendations
- Map strategies and drop locations
- Ranked tips and climbing advice
- In-game events and news
- Squad coordination tips
- General gaming questions

Keep responses concise (under 300 words), use emojis occasionally, and always be hype and supportive.
If asked something unrelated to gaming, politely redirect to gaming topics.
"""


class AIAssistantCog(commands.Cog, name="AI Assistant"):
    """AI-powered assistant for Free Fire tips and questions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = AsyncOpenAI(api_key=self.api_key) if (_openai_available and self.api_key and self.api_key != "your_openai_api_key_here") else None
        # Simple conversation memory per user (last 6 messages)
        self.history: dict[int, list] = {}

    # ── /ask ──────────────────────────────────────────────
    @app_commands.command(name="ask", description="Ask the AI anything about Free Fire 🤖")
    @app_commands.describe(question="Your question for Booyah Bot")
    async def slash_ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()

        if not self.client:
            embed = discord.Embed(
                title="🤖 Booyah Bot — AI Tips",
                description=self._fallback_answer(question),
                color=0x9B59B6,
                timestamp=datetime.utcnow(),
            )
            embed.set_footer(text="Add OPENAI_API_KEY to .env for full AI responses")
            await interaction.followup.send(embed=embed)
            return

        user_id = interaction.user.id
        if user_id not in self.history:
            self.history[user_id] = []

        self.history[user_id].append({"role": "user", "content": question})
        # Keep last 6 exchanges
        if len(self.history[user_id]) > 12:
            self.history[user_id] = self.history[user_id][-12:]

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}]
                         + self.history[user_id],
                max_tokens=400,
                temperature=0.8,
            )
            answer = response.choices[0].message.content
            self.history[user_id].append({"role": "assistant", "content": answer})

            embed = discord.Embed(
                title="🤖 Booyah Bot",
                description=answer,
                color=0x9B59B6,
                timestamp=datetime.utcnow(),
            )
            embed.set_author(
                name=f"Asked by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url,
            )
            embed.set_footer(text="Powered by GPT-4o-mini • /ask anything!")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            log.error(f"OpenAI error: {e}")
            await interaction.followup.send(
                "⚠️ AI is taking a break. Try again in a moment!", ephemeral=True
            )

    # ── /tip ──────────────────────────────────────────────
    @app_commands.command(name="tip", description="Get a random Free Fire pro tip 💡")
    async def slash_tip(self, interaction: discord.Interaction):
        tips = [
            "🎯 **Gloo Wall placement** — Always place walls perpendicular to your enemy for max cover.",
            "🔫 **Weapon combo** — AR + Shotgun is the most versatile combo for all ranges.",
            "🏃 **Movement** — Crouch-spam while shooting to reduce your hitbox significantly.",
            "🗺️ **Drop smart** — Land at the edge of the safe zone early to loot without pressure.",
            "💊 **Heal priority** — Always heal behind cover. Never heal in the open.",
            "🎧 **Use headphones** — Footstep audio is crucial for detecting enemies.",
            "🔥 **Character combo** — Pair Chrono's shield with Jota's healing for aggressive plays.",
            "🏠 **Building control** — High ground in buildings gives massive advantage in late game.",
            "🚗 **Vehicle use** — Use vehicles to rotate quickly but ditch them before the final circle.",
            "👀 **Third-party** — Always listen for nearby fights and third-party weakened squads.",
            "💎 **Ranked tip** — Survival points matter more than kills in early ranked games.",
            "🎯 **Aim training** — Use Clash Squad to practice aim before ranked BR sessions.",
        ]
        import random
        tip = random.choice(tips)
        embed = discord.Embed(
            title="💡 Free Fire Pro Tip",
            description=tip,
            color=0xFFD700,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Use /ask for personalized advice from Booyah Bot")
        await interaction.response.send_message(embed=embed)

    # ── /build ────────────────────────────────────────────
    @app_commands.command(name="build", description="Get a character build recommendation 🧬")
    @app_commands.describe(playstyle="Your playstyle")
    @app_commands.choices(playstyle=[
        app_commands.Choice(name="Aggressive Rusher",  value="aggressive"),
        app_commands.Choice(name="Support/Healer",     value="support"),
        app_commands.Choice(name="Sniper/Passive",     value="sniper"),
        app_commands.Choice(name="All-Rounder",        value="allround"),
        app_commands.Choice(name="Clash Squad",        value="clashsquad"),
    ])
    async def slash_build(self, interaction: discord.Interaction, playstyle: str):
        builds = {
            "aggressive": {
                "title": "⚔️ Aggressive Rusher Build",
                "main": "Chrono (active)",
                "skills": ["Jota (passive)", "Hayato (passive)", "Joseph (passive)"],
                "weapon": "MP40 + M1887 Shotgun",
                "pet": "Falco (faster glide for hot drops)",
                "tip": "Rush enemies right after they heal. Use Chrono shield to push.",
            },
            "support": {
                "title": "💊 Support / Healer Build",
                "main": "Alok (active)",
                "skills": ["Jota (passive)", "Moco (passive)", "Luqueta (passive)"],
                "weapon": "SCAR + MP40",
                "pet": "Ottero (EP recovery)",
                "tip": "Stay near teammates. Drop healing aura in team fights.",
            },
            "sniper": {
                "title": "🎯 Sniper / Passive Build",
                "main": "Rafael (active)",
                "skills": ["Hayato (passive)", "Moco (passive)", "Laura (passive)"],
                "weapon": "AWM/Kar98 + AR",
                "pet": "Shiba (detects enemies)",
                "tip": "Use silenced sniper with Rafael for stealth kills.",
            },
            "allround": {
                "title": "🔄 All-Rounder Build",
                "main": "Skyler (active)",
                "skills": ["Jota (passive)", "Hayato (passive)", "Joseph (passive)"],
                "weapon": "AK + M1887",
                "pet": "Falco",
                "tip": "Skyler destroys Gloo Walls — great for breaking enemy cover.",
            },
            "clashsquad": {
                "title": "🏆 Clash Squad Build",
                "main": "Chrono (active)",
                "skills": ["Jota (passive)", "Dasha (passive)", "Shirou (passive)"],
                "weapon": "M1887 + MP40",
                "pet": "Ottero",
                "tip": "Buy armor first round. Save Chrono for clutch moments.",
            },
        }

        b = builds[playstyle]
        embed = discord.Embed(title=b["title"], color=0xFF4500, timestamp=datetime.utcnow())
        embed.add_field(name="🧬 Main Character", value=b["main"],              inline=True)
        embed.add_field(name="🔫 Weapon Combo",   value=b["weapon"],            inline=True)
        embed.add_field(name="🐾 Pet",            value=b["pet"],               inline=True)
        embed.add_field(name="⚡ Passive Skills",  value="\n".join(b["skills"]), inline=False)
        embed.add_field(name="💡 Strategy",        value=b["tip"],               inline=False)
        embed.set_footer(text="Use /ask for more detailed build advice")
        await interaction.response.send_message(embed=embed)

    def _fallback_answer(self, question: str) -> str:
        """Basic keyword-based answers when OpenAI is not configured."""
        q = question.lower()
        if any(w in q for w in ["best character", "character", "skill"]):
            return "🧬 **Top characters:** Chrono (shield), Alok (heal aura), Skyler (destroy walls), Jota (heal on kills). Combine 1 active + 3 passives for best results!"
        if any(w in q for w in ["weapon", "gun", "loadout"]):
            return "🔫 **Best loadout:** M1887 Shotgun + MP40 for close range. AK47 + AWM for all-range. SCAR + M1887 for balanced play."
        if any(w in q for w in ["rank", "ranked", "climb"]):
            return "🏅 **Ranked tips:** Survive first, kill second. Land edge of zone. Third-party fights. Use Clash Squad to warm up before ranked."
        if any(w in q for w in ["map", "drop", "location"]):
            return "🗺️ **Best drop spots:** Pochinok (high loot, central), Bimasakti Strip (medium risk), Hangar (good loot, less contested)."
        return "🤖 I'm Booyah Bot! Add your **OPENAI_API_KEY** to `.env` for full AI answers. For now, try `/tip` or `/build` for Free Fire advice!"


async def setup(bot: commands.Bot):
    await bot.add_cog(AIAssistantCog(bot))
