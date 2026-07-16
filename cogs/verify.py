"""
✅ Verification Cog
- Bot posts a "Start Verification" button in #verify
- Member clicks it → popup form asks for UID, country, language
- Bot validates and grants access
"""

import discord
from discord.ext import commands
from discord import app_commands, ui
import aiohttp
import os
import logging
from datetime import datetime

log = logging.getLogger("cog.verify")

# Stored verifications: {user_id: data}
_verified: dict[int, dict] = {}

COUNTRY_TO_REGION = {
    "Indonesia": "sg", "Thailand": "sg", "Vietnam": "sg",
    "Malaysia": "sg", "Philippines": "sg", "Singapore": "sg",
    "Myanmar": "sg", "Cambodia": "sg", "Laos": "sg",
    "India": "ind", "Bangladesh": "ind", "Nepal": "ind",
    "Sri Lanka": "ind", "Pakistan": "ind",
    "Brazil": "br", "United States": "br", "Mexico": "br",
    "Colombia": "br", "Argentina": "br", "Peru": "br",
    "Chile": "br", "Venezuela": "br", "Ecuador": "br",
    "Saudi Arabia": "sg", "UAE": "sg", "Egypt": "sg",
    "Nigeria": "sg", "Ghana": "sg", "Kenya": "sg",
    "Russia": "sg", "Ukraine": "sg", "Turkey": "sg",
    "Germany": "sg", "France": "sg", "United Kingdom": "sg",
    "Other": "sg",
}


async def lookup_ff_uid(uid: str, region: str) -> dict | None:
    api_key = os.getenv("FF_API_KEY", "")
    if api_key and api_key != "your_ff_api_key_here":
        url = f"https://api.freefirecommunity.com/player?uid={uid}&region={region}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"x-api-key": api_key},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("basicInfo"):
                            info = data["basicInfo"]
                            return {
                                "nickname": info.get("nickname", "Unknown"),
                                "level":    info.get("level", "?"),
                                "region":   region.upper(),
                                "uid":      uid,
                            }
        except Exception as e:
            log.error(f"FF API error: {e}")

    # Fallback: format check only
    if uid.isdigit() and 6 <= len(uid) <= 15:
        return {
            "nickname": f"Player_{uid[-4:]}",
            "level":    "?",
            "region":   region.upper(),
            "uid":      uid,
            "unverified_api": True,
        }
    return None


# ── Verification Modal (popup form) ──────────────────────
class VerifyModal(ui.Modal, title="🔥 Free Fire Verification"):

    uid = ui.TextInput(
        label="Your Free Fire UID",
        placeholder="e.g. 123456789  (found in your FF profile)",
        min_length=6,
        max_length=15,
        required=True,
    )
    country = ui.TextInput(
        label="Your Country",
        placeholder="e.g. United States, Somalia, Saudi Arabia...",
        min_length=2,
        max_length=50,
        required=True,
    )
    language = ui.TextInput(
        label="Your Primary Language",
        placeholder="English, Arabic, or Somali",
        min_length=2,
        max_length=30,
        required=True,
    )
    translator_consent = ui.TextInput(
        label="Auto-Translate Agreement",
        placeholder='Type "yes" to receive translations of foreign messages via DM',
        min_length=2,
        max_length=10,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        member = interaction.user
        guild  = interaction.guild

        uid_val      = self.uid.value.strip()
        country_val  = self.country.value.strip()
        language_val = self.language.value.strip()
        consent_val  = self.translator_consent.value.strip().lower()
        translator_on = consent_val in ("yes", "y", "yeah", "yep", "sure", "ok", "okay")

        # Already verified
        if member.id in _verified:
            await interaction.followup.send(
                "✅ You're already verified! Use `/reverify` to update your info.",
                ephemeral=True,
            )
            return

        # Validate UID
        if not uid_val.isdigit() or not (6 <= len(uid_val) <= 15):
            await interaction.followup.send(
                "❌ **Invalid UID.** Your Free Fire UID is a number found in your profile.\n"
                "Open Free Fire → tap your avatar → copy the number below your name.\n\n"
                "Click the button again to retry.",
                ephemeral=True,
            )
            return

        # Look up UID
        region = COUNTRY_TO_REGION.get(country_val, "sg")
        player = await lookup_ff_uid(uid_val, region)

        if not player:
            await interaction.followup.send(
                "❌ **UID not found.** Please check:\n"
                "• You entered the correct UID\n"
                "• Your account is not banned\n\n"
                "Click the button again to retry.",
                ephemeral=True,
            )
            return

        # ── Assign roles ──────────────────────────────────
        verified_role   = discord.utils.get(guild.roles, name="🎮 New Player")
        unverified_role = discord.utils.get(guild.roles, name="🔒 Unverified")
        try:
            if verified_role:
                await member.add_roles(verified_role, reason="Verified FF account")
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="Verification complete")
        except discord.Forbidden:
            pass

        # ── Assign language role ──────────────────────────
        LANG_ROLE_MAP = {
            "english": "🇬🇧 English",
            "arabic":  "🇸🇦 Arabic",
            "somali":  "🇸🇴 Somali",
        }
        lang_role_name = LANG_ROLE_MAP.get(language_val.lower(), "🇬🇧 English")
        lang_role = discord.utils.get(guild.roles, name=lang_role_name)
        if lang_role:
            try:
                await member.add_roles(lang_role, reason=f"Language: {language_val}")
            except discord.Forbidden:
                pass

        verify_ch = discord.utils.get(guild.text_channels, name="✅┃ᴠᴇʀɪꜰʏ")
        if not verify_ch:
            verify_ch = discord.utils.get(guild.text_channels, name="✅│verify")
        if verify_ch:
            try:
                await verify_ch.set_permissions(
                    member,
                    read_messages=False,
                    send_messages=False,
                    reason="Verified — hiding verify channel",
                )
            except discord.Forbidden:
                pass

        # ── Set nickname to FF name ───────────────────────
        try:
            await member.edit(nick=f"{player['nickname'][:28]} 🔥", reason="FF verification")
        except discord.Forbidden:
            pass

        # ── Store ─────────────────────────────────────────
        _verified[member.id] = {
            "uid":         uid_val,
            "nickname":    player["nickname"],
            "level":       player["level"],
            "region":      player["region"],
            "country":     country_val,
            "language":    language_val,
            "verified_at": str(datetime.utcnow()),
        }

        # ── Apply translator preference ───────────────────
        try:
            from cogs.translate import _opted_out
            if translator_on:
                _opted_out.discard(member.id)   # make sure they're opted IN
            else:
                _opted_out.add(member.id)        # opted out
        except Exception:
            pass

        # ── Success message (private) ─────────────────────
        api_note = "\n⚠️ *UID format validated — add FF_API_KEY for full verification*" if player.get("unverified_api") else ""
        success = discord.Embed(
            title="✅ Verified! Welcome to the squad!",
            description=f"You now have full access to **{guild.name}**. BOOYAH! 🏆",
            color=0x00FF7F,
            timestamp=datetime.utcnow(),
        )
        success.set_thumbnail(url=member.display_avatar.url)
        success.add_field(name="🎮 FF Name",   value=player["nickname"], inline=True)
        success.add_field(name="🆔 UID",        value=uid_val,            inline=True)
        success.add_field(name="⭐ Level",       value=str(player["level"]), inline=True)
        success.add_field(name="🌍 Country",    value=country_val,        inline=True)
        success.add_field(name="💬 Language",   value=language_val,       inline=True)
        success.add_field(name="🗺️ Region",     value=player["region"],   inline=True)
        success.add_field(
            name="🌐 Auto-Translate",
            value="✅ On — you'll receive DM translations of foreign messages" if translator_on else "❌ Off — use `/mytranslate` to enable anytime",
            inline=False,
        )
        if api_note:
            success.set_footer(text=api_note.strip())
        else:
            success.set_footer(text="Free Fire Squad • PIRATES ✅")
        await interaction.followup.send(embed=success, ephemeral=True)

        # ── Public announcement ───────────────────────────
        welcome_ch_id = int(os.getenv("WELCOME_CHANNEL_ID", 0))
        welcome_ch = guild.get_channel(welcome_ch_id)
        if not welcome_ch:
            welcome_ch = discord.utils.get(guild.text_channels, name="👋│welcome")
        if welcome_ch:
            pub = discord.Embed(
                title="✅ New Verified Member!",
                description=f"{member.mention} just verified their Free Fire account!",
                color=0x00FF7F,
                timestamp=datetime.utcnow(),
            )
            pub.set_thumbnail(url=member.display_avatar.url)
            pub.add_field(name="🎮 FF Name",  value=player["nickname"], inline=True)
            pub.add_field(name="🌍 Country",  value=country_val,        inline=True)
            pub.add_field(name="💬 Language", value=language_val,       inline=True)
            pub.set_footer(text="Free Fire Squad • PIRATES")
            await welcome_ch.send(embed=pub)

        # ── Staff log ─────────────────────────────────────
        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        log_ch = guild.get_channel(log_ch_id)
        if log_ch:
            log_emb = discord.Embed(title="🛡️ Verification Log", color=0x00BFFF, timestamp=datetime.utcnow())
            log_emb.add_field(name="Discord",  value=f"{member} ({member.id})", inline=False)
            log_emb.add_field(name="FF UID",   value=uid_val,                   inline=True)
            log_emb.add_field(name="FF Name",  value=player["nickname"],        inline=True)
            log_emb.add_field(name="Country",  value=country_val,               inline=True)
            log_emb.add_field(name="Language", value=language_val,              inline=True)
            await log_ch.send(embed=log_emb)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error(f"Verify modal error: {error}")
        await interaction.followup.send("⚠️ Something went wrong. Please try again.", ephemeral=True)


# ── Verify Button View ────────────────────────────────────
class VerifyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent — survives bot restarts

    @ui.button(
        label="✅  Start Verification",
        style=discord.ButtonStyle.success,
        custom_id="verify_button",
        emoji="🔥",
    )
    async def verify_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id in _verified:
            await interaction.response.send_message(
                "✅ You're already verified! Use `/reverify` to update your info.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(VerifyModal())


# ── Cog ───────────────────────────────────────────────────
class VerifyCog(commands.Cog, name="Verify"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(VerifyView())  # register persistent view

    @commands.Cog.listener()
    async def on_ready(self):
        """Post the verify button in the verify channel on startup."""
        await self._post_verify_button()

    async def _post_verify_button(self):
        """Post or refresh the verify button message."""
        for guild in self.bot.guilds:
            verify_ch = discord.utils.get(guild.text_channels, name="✅┃ᴠᴇʀɪꜰʏ")
            if not verify_ch:
                verify_ch = discord.utils.get(guild.text_channels, name="✅│verify")
            if not verify_ch:
                continue

            # Check if button already posted
            history = [m async for m in verify_ch.history(limit=10)]
            for msg in history:
                if msg.author == self.bot.user and msg.components:
                    return  # already posted

            # Clear old messages and post fresh
            await verify_ch.purge(limit=10, check=lambda m: m.author == self.bot.user)

            embed = discord.Embed(
                title="🔥 Verify Your Free Fire Account",
                description=(
                    "Welcome to **PIRATES — Free Fire Squad**!\n\n"
                    "Click the button below to verify your account and get full access to the server.\n\n"
                    "**You'll be asked for:**\n"
                    "🆔 Your Free Fire UID\n"
                    "🌍 Your country\n"
                    "💬 Your language\n"
                    "🌐 Auto-translate consent (type **yes** to receive DM translations)\n\n"
                    "**How to find your UID:**\n"
                    "Open Free Fire → tap your profile picture → "
                    "your UID is the number shown below your nickname"
                ),
                color=0xFF4500,
            )
            embed.set_footer(text="Free Fire Squad • PIRATES • Takes less than 30 seconds")
            await verify_ch.send(embed=embed, view=VerifyView())
            log.info(f"Posted verify button in {guild.name}")

    # ── /unlink (owner only) ──────────────────────────────
    @app_commands.command(name="unlink", description="Unlink a member's FF account [Owner only] 🔓")
    @app_commands.describe(member="The member to unlink")
    async def slash_unlink(self, interaction: discord.Interaction, member: discord.Member):
        OWNER_ID = 815646767311224953  # fwpirate

        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "🚫 Only the server owner can unlink accounts.",
                ephemeral=True,
            )
            return

        guild = interaction.guild

        if member.id not in _verified:
            await interaction.response.send_message(
                f"⚠️ **{member.display_name}** has no linked FF account.",
                ephemeral=True,
            )
            return

        data = _verified.pop(member.id)

        # Remove verified role, add unverified
        verified_role   = discord.utils.get(guild.roles, name="🎮 New Player")
        unverified_role = discord.utils.get(guild.roles, name="🔒 Unverified")
        try:
            if verified_role and verified_role in member.roles:
                await member.remove_roles(verified_role, reason="Account unlinked by owner")
            if unverified_role:
                await member.add_roles(unverified_role, reason="Account unlinked by owner")
        except discord.Forbidden:
            pass

        # Restore verify channel access
        verify_ch = discord.utils.get(guild.text_channels, name="✅┃ᴠᴇʀɪꜰʏ")
        if not verify_ch:
            verify_ch = discord.utils.get(guild.text_channels, name="✅│verify")
        if verify_ch:
            try:
                await verify_ch.set_permissions(member, overwrite=None)
            except discord.Forbidden:
                pass

        # Reset nickname
        try:
            await member.edit(nick=None, reason="Account unlinked by owner")
        except discord.Forbidden:
            pass

        # Confirm to owner
        embed = discord.Embed(
            title="🔓 Account Unlinked",
            description=f"**{member.mention}**'s Free Fire account has been unlinked.",
            color=0xFF4500,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="🎮 Was linked to", value=data.get("nickname", "Unknown"), inline=True)
        embed.add_field(name="🆔 UID",            value=data.get("uid", "?"),           inline=True)
        embed.set_footer(text=f"Unlinked by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Log it
        log_ch_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        log_ch = guild.get_channel(log_ch_id)
        if log_ch:
            log_emb = discord.Embed(title="🔓 Account Unlinked", color=0xFF4500, timestamp=datetime.utcnow())
            log_emb.add_field(name="Discord",    value=f"{member} ({member.id})",          inline=False)
            log_emb.add_field(name="FF UID",     value=data.get("uid", "?"),               inline=True)
            log_emb.add_field(name="FF Name",    value=data.get("nickname", "Unknown"),    inline=True)
            log_emb.add_field(name="Unlinked by", value=str(interaction.user),             inline=True)
            await log_ch.send(embed=log_emb)

    # ── /reverify ─────────────────────────────────────────
    @app_commands.command(name="reverify", description="Reset and redo your verification 🔄")
    async def slash_reverify(self, interaction: discord.Interaction):
        _verified.pop(interaction.user.id, None)
        guild  = interaction.guild
        member = interaction.user

        verify_ch = discord.utils.get(guild.text_channels, name="✅┃ᴠᴇʀɪꜰʏ")
        if not verify_ch:
            verify_ch = discord.utils.get(guild.text_channels, name="✅│verify")
        if verify_ch:
            try:
                await verify_ch.set_permissions(member, overwrite=None)
            except discord.Forbidden:
                pass

        unverified_role = discord.utils.get(guild.roles, name="🔒 Unverified")
        if unverified_role:
            try:
                await member.add_roles(unverified_role, reason="Re-verification")
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            "🔄 Reset! Head to the verify channel and click the button to re-verify.",
            ephemeral=True,
        )

    # ── /whois ────────────────────────────────────────────
    @app_commands.command(name="whois", description="Look up a member's verified FF info 🔍")
    @app_commands.describe(member="The member to look up")
    async def slash_whois(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        data = _verified.get(target.id)
        if not data:
            await interaction.response.send_message(
                f"❌ **{target.display_name}** hasn't verified yet.", ephemeral=True
            )
            return
        embed = discord.Embed(title=f"🔍 {target.display_name}'s Profile", color=0xFF4500, timestamp=datetime.utcnow())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🎮 FF Name",  value=data["nickname"],  inline=True)
        embed.add_field(name="🆔 UID",       value=data["uid"],       inline=True)
        embed.add_field(name="⭐ Level",      value=str(data["level"]), inline=True)
        embed.add_field(name="🌍 Country",   value=data["country"],   inline=True)
        embed.add_field(name="💬 Language",  value=data["language"],  inline=True)
        embed.add_field(name="🗺️ Region",    value=data["region"],    inline=True)
        embed.set_footer(text="Free Fire Squad • Verified ✅")
        await interaction.response.send_message(embed=embed)

    # ── /verify (manual fallback) ─────────────────────────
    @app_commands.command(name="verify", description="Verify your Free Fire account ✅")
    async def slash_verify(self, interaction: discord.Interaction):
        if interaction.user.id in _verified:
            await interaction.response.send_message("✅ Already verified! Use `/reverify` to update.", ephemeral=True)
            return
        await interaction.response.send_modal(VerifyModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(VerifyCog(bot))
