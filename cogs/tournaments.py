"""
🏆 Tournament System Cog
Commands: /tournament create/start/end/bracket/register
"""

import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import datetime, timezone
import logging
import random

log = logging.getLogger("cog.tournaments")


class TournamentCog(commands.Cog, name="Tournaments"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._tournaments: dict[int, dict] = {}  # {guild_id: tournament_data}

    tournament = app_commands.Group(name="tournament", description="Tournament management 🏆")

    @tournament.command(name="create", description="Create a new tournament 🏆")
    @app_commands.describe(
        name="Tournament name",
        game="Game being played",
        max_teams="Maximum number of teams",
        team_size="Players per team",
        prize="Prize description",
    )
    async def tournament_create(
        self,
        interaction: discord.Interaction,
        name: str,
        game: str = "Free Fire",
        max_teams: int = 8,
        team_size: int = 4,
        prize: str = "Glory and bragging rights",
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        gid = interaction.guild.id
        self._tournaments[gid] = {
            "name": name,
            "game": game,
            "max_teams": max_teams,
            "team_size": team_size,
            "prize": prize,
            "teams": [],
            "status": "open",
            "created_by": interaction.user.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        embed = discord.Embed(
            title=f"🏆 {name}",
            description=f"A new **{game}** tournament has been created!",
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="🎮 Game", value=game, inline=True)
        embed.add_field(name="👥 Team Size", value=f"{team_size} players", inline=True)
        embed.add_field(name="🏟️ Max Teams", value=str(max_teams), inline=True)
        embed.add_field(name="🎁 Prize", value=prize, inline=True)
        embed.add_field(name="📋 Status", value="✅ Registration Open", inline=True)
        embed.add_field(name="📝 Register", value="Use `/tournament register <team_name>`", inline=False)
        embed.set_footer(text=f"Created by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    @tournament.command(name="register", description="Register your team 📝")
    @app_commands.describe(team_name="Your team name")
    async def tournament_register(self, interaction: discord.Interaction, team_name: str):
        gid = interaction.guild.id
        t = self._tournaments.get(gid)

        if not t:
            await interaction.response.send_message("❌ No active tournament. Ask staff to create one.", ephemeral=True)
            return
        if t["status"] != "open":
            await interaction.response.send_message("❌ Registration is closed.", ephemeral=True)
            return
        if len(t["teams"]) >= t["max_teams"]:
            await interaction.response.send_message("❌ Tournament is full!", ephemeral=True)
            return

        # Check if already registered
        for team in t["teams"]:
            if team["captain"] == interaction.user.id:
                await interaction.response.send_message("❌ You're already registered.", ephemeral=True)
                return
            if team["name"].lower() == team_name.lower():
                await interaction.response.send_message("❌ Team name already taken.", ephemeral=True)
                return

        t["teams"].append({
            "name": team_name,
            "captain": interaction.user.id,
            "captain_name": interaction.user.display_name,
        })

        await interaction.response.send_message(
            f"✅ **{team_name}** registered for **{t['name']}**!\n"
            f"Teams registered: **{len(t['teams'])}/{t['max_teams']}**"
        )

    @tournament.command(name="teams", description="Show registered teams 📋")
    async def tournament_teams(self, interaction: discord.Interaction):
        gid = interaction.guild.id
        t = self._tournaments.get(gid)

        if not t:
            await interaction.response.send_message("❌ No active tournament.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🏆 {t['name']} — Teams",
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )
        if t["teams"]:
            teams_list = "\n".join(
                f"`{i+1}.` **{team['name']}** — Captain: {team['captain_name']}"
                for i, team in enumerate(t["teams"])
            )
            embed.description = teams_list
        else:
            embed.description = "No teams registered yet."

        embed.set_footer(text=f"{len(t['teams'])}/{t['max_teams']} teams • Status: {t['status'].title()}")
        await interaction.response.send_message(embed=embed)

    @tournament.command(name="bracket", description="Generate tournament bracket 🎯")
    async def tournament_bracket(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        gid = interaction.guild.id
        t = self._tournaments.get(gid)

        if not t:
            await interaction.response.send_message("❌ No active tournament.", ephemeral=True)
            return
        if len(t["teams"]) < 2:
            await interaction.response.send_message("❌ Need at least 2 teams.", ephemeral=True)
            return

        t["status"] = "in_progress"
        teams = t["teams"].copy()
        random.shuffle(teams)

        embed = discord.Embed(
            title=f"🏆 {t['name']} — Bracket",
            description="**Round 1 Matchups:**",
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )

        matchups = []
        for i in range(0, len(teams) - 1, 2):
            team1 = teams[i]["name"]
            team2 = teams[i + 1]["name"] if i + 1 < len(teams) else "BYE"
            matchups.append(f"⚔️ **{team1}** vs **{team2}**")

        if len(teams) % 2 == 1:
            matchups.append(f"🎯 **{teams[-1]['name']}** — BYE (advances automatically)")

        embed.description = "\n".join(matchups)
        embed.add_field(name="🎮 Game", value=t["game"], inline=True)
        embed.add_field(name="🎁 Prize", value=t["prize"], inline=True)
        embed.set_footer(text="Good luck to all teams! 🏆")

        await interaction.response.send_message(embed=embed)

    @tournament.command(name="end", description="End the tournament and announce winner 🏆")
    @app_commands.describe(winner="Winning team name")
    async def tournament_end(self, interaction: discord.Interaction, winner: str):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("🚫 Staff only.", ephemeral=True)
            return

        gid = interaction.guild.id
        t = self._tournaments.get(gid)
        if not t:
            await interaction.response.send_message("❌ No active tournament.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Tournament Complete!",
            description=f"**{t['name']}** has concluded!",
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="🥇 Winner", value=f"**{winner}** 🎉", inline=False)
        embed.add_field(name="🎁 Prize", value=t["prize"], inline=True)
        embed.add_field(name="🎮 Game", value=t["game"], inline=True)
        embed.set_footer(text=f"Tournament ended by {interaction.user.display_name}")

        del self._tournaments[gid]
        await interaction.response.send_message(content="@everyone", embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TournamentCog(bot))
