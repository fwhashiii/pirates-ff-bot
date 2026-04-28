"""
🎵 Music Cog — Play music from YouTube in voice channels
Commands: /play /skip /stop /queue /pause /resume /nowplaying /volume /loop /musicstatus
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import logging
import os
from collections import deque
from datetime import datetime

log = logging.getLogger("cog.music")

FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "ffmpeg")

# ── Cookie file path (VPS or local) ──────────────────────
_COOKIE_PATHS = [
    "/root/bot/youtube_cookies.txt",
    os.path.join(os.path.dirname(__file__), "..", "youtube_cookies.txt"),
]
COOKIE_FILE = next((p for p in _COOKIE_PATHS if os.path.exists(p)), None)

# ── yt-dlp strategies ────────────────────────────────────
_STRATEGIES = [
    # 1. SoundCloud — no bot detection, works on any IP
    {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "scsearch",
        "source_address": "0.0.0.0",
        "socket_timeout": 30,
        "retries": 3,
    },
    # 2. YouTube mweb client
    {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {"player_client": ["mweb"]}
        },
        "socket_timeout": 30,
        "retries": 3,
    },
    # 3. YouTube tv_embedded
    {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {
                "player_client": ["tv_embedded"],
                "player_skip": ["webpage", "configs"],
            }
        },
        "socket_timeout": 30,
        "retries": 3,
    },
    # 4. YouTube android
    {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extractor_args": {
            "youtube": {"player_client": ["android"]}
        },
        "http_headers": {
            "User-Agent": "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip",
        },
        "socket_timeout": 30,
        "retries": 3,
    },
]

# Add cookies to YouTube strategies if available
for _s in _STRATEGIES:
    if COOKIE_FILE and _s.get("default_search") == "ytsearch":
        _s["cookiefile"] = COOKIE_FILE


def search_youtube(query: str) -> dict | None:
    """Try SoundCloud first, then multiple YouTube strategies."""
    # For direct YouTube URLs, skip SoundCloud
    is_yt_url = "youtube.com" in query or "youtu.be" in query
    strategies = _STRATEGIES[1:] if is_yt_url else _STRATEGIES

    if not query.startswith("http"):
        # Try SoundCloud search first (strategy 0), then YouTube
        pass

    last_error = None
    for i, opts in enumerate(strategies):
        search_query = query
        if not search_query.startswith("http"):
            prefix = "scsearch1:" if opts.get("default_search") == "scsearch" else "ytsearch1:"
            search_query = f"{prefix}{query}"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if info is None:
                    continue
                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        continue
                    info = entries[0]

                url = info.get("url")
                if not url:
                    formats = info.get("formats", [])
                    audio_fmts = [
                        f for f in formats
                        if f.get("acodec") != "none" and f.get("vcodec") == "none"
                    ]
                    if audio_fmts:
                        url = audio_fmts[-1]["url"]
                    elif formats:
                        url = formats[-1]["url"]

                if not url:
                    continue

                source = "SoundCloud" if opts.get("default_search") == "scsearch" else "YouTube"
                log.info(f"Strategy {i+1} ({source}) succeeded: {info.get('title', '')[:60]}")
                return {
                    "url":      url,
                    "title":    info.get("title", "Unknown"),
                    "duration": info.get("duration", 0) or 0,
                    "webpage":  info.get("webpage_url", ""),
                    "thumbnail": info.get("thumbnail", ""),
                    "uploader": info.get("uploader", "Unknown"),
                    "source":   source,
                }
        except yt_dlp.utils.DownloadError as e:
            last_error = str(e)
            log.warning(f"Strategy {i+1} failed: {last_error[:100]}")
            continue
        except Exception as e:
            last_error = str(e)
            log.warning(f"Strategy {i+1} error: {last_error[:100]}")
            continue

    log.error(f"All strategies failed. Last: {last_error}")
    return None


def fmt_duration(seconds: int) -> str:
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Per-guild music state ─────────────────────────────────
class GuildMusic:
    def __init__(self):
        self.queue:   deque[dict] = deque()
        self.current: dict | None = None
        self.volume:  float = 0.5
        self.loop:    bool  = False


_states: dict[int, GuildMusic] = {}


def get_state(guild_id: int) -> GuildMusic:
    if guild_id not in _states:
        _states[guild_id] = GuildMusic()
    return _states[guild_id]


class MusicCog(commands.Cog, name="Music"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _play_next(self, guild: discord.Guild):
        state = get_state(guild.id)
        vc = guild.voice_client
        if not vc or not vc.is_connected():
            log.warning("_play_next called but no voice client connected")
            return

        if state.loop and state.current:
            track = state.current
        elif state.queue:
            track = state.queue.popleft()
            state.current = track
        else:
            state.current = None
            asyncio.run_coroutine_threadsafe(
                self._disconnect_when_empty(guild), self.bot.loop
            )
            return

        try:
            source = discord.FFmpegPCMAudio(
                track["url"],
                executable=FFMPEG_PATH,
                before_options=(
                    "-reconnect 1 -reconnect_streamed 1 "
                    "-reconnect_delay_max 5 -nostdin "
                    "-timeout 30000000"
                ),
                options="-vn -loglevel warning -bufsize 64k",
            )
            source = discord.PCMVolumeTransformer(source, volume=state.volume)

            def after(error):
                if error:
                    log.error(f"Playback error: {error}")
                asyncio.run_coroutine_threadsafe(
                    self._after_track(guild), self.bot.loop
                )

            vc.play(source, after=after)
        except Exception as e:
            log.error(f"Failed to start playback: {e}")
            asyncio.run_coroutine_threadsafe(
                self._after_track(guild), self.bot.loop
            )

    async def _after_track(self, guild: discord.Guild):
        await asyncio.sleep(0.5)
        self._play_next(guild)

    async def _disconnect_when_empty(self, guild: discord.Guild):
        """Disconnect after queue is empty (with a delay to allow new songs)."""
        await asyncio.sleep(300)  # Wait 5 min before auto-disconnect
        state = get_state(guild.id)
        vc = guild.voice_client
        if vc and not vc.is_playing() and not state.queue:
            await vc.disconnect()
            log.info(f"Auto-disconnected from {guild.name} (queue empty)")

    # ── /play ─────────────────────────────────────────────
    @app_commands.command(name="play", description="Play a song from YouTube 🎵")
    @app_commands.describe(query="Song name or YouTube URL")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)
            return

        vc_channel = interaction.user.voice.channel
        guild = interaction.guild

        # ── Step 1: Search FIRST before connecting to voice ──
        await interaction.followup.send(f"🔍 Searching for **{query}**...")
        try:
            track = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, search_youtube, query),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="❌ Search timed out. Try again.")
            return

        if not track:
            await interaction.edit_original_response(
                content="❌ Couldn't find that song. Try a different search term."
            )
            # Announce in channel if all sources failed
            try:
                channel_id = int(os.getenv("ANNOUNCEMENTS_CHANNEL_ID", 0))
                if channel_id:
                    ann_ch = interaction.guild.get_channel(channel_id)
                    if ann_ch:
                        embed = discord.Embed(title="⚠️ Music Bot Issue", color=0xFF4500)
                        embed.add_field(name="🇬🇧 English", value="Music is temporarily unavailable. We're working on it!", inline=False)
                        embed.add_field(name="🇸🇦 العربية", value="الموسيقى غير متاحة مؤقتاً. نعمل على إصلاح المشكلة!", inline=False)
                        embed.add_field(name="🇸🇴 Soomaali", value="Muusikada waxay ku jirtaa dhibaato ku meel gaar ah. Waxaan ka shaqeyneynaa!", inline=False)
                        await ann_ch.send(content="@everyone", embed=embed)
            except Exception:
                pass
            return

        # ── Step 2: Connect to voice AFTER finding the song ──
        vc = guild.voice_client
        try:
            if guild.voice_client:
                try:
                    await guild.voice_client.disconnect(force=True)
                    await asyncio.sleep(1)
                except Exception:
                    pass
            vc = await vc_channel.connect(timeout=60.0, reconnect=False)
        except discord.errors.ConnectionClosed as e:
            if e.code == 4006:
                log.warning("Got 4006 — waiting 5s and retrying")
                await asyncio.sleep(5)
                try:
                    vc = await vc_channel.connect(timeout=60.0, reconnect=False)
                except Exception as e2:
                    await interaction.edit_original_response(content=f"❌ Voice connection failed: {e2}")
                    return
            else:
                await interaction.edit_original_response(content=f"❌ Couldn't connect to voice: {e}")
                return
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Couldn't connect to voice: {e}")
            return

        state = get_state(guild.id)
        state.queue.append(track)

        # Wait for voice connection to fully stabilize before playing
        await asyncio.sleep(1)

        # Start playing immediately
        if not vc.is_playing() and not vc.is_paused():
            self._play_next(guild)

        # Send embed response
        embed = discord.Embed(color=0xFF4500, timestamp=datetime.utcnow())
        if track.get("thumbnail"):
            embed.set_thumbnail(url=track["thumbnail"])

        if len(state.queue) > 0 and (vc.is_playing() or vc.is_paused()):
            embed.title = "➕ Added to Queue"
            embed.description = f"**[{track['title']}]({track['webpage']})**"
            embed.add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
            embed.add_field(name="📋 Position", value=f"#{len(state.queue)}", inline=True)
            embed.add_field(name="🎵 Source", value=track.get("source", "YouTube"), inline=True)
        else:
            embed.title = "🎵 Now Playing"
            embed.description = f"**[{track['title']}]({track['webpage']})**"
            embed.add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
            embed.add_field(name="📺 Channel",  value=track["uploader"],               inline=True)
            embed.add_field(name="🎵 Source", value=track.get("source", "YouTube"), inline=True)

        embed.set_footer(
            text=f"Requested by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.edit_original_response(content=None, embed=embed)

    # ── /skip ─────────────────────────────────────────────
    @app_commands.command(name="skip", description="Skip the current song ⏭️")
    async def slash_skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped!")

    # ── /stop ─────────────────────────────────────────────
    @app_commands.command(name="stop", description="Stop music and disconnect 🛑")
    async def slash_stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        state = get_state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        if vc:
            await vc.disconnect()
        try:
            from cogs.voice_monitor import MUSIC_ACTIVE
            MUSIC_ACTIVE[interaction.guild.id] = False
        except ImportError:
            pass
        await interaction.response.send_message("🛑 Stopped and disconnected.")

    # ── /pause ────────────────────────────────────────────
    @app_commands.command(name="pause", description="Pause the music ⏸️")
    async def slash_pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)

    # ── /resume ───────────────────────────────────────────
    @app_commands.command(name="resume", description="Resume the music ▶️")
    async def slash_resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)

    # ── /queue ────────────────────────────────────────────
    @app_commands.command(name="queue", description="Show the music queue 📋")
    async def slash_queue(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        embed = discord.Embed(title="🎵 Music Queue", color=0xFF4500, timestamp=datetime.utcnow())

        if state.current:
            embed.add_field(
                name="▶️ Now Playing",
                value=f"[{state.current['title']}]({state.current['webpage']}) `{fmt_duration(state.current['duration'])}`",
                inline=False,
            )

        if state.queue:
            queue_list = "\n".join(
                f"`{i+1}.` [{t['title']}]({t['webpage']}) `{fmt_duration(t['duration'])}`"
                for i, t in enumerate(list(state.queue)[:10])
            )
            embed.add_field(name=f"📋 Up Next ({len(state.queue)} songs)", value=queue_list, inline=False)
        else:
            embed.add_field(name="📋 Queue", value="Empty — use `/play` to add songs!", inline=False)

        await interaction.response.send_message(embed=embed)

    # ── /nowplaying ───────────────────────────────────────
    @app_commands.command(name="nowplaying", description="Show current song 🎶")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        if not state.current:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
            return
        t = state.current
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{t['title']}]({t['webpage']})**",
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )
        if t.get("thumbnail"):
            embed.set_thumbnail(url=t["thumbnail"])
        embed.add_field(name="⏱️ Duration", value=fmt_duration(t["duration"]), inline=True)
        embed.add_field(name="📺 Channel",  value=t["uploader"],               inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /volume ───────────────────────────────────────────
    @app_commands.command(name="volume", description="Set music volume 🔊")
    @app_commands.describe(level="Volume level 1–100")
    async def slash_volume(self, interaction: discord.Interaction, level: int):
        level = max(1, min(level, 100))
        state = get_state(interaction.guild.id)
        state.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**")

    # ── /loop ─────────────────────────────────────────────
    @app_commands.command(name="loop", description="Toggle loop for current song 🔁")
    async def slash_loop(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        state.loop = not state.loop
        await interaction.response.send_message(
            f"🔁 Loop **{'enabled' if state.loop else 'disabled'}**."
        )

    # ── /musicstatus ──────────────────────────────────────
    @app_commands.command(name="musicstatus", description="Check the music bot's status 🎵")
    async def slash_musicstatus(self, interaction: discord.Interaction):
        import psutil
        import platform
        import time

        bot = interaction.client
        latency = round(bot.latency * 1000)
        latency_color = 0x00FF7F if latency < 100 else 0xFFD700 if latency < 200 else 0xFF4500

        process = psutil.Process()
        uptime_seconds = int(time.time() - process.create_time())
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        mem_mb = round(process.memory_info().rss / 1024 / 1024, 1)
        cpu = psutil.cpu_percent(interval=0.1)

        state = get_state(interaction.guild.id)
        vc = interaction.guild.voice_client

        embed = discord.Embed(
            title="🎵 Music Bot Status",
            color=latency_color,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name="🏓 Latency",    value=f"{latency}ms",                                    inline=True)
        embed.add_field(name="⏱️ Uptime",      value=uptime_str,                                       inline=True)
        embed.add_field(name="💾 Memory",      value=f"{mem_mb} MB",                                   inline=True)
        embed.add_field(name="🖥️ CPU",         value=f"{cpu}%",                                        inline=True)
        embed.add_field(name="🎵 Now Playing", value=(state.current["title"][:40] if state.current else "Nothing"), inline=True)
        embed.add_field(name="📋 Queue",       value=f"{len(state.queue)} songs",                      inline=True)
        embed.add_field(name="🔊 Voice",       value=(vc.channel.name if vc else "Not connected"),     inline=True)
        embed.add_field(name="🔁 Loop",        value=("On" if state.loop else "Off"),                  inline=True)
        embed.add_field(name="🍪 Cookies",     value=("✅ Loaded" if COOKIE_FILE else "❌ Not found"), inline=True)
        embed.add_field(name="🐍 Python",      value=platform.python_version(),                        inline=True)
        embed.set_footer(text=f"Music Bot ID: {bot.user.id}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
