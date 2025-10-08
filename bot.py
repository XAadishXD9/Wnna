# ============================================================
#  EAGLENODE VPS MANAGEMENT BOT
#  Supports Ubuntu 22.04 & Debian 12 VPS Containers
#  Admin + User Command System
# ============================================================

import discord, subprocess, asyncio, os, random, string
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

# -------------------------------
# CONFIGURATION
# -------------------------------
TOKEN = "None"  # 🔒 Paste your Discord bot token here
ADMIN_IDS = [123456789012345678]  # 🔧 Replace with your Discord ID
DATABASE_FILE = "database.txt"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# -------------------------------
# UTILITIES
# -------------------------------
def is_admin(user_id: int):
    return user_id in ADMIN_IDS

def generate_random_string(length=8):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

async def capture_ssh_session(container_name):
    """Capture SSH connection from tmate output inside Docker container."""
    process = await asyncio.create_subprocess_exec(
        "docker", "exec", container_name, "tmate", "-F",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        text = line.decode().strip()
        if text.startswith("ssh "):
            return text
    return None

# -------------------------------
# BOT EVENTS
# -------------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# -------------------------------
# COMMANDS
# -------------------------------

# /ping
@bot.tree.command(name="ping", description="🏓 Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency*1000)}ms")

# /resources
@bot.tree.command(name="resources", description="📊 Show system resource usage (Admin only)")
async def resources(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    mem = subprocess.getoutput("free -m")
    disk = subprocess.getoutput("df -h /")
    await interaction.response.send_message(f"```Memory:\n{mem}\n\nDisk:\n{disk}```")

# /list-all
@bot.tree.command(name="list-all", description="📋 List all VPS containers (Admin only)")
async def list_all(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    containers = subprocess.getoutput("docker ps -a --format '{{.Names}} ({{.Status}})'")
    if not containers:
        return await interaction.response.send_message("No containers found.")
    await interaction.response.send_message(f"**All VPS Containers:**\n```{containers}```")

# /remove
@bot.tree.command(name="remove", description="💥 Force remove a container instantly (Admin only)")
@app_commands.describe(container_id="Container name or ID")
async def remove(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    result = subprocess.getoutput(f"docker rm -f {container_id}")
    await interaction.response.send_message(f"🗑️ Removed container:\n```\n{result}\n```")

# /delete-user-container
@bot.tree.command(name="delete-user-container", description="❌ Delete a user's VPS container (Admin only)")
@app_commands.describe(container_id="Container name or ID")
async def delete_user_container(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    subprocess.run(["docker", "stop", container_id])
    subprocess.run(["docker", "rm", container_id])
    await interaction.response.send_message(f"🗑️ Deleted container `{container_id}`")

# /deploy
@bot.tree.command(name="deploy", description="🚀 Deploy a new VPS for a user (Admin only)")
@app_commands.describe(user="User ID of the target user", os="Operating system (ubuntu/debian)")
async def deploy(interaction: discord.Interaction, user: str, os: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message("❌ Admins only.", ephemeral=True)
    os = os.lower()
    if os not in ["ubuntu", "debian"]:
        return await interaction.response.send_message("❌ Invalid OS. Use ubuntu or debian.")

    container_name = f"VPS_{user}_{generate_random_string(6)}"
    image = "ubuntu-22.04-with-tmate" if os == "ubuntu" else "debian-with-tmate"

    await interaction.response.send_message(f"⚙️ Creating VPS `{container_name}` using {os} image...")

    # Start Docker container
    subprocess.run(["docker", "run", "-itd", "--privileged", "--name", container_name, image])

    # Capture SSH session
    ssh_line = await capture_ssh_session(container_name)
    ssh_line = ssh_line or "SSH session unavailable"

    # Create embed for DM
    embed = discord.Embed(title="🎉 EAGLENODE VPS Creation Successful", color=0x2400ff)
    embed.description = (
        f"🔑 **SSH Connection Command:**\n`{ssh_line}`\n\n"
        f"👤 **USERNAME:** {user}\n"
        f"💾 **RAM Allocation:** 16 GB\n"
        f"🔥 **CPU Cores:** 4 cores\n"
        f"🧊 **Container Name:** {container_name}\n"
        f"💾 **Storage:** 1000 GB (Shared storage)\n"
        f"🔒 **Password:** eagle@123\n\n"
        f"ℹ️ **Note**\nThis is an EAGLENODE VPS instance. You can install and configure additional packages as needed."
    )

    try:
        target_user = await bot.fetch_user(int(user))
        await target_user.send(embed=embed)
        await interaction.followup.send(f"✅ VPS created successfully and DM sent to <@{user}>")
    except Exception as e:
        await interaction.followup.send(f"⚠️ VPS created but failed to DM user. Error: {e}")

# -------------------------------
# USER COMMANDS
# -------------------------------
@bot.tree.command(name="start", description="▶️ Start your VPS container")
async def start(interaction: discord.Interaction, container_id: str):
    subprocess.run(["docker", "start", container_id])
    await interaction.response.send_message(f"✅ Started `{container_id}`")

@bot.tree.command(name="stop", description="⏹️ Stop your VPS container")
async def stop(interaction: discord.Interaction, container_id: str):
    subprocess.run(["docker", "stop", container_id])
    await interaction.response.send_message(f"🛑 Stopped `{container_id}`")

@bot.tree.command(name="restart", description="🔄 Restart your VPS container")
async def restart(interaction: discord.Interaction, container_id: str):
    subprocess.run(["docker", "restart", container_id])
    await interaction.response.send_message(f"🔁 Restarted `{container_id}`")

@bot.tree.command(name="regen-ssh", description="🔑 Regenerate SSH session for your VPS")
async def regen_ssh(interaction: discord.Interaction, container_id: str):
    ssh_line = await capture_ssh_session(container_id)
    ssh_line = ssh_line or "SSH session unavailable"
    await interaction.response.send_message(f"🔁 New SSH session:\n`{ssh_line}`")

@bot.tree.command(name="list", description="📋 Show all your VPS containers")
async def list_cmd(interaction: discord.Interaction):
    containers = subprocess.getoutput("docker ps -a --format '{{.Names}} ({{.Status}})'")
    if not containers:
        return await interaction.response.send_message("You have no VPS instances.")
    await interaction.response.send_message(f"**Your VPS Instances:**\n```{containers}```")

@bot.tree.command(name="help", description="❓ Show all available commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="EAGLENODE VPS Bot Help", color=0x2400ff)
    embed.add_field(name="Admin Commands", value="/deploy, /delete-user-container, /remove, /list-all, /resources", inline=False)
    embed.add_field(name="User Commands", value="/start, /stop, /restart, /regen-ssh, /list, /ping, /help", inline=False)
    await interaction.response.send_message(embed=embed)

# -------------------------------
# RUN BOT
# -------------------------------
bot.run(TOKEN)
