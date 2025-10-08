# bot_eaglenode_stub.py
# Safe stub version of EAGLENODE bot.
# This file implements command structure, DB handling, presence, and message flow,
# but DOES NOT perform any Docker or SSH/tmate actions.
# Replace the TODO functions with your real Docker + tmate logic on your system.

import os
import random
import string
import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Select

# ---------- CONFIG ----------
TOKEN = ""  # <-- Put your token here
ADMIN_IDS = [1405778722732376176]  # replace with your admin IDs (ints)
database_file = "database.txt"
PUBLIC_IP = "138.68.79.95"  # kept for compatibility / display
# ----------------------------

intents = discord.Intents.default()
intents.message_content = False  # slash commands only
bot = commands.Bot(command_prefix="/", intents=intents)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# -------------------------
# Utilities: DB and helpers
# -------------------------
def ensure_db():
    if not os.path.exists(database_file):
        with open(database_file, "w") as f:
            f.write("")

def add_to_database(user: str, container_name: str, ssh_command: str, ram: int = 8, cpu: int = 2,
                    creator: str = None, expiry: str = None, os_type: str = "Ubuntu 22.04"):
    ensure_db()
    creator = creator or user
    with open(database_file, "a") as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram}|{cpu}|{creator}|{os_type}|{expiry or 'None'}\n")

def remove_from_database(container_name: str):
    ensure_db()
    lines = []
    with open(database_file, "r") as f:
        for l in f:
            if container_name not in l:
                lines.append(l)
    with open(database_file, "w") as f:
        f.writelines(lines)

def get_all_containers():
    ensure_db()
    with open(database_file, "r") as f:
        return [line.strip() for line in f if line.strip()]

def get_user_servers(user: str):
    ensure_db()
    entries = []
    with open(database_file, "r") as f:
        for line in f:
            if line.startswith(user + "|"):
                entries.append(line.strip())
    return entries

def get_container_by_name(container_name: str):
    ensure_db()
    with open(database_file, "r") as f:
        for line in f:
            if f"|{container_name}|" in line or line.startswith(container_name + "|") or line.split("|")[1] == container_name:
                return line.strip()
    return None

def generate_random_string(n=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

def parse_time_to_seconds(time_str: str):
    if not time_str:
        return None
    units = {'s':1, 'm':60, 'h':3600, 'd':86400, 'M':2592000, 'y':31536000}
    unit = time_str[-1]
    if unit in units and time_str[:-1].isdigit():
        return int(time_str[:-1]) * units[unit]
    elif time_str.isdigit():
        return int(time_str) * 86400
    return None

def format_expiry_date(seconds_from_now):
    if not seconds_from_now:
        return "None"
    return (datetime.now() + timedelta(seconds=seconds_from_now)).strftime("%Y-%m-%d %H:%M:%S")

# -------------------------
# STUBS for Docker/tmate actions
# -------------------------
# These are SAFE placeholders. Replace their internals with your real Docker/subprocess code.

async def create_container_stub(container_name: str, image: str, ram: int, cpu: int, hostname: str = "eaglenode"):
    """
    Simulate container creation.
    Replace this with code that runs 'docker run ...' and starts tmate, capturing ssh_session_line.
    Return: ssh_session_line (string) or None on failure.
    """
    await asyncio.sleep(0.5)  # simulate delay
    # Simulated tmate SSH string:
    ssh_token = "g" + generate_random_string(15)
    ssh_line = f"ssh {ssh_token}@nyc1.tmate.io"
    return ssh_line

async def start_container_stub(container_name: str):
    await asyncio.sleep(0.2)
    # Return a new tmate ssh line
    ssh_token = "g" + generate_random_string(15)
    return f"ssh {ssh_token}@nyc1.tmate.io"

async def stop_container_stub(container_name: str):
    await asyncio.sleep(0.2)
    return True

async def restart_container_stub(container_name: str):
    await asyncio.sleep(0.3)
    ssh_token = "g" + generate_random_string(15)
    return f"ssh {ssh_token}@nyc1.tmate.io"

# -------------------------
# OS selector view
# -------------------------
class OSSelectView(View):
    def __init__(self, callback):
        super().__init__(timeout=60)
        self.callback = callback
        options = [
            discord.SelectOption(label="Ubuntu 22.04", description="Ubuntu LTS", value="ubuntu"),
            discord.SelectOption(label="Debian 12", description="Debian stable", value="debian")
        ]
        self.add_item(Select(placeholder="Select OS", options=options, custom_id="os_select"))

    @discord.ui.select(custom_id="os_select")
    async def select_callback(self, select: Select, interaction: discord.Interaction):
        selected = select.values[0]
        await interaction.response.defer()
        await self.callback(interaction, selected)

# -------------------------
# Presence updater
# -------------------------
@tasks.loop(seconds=5)
async def change_status():
    try:
        containers = get_all_containers()
        count = len(containers)
        status_text = f"EAGLE NODE {count} VPS"
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status_text))
    except Exception as e:
        print("Status update failed:", e)

# -------------------------
# Commands
# -------------------------

@bot.event
async def on_ready():
    change_status.start()
    print(f"🚀 Bot is ready. Logged in as {bot.user}")
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Sync failed:", e)

# ---- /help ----
@bot.tree.command(name="help", description="❓ Show available EAGLENODE commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🌐 EAGLENODE Command List", description="Commands for users and admins", color=0x00aaff)
    embed.add_field(name="🧑‍💻 User Commands", value=(
        "/help\n"
        "/list\n"
        "/ping\n"
        "/regen-ssh <container_id>\n"
        "/resources\n"
        "/restart <container_id>\n"
        "/start <container_id>\n"
        "/stop <container_id>"
    ), inline=False)
    if is_admin(interaction.user.id):
        embed.add_field(name="👑 Admin Commands", value=(
            "/deploy <user_mention_or_id> <os>\n"
            "/delete-user-container <container_id>\n"
            "/list-all\n"
            "/remove <container_id>"
        ), inline=False)
    embed.set_footer(text="🪐 Powered by EAGLENODE VPS System")
    await interaction.response.send_message(embed=embed)

# ---- /ping ----
@bot.tree.command(name="ping", description="🏓 Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! {latency}ms")

# ---- /list ----
@bot.tree.command(name="list", description="📋 List your VPS instances")
async def list_servers(interaction: discord.Interaction):
    user = str(interaction.user)
    servers = get_user_servers(user)
    await interaction.response.defer()
    if not servers:
        await interaction.followup.send(embed=discord.Embed(title="📋 Your VPS", description="You don't have any VPS instances yet.", color=0x2400ff))
        return
    embed = discord.Embed(title=f"📋 {interaction.user.name}'s VPS", description=f"You have {len(servers)} VPS instance(s)", color=0x2400ff)
    for line in servers:
        parts = line.split("|")
        # parts: user|name|ssh|ram|cpu|creator|os|expiry
        name = parts[1]
        ssh = parts[2]
        ram = parts[3] if len(parts) > 3 else "N/A"
        cpu = parts[4] if len(parts) > 4 else "N/A"
        os_type = parts[6] if len(parts) > 6 else "Unknown"
        expiry = parts[7] if len(parts) > 7 else "None"
        # Simulated status
        status = "🟢 Running"
        embed.add_field(name=f"🖥️ {name} ({status})", value=f"🔑 `{ssh}`\n💾 {ram}GB | 🔥 {cpu} core(s)\n🧊 {os_type}\n⏱ Expires: {expiry}", inline=False)
    await interaction.followup.send(embed=embed)

# ---- /list-all (admin) ----
@bot.tree.command(name="list-all", description="👑 Admin: List all VPS containers")
async def list_all(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You are not an admin.", ephemeral=True)
        return
    await interaction.response.defer()
    containers = get_all_containers()
    if not containers:
        await interaction.followup.send("No VPS instances found.")
        return
    embed = discord.Embed(title="📊 All VPS Instances", description=f"Total: {len(containers)} VPS", color=0x2400ff)
    for line in containers:
        parts = line.split("|")
        if len(parts) >= 8:
            user, name, ssh, ram, cpu, creator, os_type, expiry = parts
            # Simulated status
            status = "🟢 Running"
            embed.add_field(name=f"🖥️ {name} ({status})", value=(f"👤 {user}\n🔑 `{ssh}`\n💾 {ram}GB | 🔥 {cpu} core(s)\n🧊 {os_type}\n👑 Creator: {creator}\n⏱ Expires: {expiry}"), inline=False)
    await interaction.followup.send(embed=embed)

# ---- /deploy (admin) ----
@bot.tree.command(name="deploy", description="👑 Admin: Deploy a new VPS instance")
@app_commands.describe(user="Target user mention or ID", os="Operating system: ubuntu or debian", ram="RAM in GB", cpu="CPU cores", expiry="Expiry e.g. 1d")
async def deploy(interaction: discord.Interaction, user: str, os: str, ram: int = 8, cpu: int = 2, expiry: str = None):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You are not authorized to deploy.", ephemeral=True)
        return

    # Normalize OS selection
    os_lower = os.lower()
    if os_lower not in ("ubuntu", "debian"):
        await interaction.response.send_message("❌ Invalid OS. Choose 'ubuntu' or 'debian'.", ephemeral=True)
        return

    # Prepare container name
    username = user.replace("<", "").replace(">", "").replace("@", "").replace("!", "")
    rand = generate_random_string(6)
    container_name = f"VPS_{username}_{rand}"

    await interaction.response.defer()

    # Choose image placeholder
    image = "ubuntu-22.04-with-tmate" if os_lower == "ubuntu" else "debian-with-tmate"

    # Create container (STUB) - REPLACE with docker run & tmate calls
    ssh_line = await create_container_stub(container_name, image=image, ram=ram, cpu=cpu, hostname="eaglenode")

    if not ssh_line:
        await interaction.followup.send(embed=discord.Embed(title="❌ Deployment Failed", description="Could not create VPS (stub).", color=0xff0000))
        return

    expiry_date = format_expiry_date(parse_time_to_seconds(expiry)) if expiry else "None"
    add_to_database(user, container_name, ssh_line, ram=ram, cpu=cpu, creator=str(interaction.user), expiry=expiry_date, os_type=("Ubuntu 22.04" if os_lower=="ubuntu" else "Debian 12"))

    # Send DM to target user (try to resolve ID)
    target_user_obj = None
    try:
        if user.isdigit():
            target_user_obj = await bot.fetch_user(int(user))
        else:
            # attempt to parse mention
            # leave fallback to interaction.user for testing
            # In a real bot you might want to resolve mention to ID
            target_user_obj = await bot.fetch_user(interaction.user.id)
    except Exception:
        target_user_obj = None

    dm_embed = discord.Embed(title="✅ VPS Created Successfully!", description="Your VPS instance has been created and is ready to use (tmate SSH).", color=0x2400ff)
    dm_embed.add_field(name="🔑 SSH Connection Command", value=f"```{ssh_line}```", inline=False)
    dm_embed.add_field(name="💾 RAM", value=f"{ram} GB", inline=True)
    dm_embed.add_field(name="🔥 CPU", value=f"{cpu} cores", inline=True)
    dm_embed.add_field(name="🧊 Container Name", value=container_name, inline=False)
    dm_embed.add_field(name="💾 Storage", value="1000 GB (Shared)", inline=True)
    dm_embed.add_field(name="🔒 Password", value="eagle@123", inline=False)
    dm_embed.set_footer(text="🪐 Powered by EAGLENODE VPS System — Keep this info private")

    # Try DM
    if target_user_obj:
        try:
            await target_user_obj.send(embed=dm_embed)
        except discord.Forbidden:
            # If can't DM, fall through to send in channel
            pass

    # Public confirmation
    public_embed = discord.Embed(title="✅ VPS Created", description=f"VPS instance has been created for {user}.", color=0x00ff00)
    public_embed.add_field(name="🔑 SSH", value=f"`{ssh_line}`", inline=False)
    public_embed.add_field(name="⚙️ Specs", value=f"{ram}GB RAM | {cpu} cores | eaglenode", inline=False)
    await interaction.followup.send(embed=public_embed)

# ---- /delete-user-container (admin) ----
@bot.tree.command(name="delete-user-container", description="👑 Admin: Delete a user's VPS container")
@app_commands.describe(container_id="Container name to delete")
async def delete_user_container(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You are not authorized.", ephemeral=True)
        return
    await interaction.response.defer()
    # STUB: stop & remove container logic should be here
    removed = get_container_by_name(container_id)
    if not removed:
        await interaction.followup.send(f"❌ Container `{container_id}` not found.")
        return
    # simulate stop/remove
    await stop_container_stub(container_id)
    remove_from_database(container_id)
    await interaction.followup.send(f"✅ Container `{container_id}` deleted.")

# ---- /remove (admin alias) ----
@bot.tree.command(name="remove", description="👑 Admin: Remove a VPS container (alias)")
@app_commands.describe(container_id="Container name to remove")
async def remove_container(interaction: discord.Interaction, container_id: str):
    await delete_user_container(interaction, container_id)

# ---- /regen-ssh ----
@bot.tree.command(name="regen-ssh", description="🔄 Regenerate SSH session for your container")
@app_commands.describe(container_id="Container name")
async def regen_ssh(interaction: discord.Interaction, container_id: str):
    await interaction.response.defer(ephemeral=True)
    record = get_container_by_name(container_id)
    if not record:
        await interaction.followup.send("❌ Container not found for you.", ephemeral=True)
        return
    # STUB: should exec tmate in container to get new ssh
    new_ssh = await start_container_stub(container_id)
    # Update database: replace ssh in record
    # Simple replace logic:
    ensure_db()
    lines = get_all_containers()
    updated = False
    for i, line in enumerate(lines):
        if f"|{container_id}|" in line or line.split("|")[1] == container_id:
            parts = line.split("|")
            parts[2] = new_ssh
            lines[i] = "|".join(parts) + "\n"
            updated = True
            break
    if updated:
        with open(database_file, "w") as f:
            f.writelines(lines)
    try:
        await interaction.user.send(embed=discord.Embed(title="🔄 New SSH Session", description=f"`{new_ssh}`", color=0x00ff00))
        await interaction.followup.send("✅ New SSH session generated and sent to your DMs.", ephemeral=True)
    except Exception:
        await interaction.followup.send("⚠️ Could not DM you. New SSH: " + new_ssh)

# ---- /start ----
@bot.tree.command(name="start", description="▶️ Start your VPS container")
@app_commands.describe(container_id="Container name")
async def start_cmd(interaction: discord.Interaction, container_id: str):
    await interaction.response.defer()
    rec = get_container_by_name(container_id)
    if not rec:
        await interaction.followup.send("❌ Container not found.")
        return
    # STUB: start container & obtain new ssh
    new_ssh = await start_container_stub(container_id)
    # update DB like in regen-ssh
    lines = get_all_containers()
    for i, line in enumerate(lines):
        if f"|{container_id}|" in line or line.split("|")[1] == container_id:
            parts = line.split("|")
            parts[2] = new_ssh
            lines[i] = "|".join(parts) + "\n"
            break
    with open(database_file, "w") as f:
        f.writelines(lines)
    try:
        await interaction.user.send(embed=discord.Embed(title="▶️ VPS Started", description=f"SSH: `{new_ssh}`", color=0x00ff00))
    except Exception:
        pass
    await interaction.followup.send("✅ VPS started. Check your DMs for SSH.")

# ---- /stop ----
@bot.tree.command(name="stop", description="⏹️ Stop your VPS container")
@app_commands.describe(container_id="Container name")
async def stop_cmd(interaction: discord.Interaction, container_id: str):
    await interaction.response.defer()
    rec = get_container_by_name(container_id)
    if not rec:
        await interaction.followup.send("❌ Container not found.")
        return
    # STUB: stop container
    await stop_container_stub(container_id)
    await interaction.followup.send("⏹️ VPS stopped.")

# ---- /restart ----
@bot.tree.command(name="restart", description="🔄 Restart your VPS container")
@app_commands.describe(container_id="Container name")
async def restart_cmd(interaction: discord.Interaction, container_id: str):
    await interaction.response.defer()
    rec = get_container_by_name(container_id)
    if not rec:
        await interaction.followup.send("❌ Container not found.")
        return
    new_ssh = await restart_container_stub(container_id)
    # update DB
    lines = get_all_containers()
    for i, line in enumerate(lines):
        if f"|{container_id}|" in line or line.split("|")[1] == container_id:
            parts = line.split("|")
            parts[2] = new_ssh
            lines[i] = "|".join(parts) + "\n"
            break
    with open(database_file, "w") as f:
        f.writelines(lines)
    try:
        await interaction.user.send(embed=discord.Embed(title="🔄 VPS Restarted", description=f"SSH: `{new_ssh}`", color=0x00ff00))
    except Exception:
        pass
    await interaction.followup.send("✅ VPS restarted. Check your DMs for SSH.")

# ---- /resources ----
@bot.tree.command(name="resources", description="📊 Show system resources")
async def resources(interaction: discord.Interaction):
    # STUB: We simulate resources; replace with actual system calls if desired
    total_mem = "32 GB"
    used_mem = "8 GB"
    total_disk = "500 GB"
    used_disk = "120 GB"
    containers = get_all_containers()
    embed = discord.Embed(title="📊 System Resources", color=0x00aaff)
    embed.add_field(name="🔥 Memory", value=f"{used_mem} / {total_mem}", inline=False)
    embed.add_field(name="💾 Disk", value=f"{used_disk} / {total_disk}", inline=False)
    embed.add_field(name="🖥️ VPS Count", value=str(len(containers)), inline=False)
    await interaction.response.send_message(embed=embed)

# ---- /delete-user-container (alias handled above) done ----

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    print("Starting EAGLENODE stub...")
    ensure_db()
    bot.run(TOKEN)
