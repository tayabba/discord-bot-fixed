import os
import discord
from discord.ext import commands
from discord import app_commands

# ==========================
# COG: Admin Commands
# ==========================
class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="boost", description="Boost a server with a given key")
    async def boost(self, interaction: discord.Interaction, key: str):
        await interaction.response.send_message(f"🔑 Boosting server with key: {key}")

    @app_commands.command(name="create_key", description="Create a new license key")
    async def create_key(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ New key created!")

    # ⚡ Add all your other admin commands here
    # (multiboost, key_info, tokenchecker, restock, livestock, sendtokens, delete_key, unboost, transfer_boost, etc.)


# ==========================
# COG: User Commands
# ==========================
class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="redeem", description="Redeem a key")
    async def redeem(self, interaction: discord.Interaction, key: str):
        await interaction.response.send_message(f"🎉 Successfully redeemed key: {key}")

    @app_commands.command(name="stock", description="Check stock")
    async def stock(self, interaction: discord.Interaction):
        await interaction.response.send_message("📦 Current stock status goes here")


# ==========================
# BOT CLASS
# ==========================
class BoostBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Load all cogs
        await self.add_cog(AdminCommands(self))
        await self.add_cog(UserCommands(self))

        # Sync slash commands with Discord
        try:
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} commands")
        except Exception as e:
            print(f"❌ Error syncing commands: {e}")

    async def on_ready(self):
        print(f"🤖 Logged in as {self.user} (ID: {self.user.id})")


# ==========================
# ENTRY POINT
# ==========================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("⚠️ DISCORD_TOKEN not set in environment variables")
    bot = BoostBot()
    bot.run(TOKEN)
