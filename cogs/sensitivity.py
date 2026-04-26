"""
🎯 Sensitivity Cog
- /sensitivity  — built-in recommended settings for phone & emulator
- /sensvideo    — search YouTube for real-time sensitivity videos
- /phonesetup   — full phone setup guide
- /emulatorsetup — full emulator setup guide
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import os
import logging

log = logging.getLogger("cog.sensitivity")

try:
    from googleapiclient.discovery import build as yt_build
    _yt_available = True
except ImportError:
    _yt_available = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _transcript_available = True
except ImportError:
    _transcript_available = False

import re

# ── Built-in sensitivity presets ─────────────────────────
PHONE_PRESETS = {
    "General": {
        "description": "Balanced settings for most Android/iOS phones",
        "general":     "100",
        "red_dot":     "90",
        "2x_scope":    "80",
        "4x_scope":    "60",
        "awm_scope":   "50",
        "free_look":   "80",
        "tip": "Start here and adjust ±10 based on your feel.",
    },
    "Aggressive": {
        "description": "High sensitivity for rushers and close-range",
        "general":     "150",
        "red_dot":     "140",
        "2x_scope":    "120",
        "4x_scope":    "90",
        "awm_scope":   "70",
        "free_look":   "130",
        "tip": "Good for M1887 + MP40 aggressive playstyle. High general for fast flicks.",
    },
    "Sniper": {
        "description": "Low sensitivity for precise long-range shots",
        "general":     "80",
        "red_dot":     "75",
        "2x_scope":    "65",
        "4x_scope":    "45",
        "awm_scope":   "35",
        "free_look":   "70",
        "tip": "Pair with AWM or Kar98. Keep AWM scope low for pixel-perfect shots.",
    },
    "Heroic": {
        "description": "Used by top Heroic/Grandmaster players",
        "general":     "170",
        "red_dot":     "160",
        "2x_scope":    "140",
        "4x_scope":    "100",
        "awm_scope":   "75",
        "free_look":   "150",
        "tip": "Very high general + red dot for instant tracking in ranked. Takes practice.",
    },
}

EMULATOR_PRESETS = {
    "General": {
        "description": "Balanced for GameLoop / LDPlayer / BlueStacks",
        "general":     "80",
        "red_dot":     "72",
        "2x_scope":    "65",
        "4x_scope":    "50",
        "awm_scope":   "38",
        "free_look":   "70",
        "dpi":         "400–800 DPI mouse",
        "tip": "Mouse gives more precision than touch — keep sensitivity moderate.",
    },
    "Aggressive": {
        "description": "Fast tracking for close-range emulator play",
        "general":     "100",
        "red_dot":     "90",
        "2x_scope":    "80",
        "4x_scope":    "62",
        "awm_scope":   "48",
        "free_look":   "90",
        "dpi":         "800–1200 DPI mouse",
        "tip": "Increase DPI on mouse for faster flicks.",
    },
    "Sniper": {
        "description": "Precise long-range emulator settings",
        "general":     "60",
        "red_dot":     "55",
        "2x_scope":    "48",
        "4x_scope":    "35",
        "awm_scope":   "25",
        "free_look":   "55",
        "dpi":         "400 DPI mouse",
        "tip": "Low DPI + low sensitivity = pixel-perfect shots.",
    },
    "Pro": {
        "description": "Used by top emulator players in tournaments",
        "general":     "85",
        "red_dot":     "78",
        "2x_scope":    "70",
        "4x_scope":    "55",
        "awm_scope":   "42",
        "free_look":   "75",
        "dpi":         "600–800 DPI mouse",
        "tip": "Consistent mid-range settings for all weapons.",
    },
    "MSI5": {
        "description": "Optimised for MSI Afterburner + BlueStacks 5 / MuMu Player",
        "general":     "88",
        "red_dot":     "80",
        "2x_scope":    "72",
        "4x_scope":    "56",
        "awm_scope":   "42",
        "free_look":   "78",
        "dpi":         "800 DPI — disable Windows mouse acceleration",
        "tip": (
            "BlueStacks 5 settings:\n"
            "• Performance: High (Hyper-V or Android 9)\n"
            "• Resolution: 1280×720 @ 60fps\n"
            "• CPU: 4 cores | RAM: 4GB\n"
            "• Enable High FPS mode in BlueStacks settings\n"
            "• In-game: Graphics = Smooth, Frame Rate = Ultra\n"
            "• Disable mouse acceleration: Windows Settings → Mouse → Additional settings → Pointer Options → uncheck 'Enhance pointer precision'"
        ),
    },
    "BlueStacks5": {
        "description": "BlueStacks 5 competitive settings for ranked play",
        "general":     "92",
        "red_dot":     "84",
        "2x_scope":    "76",
        "4x_scope":    "58",
        "awm_scope":   "45",
        "free_look":   "82",
        "dpi":         "800–1000 DPI",
        "tip": (
            "BlueStacks 5 keybind tips:\n"
            "• WASD — Move | Space — Jump | C — Crouch\n"
            "• F — Interact | Q/E — Peek | R — Reload\n"
            "• Mouse wheel — Switch weapons\n"
            "• Set shooting mode to 'Right click to ADS'\n"
            "• Enable 'Eco Mode' OFF for max performance"
        ),
    },
}

# YouTube search queries per category
YT_QUERIES = {
    "phone_general":      "Free Fire best sensitivity settings mobile 2025",
    "phone_aggressive":   "Free Fire aggressive sensitivity settings phone 2025",
    "phone_sniper":       "Free Fire sniper sensitivity settings mobile 2025",
    "phone_heroic":       "Free Fire heroic grandmaster sensitivity settings 2025",
    "emulator_general":   "Free Fire emulator sensitivity settings GameLoop 2025",
    "emulator_pro":       "Free Fire emulator pro sensitivity settings PC 2025",
    "emulator_sniper":    "Free Fire emulator sniper sensitivity settings 2025",
    "emulator_msi5":      "Free Fire BlueStacks 5 sensitivity settings PC 2025",
    "emulator_bluestacks5": "Free Fire BlueStacks 5 best settings competitive 2025",
    "phone_hud":          "Free Fire best HUD layout settings mobile 2025",
    "emulator_hud":       "Free Fire emulator HUD keybinds settings 2025",
}


def extract_sensitivity_from_text(text: str) -> dict | None:
    """
    Parse sensitivity numbers from a YouTube video description or transcript.
    Looks for patterns like:
      General: 150  |  Red Dot: 140  |  2x: 120  etc.
    Returns a dict of found values or None if nothing found.
    """
    text = text.replace("\n", " ").replace("|", " ").lower()

    patterns = {
        "general":  r"general[\s:=\-]+(\d{1,3})",
        "red_dot":  r"red\s*dot[\s:=\-]+(\d{1,3})",
        "2x_scope": r"2x[\s:=\-]+(\d{1,3})",
        "4x_scope": r"4x[\s:=\-]+(\d{1,3})",
        "awm_scope":r"(?:awm|sniper)[\s:=\-]+(\d{1,3})",
        "free_look":r"free\s*look[\s:=\-]+(\d{1,3})",
    }

    found = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            val = int(match.group(1))
            if 1 <= val <= 200:  # valid FF sensitivity range
                found[key] = str(val)

    return found if len(found) >= 3 else None  # need at least 3 values to be useful


async def scrape_video_sensitivity(video_id: str, description: str) -> dict | None:
    """
    Try to extract sensitivity settings from:
    1. Video description (fastest)
    2. Video transcript/captions (fallback)
    Returns dict of sensitivity values or None.
    """
    # Try description first
    result = extract_sensitivity_from_text(description)
    if result:
        log.info(f"Scraped sensitivity from description: {video_id}")
        return result

    # Try transcript
    if not _transcript_available:
        return None

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        full_text = " ".join(entry["text"] for entry in transcript_list[:100])  # first ~100 lines
        result = extract_sensitivity_from_text(full_text)
        if result:
            log.info(f"Scraped sensitivity from transcript: {video_id}")
            return result
    except Exception as e:
        log.debug(f"Transcript unavailable for {video_id}: {e}")

    return None


def build_sens_embed(preset: dict, name: str, platform: str, color: int) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎯 {platform} — {name} Sensitivity",
        description=preset["description"],
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="🔵 General",      value=preset["general"],   inline=True)
    embed.add_field(name="🔴 Red Dot",      value=preset["red_dot"],   inline=True)
    embed.add_field(name="🔭 2x Scope",     value=preset["2x_scope"],  inline=True)
    embed.add_field(name="🔭 4x Scope",     value=preset["4x_scope"],  inline=True)
    embed.add_field(name="🎯 AWM Scope",    value=preset["awm_scope"], inline=True)
    embed.add_field(name="👁️ Free Look",    value=preset["free_look"], inline=True)
    if "dpi" in preset:
        embed.add_field(name="🖱️ Mouse DPI", value=preset["dpi"],      inline=True)
    embed.add_field(name="💡 Pro Tip",      value=preset["tip"],       inline=False)
    embed.set_footer(text="Use /sensvideo to find YouTube tutorials • Free Fire Squad")
    return embed


async def search_youtube(query: str, max_results: int = 4) -> list[dict]:
    """Search YouTube from the last 7 days, sorted by view count."""
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key or api_key == "your_youtube_api_key_here":
        return []
    if not _yt_available:
        return []
    try:
        from datetime import timezone, timedelta
        youtube = yt_build("youtube", "v3", developerKey=api_key)

        # Published after date = 7 days ago in RFC 3339 format
        published_after = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Step 1: Search last 7 days
        search_req = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=15,
            order="viewCount",
            relevanceLanguage="en",
            safeSearch="moderate",
            videoDuration="medium",
            publishedAfter=published_after,
        )
        search_resp = search_req.execute()
        items = search_resp.get("items", [])

        # If nothing in last 7 days, fall back to last 30 days
        if not items:
            published_after = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            search_req = youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=15,
                order="viewCount",
                relevanceLanguage="en",
                safeSearch="moderate",
                videoDuration="medium",
                publishedAfter=published_after,
            )
            search_resp = search_req.execute()
            items = search_resp.get("items", [])

        # If still nothing, drop the date filter entirely
        if not items:
            search_req = youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=15,
                order="viewCount",
                relevanceLanguage="en",
                safeSearch="moderate",
                videoDuration="medium",
            )
            search_resp = search_req.execute()
            items = search_resp.get("items", [])

        if not items:
            return []

        # Step 2: Get real view counts via videos.list
        video_ids = [item["id"]["videoId"] for item in items]
        stats_req = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids),
        )
        stats_resp = stats_req.execute()

        results = []
        for item in stats_resp.get("items", []):
            stats   = item.get("statistics", {})
            snippet = item["snippet"]
            views   = int(stats.get("viewCount", 0))
            results.append({
                "title":       snippet["title"],
                "channel":     snippet["channelTitle"],
                "url":         f"https://www.youtube.com/watch?v={item['id']}",
                "thumbnail":   snippet["thumbnails"]["medium"]["url"],
                "published":   snippet["publishedAt"][:10],
                "views":       views,
                "views_fmt":   f"{views:,}",
                "video_id":    item["id"],
                "description": snippet.get("description", ""),
            })

        # Sort by views descending
        results.sort(key=lambda x: x["views"], reverse=True)
        return results[:max_results]

    except Exception as e:
        log.error(f"YouTube search error: {e}")
        return []


class SensitivityCog(commands.Cog, name="Sensitivity"):
    """Free Fire sensitivity settings and YouTube video search."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /sensitivity ──────────────────────────────────────
    @app_commands.command(name="sensitivity", description="Get Free Fire sensitivity settings 🎯")
    @app_commands.describe(
        platform="Phone or PC Emulator?",
        style="Your playstyle",
        phone_model="Your phone model for device-specific videos (e.g. iPhone 15, Samsung S24, Redmi Note 13)",
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="📱 Phone (Android/iOS)", value="phone"),
        app_commands.Choice(name="💻 PC Emulator (GameLoop/LDPlayer)", value="emulator"),
    ])
    @app_commands.choices(style=[
        app_commands.Choice(name="⚖️ General (Balanced)",        value="General"),
        app_commands.Choice(name="⚔️ Aggressive (Rusher)",       value="Aggressive"),
        app_commands.Choice(name="🎯 Sniper (Long Range)",       value="Sniper"),
        app_commands.Choice(name="💎 Heroic / Pro",              value="Heroic"),
        app_commands.Choice(name="🖥️ MSI5 / BlueStacks 5",      value="MSI5"),
        app_commands.Choice(name="🟦 BlueStacks 5 Competitive",  value="BlueStacks5"),
    ])
    async def slash_sensitivity(
        self,
        interaction: discord.Interaction,
        platform: str,
        style: str = "General",
        phone_model: str = None,
    ):
        await interaction.response.defer()

        if platform == "phone":
            preset = PHONE_PRESETS.get(style, PHONE_PRESETS["General"])
            color = 0x00BFFF
            plat_label = "📱 Phone"
            if phone_model:
                # Tight query — must mention the exact phone model
                clean_model = phone_model.strip()
                query = f'Free Fire sensitivity settings "{clean_model}" 2025'
                # Adjust preset tip based on brand
                model_lower = clean_model.lower()
                if any(x in model_lower for x in ["iphone", "ios", "apple"]):
                    preset = dict(preset)
                    preset["tip"] = f"iPhone tip: Enable 120fps in Free Fire if your model supports it (iPhone 13+). Use ProMotion display for smoother tracking. " + preset["tip"]
                elif any(x in model_lower for x in ["samsung", "galaxy"]):
                    preset = dict(preset)
                    preset["tip"] = f"Samsung tip: Enable Game Booster, set display to 120Hz, and turn off adaptive brightness during gameplay. " + preset["tip"]
                elif any(x in model_lower for x in ["redmi", "xiaomi", "poco"]):
                    preset = dict(preset)
                    preset["tip"] = f"Xiaomi/Redmi tip: Enable MIUI Game Turbo, set touch sampling rate to 240Hz if available, disable notifications. " + preset["tip"]
                elif any(x in model_lower for x in ["rog", "asus"]):
                    preset = dict(preset)
                    preset["tip"] = f"ASUS ROG tip: Use X Mode, set display to 165Hz, enable AirTriggers for fire/scope buttons. " + preset["tip"]
                elif any(x in model_lower for x in ["oneplus", "one plus"]):
                    preset = dict(preset)
                    preset["tip"] = f"OnePlus tip: Enable Pro Gaming Mode, set display to 120Hz, use HyperBoost Gaming Engine. " + preset["tip"]
                elif any(x in model_lower for x in ["oppo", "realme"]):
                    preset = dict(preset)
                    preset["tip"] = f"OPPO/Realme tip: Enable O-Sync display, use Game Space for performance boost, set touch response to Fast. " + preset["tip"]
                elif any(x in model_lower for x in ["vivo", "iqoo"]):
                    preset = dict(preset)
                    preset["tip"] = f"Vivo/iQOO tip: Enable Ultra Game Mode, set display refresh to 120Hz, use Monster Mode for max performance. " + preset["tip"]
                elif any(x in model_lower for x in ["pixel", "google"]):
                    preset = dict(preset)
                    preset["tip"] = f"Pixel tip: Enable Smooth Display (90/120Hz), use Game Dashboard, disable battery saver during play. " + preset["tip"]
            else:
                query = YT_QUERIES.get(f"phone_{style.lower()}", YT_QUERIES["phone_general"])
        else:
            preset = EMULATOR_PRESETS.get(style, EMULATOR_PRESETS["General"])
            if style == "Heroic":
                preset = EMULATOR_PRESETS["Pro"]
                style = "Pro"
            color = 0x9B59B6
            plat_label = "💻 Emulator"
            query = YT_QUERIES.get(f"emulator_{style.lower()}", YT_QUERIES["emulator_general"])
            phone_model = None

        # Build settings embed
        embed = build_sens_embed(preset, style, plat_label, color)

        # Show device if specified
        if phone_model:
            embed.insert_field_at(0, name="📱 Device", value=phone_model, inline=True)

        # Search YouTube
        videos = await search_youtube(query, max_results=5)

        # Try to scrape sensitivity from each video until one works
        scraped = None
        source_video = None
        if videos:
            for v in videos:
                scraped = await scrape_video_sensitivity(
                    v.get("video_id", ""),
                    v.get("description", ""),
                )
                if scraped:
                    source_video = v
                    break

        # ── Build the embed ───────────────────────────────
        if scraped and source_video:
            # Settings came directly from this specific video
            title_line = f"🎯 {plat_label} Sensitivity"
            if phone_model:
                title_line += f" — {phone_model}"

            embed = discord.Embed(
                title=title_line,
                color=color,
                timestamp=datetime.utcnow(),
            )

            # Video source banner at the top
            embed.set_author(
                name=f"📺 Source: {source_video['channel']}",
                url=source_video["url"],
                icon_url="https://i.imgur.com/8QfKFqA.png",
            )
            embed.set_thumbnail(url=source_video.get("thumbnail", ""))

            if phone_model:
                embed.add_field(name="📱 Device",     value=phone_model,                    inline=True)
            embed.add_field(name="🎬 Video",          value=f"[{source_video['title'][:55]}]({source_video['url']})", inline=False)
            embed.add_field(name="👁️ Views",          value=source_video.get("views_fmt","?"), inline=True)
            embed.add_field(name="📅 Uploaded",       value=source_video.get("published","?"), inline=True)
            embed.add_field(name="📺 Channel",        value=source_video["channel"],           inline=True)

            embed.add_field(name="\u200b", value="**— Sensitivity Settings from this video —**", inline=False)

            embed.add_field(name="🔵 General",   value=scraped.get("general",  "—"), inline=True)
            embed.add_field(name="🔴 Red Dot",   value=scraped.get("red_dot",  "—"), inline=True)
            embed.add_field(name="🔭 2x Scope",  value=scraped.get("2x_scope", "—"), inline=True)
            embed.add_field(name="🔭 4x Scope",  value=scraped.get("4x_scope", "—"), inline=True)
            embed.add_field(name="🎯 AWM Scope", value=scraped.get("awm_scope","—"), inline=True)
            embed.add_field(name="👁️ Free Look", value=scraped.get("free_look","—"), inline=True)
            if "dpi" in preset:
                embed.add_field(name="🖱️ Mouse DPI", value=preset["dpi"], inline=True)

            embed.set_footer(text="✅ Settings pulled directly from this video • Free Fire Squad")

        else:
            # No scrapeable video found — use preset + link videos
            embed = build_sens_embed(preset, style, plat_label, color)
            if phone_model:
                embed.insert_field_at(0, name="📱 Device", value=phone_model, inline=True)

            if videos:
                links = "\n".join(
                    f"[{v['title'][:55]}]({v['url']})\n"
                    f"└ {v['channel']} • 👁️ {v.get('views_fmt','?')} views • 📅 {v.get('published','')}"
                    for v in videos[:3]
                )
                embed.add_field(
                    name="📺 Related Videos (settings not found in description)",
                    value=links,
                    inline=False,
                )
            else:
                search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
                embed.add_field(
                    name="📺 Search YouTube",
                    value=f"[🔍 Find tutorials here]({search_url})",
                    inline=False,
                )

        await interaction.followup.send(embed=embed)

    # ── /sensvideo ────────────────────────────────────────
    @app_commands.command(name="sensvideo", description="Find YouTube sensitivity tutorials 📺")
    @app_commands.describe(
        platform="Phone or Emulator?",
        style="What type of sensitivity video?",
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="📱 Phone",     value="phone"),
        app_commands.Choice(name="💻 Emulator",  value="emulator"),
    ])
    @app_commands.choices(style=[
        app_commands.Choice(name="⚖️ General",   value="general"),
        app_commands.Choice(name="⚔️ Aggressive", value="aggressive"),
        app_commands.Choice(name="🎯 Sniper",    value="sniper"),
        app_commands.Choice(name="💎 Heroic/Pro", value="heroic"),
        app_commands.Choice(name="🖥️ HUD Layout", value="hud"),
    ])
    async def slash_sensvideo(
        self,
        interaction: discord.Interaction,
        platform: str,
        style: str = "general",
    ):
        await interaction.response.defer()

        key = f"{platform}_{style}"
        if key not in YT_QUERIES:
            key = f"{platform}_general"
        query = YT_QUERIES[key]

        results = await search_youtube(query, max_results=4)

        if not results:
            # Fallback embed with manual search link
            embed = discord.Embed(
                title="📺 Free Fire Sensitivity Videos",
                description=(
                    f"YouTube API not configured or no results found.\n\n"
                    f"**Search manually:**\n"
                    f"[🔍 Click here to search YouTube]"
                    f"(https://www.youtube.com/results?search_query={query.replace(' ', '+')})"
                ),
                color=0xFF0000,
            )
            embed.set_footer(text="Add YOUTUBE_API_KEY to .env for auto-search")
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(
            title=f"📺 Free Fire — {platform.title()} {style.title()} Sensitivity Videos",
            description=f"Latest YouTube results for: `{query}`",
            color=0xFF0000,
            timestamp=datetime.utcnow(),
        )

        for i, video in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {video['title'][:60]}",
                value=(
                    f"📺 [{video['channel']}]({video['url']})\n"
                    f"📅 {video['published']}\n"
                    f"🔗 [Watch Now]({video['url']})"
                ),
                inline=False,
            )

        if results:
            embed.set_thumbnail(url=results[0]["thumbnail"])

        embed.set_footer(text="Results from YouTube • Use /sensitivity for built-in settings")
        await interaction.followup.send(embed=embed)

    # ── /phonesetup ───────────────────────────────────────
    @app_commands.command(name="phonesetup", description="Complete phone settings guide 📱")
    async def slash_phonesetup(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="📱 Free Fire — Complete Phone Setup Guide",
            color=0x00BFFF,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="⚙️ Graphics Settings",
            value=(
                "• **Resolution:** HD or Ultra HD\n"
                "• **Graphics:** Smooth or Balanced\n"
                "• **Frame Rate:** Ultra (60fps)\n"
                "• **Anti-Aliasing:** OFF\n"
                "• **Auto-Adjust Graphics:** OFF"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎯 Sensitivity (General Preset)",
            value=(
                "• General: **100** | Red Dot: **90**\n"
                "• 2x Scope: **80** | 4x Scope: **60**\n"
                "• AWM Scope: **50** | Free Look: **80**"
            ),
            inline=False,
        )
        embed.add_field(
            name="🖐️ HUD Tips",
            value=(
                "• Use **4-finger claw** for best control\n"
                "• Fire button bottom-right\n"
                "• Crouch + jump on left side\n"
                "• Use `/sensitivity` for more presets"
            ),
            inline=False,
        )

        videos = await search_youtube("Free Fire best phone settings setup guide 2025", max_results=3)
        if videos:
            embed.add_field(
                name="📺 Top Video Sources (by views)",
                value="\n".join(f"[{v['title'][:50]}]({v['url']}) — {v['channel']} • 👁️ {v.get('views_fmt','?')} views" for v in videos),
                inline=False,
            )
        else:
            embed.add_field(
                name="📺 Video Sources",
                value="[🔍 Search YouTube](https://www.youtube.com/results?search_query=Free+Fire+phone+setup+guide+2025)\n⚠️ Add `YOUTUBE_API_KEY` to `.env` for live results",
                inline=False,
            )
        embed.set_footer(text="Use /sensitivity for specific presets")
        await interaction.followup.send(embed=embed)

    # ── /emulatorsetup ────────────────────────────────────
    @app_commands.command(name="emulatorsetup", description="Complete PC emulator settings guide 💻")
    async def slash_emulatorsetup(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="💻 Free Fire — Complete Emulator Setup Guide",
            color=0x9B59B6,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="🖥️ Recommended Emulators",
            value="• **GameLoop** (Official)\n• **LDPlayer 9**\n• **BlueStacks 5**",
            inline=False,
        )
        embed.add_field(
            name="⚙️ Emulator Settings",
            value="• Resolution: **1280x720**\n• FPS: **60**\n• CPU: **4 cores** | RAM: **4GB+**",
            inline=False,
        )
        embed.add_field(
            name="🎯 Sensitivity (General Preset)",
            value=(
                "• General: **55** | Red Dot: **50**\n"
                "• 2x: **45** | 4x: **35** | AWM: **28**\n"
                "• Free Look: **50** | Mouse DPI: **400–800**"
            ),
            inline=False,
        )
        embed.add_field(
            name="⌨️ Key Bindings",
            value="• WASD — Move | Space — Jump | C — Crouch\n• F — Interact | Q/E — Peek",
            inline=False,
        )

        videos = await search_youtube("Free Fire emulator settings guide GameLoop 2025", max_results=3)
        if videos:
            embed.add_field(
                name="📺 Top Video Sources (by views)",
                value="\n".join(f"[{v['title'][:50]}]({v['url']}) — {v['channel']} • 👁️ {v.get('views_fmt','?')} views" for v in videos),
                inline=False,
            )
        else:
            embed.add_field(
                name="📺 Video Sources",
                value="[🔍 Search YouTube](https://www.youtube.com/results?search_query=Free+Fire+emulator+setup+guide+2025)\n⚠️ Add `YOUTUBE_API_KEY` to `.env` for live results",
                inline=False,
            )
        embed.set_footer(text="Use /sensitivity for specific presets")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SensitivityCog(bot))
