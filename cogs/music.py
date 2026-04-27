"""
🎵 Music Cog — Play music from YouTube in voice channels
Commands: /play /skip /stop /queue /pause /resume /nowplaying /volume
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
import logging
from collections import deque
from datetime import datetime

log = logging.getLogger("cog.music")

import os as _os_module
FFMPEG_PATH = _os_module.environ.get("FFMPEG_PATH", "ffmpeg")  # Railway uses system ffmpeg

FFMPEG_OPTIONS = {
    "executable": FFMPEG_PATH,
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -loglevel error",
}


def is_spotify(query: str) -> bool:
    return "spotify.com" in query


def search_youtube(query: str) -> dict | None:
    """Stream audio directly from YouTube."""
    import os as _os
    # Add Node.js to PATH if on Windows
    node_path = r"C:\Program Files\nodejs"
    if _os.path.exists(node_path):
        env_path = _os.environ.get("PATH", "")
        if node_path not in env_path:
            _os.environ["PATH"] = node_path + ";" + env_path

    opts = {
        "format":         "bestaudio/best",
        "noplaylist":     True,
        "quiet":          True,
        "no_warnings":    True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0",
        "extractor_args": {"youtube": {"skip": ["hls"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            if not query.startswith("http"):
                query = f"ytsearch:{query}"
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "url":      info["url"],
                "title":    info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "webpage":  info.get("webpage_url", ""),
                "thumbnail":info.get("thumbnail", ""),
                "uploader": info.get("uploader", "Unknown"),
            }
        except Exception as e:
            log.error(f"yt-dlp error: {e}")
            return None


def fmt_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# Per-guild music state
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
        if not vc:
            return

        if state.loop and state.current:
            track = state.current
        elif state.queue:
            track = state.queue.popleft()
            state.current = track
        else:
            state.current = None
            return

        source = discord.FFmpegPCMAudio(
            track["url"],
            executable=FFMPEG_PATH,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
            stderr=__import__("subprocess").PIPE,
        )
        source = discord.PCMVolumeTransformer(source, volume=state.volume)

        def after(error):
            if error:
                log.error(f"Playback error: {error}")
            asyncio.run_coroutine_threadsafe(
                self._after_track(guild), self.bot.loop
            )

        vc.play(source, after=after)

    async def _after_track(self, guild: discord.Guild):
        await asyncio.sleep(0.5)
        self._play_next(guild)

    # ── /play ─────────────────────────────────────────────
    @app_commands.command(name="play", description="Play a song from YouTube 🎵")
    @app_commands.describe(query="Song name or YouTube URL")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        # Must be in a voice channel
        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)
            return

        vc_channel = interaction.user.voice.channel
        guild = interaction.guild
        vc = guild.voice_client

        # Connect or move
        if not vc:
            vc = await vc_channel.connect()
        elif vc.channel != vc_channel:
            await vc.move_to(vc_channel)

        # Pause voice monitor if it's active in this guild
        from cogs.voice_monitor import _monitors as vm_monitors, MUSIC_ACTIVE
        MUSIC_ACTIVE[guild.id] = True  # Lock monitor out
        if guild.id in vm_monitors:
            vm_vc = vm_monitors.pop(guild.id, None)
            if vm_vc and isinstance(vm_vc, discord.VoiceClient):
                try:
                    await vm_vc.disconnect(force=True)
                    log.info("Paused voice monitor for music playback")
                except Exception:
                    pass

        # Search
        await interaction.followup.send(f"🔍 Searching for `{query}`... *(10-15 seconds)*")
        try:
            track = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, search_youtube, query),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="❌ Search timed out. Try again.")
            return

        if not track:
            await interaction.edit_original_response(content="❌ Couldn't find that song. Try a different search.")
            return

        state = get_state(guild.id)
        state.queue.append(track)

        embed = discord.Embed(color=0xFF4500, timestamp=datetime.utcnow())
        embed.set_thumbnail(url=track["thumbnail"])

        if vc.is_playing() or vc.is_paused():
            embed.title = "➕ Added to Queue"
            embed.description = f"**[{track['title']}]({track['webpage']})**"
            embed.add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
            embed.add_field(name="📋 Position", value=f"#{len(state.queue)}", inline=True)
        else:
            self._play_next(guild)
            embed.title = "🎵 Now Playing"
            embed.description = f"**[{track['title']}]({track['webpage']})**"
            embed.add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
            embed.add_field(name="📺 Channel",  value=track["uploader"],               inline=True)

        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
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
        # Release music lock so monitor can rejoin
        from cogs.voice_monitor import MUSIC_ACTIVE
        MUSIC_ACTIVE[interaction.guild.id] = False
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
        import psutil, platform, time
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
        embed.add_field(name="🏓 Latency",      value=f"{latency}ms",                          inline=True)
        embed.add_field(name="⏱️ Uptime",        value=uptime_str,                              inline=True)
        embed.add_field(name="💾 Memory",        value=f"{mem_mb} MB",                          inline=True)
        embed.add_field(name="🖥️ CPU",           value=f"{cpu}%",                               inline=True)
        embed.add_field(name="🎵 Now Playing",   value=state.current["title"][:40] if state.current else "Nothing", inline=True)
        embed.add_field(name="📋 Queue",         value=f"{len(state.queue)} songs",             inline=True)
        embed.add_field(name="🔊 Voice",         value=vc.channel.name if vc else "Not connected", inline=True)
        embed.add_field(name="🔁 Loop",          value="On" if state.loop else "Off",           inline=True)
        embed.add_field(name="🐍 Python",        value=platform.python_version(),               inline=True)
        embed.set_footer(text=f"Music Bot ID: {bot.user.id}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
