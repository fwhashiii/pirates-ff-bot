"""
🎙️ Voice Monitor Cog
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import io
import wave
import tempfile
import logging
from datetime import datetime

log = logging.getLogger("cog.voice_monitor")

# Set to True when music bot is active — prevents monitor from joining
MUSIC_ACTIVE: dict[int, bool] = {}  # guild_id → bool

try:
    from openai import AsyncOpenAI
    _openai_available = True
except ImportError:
    _openai_available = False

# Spoken words/phrases that trigger a ticket
SPOKEN_BANNED = [
    "nigger", "nigga", "faggot", "kys", "kill yourself",
    "kill your self", "retard", "spick", "chink", "kike",
    "wetback", "coon", "tranny", "whore", "cunt",
]

# Active monitors: {guild_id: VoiceClient}
_monitors: dict[int, discord.VoiceClient] = {}


def contains_violation(transcript: str) -> str | None:
    lower = transcript.lower()
    for word in SPOKEN_BANNED:
        if word in lower:
            return word
    return None


def pcm_to_wav(pcm_data: bytes, channels: int = 2, rate: int = 48000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


class VoiceMonitorCog(commands.Cog, name="Voice Monitor"):
    """Voice channel monitoring with Whisper transcription and auto-ticketing."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai = AsyncOpenAI(api_key=self.api_key) if (_openai_available and self.api_key) else None
        self._monitor_tasks: dict[int, asyncio.Task] = {}

    # ── Auto-monitor on voice join ────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Auto-join and monitor any voice channel a member enters."""
        # Ignore all bot movements (including our own bot reconnecting)
        if member.bot:
            return

        guild = member.guild

        # Member joined a voice channel
        if after.channel and not before.channel:
            channel = after.channel

            # Skip private staff VCs
            staff_vc_names = ["👑 OWNER VC", "⚔️ CAPTAIN VC", "🛡️ MOD VC", "🔒 STAFF LOUNGE"]
            if channel.name.upper() in [n.upper() for n in staff_vc_names]:
                return

            # Don't join if music is active in this guild
            if MUSIC_ACTIVE.get(guild.id):
                log.info(f"Skipping monitor join — music is active in {guild.name}")
                return

            # Don't join if any bot is already in a voice channel
            if guild.voice_client:
                return

            # Already monitoring this guild
            if guild.id in _monitors:
                return

            # Small delay to let Discord settle before connecting
            await asyncio.sleep(3)

            # Re-check everything after the delay
            if MUSIC_ACTIVE.get(guild.id):
                return
            if guild.id in _monitors or guild.voice_client:
                return
            if member not in channel.members:
                return

            # Spawn a background task to connect — avoids blocking the event loop
            _monitors[guild.id] = None  # placeholder to block duplicate triggers
            asyncio.create_task(self._connect_and_monitor(guild, channel, member))

        # Last human left the channel the bot is in — disconnect
        elif before.channel and not after.channel:
            vc = _monitors.get(guild.id)
            if vc and vc.channel == before.channel:
                humans = [m for m in before.channel.members if not m.bot]
                if not humans:
                    await asyncio.sleep(2)
                    humans = [m for m in before.channel.members if not m.bot]
                    if not humans:
                        task = self._monitor_tasks.pop(guild.id, None)
                        if task:
                            task.cancel()
                        _monitors.pop(guild.id, None)
                        try:
                            if vc.is_connected():
                                await vc.disconnect()
                        except Exception:
                            pass
                        log.info(f"Auto-monitor stopped: {before.channel.name} (channel empty)")

    async def _connect_and_monitor(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel,
        triggered_by: discord.Member,
    ):
        """Background task: connect to VC once cleanly, then start monitoring."""
        if guild.id not in _monitors:
            return

        # Final check — abort if music became active while we were waiting
        if MUSIC_ACTIVE.get(guild.id):
            _monitors.pop(guild.id, None)
            log.info(f"Aborted monitor connect — music is now active in {guild.name}")
            return

        # Abort if another voice client appeared (e.g. music bot connected)
        if guild.voice_client:
            _monitors.pop(guild.id, None)
            log.info(f"Aborted monitor connect — voice client already exists in {guild.name}")
            return

        try:
            vc = await channel.connect(timeout=30.0, reconnect=False, self_deaf=True)
            log.info(f"Connected to {channel.name}")
        except Exception as e:
            log.error(f"Failed to connect to {channel.name}: {e}")
            _monitors.pop(guild.id, None)
            return

        if not vc.is_connected():
            _monitors.pop(guild.id, None)
            return

        _monitors[guild.id] = vc
        started_by = guild.owner or triggered_by

        task = asyncio.create_task(
            self._record_loop(guild, channel, vc, started_by)
        )
        self._monitor_tasks[guild.id] = task
        log.info(f"Auto-monitor active: {channel.name}")

    @app_commands.command(name="monitor", description="Start monitoring a voice channel 🎙️")
    @app_commands.describe(channel="Voice channel to monitor")
    async def slash_monitor(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        guild = interaction.guild

        if guild.id in _monitors:
            await interaction.response.send_message(
                "⚠️ Already monitoring a channel. Use `/stopmonitor` first.", ephemeral=True
            )
            return

        try:
            vc = await channel.connect()
        except Exception as e:
            await interaction.response.send_message(f"❌ Could not join: {e}", ephemeral=True)
            return

        _monitors[guild.id] = vc

        # Start the chunk-record loop
        task = asyncio.create_task(
            self._record_loop(guild, channel, vc, interaction.user)
        )
        self._monitor_tasks[guild.id] = task

        embed = discord.Embed(
            title="🎙️ Voice Monitor Active",
            description=f"Monitoring **{channel.name}**\nRecording in 15-second chunks.",
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text=f"Started by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log.info(f"Monitor started: {channel.name}")

    # ── /stopmonitor ──────────────────────────────────────
    @app_commands.command(name="stopmonitor", description="Stop voice monitoring 🛑")
    async def slash_stopmonitor(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        guild = interaction.guild
        task = self._monitor_tasks.pop(guild.id, None)
        if task:
            task.cancel()

        vc = _monitors.pop(guild.id, None)
        if vc:
            try:
                if vc.is_connected():
                    await vc.disconnect()
            except Exception:
                pass
            await interaction.response.send_message("🛑 Monitoring stopped.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ No active monitor.", ephemeral=True)

    # ── Record loop ───────────────────────────────────────
    async def _record_loop(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel,
        vc: discord.VoiceClient,
        started_by: discord.Member,
    ):
        """Record 15-second chunks, transcribe, check for violations."""
        # Wait for voice connection to fully stabilise
        await asyncio.sleep(3)

        while guild.id in _monitors:
            # Re-fetch vc in case it reconnected
            vc = _monitors.get(guild.id)
            if not vc or not vc.is_connected():
                await asyncio.sleep(3)
                continue
            try:
                # Record for 15 seconds using WaveSink
                if not hasattr(discord, 'sinks'):
                    await asyncio.sleep(15)
                    continue
                sink = discord.sinks.WaveSink()
                vc.start_recording(sink, self._on_recording_done, guild)
                await asyncio.sleep(15)

                if vc.is_recording():
                    vc.stop_recording()

                # Give the callback a moment to fire
                await asyncio.sleep(1)

                # Process the recorded audio stored in sink.audio
                if not sink.audio:
                    continue

                for uid, audio in sink.audio.items():
                    member = guild.get_member(uid)
                    name = member.display_name if member else f"User {uid}"

                    raw = audio.file.read()
                    if len(raw) < 9600:  # skip very short clips
                        continue

                    if not self.openai:
                        log.warning("OpenAI not set — skipping transcription")
                        continue

                    try:
                        transcript = await self._transcribe(raw)
                    except Exception as e:
                        log.error(f"Transcription error ({name}): {e}")
                        continue

                    if not transcript:
                        continue

                    log.info(f"[{channel.name}] {name}: {transcript}")

                    violation = contains_violation(transcript)
                    if violation:
                        await self._create_ticket(
                            guild=guild,
                            offender=member,
                            channel=channel,
                            transcript=transcript,
                            audio_bytes=raw,
                            violation=violation,
                            started_by=started_by,
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Record loop error: {e}")
                await asyncio.sleep(5)

    def _on_recording_done(self, sink, guild, *args):
        """Callback when stop_recording fires — nothing needed, sink holds data."""
        pass

    # ── Transcribe with Whisper ───────────────────────────
    async def _transcribe(self, wav_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                resp = await self.openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="en",
                )
            return resp.text.strip()
        finally:
            os.unlink(tmp_path)

    # ── Create ticket ─────────────────────────────────────
    async def _create_ticket(
        self,
        guild: discord.Guild,
        offender: discord.Member,
        channel: discord.VoiceChannel,
        transcript: str,
        audio_bytes: bytes,
        violation: str,
        started_by: discord.Member,
    ):
        # Find or create tickets category
        cat = discord.utils.get(guild.categories, name="🎫 TICKETS")
        if not cat:
            cat = await guild.create_category("🎫 TICKETS")

        ts = datetime.utcnow().strftime("%m%d%H%M")
        name_slug = offender.display_name.lower()[:12] if offender else "unknown"
        ticket_name = f"voice-{name_slug}-{ts}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
        }
        if offender:
            overwrites[offender] = discord.PermissionOverwrite(read_messages=False)
        for rn in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
            r = discord.utils.get(guild.roles, name=rn)
            if r:
                overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_ch = await guild.create_text_channel(
            ticket_name, category=cat, overwrites=overwrites,
            topic=f"Voice violation by {offender} in {channel.name}",
        )

        # Staff ping
        pings = []
        for rn in ["👑 Owner", "⚔️ Captain", "🛡️ Moderator"]:
            r = discord.utils.get(guild.roles, name=rn)
            if r:
                pings.append(r.mention)

        embed = discord.Embed(
            title="🚨 Voice Violation Detected",
            color=0xFF0000,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="👤 Offender",      value=offender.mention if offender else "Unknown", inline=True)
        embed.add_field(name="🎙️ Channel",       value=channel.name,    inline=True)
        embed.add_field(name="⚠️ Violation",     value=f"`{violation}`", inline=True)
        embed.add_field(name="📝 Transcript",    value=f"```{transcript[:1000]}```", inline=False)
        embed.set_footer(text=f"Monitor by {started_by.display_name}")

        await ticket_ch.send(content=f"🚨 {' '.join(pings)}", embed=embed)

        # Attach audio
        await ticket_ch.send(
            file=discord.File(
                io.BytesIO(audio_bytes),
                filename=f"evidence_{getattr(offender, 'id', 0)}_{ts}.wav",
            )
        )

        # Action guide
        name = offender.display_name if offender else "user"
        action_embed = discord.Embed(
            title="⚖️ Suggested Actions",
            description=(
                f"`/warn @{name} Verbal rule violation in VC`\n"
                f"`/mute @{name} 60 Verbal abuse in voice chat`\n"
                f"`/ban @{name} Verbal rule violation`\n\n"
                f"Delete this channel when resolved."
            ),
            color=0xFFD700,
        )
        await ticket_ch.send(embed=action_embed)
        log.info(f"Ticket created: {ticket_name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMonitorCog(bot))
