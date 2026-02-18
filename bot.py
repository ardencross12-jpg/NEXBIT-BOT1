import discord
from discord import app_commands
import sqlite3
import os

TOKEN = os.getenv("TOKEN")

# 🔁 REPLACE THESE WITH YOUR REAL IDS
GUILD_ID = 1473272664675188882
LOG_CHANNEL_ID = 1473652605451370528
EXCHANGER_ROLE_ID = 1473652906241822894

# ---------------- DATABASE ----------------
conn = sqlite3.connect("exchange.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY,
    usdt_to_inr REAL,
    inr_to_usdt REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER,
    type TEXT,
    amount REAL,
    result REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("SELECT * FROM settings WHERE id = 1")
if cursor.fetchone() is None:
    cursor.execute("INSERT INTO settings VALUES (1, 80, 0.0125)")
    conn.commit()

def get_rates():
    cursor.execute("SELECT usdt_to_inr, inr_to_usdt FROM settings WHERE id = 1")
    return cursor.fetchone()

# ---------------- BOT ----------------
class Bot(discord.Client):
    def init(self):
        intents = discord.Intents.default()
        intents.members = True
        super().init(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        await self.tree.sync(guild=guild)

bot = Bot()

def has_exchanger_role(user):
    return any(role.id == EXCHANGER_ROLE_ID for role in user.roles)

# ---------------- SET RATES (ADMIN ONLY) ----------------
@bot.tree.command(name="setrates", description="Set exchange rates")
@app_commands.guilds(discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def setrates(interaction: discord.Interaction, usdt_to_inr: float, inr_to_usdt: float):

    cursor.execute(
        "UPDATE settings SET usdt_to_inr = ?, inr_to_usdt = ? WHERE id = 1",
        (usdt_to_inr, inr_to_usdt)
    )
    conn.commit()

    await interaction.response.send_message("✅ Rates updated.", ephemeral=True)

# ---------------- USDT → INR ----------------
@bot.tree.command(name="usdt_to_inr", description="Convert USDT to INR")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def usdt_to_inr(interaction: discord.Interaction, amount: float):

    if not has_exchanger_role(interaction.user):
        await interaction.response.send_message("❌ Not allowed.", ephemeral=True)
        return

    usdt_rate, _ = get_rates()
    result = amount * usdt_rate

    cursor.execute(
        "INSERT INTO transactions (staff_id, type, amount, result) VALUES (?, ?, ?, ?)",
        (interaction.user.id, "USDT→INR", amount, result)
    )
    conn.commit()

    await interaction.response.send_message(f"{amount} USDT = {result} INR")

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(
            f"📜 USDT→INR\n"
            f"Staff: {interaction.user.mention}\n"
            f"Amount: {amount}\n"
            f"Result: {result}"
        )

# ---------------- INR → USDT ----------------
@bot.tree.command(name="inr_to_usdt", description="Convert INR to USDT")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def inr_to_usdt(interaction: discord.Interaction, amount: float):

    if not has_exchanger_role(interaction.user):
        await interaction.response.send_message("❌ Not allowed.", ephemeral=True)
        return

    _, inr_rate = get_rates()
    result = amount * inr_rate

    cursor.execute(
        "INSERT INTO transactions (staff_id, type, amount, result) VALUES (?, ?, ?, ?)",
        (interaction.user.id, "INR→USDT", amount, result)
    )
    conn.commit()

    await interaction.response.send_message(f"{amount} INR = {result} USDT")

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(
            f"📜 INR→USDT\n"
            f"Staff: {interaction.user.mention}\n"
            f"Amount: {amount}\n"
            f"Result: {result}"
)

# ---------------- PERSONAL STATS ----------------
@bot.tree.command(name="stats", description="Check your stats")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def stats(interaction: discord.Interaction):

    cursor.execute(
        "SELECT COUNT(*), SUM(amount), SUM(result) FROM transactions WHERE staff_id = ?",
        (interaction.user.id,)
    )

    count, total_amount, total_result = cursor.fetchone()
    total_amount = total_amount or 0
    total_result = total_result or 0

    await interaction.response.send_message(
        f"📊 Transactions: {count}\n"
        f"Total Input: {total_amount}\n"
        f"Total Output: {total_result}",
        ephemeral=True
    )

bot.run(TOKEN)
