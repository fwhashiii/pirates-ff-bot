"""
Test script — sends a test failure announcement to the announcements channel.
Run on VPS: python3 test_announcement.py
"""
import asyncio
import os
import discord
from dotenv import load_dotenv

load_dotenv()

async def main():
    token = os.getenv("MUSIC_BOT_TOKEN")
    channel_id = int(os.getenv("ANNOUNCEMENTS_CHANNEL_ID", 0))

    if not channel_id:
        print("❌ ANNOUNCEMENTS_CHANNEL_ID not set in .env")
        return

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"✅ Logged in as {client.user}")
        channel = client.get_channel(channel_id)
        if not channel:
            print(f"❌ Channel {channel_id} not found")
            await client.close()
            return

        embed = discord.Embed(title="⚠️ Music Bot Issue", color=0xFF4500)
        embed.add_field(
            name="🇬🇧 English",
            value="The music bot is currently experiencing issues and will be back shortly. Sorry for the inconvenience!",
            inline=False,
        )
        embed.add_field(
            name="🇸🇦 العربية",
            value="بوت الموسيقى يواجه مشكلة حالياً وسيعود قريباً. نعتذر عن الإزعاج!",
            inline=False,
        )
        embed.add_field(
            name="🇸🇴 Soomaali",
            value="Botka muusikada ayaa hadda la kulma dhibaato waxaana dib u soo noqon doona dhawaan. Raali noqo!",
            inline=False,
        )
        embed.set_footer(text="PIRATES Music Bot • Test Message")

        await channel.send(embed=embed)
        print(f"✅ Test message sent to #{channel.name}")
        await client.close()

    await client.start(token)

asyncio.run(main())
