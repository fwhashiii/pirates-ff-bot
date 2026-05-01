"""
🎭 Self-Role & Country Role Selector Cog
Commands: /roles /countryroles /setuproles
"""

import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import datetime, timezone
import logging

log = logging.getLogger("cog.roles")

# Country roles with flags
COUNTRY_ROLES = {
    "🇸🇴 Somalia": "🇸🇴 Somali",
    "🇸🇦 Saudi Arabia": "🇸🇦 Saudi",
    "🇦🇪 UAE": "🇦🇪 UAE",
    "🇪🇬 Egypt": "🇪🇬 Egyptian",
    "🇮🇶 Iraq": "🇮🇶 Iraqi",
    "🇾🇪 Yemen": "🇾🇪 Yemeni",
    "🇯🇴 Jordan": "🇯🇴 Jordanian",
    "🇬🇧 UK": "🇬🇧 UK",
    "🇺🇸 USA": "🇺🇸 USA",
    "🇨🇦 Canada": "🇨🇦 Canadian",
    "🇦🇺 Australia": "🇦🇺 Australian",
    "🇩🇪 Germany": "🇩🇪 German",
    "🇸🇪 Sweden": "🇸🇪 Swedish",
    "🇳🇴 Norway": "🇳🇴 Norwegian",
    "🇩🇰 Denmark": "🇩🇰 Danish",
    "🇳🇱 Netherlands": "🇳🇱 Dutch",
}

# Game role options
GAME_ROLES = {
    "🔫 Free Fire": "🔫 Free Fire Player",
    "⚽ FIFA": "⚽ FIFA Player",
    "🎮 COD": "🎮 COD Player",
    "🏆 Competitive": "🏆 Competitive",
    "🎯 Casual": "🎯 Casual Player",
}

# Notification roles
NOTIF_ROLES = {
    "📢 Announcements": "📢 Announcements",
    "🎮 Game Updates": "🎮 Game Updates",
    "🎵 Music": "🎵 Music Lover",
    "🎁 Giveaways": "🎁 Giveaway Pings",
    "🏆 Tournaments": "🏆 Tournament Pings",
}


class CountrySelect(ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [
            discord.SelectOption(label=label, value=role_name)
            for label, role_name in COUNTRY_ROLES.items()
        ]
        super().__init__(
            placeholder="🌍 Select your country...",
            options=options[:25],
            min_values=0,
            max_values=1,
        )
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        # Remove all country roles first
        country_role_names = list(COUNTRY_ROLES.values())
        roles_to_remove = [r for r in member.roles if r.name in country_role_names]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        if self.values:
            role_name = self.values[0]
            role = discord.utils.get(self.guild.roles, name=role_name)
            if not role:
                role = await self.guild.create_role(name=role_name, reason="Country role auto-created")
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Set your country to **{role_name}**!", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Country role removed.", ephemeral=True)


class GameRoleSelect(ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [
            discord.SelectOption(label=label, value=role_name)
            for label, role_name in GAME_ROLES.items()
        ]
        super().__init__(
            placeholder="🎮 Select your game roles...",
            options=options,
            min_values=0,
            max_values=len(options),
        )
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        game_role_names = list(GAME_ROLES.values())

        # Remove all game roles
        roles_to_remove = [r for r in member.roles if r.name in game_role_names]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        # Add selected roles
        added = []
        for role_name in self.values:
            role = discord.utils.get(self.guild.roles, name=role_name)
            if not role:
                role = await self.guild.create_role(name=role_name, reason="Game role auto-created")
            await member.add_roles(role)
            added.append(role_name)

        if added:
            await interaction.response.send_message(f"✅ Game roles updated: **{', '.join(added)}**", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Game roles removed.", ephemeral=True)


class NotifRoleSelect(ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [
            discord.SelectOption(label=label, value=role_name)
            for label, role_name in NOTIF_ROLES.items()
        ]
        super().__init__(
            placeholder="🔔 Select notification roles...",
            options=options,
            min_values=0,
            max_values=len(options),
        )
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        notif_role_names = list(NOTIF_ROLES.values())

        roles_to_remove = [r for r in member.roles if r.name in notif_role_names]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        added = []
        for role_name in self.values:
            role = discord.utils.get(self.guild.roles, name=role_name)
            if not role:
                role = await self.guild.create_role(name=role_name, reason="Notif role auto-created")
            await member.add_roles(role)
            added.append(role_name)

        if added:
            await interaction.response.send_message(f"✅ Notification roles updated: **{', '.join(added)}**", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Notification roles removed.", ephemeral=True)


class RoleView(ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        self.add_item(CountrySelect(guild))
        self.add_item(GameRoleSelect(guild))
        self.add_item(NotifRoleSelect(guild))


class RolesCog(commands.Cog, name="Roles"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="roles", description="Pick your roles 🎭")
    async def slash_roles(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎭 Role Selector",
            description=(
                "Pick your **country**, **game**, and **notification** roles below.\n"
                "You can change them anytime!"
            ),
            color=0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="🌍 Country Roles", value="Show where you're from", inline=True)
        embed.add_field(name="🎮 Game Roles", value="Show what you play", inline=True)
        embed.add_field(name="🔔 Notifications", value="Choose what to be pinged for", inline=True)
        embed.set_footer(text="PIRATES • Role Selector")
        await interaction.response.send_message(embed=embed, view=RoleView(interaction.guild), ephemeral=True)

    @app_commands.command(name="setuproles", description="Post the role selector in a channel (Staff) 📌")
    async def slash_setuproles(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("🚫 Need Manage Roles permission.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎭 Pick Your Roles!",
            description=(
                "Use the dropdowns below to customize your roles.\n\n"
                "🌍 **Country** — Show where you're from\n"
                "🎮 **Games** — Show what you play\n"
                "🔔 **Notifications** — Choose your pings\n\n"
                "*You can change your roles anytime!*"
            ),
            color=0xFF4500,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="PIRATES • Self-Role Selector")
        await interaction.channel.send(embed=embed, view=RoleView(interaction.guild))
        await interaction.response.send_message("✅ Role selector posted!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolesCog(bot))
