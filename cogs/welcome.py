"""
👋 Welcome Cog — Full welcome experience with GIF, PFP, and quick start guide
"""

import discord
from discord.ext import commands
import os
import random
from datetime import datetime

# ── One Piece welcome GIFs ────────────────────────────
WELCOME_GIFS = [
    # Luffy laughing / happy
    "https://media.giphy.com/media/3oEjHGr1Fhz0kyv8Ig/giphy.gif",
    # Luffy excited fist pump
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    # One Piece crew celebration
    "https://media.giphy.com/media/26BRuo6sLetdllPAQ/giphy.gif",
    # Luffy big smile
    "https://media.giphy.com/media/xT9IgG50Lg7russbDa/giphy.gif",
    # Luffy Gear 5 laugh
    "https://media.giphy.com/media/077i6AULCXc0FKTj9s/giphy.gif",
    # One Piece welcome
    "https://media.giphy.com/media/artj92V8o75VPL7AeQ/giphy.gif",
]

# ── Welcome messages (rotates) ────────────────────────
WELCOME_TITLES = [
    "🔥 A new soldier has dropped in!",
    "🪂 Someone just landed on the island!",
    "🏆 A new squad member has arrived!",
    "🎯 Fresh blood just joined the fight!",
    "💥 BOOYAH! New player in the server!",
]

WELCOME_LINES = [
    "Lock and load — the squad just got stronger! 🔥",
    "The island just got a new survivor. Welcome! 🏝️",
    "Another warrior joins the fight. Let's get that Booyah! 🏆",
    "Drop zone secured. Welcome to the squad! 🪂",
    "New player detected. Threat level: BOOYAH! 💥",
]


def get_channel_id(guild: discord.Guild, name: str) -> str:
    ch = discord.utils.get(guild.text_channels, name=name)
    return str(ch.id) if ch else "the channel"


class WelcomeCog(commands.Cog, name="Welcome"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild

        # ── 1. Auto-assign New Player role ───────────────
        new_member_role = discord.utils.get(guild.roles, name="🎮 New Player")
        if new_member_role:
            try:
                await member.add_roles(new_member_role, reason="Auto-assign on join")
            except discord.Forbidden:
                pass

        # ── 2. Find welcome channel ───────────────────────
        welcome_ch_id = int(os.getenv("WELCOME_CHANNEL_ID", 0))
        channel = guild.get_channel(welcome_ch_id)
        if not channel:
            channel = discord.utils.get(guild.text_channels, name="👋│welcome")
        if not channel:
            return

        gif = random.choice(WELCOME_GIFS)
        title = random.choice(WELCOME_TITLES)
        tagline = random.choice(WELCOME_LINES)

        # Get channel IDs for quick start links
        rules_id    = get_channel_id(guild, "📜│rules")
        general_id  = get_channel_id(guild, "💬│general-chat")
        lfg_id      = get_channel_id(guild, "🔍│lfg")
        ai_id       = get_channel_id(guild, "🤖│ai-assistant")
        bot_cmd_id  = get_channel_id(guild, "🤖│bot-commands")

        # ── Main welcome embed ────────────────────────────
        embed = discord.Embed(
            title=title,
            description=(
                f"{tagline}\n\n"
                f"**{member.mention}** just joined — "
                f"they're member **#{guild.member_count}**! 🎉"
            ),
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )

        # Their PFP large on the side
        embed.set_thumbnail(url=member.display_avatar.url)

        # GIF as the main image
        embed.set_image(url=gif)

        # Quick start guide
        embed.add_field(
            name="📋 Quick Start Guide",
            value=(
                f"**Step 1** — Read the rules\n"
                f"└ <#{rules_id}>\n\n"
                f"**Step 2** — Set your Free Fire rank\n"
                f"└ `/rank` in <#{bot_cmd_id}>\n\n"
                f"**Step 3** — Introduce yourself\n"
                f"└ <#{general_id}>\n\n"
                f"**Step 4** — Find squadmates\n"
                f"└ `/lfg` in <#{lfg_id}>\n\n"
                f"**Step 5** — Ask the AI anything\n"
                f"└ `/ask` in <#{ai_id}>"
            ),
            inline=False,
        )

        embed.add_field(
            name="🤖 Useful Commands",
            value=(
                "`/sensitivity` — Get settings for your phone\n"
                "`/stats` — View player stats\n"
                "`/tip` — Get a pro tip\n"
                "`/build` — Character build guide\n"
                "`/help` — See all commands"
            ),
            inline=False,
        )

        embed.set_author(
            name=f"{member.display_name} joined {guild.name}",
            icon_url=member.display_avatar.url,
        )
        embed.set_footer(
            text=f"Free Fire Squad • {guild.name}",
            icon_url=guild.icon.url if guild.icon else None,
        )

        await channel.send(embed=embed)

        # ── 3. DM the new member ──────────────────────────
        try:
            dm_embed = discord.Embed(
                title=f"🔥 Welcome to {guild.name}!",
                description=(
                    f"Hey **{member.display_name}**! You just dropped into **{guild.name}**!\n\n"
                    f"Before you can chat, you need to **verify your Free Fire account**.\n"
                    f"Head to the verify channel and click the button — takes 30 seconds."
                ),
                color=0xFF4500,
            )
            dm_embed.set_thumbnail(url=guild.icon.url if guild.icon else member.display_avatar.url)
            dm_embed.set_image(url=random.choice(WELCOME_GIFS))

            dm_embed.add_field(
                name="📜 Server Rules",
                value=(
                    "**1.** Respect everyone — no toxicity or harassment\n"
                    "**2.** No racist, hateful or offensive language\n"
                    "**3.** No spam or flooding chats\n"
                    "**4.** No NSFW content\n"
                    "**5.** No self-promotion without staff permission\n"
                    "**6.** No cheating discussion\n"
                    "**7.** Listen to staff — their word is final\n\n"
                    "⚠️ Breaking rules = warning → mute → **ban**"
                ),
                inline=False,
            )

            dm_embed.add_field(
                name="✅ How to Verify",
                value=(
                    "**1.** Go to the `✅┃ᴠᴇʀɪꜰʏ` channel in the server\n"
                    "**2.** Click the **Start Verification** button\n"
                    "**3.** Fill in your Free Fire UID, country and language\n"
                    "**4.** Done — you'll get full access instantly\n\n"
                    "📍 **Your UID:** Open Free Fire → tap your profile picture → "
                    "the number below your name is your UID"
                ),
                inline=False,
            )

            dm_embed.add_field(
                name="🤖 Useful Commands",
                value=(
                    "`/sensitivity` — Get settings for your phone\n"
                    "`/rank` — Set your Free Fire rank\n"
                    "`/lfg` — Find squadmates\n"
                    "`/ask` — Ask the AI anything\n"
                    "`/help` — See all commands"
                ),
                inline=False,
            )

            dm_embed.set_footer(text=f"{guild.name} • Free Fire Squad • PIRATES")
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        welcome_ch_id = int(os.getenv("WELCOME_CHANNEL_ID", 0))
        channel = self.bot.get_channel(welcome_ch_id)
        if not channel:
            channel = discord.utils.get(member.guild.text_channels, name="👋│welcome")
        if channel:
            embed = discord.Embed(
                description=(
                    f"👋 **{member.display_name}** has left the server.\n"
                    f"We're now **{member.guild.member_count}** members strong."
                ),
                color=0x7F8C8D,
                timestamp=datetime.utcnow(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
