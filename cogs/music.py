"""
🎵 Music Cog — Play music from SoundCloud/YouTube in voice channels
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

# ── Cookie file ───────────────────────────────────────────
_COOKIE_PATHS = [
    "/root/bot/youtube_cookies.txt",
    os.path.join(os.path.dirname(__file__), "..", "youtube_cookies.txt"),
]
COOKIE_FILE = next((p for p in _COOKIE_PATHS if os.path.exists(p)), None)


def search_youtube(query: str) -> dict | None:
    """Search SoundCloud first, then YouTube. Returns stream URL."""
    searches = [
        # SoundCloud — no bot detection
        {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "source_address": "0.0.0.0",
            "socket_timeout": 30,
            "_query": f"scsearch1:{query}" if not query.startswith("http") else query,
        },
        # YouTube android
        {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "source_address": "0.0.0.0",
            "extractor_args": {"youtube": {"player_client": ["android"]}},
            "http_headers": {"User-Agent": "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"},
            "socket_timeout": 30,
            "_query": f"ytsearch1:{query}" if not query.startswith("http") else query,
        },
    ]

    if COOKIE_FILE:
        for s in searches:
            s["cookiefile"] = COOKIE_FILE

    last_error = None
    for i, opts in enumerate(searches):
        q = opts.pop("_query")
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(q, download=False)
                if not info:
                    continue
                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        continue
                    info = entries[0]

                url = info.get("url")
                if not url:
                    fmts = info.get("formats", [])
                    audio = [f for f in fmts if f.get("acodec") != "none" and f.get("vcodec") == "none"]
                    url = (audio or fmts or [{}])[-1].get("url")

                if not url:
                    continue

                source = "SoundCloud" if "soundcloud" in info.get("webpage_url", "") else "YouTube"
                log.info(f"[{source}] Found: {info.get('title', '')[:60]}")
                return {
                    "url":      url,
                    "title":    info.get("title", "Unknown"),
                    "duration": info.get("duration", 0) or 0,
                    "webpage":  info.get("webpage_url", ""),
                    "thumbnail": info.get("thumbnail", ""),
                    "uploader": info.get("uploader", "Unknown"),
                    "source":   source,
                }
        except Exception as e:
            last_error = str(e)
            log.warning(f"Strategy {i+1} failed: {last_error[:100]}")
            continue

    log.error(f"All strategies failed. Last: {last_error}")
    return None


def fmt_duration(seconds: int) -> str:
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class GuildMusic:
    def __init__(self):
        self.queue:   deque[dict] = deque()
        self.current: dict | None = None
        self.volume:  float = 1.0  # Default 100%
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
            log.warning("_play_next: no voice client — scheduling reconnect")
            asyncio.run_coroutine_threadsafe(
                self._reconnect_and_play(guild), self.bot.loop
            )
            return

        if state.loop and state.current:
            track = state.current
        elif state.queue:
            track = state.queue.popleft()
            state.current = track
        else:
            state.current = None
            return

        # Re-fetch fresh URL if track has a webpage URL (stream URLs expire)
        if track.get("webpage") and not track.get("_fresh"):
            asyncio.run_coroutine_threadsafe(
                self._play_fresh(guild, track), self.bot.loop
            )
            return

        try:
            # Apply volume boost via FFmpeg filter (supports >100%)
            vol = getattr(state, 'ffmpeg_volume', 1.5)  # Default 150% for louder output
            source = discord.FFmpegPCMAudio(
                track["url"],
                executable=FFMPEG_PATH,
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options=f"-vn -ar 48000 -ac 2 -f s16le -af volume={vol}",
            )
            source = discord.PCMVolumeTransformer(source, volume=state.volume)

            def after(error):
                if error:
                    log.error(f"Playback error: {error}")
                asyncio.run_coroutine_threadsafe(self._after_track(guild), self.bot.loop)

            vc.play(source, after=after)
            log.info(f"Playing: {track['title'][:60]}")
        except Exception as e:
            log.error(f"Failed to start playback: {e}")
            asyncio.run_coroutine_threadsafe(self._after_track(guild), self.bot.loop)

    async def _reconnect_and_play(self, guild: discord.Guild):
        """Reconnect to the last known voice channel and continue playing."""
        state = get_state(guild.id)
        if not state.queue and not state.current:
            return
        # Find the channel from the queue or current track context
        # Look for any voice channel with members
        for vc_channel in guild.voice_channels:
            members = [m for m in vc_channel.members if not m.bot]
            if members:
                try:
                    vc = await vc_channel.connect(reconnect=True, self_deaf=True)
                    log.info(f"Reconnected to {vc_channel.name}")
                    await asyncio.sleep(1)
                    self._play_next(guild)
                    return
                except Exception as e:
                    log.error(f"Reconnect failed: {e}")
                    return

    async def _play_fresh(self, guild: discord.Guild, track: dict):
        """Re-fetch a fresh stream URL before playing."""
        query = track.get("webpage") or track.get("title", "")
        log.info(f"Re-fetching fresh URL for: {track['title'][:60]}")
        try:
            fresh = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, search_youtube, query),
                timeout=30.0,
            )
            if fresh:
                fresh["_fresh"] = True
                state = get_state(guild.id)
                state.current = fresh
                self._play_next(guild)
            else:
                log.error("Failed to re-fetch URL, skipping track")
                await self._after_track(guild)
        except Exception as e:
            log.error(f"Re-fetch error: {e}")
            await self._after_track(guild)

    async def _after_track(self, guild: discord.Guild):
        await asyncio.sleep(0.5)
        self._play_next(guild)

    async def _disconnect_when_empty(self, guild: discord.Guild):
        await asyncio.sleep(300)
        state = get_state(guild.id)
        vc = guild.voice_client
        if vc and not vc.is_playing() and not state.queue:
            await vc.disconnect()

    @app_commands.command(name="play", description="Play a song 🎵")
    @app_commands.describe(query="Song name or URL")
    async def slash_play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)
            return

        vc_channel = interaction.user.voice.channel
        guild = interaction.guild

        # Search first
        await interaction.followup.send(f"🔍 Searching for **{query}**...")
        try:
            track = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, search_youtube, query),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="❌ Search timed out.")
            return

        if not track:
            await interaction.edit_original_response(content="❌ Couldn't find that song.")
            return

        # Connect to voice after search — only reconnect if needed
        vc = guild.voice_client
        try:
            if vc and vc.is_connected() and vc.channel == vc_channel:
                pass  # Already in the right channel, don't reconnect
            elif vc and vc.is_connected() and vc.channel != vc_channel:
                await vc.move_to(vc_channel)
            else:
                if vc:
                    await vc.disconnect(force=True)
                    await asyncio.sleep(1)
                vc = await vc_channel.connect(reconnect=True, self_deaf=True)
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Voice error: {e}")
            return

        state = get_state(guild.id)
        track["_fresh"] = True  # URL just fetched, use directly
        state.queue.append(track)

        if not vc.is_playing() and not vc.is_paused():
            self._play_next(guild)

        embed = discord.Embed(color=0xFF4500, timestamp=datetime.utcnow())
        if track.get("thumbnail"):
            embed.set_thumbnail(url=track["thumbnail"])

        if vc.is_playing() and len(state.queue) > 0:
            embed.title = "➕ Added to Queue"
            embed.description = f"**[{track['title']}]({track['webpage']})**"
            embed.add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
            embed.add_field(name="🎵 Source", value=track.get("source", "?"), inline=True)
        else:
            embed.title = "🎵 Now Playing"
            embed.description = f"**[{track['title']}]({track['webpage']})**"
            embed.add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
            embed.add_field(name="📺 Channel", value=track["uploader"], inline=True)
            embed.add_field(name="🎵 Source", value=track.get("source", "?"), inline=True)

        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.edit_original_response(content=None, embed=embed)

    @app_commands.command(name="skip", description="Skip the current song ⏭️")
    async def slash_skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped!")

    @app_commands.command(name="stop", description="Stop music and disconnect 🛑")
    async def slash_stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        state = get_state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        if vc:
            await vc.disconnect()
        await interaction.response.send_message("🛑 Stopped.")

    @app_commands.command(name="pause", description="Pause ⏸️")
    async def slash_pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume ▶️")
    async def slash_resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("❌ Nothing paused.", ephemeral=True)

    @app_commands.command(name="queue", description="Show queue 📋")
    async def slash_queue(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        embed = discord.Embed(title="🎵 Music Queue", color=0xFF4500)
        if state.current:
            embed.add_field(name="▶️ Now Playing", value=f"[{state.current['title']}]({state.current['webpage']}) `{fmt_duration(state.current['duration'])}`", inline=False)
        if state.queue:
            embed.add_field(name=f"📋 Up Next ({len(state.queue)})", value="\n".join(f"`{i+1}.` {t['title']}" for i, t in enumerate(list(state.queue)[:10])), inline=False)
        else:
            embed.add_field(name="📋 Queue", value="Empty", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nowplaying", description="Current song 🎶")
    async def slash_nowplaying(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        if not state.current:
            await interaction.response.send_message("❌ Nothing playing.", ephemeral=True)
            return
        t = state.current
        embed = discord.Embed(title="🎶 Now Playing", description=f"**[{t['title']}]({t['webpage']})**", color=0xFF4500)
        if t.get("thumbnail"):
            embed.set_thumbnail(url=t["thumbnail"])
        embed.add_field(name="⏱️ Duration", value=fmt_duration(t["duration"]), inline=True)
        embed.add_field(name="📺 Channel", value=t["uploader"], inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set volume 🔊 (1-200%)")
    @app_commands.describe(level="Volume level 1–200 (default 150)")
    async def slash_volume(self, interaction: discord.Interaction, level: int):
        level = max(1, min(level, 200))
        state = get_state(interaction.guild.id)
        state.volume = level / 100
        state.ffmpeg_volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = state.volume
        bar = "█" * (level // 20) + "░" * (10 - level // 20)
        await interaction.response.send_message(f"🔊 Volume: **{level}%** `{bar}`")

    @app_commands.command(name="loop", description="Toggle loop 🔁")
    async def slash_loop(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        state.loop = not state.loop
        await interaction.response.send_message(f"🔁 Loop **{'on' if state.loop else 'off'}**.")

    @app_commands.command(name="shuffle", description="Shuffle the queue 🔀")
    async def slash_shuffle(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        if len(state.queue) < 2:
            await interaction.response.send_message("❌ Need at least 2 songs in queue to shuffle.", ephemeral=True)
            return
        import random
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = deque(queue_list)
        await interaction.response.send_message(f"🔀 Shuffled **{len(state.queue)}** songs in the queue!")

    @app_commands.command(name="remove", description="Remove a song from the queue 🗑️")
    @app_commands.describe(position="Position in queue (1 = first)")
    async def slash_remove(self, interaction: discord.Interaction, position: int):
        state = get_state(interaction.guild.id)
        if not state.queue:
            await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
            return
        if position < 1 or position > len(state.queue):
            await interaction.response.send_message(f"❌ Invalid position. Queue has {len(state.queue)} songs.", ephemeral=True)
            return
        queue_list = list(state.queue)
        removed = queue_list.pop(position - 1)
        state.queue = deque(queue_list)
        await interaction.response.send_message(f"🗑️ Removed **{removed['title']}** from position #{position}.")

    @app_commands.command(name="clearqueue", description="Clear the entire queue 🧹")
    async def slash_clearqueue(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        count = len(state.queue)
        state.queue.clear()
        await interaction.response.send_message(f"🧹 Cleared **{count}** songs from the queue.")

    @app_commands.command(name="playtop", description="Add a song to the top of the queue ⬆️")
    @app_commands.describe(query="Song name or URL")
    async def slash_playtop(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)
            return

        await interaction.followup.send(f"🔍 Searching for **{query}**...")
        try:
            track = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, search_youtube, query),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="❌ Search timed out.")
            return

        if not track:
            await interaction.edit_original_response(content="❌ Couldn't find that song.")
            return

        state = get_state(interaction.guild.id)
        track["_fresh"] = True
        state.queue.appendleft(track)  # Add to front of queue

        vc = interaction.guild.voice_client
        if not vc or not vc.is_connected():
            vc_channel = interaction.user.voice.channel
            vc = await vc_channel.connect(reconnect=True)

        if not vc.is_playing() and not vc.is_paused():
            self._play_next(interaction.guild)

        await interaction.edit_original_response(content=None, embed=discord.Embed(
            title="⬆️ Added to Top of Queue",
            description=f"**[{track['title']}]({track['webpage']})**",
            color=0xFF4500,
        ).add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
         .add_field(name="🎵 Source", value=track.get("source", "?"), inline=True))

    @app_commands.command(name="replay", description="Replay the current song 🔄")
    async def slash_replay(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        vc = interaction.guild.voice_client
        if not state.current:
            await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
            return
        # Re-add current song to front of queue and skip
        track = dict(state.current)
        track.pop("_fresh", None)  # Force re-fetch
        state.queue.appendleft(track)
        if vc and vc.is_playing():
            vc.stop()
        await interaction.response.send_message("🔄 Replaying current song!")

    @app_commands.command(name="disconnect", description="Disconnect the bot from voice 👋")
    async def slash_disconnect(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("❌ Not in a voice channel.", ephemeral=True)
            return
        state = get_state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        await vc.disconnect()
        await interaction.response.send_message("👋 Disconnected.")

    @app_commands.command(name="search", description="Search and pick from top 5 results 🔎")
    @app_commands.describe(query="Song to search for")
    async def slash_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)
            return

        await interaction.followup.send(f"🔍 Searching for **{query}**...")

        def get_top5(q):
            opts = {
                "format": "bestaudio/best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "source_address": "0.0.0.0",
                "socket_timeout": 30,
            }
            results = []
            for src, search_q in [
                (opts, f"scsearch5:{q}"),
                ({**opts, "extractor_args": {"youtube": {"player_client": ["android"]}}}, f"ytsearch5:{q}"),
            ]:
                try:
                    with yt_dlp.YoutubeDL(src) as ydl:
                        info = ydl.extract_info(search_q, download=False)
                        if info and "entries" in info:
                            for e in info["entries"][:5]:
                                if e:
                                    results.append({
                                        "title": e.get("title", "Unknown"),
                                        "duration": e.get("duration", 0) or 0,
                                        "webpage": e.get("webpage_url", ""),
                                        "uploader": e.get("uploader", "Unknown"),
                                        "url": e.get("url", ""),
                                        "thumbnail": e.get("thumbnail", ""),
                                        "source": "SoundCloud" if "soundcloud" in e.get("webpage_url", "") else "YouTube",
                                        "_fresh": True,
                                    })
                            if results:
                                break
                except Exception:
                    continue
            return results[:5]

        try:
            results = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, get_top5, query),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="❌ Search timed out.")
            return

        if not results:
            await interaction.edit_original_response(content="❌ No results found.")
            return

        embed = discord.Embed(title=f"🔎 Search Results for: {query}", color=0xFF4500)
        for i, r in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {r['title'][:50]}",
                value=f"⏱️ {fmt_duration(r['duration'])} • 📺 {r['uploader'][:30]} • 🎵 {r['source']}",
                inline=False,
            )
        embed.set_footer(text="Reply with a number 1-5 to pick a song (30s timeout)")

        await interaction.edit_original_response(content=None, embed=embed)

        def check(m):
            return (
                m.author == interaction.user
                and m.channel.id == interaction.channel_id
                and m.content.strip() in [str(i) for i in range(1, len(results) + 1)]
            )

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30.0)
            choice = int(msg.content.strip()) - 1
            track = results[choice]
            await msg.delete()
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="⏰ Search timed out — no selection made.")
            return

        vc = interaction.guild.voice_client
        vc_channel = interaction.user.voice.channel
        try:
            if vc and vc.is_connected():
                if vc.channel != vc_channel:
                    await vc.move_to(vc_channel)
            else:
                if vc:
                    await vc.disconnect(force=True)
                vc = await vc_channel.connect(reconnect=True)
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Voice error: {e}")
            return

        state = get_state(interaction.guild.id)
        state.queue.append(track)
        if not vc.is_playing() and not vc.is_paused():
            self._play_next(interaction.guild)

        await interaction.edit_original_response(
            content=None,
            embed=discord.Embed(
                title="🎵 Now Playing" if not vc.is_playing() else "➕ Added to Queue",
                description=f"**[{track['title']}]({track['webpage']})**",
                color=0xFF4500,
            ).add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
             .add_field(name="🎵 Source", value=track["source"], inline=True),
        )

    @app_commands.command(name="move", description="Move a song in the queue 🔃")
    @app_commands.describe(from_pos="Current position", to_pos="New position")
    async def slash_move(self, interaction: discord.Interaction, from_pos: int, to_pos: int):
        state = get_state(interaction.guild.id)
        q = list(state.queue)
        if not q:
            await interaction.response.send_message("❌ Queue is empty.", ephemeral=True)
            return
        if not (1 <= from_pos <= len(q)) or not (1 <= to_pos <= len(q)):
            await interaction.response.send_message(f"❌ Positions must be between 1 and {len(q)}.", ephemeral=True)
            return
        track = q.pop(from_pos - 1)
        q.insert(to_pos - 1, track)
        state.queue = deque(q)
        await interaction.response.send_message(f"🔃 Moved **{track['title'][:50]}** from #{from_pos} to #{to_pos}.")

    @app_commands.command(name="autoplay", description="Toggle autoplay — auto-queue related songs 🎲")
    async def slash_autoplay(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        state.autoplay = not getattr(state, "autoplay", False)
        await interaction.response.send_message(
            f"🎲 Autoplay **{'enabled' if state.autoplay else 'disabled'}** — "
            f"{'will auto-queue related songs when queue ends.' if state.autoplay else 'queue will stop when empty.'}"
        )

    @app_commands.command(name="bass", description="Toggle bass boost 🔊")
    async def slash_bass(self, interaction: discord.Interaction):
        state = get_state(interaction.guild.id)
        state.bass_boost = not getattr(state, "bass_boost", False)
        await interaction.response.send_message(
            f"🔊 Bass boost **{'enabled' if state.bass_boost else 'disabled'}**.\n"
            f"{'Use `/skip` to apply to current song.' if state.bass_boost else ''}"
        )

    @app_commands.command(name="lyrics", description="Get lyrics for the current song 📝")
    async def slash_lyrics(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        state = get_state(interaction.guild.id)
        if not state.current:
            await interaction.followup.send("❌ Nothing is playing.", ephemeral=True)
            return

        title = state.current.get("title", "")
        uploader = state.current.get("uploader", "")
        search_term = f"{title} {uploader}".strip()

        try:
            import urllib.request, urllib.parse, json
            # Use lyrics.ovh API (free, no key needed)
            artist = uploader.replace(" - Topic", "").strip()
            song = title.strip()
            url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(song)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            lyrics = data.get("lyrics", "")
            if not lyrics:
                raise ValueError("No lyrics found")

            # Split into chunks of 1000 chars
            chunks = [lyrics[i:i+1000] for i in range(0, min(len(lyrics), 3000), 1000)]
            embed = discord.Embed(
                title=f"📝 {title[:50]}",
                description=chunks[0],
                color=0xFF4500,
            )
            embed.set_footer(text=f"Lyrics via lyrics.ovh • {uploader}")
            await interaction.followup.send(embed=embed)
            for chunk in chunks[1:]:
                await interaction.followup.send(embed=discord.Embed(description=chunk, color=0xFF4500))
        except Exception:
            await interaction.followup.send(
                f"❌ Couldn't find lyrics for **{title}**.\n"
                f"Try searching: [Genius](https://genius.com/search?q={urllib.parse.quote(search_term)})",
                ephemeral=True,
            )

    @app_commands.command(name="musicstatus", description="Music bot status 🎵")
    async def slash_musicstatus(self, interaction: discord.Interaction):
        import psutil, platform, time
        bot = interaction.client
        latency = round(bot.latency * 1000)
        process = psutil.Process()
        uptime = int(time.time() - process.create_time())
        h, r = divmod(uptime, 3600)
        m, s = divmod(r, 60)
        state = get_state(interaction.guild.id)
        vc = interaction.guild.voice_client
        embed = discord.Embed(title="🎵 Music Bot Status", color=0x00FF7F if latency < 100 else 0xFF4500)
        embed.add_field(name="🏓 Latency", value=f"{latency}ms", inline=True)
        embed.add_field(name="⏱️ Uptime", value=f"{h}h {m}m {s}s", inline=True)
        embed.add_field(name="💾 Memory", value=f"{round(process.memory_info().rss/1024/1024,1)} MB", inline=True)
        embed.add_field(name="🎵 Playing", value=state.current["title"][:40] if state.current else "Nothing", inline=True)
        embed.add_field(name="📋 Queue", value=f"{len(state.queue)} songs", inline=True)
        embed.add_field(name="🔊 Voice", value=vc.channel.name if vc else "Not connected", inline=True)
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="artist", description="Find all songs by an artist and queue them 🎤")
    @app_commands.describe(
        artist="Artist name to search for",
        limit="How many songs to load (default: 10, max: 25)",
    )
    async def slash_artist(self, interaction: discord.Interaction, artist: str, limit: int = 10):
        await interaction.response.defer(thinking=True)

        if not interaction.user.voice:
            await interaction.followup.send("❌ Join a voice channel first!", ephemeral=True)
            return

        limit = max(1, min(limit, 25))

        await interaction.followup.send(f"🔍 Searching for songs by **{artist}**...")

        def fetch_artist_songs(name: str, count: int) -> list[dict]:
            results = []
            opts = {
                "format": "bestaudio/best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "source_address": "0.0.0.0",
                "socket_timeout": 30,
            }

            # Try SoundCloud first
            sc_opts = {**opts}
            try:
                with yt_dlp.YoutubeDL(sc_opts) as ydl:
                    info = ydl.extract_info(f"scsearch{count}:{name}", download=False)
                    if info and "entries" in info:
                        for e in info["entries"]:
                            if e and len(results) < count:
                                results.append({
                                    "title":     e.get("title", "Unknown"),
                                    "duration":  e.get("duration", 0) or 0,
                                    "webpage":   e.get("webpage_url", ""),
                                    "uploader":  e.get("uploader", "Unknown"),
                                    "url":       e.get("url", ""),
                                    "thumbnail": e.get("thumbnail", ""),
                                    "source":    "SoundCloud",
                                    "_fresh":    True,
                                })
            except Exception as e:
                log.warning(f"SoundCloud artist search failed: {e}")

            # Fill remaining from YouTube
            remaining = count - len(results)
            if remaining > 0:
                yt_opts = {
                    **opts,
                    "extractor_args": {"youtube": {"player_client": ["android"]}},
                    "http_headers": {"User-Agent": "com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip"},
                }
                if COOKIE_FILE:
                    yt_opts["cookiefile"] = COOKIE_FILE
                try:
                    with yt_dlp.YoutubeDL(yt_opts) as ydl:
                        info = ydl.extract_info(f"ytsearch{remaining}:{name} songs", download=False)
                        if info and "entries" in info:
                            for e in info["entries"]:
                                if e and len(results) < count:
                                    results.append({
                                        "title":     e.get("title", "Unknown"),
                                        "duration":  e.get("duration", 0) or 0,
                                        "webpage":   e.get("webpage_url", ""),
                                        "uploader":  e.get("uploader", "Unknown"),
                                        "url":       e.get("url", ""),
                                        "thumbnail": e.get("thumbnail", ""),
                                        "source":    "YouTube",
                                        "_fresh":    True,
                                    })
                except Exception as e:
                    log.warning(f"YouTube artist search failed: {e}")

            return results

        try:
            songs = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, fetch_artist_songs, artist, limit),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="❌ Search timed out. Try a smaller limit.")
            return

        if not songs:
            await interaction.edit_original_response(content=f"❌ No songs found for **{artist}**.")
            return

        # Build results embed
        embed = discord.Embed(
            title=f"🎤 Songs by: {artist}",
            description=f"Found **{len(songs)}** songs. Reply with:\n• A number (e.g. `3`) to queue one song\n• `all` to queue all songs\n• `cancel` to dismiss",
            color=0xFF4500,
            timestamp=datetime.now(),
        )
        for i, s in enumerate(songs, 1):
            embed.add_field(
                name=f"{i}. {s['title'][:50]}",
                value=f"⏱️ {fmt_duration(s['duration'])} • 🎵 {s['source']}",
                inline=False,
            )
        embed.set_footer(text=f"Reply within 45 seconds • PIRATES Music")

        await interaction.edit_original_response(content=None, embed=embed)

        def check(m):
            return (
                m.author == interaction.user
                and m.channel.id == interaction.channel_id
                and (
                    m.content.strip().lower() in ["all", "cancel"]
                    or m.content.strip().isdigit()
                )
            )

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=45.0)
            reply = msg.content.strip().lower()
            await msg.delete()
        except asyncio.TimeoutError:
            await interaction.edit_original_response(content="⏰ Timed out — no selection made.", embed=None)
            return

        if reply == "cancel":
            await interaction.edit_original_response(content="❌ Cancelled.", embed=None)
            return

        # Connect to VC
        vc = interaction.guild.voice_client
        vc_channel = interaction.user.voice.channel
        try:
            if vc and vc.is_connected():
                if vc.channel != vc_channel:
                    await vc.move_to(vc_channel)
            else:
                if vc:
                    await vc.disconnect(force=True)
                vc = await vc_channel.connect(reconnect=True)
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Voice error: {e}", embed=None)
            return

        state = get_state(interaction.guild.id)

        if reply == "all":
            for s in songs:
                state.queue.append(s)
            if not vc.is_playing() and not vc.is_paused():
                self._play_next(interaction.guild)
            result_embed = discord.Embed(
                title=f"🎤 Queued {len(songs)} songs by {artist}",
                description="\n".join(f"`{i}.` {s['title'][:60]}" for i, s in enumerate(songs, 1)),
                color=0x00FF7F,
            )
            result_embed.set_footer(text=f"PIRATES Music • {len(songs)} songs added")
            await interaction.edit_original_response(content=None, embed=result_embed)
        else:
            idx = int(reply) - 1
            if idx < 0 or idx >= len(songs):
                await interaction.edit_original_response(content="❌ Invalid number.", embed=None)
                return
            track = songs[idx]
            state.queue.append(track)
            if not vc.is_playing() and not vc.is_paused():
                self._play_next(interaction.guild)
            result_embed = discord.Embed(
                title="🎵 Added to Queue",
                description=f"**[{track['title']}]({track['webpage']})**",
                color=0xFF4500,
            )
            result_embed.add_field(name="⏱️ Duration", value=fmt_duration(track["duration"]), inline=True)
            result_embed.add_field(name="🎵 Source",   value=track["source"],                 inline=True)
            await interaction.edit_original_response(content=None, embed=result_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
