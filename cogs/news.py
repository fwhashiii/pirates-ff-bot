"""
🔥 News Cog — Fetches latest Free Fire news & posts auto-updates
Sources: freefireinfo.in RSS / web scrape
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import feedparser
import os
import logging
from datetime import datetime

log = logging.getLogger("cog.news")

FF_RSS_FEEDS = [
    "https://freefireinfo.in/feed/",  # Primary — Free Fire only
]

# Keywords that must appear in title or summary for the article to be posted
FF_KEYWORDS = [
    "free fire", "freefire", "ff max", "garena", "booyah",
    "ffws", "free fire max", "ff esports", "free fire esports",
    "free fire update", "free fire event", "free fire patch",
    "free fire character", "free fire skin", "free fire rank",
]

# Keywords that disqualify an article (other games)
BLOCKED_KEYWORDS = [
    "pubg", "bgmi", "call of duty", "cod", "fortnite", "apex",
    "valorant", "minecraft", "roblox", "genshin", "mobile legends",
    "clash of clans", "clash royale", "pokemon", "fifa", "warzone",
    "battlegrounds", "arena of valor", "honor of kings",
]

# Track posted article URLs so we don't double-post
_posted_urls: set[str] = set()


def is_ff_article(entry: dict) -> bool:
    """Return True only if the article is actually about Free Fire."""
    text = (
        (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    )
    # Must contain at least one FF keyword
    if not any(kw in text for kw in FF_KEYWORDS):
        return False
    # Must not contain blocked game keywords
    if any(kw in text for kw in BLOCKED_KEYWORDS):
        return False
    return True


def ff_news_embed(entry: dict) -> discord.Embed:
    """Build a styled embed from an RSS feed entry."""
    embed = discord.Embed(
        title=entry.get("title", "Free Fire News"),
        url=entry.get("link", ""),
        description=(entry.get("summary", "")[:300] + "…") if entry.get("summary") else "",
        color=0xFF4500,  # Fiery orange
        timestamp=datetime.utcnow(),
    )
    embed.set_author(
        name="🔥 Free Fire News",
        icon_url="https://i.imgur.com/8QfKFqA.png",
    )
    # Try to grab thumbnail from media content
    media = entry.get("media_content", [])
    if media and isinstance(media, list):
        embed.set_thumbnail(url=media[0].get("url", ""))
    embed.set_footer(text="freefireinfo.in • Stay ahead of the game")
    return embed


class NewsCog(commands.Cog, name="News"):
    """Free Fire news, patch notes, and event updates."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.news_channel_id = int(os.getenv("NEWS_CHANNEL_ID", 0))
        self.auto_news_task.start()

    def cog_unload(self):
        self.auto_news_task.cancel()

    # ── Auto-post news every 30 minutes ──────────────────
    @tasks.loop(minutes=30)
    async def auto_news_task(self):
        if not self.news_channel_id:
            return
        channel = self.bot.get_channel(self.news_channel_id)
        if not channel:
            return

        for feed_url in FF_RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:  # check more, filter down
                    url = entry.get("link", "")
                    if url and url not in _posted_urls and is_ff_article(entry):
                        _posted_urls.add(url)
                        embed = ff_news_embed(entry)
                        await channel.send(embed=embed)
            except Exception as e:
                log.error(f"News fetch error ({feed_url}): {e}")

    @auto_news_task.before_loop
    async def before_news(self):
        await self.bot.wait_until_ready()

    # ── Slash: /news ──────────────────────────────────────
    @app_commands.command(name="news", description="Get the latest Free Fire news 🔥")
    @app_commands.describe(count="How many articles to show (1–5)")
    async def slash_news(self, interaction: discord.Interaction, count: int = 3):
        await interaction.response.defer()
        count = max(1, min(count, 5))
        embeds = []

        for feed_url in FF_RSS_FEEDS[:1]:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:20]:  # scan more to find FF-only ones
                    if is_ff_article(entry):
                        embeds.append(ff_news_embed(entry))
                    if len(embeds) >= count:
                        break
            except Exception as e:
                log.error(f"Manual news fetch error: {e}")

        if embeds:
            for embed in embeds:
                await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "⚠️ Couldn't fetch news right now. Try again in a moment."
            )

    # ── Slash: /events ────────────────────────────────────
    @app_commands.command(name="events", description="See current Free Fire in-game events 🎯")
    async def slash_events(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎯 Free Fire — Active Events (2026)",
            color=0xFFD700,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/8QfKFqA.png")
        embed.add_field(
            name="🏆 Esports World Cup 2026",
            value="📍 Riyadh, Saudi Arabia\n📅 July 15–18, 2026\n24 teams • Massive prize pool",
            inline=False,
        )
        embed.add_field(
            name="🌏 FFWS Global Finals 2026",
            value="📍 Bangkok, Thailand\n📅 Nov 6–29, 2026\n24 teams across 4 weekends",
            inline=False,
        )
        embed.add_field(
            name="🛒 Mystery Shop",
            value="Up to 90% off Mono Enigma & Mono Charm Bundles!",
            inline=False,
        )
        embed.add_field(
            name="💎 Ring Event",
            value="Redeem Universal Ring Tokens for Undersea Bundles & Katana",
            inline=False,
        )
        embed.add_field(
            name="🎁 Top-Up Event",
            value="Free 24K Paw Scythe — limited time top-up reward",
            inline=False,
        )
        embed.set_footer(text="Use /news for full articles • freefireinfo.in")
        await interaction.response.send_message(embed=embed)

    # ── Slash: /patchnotes ────────────────────────────────
    @app_commands.command(name="patchnotes", description="Latest Free Fire patch notes 📋")
    async def slash_patchnotes(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📋 Free Fire — Latest Patch Highlights",
            description="Here's what's new in the latest update:",
            color=0x00BFFF,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🗺️ Map Updates", value="Bermuda & Kalahari balance tweaks", inline=False)
        embed.add_field(name="🔫 Weapon Balancing", value="AR & SMG damage adjustments for ranked play", inline=False)
        embed.add_field(name="🧬 New Character", value="Check in-game for the latest character ability reveal", inline=False)
        embed.add_field(name="🐛 Bug Fixes", value="Lobby crash fix, parachute animation improvements", inline=False)
        embed.add_field(
            name="📰 Full Notes",
            value="[Read on Free Fire Info](https://freefireinfo.in)",
            inline=False,
        )
        embed.set_footer(text="Stay updated • /news for live articles")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(NewsCog(bot))
