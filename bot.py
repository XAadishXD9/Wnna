
# EAGLENODE.py - Safe simulation Discord bot (slash commands)
# NOTE: This is a simulation-only bot. It does NOT perform real Docker, SSH, or system control.
# Replace TOKEN with your bot token to run. Tested with discord.py v2.x.

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
import string
from datetime import datetime

# ---------------- CONFIG ----------------
TOKEN = "YOUR_BOT_TOKEN_HERE"  # <-- Replace with your bot token
DATA_FILE = "eaglenode_db.json"
ADMINS_FILE = "eaglenode_admins.json"
BOT_NAME = "EagleNode"
DEFAULT_RAM_GB = 4
DEFAULT_CPU = 2
DEFAULT_DISK_GB = 20
# ----------------------------------------

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------------- Storage helpers ----------------
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default
    else:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# Initialize data structures
db = load_json(DATA_FILE, {"vps": {}})
admins = load_json(ADMINS_FILE, {"admins": []})
# If no admins, leave empty; use /add_admin to add yourself

def is_admin(user_id: int) -> bool:
    return user_id in admins.get("admins", [])

def generate_password(length=10):
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(random.choice(chars) for _ in range(length))

def generate_container_name():
    return f"eaglenode_{''.join(random.choice(string.ascii_lowercase+string.digits) for _ in range(6))}"

# ---------------- DM Template ----------------
def build_deploy_dm(container_name, user_pass, root_pass, os_name, ram=DEFAULT_RAM_GB, cpu=DEFAULT_CPU, disk=DEFAULT_DISK_GB):
    ssh_code = f"ssh simulated@{container_name}.fake"
    dm = (
        f"🎉 {BOT_NAME} VPS Creation Successful\n\n"
        f"💾 Memory: {ram} GB\n"
        f"⚡ CPU: {cpu} Cores\n"
        f"💿 Disk: {disk} GB\n"
        f"👤 Username: eaglenode\n\n"
        f"🔑 User Password: `{user_pass}`\n"
        f"🔑 Root Password: `{root_pass}`\n\n"
        f"🖥️ SSH Code:\n`{ssh_code}`\n\n"
        f"🔌 Direct SSH:\n`ssh root@localhost -p 8888`\n\n"
        f"ℹ️ Note:\nThis is an {BOT_NAME} VPS instance. You can install and configure additional packages as needed."
    )
    return dm

# ---------------- Bot events ----------------
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception:
        pass
    print(f"✅ {BOT_NAME} simulation bot ready. Logged in as {bot.user} ({bot.user.id})")

# ---------------- Slash commands ----------------

# Admin management
@bot.tree.command(name="add_admin", description="Add a new admin (Discord user ID)")
@app_commands.describe(user="Discord user ID to add as admin")
async def add_admin(interaction: discord.Interaction, user: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to add admins.", ephemeral=True)
        return
    try:
        uid = int(user)
    except:
        await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        return
    if uid in admins["admins"]:
        await interaction.response.send_message("⚠️ That user is already an admin.", ephemeral=True)
        return
    admins["admins"].append(uid)
    save_json(ADMINS_FILE, admins)
    await interaction.response.send_message(f"✅ Added <@{uid}> as admin.")

@bot.tree.command(name="remove_admin", description="Remove an admin (Discord user ID)")
@app_commands.describe(user="Discord user ID to remove")
async def remove_admin(interaction: discord.Interaction, user: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to remove admins.", ephemeral=True)
        return
    try:
        uid = int(user)
    except:
        await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        return
    if uid not in admins["admins"]:
        await interaction.response.send_message("⚠️ That user is not an admin.", ephemeral=True)
        return
    admins["admins"].remove(uid)
    save_json(ADMINS_FILE, admins)
    await interaction.response.send_message(f"✅ Removed <@{uid}> from admins.")

@bot.tree.command(name="list_admins", description="List current admins")
async def list_admins(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to view admins.", ephemeral=True)
        return
    if not admins["admins"]:
        await interaction.response.send_message("No admins set.")
        return
    mention_list = [f"<@{x}>" for x in admins["admins"]]
    await interaction.response.send_message("🛡️ Admins:\n" + "\n".join(mention_list))

# Deploy (simulation)
@bot.tree.command(name="deploy", description="Simulate deploying a new VPS for a user (Ubuntu/Debian)")
@app_commands.describe(target_user="Discord user ID to send the VPS info to", os="Operating system (ubuntu/debian)")
async def deploy(interaction: discord.Interaction, target_user: str, os: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to deploy.", ephemeral=True)
        return
    os = os.lower()
    if os not in ["ubuntu", "debian"]:
        await interaction.response.send_message("⚠️ OS must be 'ubuntu' or 'debian'.", ephemeral=True)
        return
    await interaction.response.defer()
    container_name = generate_container_name()
    user_pass = generate_password(10)
    root_pass = generate_password(12)
    created_at = datetime.utcnow().isoformat()
    # store simulated entry
    db["vps"][container_name] = {
        "user_id": target_user,
        "os": os,
        "ram": DEFAULT_RAM_GB,
        "cpu": DEFAULT_CPU,
        "disk": DEFAULT_DISK_GB,
        "user_pass": user_pass,
        "root_pass": root_pass,
        "ssh": f"simulated@{container_name}.fake",
        "created_at": created_at,
        "status": "running"
    }
    save_json(DATA_FILE, db)
    # Send DM
    dm_text = build_deploy_dm(container_name, user_pass, root_pass, os)
    dm_sent = False
    try:
        user_obj = await bot.fetch_user(int(target_user))
        await user_obj.send(dm_text)
        dm_sent = True
    except Exception:
        dm_sent = False
    if dm_sent:
        await interaction.followup.send(f"✅ Simulated VPS created for <@{target_user}> as `{container_name}`. DM sent.")
    else:
        await interaction.followup.send(f"✅ Simulated VPS created for <@{target_user}> as `{container_name}`. ⚠️ Could not send DM — user may have DMs disabled. SSH: `simulated@{container_name}.fake`")

# Delete (simulation)
@bot.tree.command(name="delete-user-container", description="Simulate deleting a container")
@app_commands.describe(container_id="Container name/ID to delete")
async def delete_user_container(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to delete containers.", ephemeral=True)
        return
    if container_id in db["vps"]:
        del db["vps"][container_id]
        save_json(DATA_FILE, db)
        await interaction.response.send_message(f"🗑️ Simulated deletion of `{container_id}`.")
    else:
        await interaction.response.send_message("❌ Container not found in simulation database.", ephemeral=True)

# Remove record
@bot.tree.command(name="remove", description="Remove simulated container record from DB")
@app_commands.describe(container_id="Container name/ID")
async def remove_record(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to remove records.", ephemeral=True)
        return
    if container_id in db["vps"]:
        del db["vps"][container_id]
        save_json(DATA_FILE, db)
        await interaction.response.send_message(f"✅ Removed `{container_id}` from simulation DB.")
    else:
        await interaction.response.send_message("❌ Container not found in simulation DB.", ephemeral=True)

# Start/stop/restart (simulation)
@bot.tree.command(name="start", description="Simulate starting a container")
@app_commands.describe(container_id="Container name/ID")
async def start_container(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to start containers.", ephemeral=True)
        return
    entry = db["vps"].get(container_id)
    if not entry:
        await interaction.response.send_message("❌ Container not found.", ephemeral=True)
        return
    entry["status"] = "running"
    save_json(DATA_FILE, db)
    await interaction.response.send_message(f"▶️ Simulated start of `{container_id}`")

@bot.tree.command(name="stop", description="Simulate stopping a container")
@app_commands.describe(container_id="Container name/ID")
async def stop_container(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to stop containers.", ephemeral=True)
        return
    entry = db["vps"].get(container_id)
    if not entry:
        await interaction.response.send_message("❌ Container not found.", ephemeral=True)
        return
    entry["status"] = "stopped"
    save_json(DATA_FILE, db)
    await interaction.response.send_message(f"⏹️ Simulated stop of `{container_id}`")

@bot.tree.command(name="restart", description="Simulate restarting a container")
@app_commands.describe(container_id="Container name/ID")
async def restart_container(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to restart containers.", ephemeral=True)
        return
    entry = db["vps"].get(container_id)
    if not entry:
        await interaction.response.send_message("❌ Container not found.", ephemeral=True)
        return
    entry["status"] = "running"
    save_json(DATA_FILE, db)
    await interaction.response.send_message(f"🔄 Simulated restart of `{container_id}`")

# Regen SSH (simulation)
@bot.tree.command(name="regen-ssh", description="Regenerate simulated SSH link for a container")
@app_commands.describe(container_id="Container name/ID")
async def regen_ssh(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to regenerate SSH.", ephemeral=True)
        return
    entry = db["vps"].get(container_id)
    if not entry:
        await interaction.response.send_message("❌ Container not found.", ephemeral=True)
        return
    new_link = f"simulated@{container_id}.fake"
    entry["ssh"] = new_link
    save_json(DATA_FILE, db)
    await interaction.response.send_message(f"✅ New simulated SSH: `{new_link}`")

# List
@bot.tree.command(name="list", description="List simulated VPS entries")
async def list_cmd(interaction: discord.Interaction):
    lines = []
    for name, info in db["vps"].items():
        lines.append(f"{name} | {info.get('status','unknown')} | user: {info.get('user_id')}")
    if not lines:
        await interaction.response.send_message("No simulated VPS entries.")
    else:
        # limit message length
        await interaction.response.send_message("📋 Simulated VPS Entries:\n" + "\n".join(lines[:40]))

# Info
@bot.tree.command(name="info", description="Show simulated container info")
@app_commands.describe(container_id="Container name/ID")
async def info_cmd(interaction: discord.Interaction, container_id: str):
    entry = db["vps"].get(container_id)
    if not entry:
        await interaction.response.send_message("❌ Container not found.", ephemeral=True)
        return
    reply = (
        f"ℹ️ Info for `{container_id}`\n"
        f"OS: {entry.get('os')}\n"
        f"User ID: {entry.get('user_id')}\n"
        f"RAM: {entry.get('ram')} GB\n"
        f"CPU: {entry.get('cpu')} cores\n"
        f"Disk: {entry.get('disk')} GB\n"
        f"SSH: {entry.get('ssh')}\n"
        f"User Password: `{entry.get('user_pass')}`\n"
        f"Root Password: `{entry.get('root_pass')}`\n"
        f"Status: {entry.get('status')}\n"
    )
    await interaction.response.send_message(reply)

# Resources (mocked)
@bot.tree.command(name="resources", description="Show mocked host resources")
async def resources(interaction: discord.Interaction):
    # Provide mocked values for safety
    await interaction.response.send_message(f"💾 RAM: 8 GB used / 16 GB total\n💽 Disk: 120 GB used / 200 GB total\n⚙️ CPU Cores: 8")

# Node (mocked)
@bot.tree.command(name="node", description="Show mocked node information")
async def node(interaction: discord.Interaction):
    await interaction.response.send_message("🖥️ Host: simulated-host\n⏱️ Uptime: 3 days, 4 hours\nCPU: Intel(R) Simulated CPU\nOS: SimOS 1.0")

# Ping
@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! {latency}ms")

# Help
@bot.tree.command(name="help", description="Show bot commands and usage")
async def help_cmd(interaction: discord.Interaction):
    help_text = (
        "📚 **EagleNode Simulation Bot Commands**\n\n"
        "/deploy target_user: os: — Simulate VPS creation and DM user (admin only)\n"
        "/delete-user-container container_id: — Simulate deletion (admin only)\n"
        "/remove container_id: — Remove simulated record (admin only)\n"
        "/start/stop/restart container_id: — Simulate lifecycle (admin only)\n"
        "/regen-ssh container_id: — Simulate SSH regeneration (admin only)\n"
        "/resources — Show mocked host resources\n"
        "/node — Mocked node info\n"
        "/info container_id: — Show simulated VPS info\n"
        "/list — List simulated VPS entries\n"
        "/add_admin user:, /remove_admin user:, /list_admins — Admin management (admin only)\n"
        "/ping — Bot latency\n"
    )
    await interaction.response.send_message(help_text)

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)
