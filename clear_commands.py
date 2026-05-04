"""
Run this ONCE to clear all global slash commands (removes duplicates).
Guild-specific commands registered by the bots will remain.

Usage:
    python clear_commands.py
"""

import asyncio
import os
from dotenv import load_dotenv
import discord

load_dotenv()


async def clear_global_commands(token: str, bot_name: str):
    if not token:
        print(f"⚠️  No token for {bot_name}, skipping")
        return

    client = discord.Client(intents=discord.Intents.default())
    try:
        await client.login(token)
        app = await client.application_info()
        app_id = app.id

        # Wipe all global commands
        await client.http.bulk_upsert_global_commands(app_id, [])
        print(f"✅ Cleared global commands for {bot_name} (ID: {app_id})")

    except Exception as e:
        print(f"❌ Failed for {bot_name}: {e}")
    finally:
        await client.close()


async def main():
    print("Clearing global slash commands for all bots...")
    print("(Guild-specific commands will remain)\n")

    # Clear main bot global commands
    await clear_global_commands(
        os.getenv("DISCORD_TOKEN"),
        "Main Bot"
    )

    await asyncio.sleep(2)

    # Clear music bot global commands
    await clear_global_commands(
        os.getenv("MUSIC_BOT_TOKEN"),
        "Music Bot"
    )

    print("\nDone! Discord may take a few minutes to update the UI.")
    print("If duplicates still show, restart your Discord client (Ctrl+R).")


if __name__ == "__main__":
    asyncio.run(main())
