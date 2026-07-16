"""
🏅 Free Fire Rank Icon Setter
Sets official Free Fire rank badge images as Discord role icons.

REQUIRES: Server Level 2 boost (14 boosts).
Run this after setup_server.py has created the roles.

Usage: python set_rank_icons.py
"""

import discord
import asyncio
import os
import aiohttp
import io
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

TOKEN    = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", 0))

# ── Official Free Fire rank badge URLs ───────────────────
# Multiple fallback sources per rank
RANK_ICONS = {
    "🌱 Bronze": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/5/5b/Bronze_Rank_Icon.png/120px-Bronze_Rank_Icon.png",
        "https://i.imgur.com/bronze_ff.png",
    ],
    "🔰 Silver": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/4/4e/Silver_Rank_Icon.png/120px-Silver_Rank_Icon.png",
    ],
    "🥉 Gold": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/8/8e/Gold_Rank_Icon.png/120px-Gold_Rank_Icon.png",
    ],
    "🥈 Platinum": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/b/b5/Platinum_Rank_Icon.png/120px-Platinum_Rank_Icon.png",
    ],
    "💠 Diamond": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/3/3e/Diamond_Rank_Icon.png/120px-Diamond_Rank_Icon.png",
    ],
    "🥇 Master": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/6/6e/Master_Rank_Icon.png/120px-Master_Rank_Icon.png",
    ],
    "🏆 Grandmaster": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/9/9e/Grandmaster_Rank_Icon.png/120px-Grandmaster_Rank_Icon.png",
    ],
    "💎 Heroic": [
        "https://static.wikia.nocookie.net/freefire/images/thumb/2/2e/Heroic_Rank_Icon.png/120px-Heroic_Rank_Icon.png",
    ],
}

# ── Fallback: colored circle images if URLs fail ─────────
RANK_COLORS_FALLBACK = {
    "🌱 Bronze":      (205, 127,  50),
    "🔰 Silver":      (189, 195, 199),
    "🥉 Gold":        (241, 196,  15),
    "🥈 Platinum":    (149, 165, 166),
    "💠 Diamond":     (  0, 191, 255),
    "🥇 Master":      (255, 215,   0),
    "🏆 Grandmaster": (255, 107,  53),
    "💎 Heroic":      (233,  30,  99),
}


def make_colored_circle(rgb: tuple, size: int = 128) -> bytes:
    """Generate a simple colored circle PNG as fallback."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=(*rgb, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def fetch_image(session: aiohttp.ClientSession, urls: list[str]) -> bytes | None:
    """Try each URL in order, return first successful download."""
    for url in urls:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    # Validate it's actually an image
                    try:
                        img = Image.open(io.BytesIO(data))
                        img.verify()
                        return data
                    except Exception:
                        continue
        except Exception:
            continue
    return None


class IconSetterClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.done = False

    async def on_ready(self):
        if self.done:
            return
        self.done = True

        guild = self.get_guild(GUILD_ID)
        if not guild:
            print(f"❌ Guild {GUILD_ID} not found.")
            await self.close()
            return

        print(f"\n🏅 Setting rank icons for: {guild.name}")
        print(f"   Boost level: {guild.premium_tier} ({guild.premium_subscription_count} boosts)")

        if guild.premium_tier < 2:
            needed = 14 - guild.premium_subscription_count
            print(f"\n⚠️  Need Level 2 boost to set role icons.")
            print(f"   You need {needed} more boost(s) to reach Level 2.")
            print(f"   Run this script again after boosting!\n")
            await self.close()
            return

        print("=" * 50)
        print("✅ Server is Level 2+! Setting rank icons...\n")

        async with aiohttp.ClientSession() as session:
            for role_name, urls in RANK_ICONS.items():
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    print(f"   ⚠️  Role not found: {role_name}")
                    continue

                print(f"   🔄 {role_name}...")

                # Try downloading the real badge image
                img_bytes = await fetch_image(session, urls)

                # Fall back to colored circle if download fails
                if not img_bytes:
                    print(f"      ⚠️  Image download failed, using colored circle fallback")
                    rgb = RANK_COLORS_FALLBACK.get(role_name, (128, 128, 128))
                    img_bytes = make_colored_circle(rgb)

                try:
                    await role.edit(display_icon=img_bytes, reason="Free Fire rank icon")
                    print(f"      ✅ Icon set!")
                except discord.Forbidden:
                    print(f"      ❌ Bot lacks permission to edit this role")
                except discord.HTTPException as e:
                    print(f"      ❌ Discord rejected image: {e}")

                await asyncio.sleep(1)

        print("\n" + "=" * 50)
        print("✅ All rank icons updated!")
        print("   Members will see the badges next to their rank in the sidebar.")
        await self.close()


if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set in .env")
        exit(1)
    if not GUILD_ID:
        print("❌ GUILD_ID not set in .env")
        exit(1)

    client = IconSetterClient()
    client.run(TOKEN)
