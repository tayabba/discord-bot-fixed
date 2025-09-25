import os
import discord
from discord.ext import commands
from discord import app_commands


# ==========================
# Admin Commands
# ==========================
class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="boost", description="Boost a server with a given key")
    async def boost(self, interaction: discord.Interaction, key: str):
        await interaction.response.send_message(f"🔑 Boosting server with key: {key}")

    @app_commands.command(name="multiboost", description="Multi-boost servers")
    async def multiboost(self, interaction: discord.Interaction, amount: int):
        await interaction.response.send_message(f"🚀 Multi-boosting {amount} servers")

    @app_commands.command(name="key_info", description="Get info about a license key")
    async def key_info(self, interaction: discord.Interaction, key: str):
        await interaction.response.send_message(f"ℹ️ Info for key: {key}")

    @app_commands.command(name="create_key", description="Create a new license key")
    async def create_key(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ New key created!")

    @app_commands.command(name="tokenchecker", description="Check tokens")
    async def tokenchecker(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔍 Token check complete!")

    @app_commands.command(name="restock", description="Restock tokens")
    async def restock(self, interaction: discord.Interaction):
        await interaction.response.send_message("📦 Tokens restocked!")

    @app_commands.command(name="livestock", description="Check live stock")
    async def livestock(self, interaction: discord.Interaction):
        await interaction.response.send_message("📡 Live stock status")

    @app_commands.command(name="sendtokens", description="Send tokens to a user")
    async def sendtokens(self, interaction: discord.Interaction, user: str, amount: int):
        await interaction.response.send_message(f"📤 Sent {amount} tokens to {user}")

    @app_commands.command(name="delete_key", description="Delete a license key")
    async def delete_key(self, interaction: discord.Interaction, key: str):
        await interaction.response.send_message(f"🗑️ Deleted key: {key}")

    @app_commands.command(name="unboost", description="Remove boosts from a server")
    async def unboost(self, interaction: discord.Interaction, server_id: str):
        await interaction.response.send_message(f"❌ Removed boosts from server {server_id}")

    @app_commands.command(name="transfer_boost", description="Transfer a boost to another server")
    async def transfer_boost(self, interaction: discord.Interaction, from_server: str, to_server: str):
        await interaction.response.send_message(f"🔄 Transferred boost from {from_server} to {to_server}")

    @app_commands.command(name="setup_autobuy", description="Setup autobuy system")
    async def setup_autobuy(self, interaction: discord.Interaction):
        await interaction.response.send_message("⚙️ Autobuy system setup!")

    @app_commands.command(name="stock_status", description="Check stock status")
    async def stock_status(self, interaction: discord.Interaction):
        await interaction.response.send_message("📊 Stock status report")

    @app_commands.command(name="setactivity", description="Set the bot's activity")
    async def setactivity(self, interaction: discord.Interaction, activity: str):
        await interaction.response.send_message(f"🎮 Bot activity set to: {activity}")


# ==========================
# User Commands
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
# Bot Class
# ==========================
class BoostBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.add_cog(AdminCommands(self))
        await self.add_cog(UserCommands(self))
        await self.tree.sync()
        print("✅ Commands synced!")

    async def on_ready(self):
        print(f"🤖 Logged in as {self.user} ({self.user.id})")


# ==========================
# Run Bot
# ==========================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("❌ DISCORD_BOT_TOKEN not set in environment!")
    bot = BoostBot()
    bot.run(TOKEN)

