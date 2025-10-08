import discord
from discord.ext import commands, tasks
import random
import string

TOKEN = "YOUR_DISCORD_BOT_TOKEN"  # Replace with your token
ADMIN_IDS = [123456789012345678]  # Replace with your Discord user ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)

# Simulated VPS records
vps_list = {}

# Auto status updater
@tasks.loop(seconds=10)
async def update_status():
    count = len(vps_list)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"EAGLE NODE {count} VPS"
    ))

@bot.event
async def on_ready():
    update_status.start()
    print(f"🪐 EAGLE NODE bot online as {bot.user}")

# Utility
def is_admin(user_id):
    return user_id in ADMIN_IDS

def generate_password(length=10):
    chars = string.ascii_letters + string.digits + "!@#$%?"
    return ''.join(random.choice(chars) for _ in range(length))

def generate_username():
    return f"user{random.randint(1000,9999)}"

# -----------------------------
# User Commands
# -----------------------------
@bot.tree.command(name="help", description="Show all EAGLE NODE commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🪐 EAGLE NODE Help", color=0x2400ff)
    embed.add_field(name="👤 User Commands",
                    value="/help\n/list\n/ping\n/regen-ssh\n/resources\n/start\n/stop\n/restart",
                    inline=False)
    embed.add_field(name="👑 Admin Commands",
                    value="/deploy\n/list-all\n/delete-user-container\n/remove",
                    inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="🏓 Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! `{latency}ms`", ephemeral=True)

@bot.tree.command(name="list", description="📋 List your VPS instances")
async def list_vps(interaction: discord.Interaction):
    user_vps = [v for v in vps_list.values() if v["owner"] == interaction.user.id]
    if not user_vps:
        await interaction.response.send_message("You don’t have any VPS yet 💤", ephemeral=True)
        return
    embed = discord.Embed(title="📋 Your VPS", color=0x2400ff)
    for v in user_vps:
        embed.add_field(
            name=f"{v['name']} (🟢 Running)",
            value=f"RAM: {v['ram']}GB | CPU: {v['cpu']} cores | Disk: {v['disk']}GB",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Fake control commands
@bot.tree.command(name="start", description="▶️ Start your VPS")
async def start_vps(interaction: discord.Interaction, container_id: str):
    await interaction.response.send_message(
        f"▶️ VPS `{container_id}` started successfully!", ephemeral=True
    )

@bot.tree.command(name="stop", description="⏹️ Stop your VPS")
async def stop_vps(interaction: discord.Interaction, container_id: str):
    await interaction.response.send_message(
        f"⏹️ VPS `{container_id}` stopped successfully!", ephemeral=True
    )

@bot.tree.command(name="restart", description="🔁 Restart your VPS")
async def restart_vps(interaction: discord.Interaction, container_id: str):
    await interaction.response.send_message(
        f"🔁 VPS `{container_id}` restarted successfully!", ephemeral=True
    )

@bot.tree.command(name="regen-ssh", description="🔑 Regenerate SSH session")
async def regen_ssh(interaction: discord.Interaction, container_id: str):
    await interaction.response.send_message(
        f"🔑 New SSH session created for VPS `{container_id}`:\n```bash\nssh user@lon1.tmate.io\n```",
        ephemeral=True
    )

@bot.tree.command(name="resources", description="📊 Show system resources")
async def resources(interaction: discord.Interaction):
    cpu_usage = random.randint(10, 90)
    ram_usage = random.randint(20, 95)
    disk_usage = random.randint(10, 80)
    embed = discord.Embed(title="📊 EAGLE NODE Resources", color=0x2400ff)
    embed.add_field(name="🔥 CPU Usage", value=f"{cpu_usage}%", inline=True)
    embed.add_field(name="💾 RAM Usage", value=f"{ram_usage}%", inline=True)
    embed.add_field(name="💽 Disk Usage", value=f"{disk_usage}%", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# -----------------------------
# Admin Commands
# -----------------------------
@bot.tree.command(name="deploy", description="(Admin) Deploy a VPS for a user")
async def deploy(interaction: discord.Interaction, user: discord.User, os: str, ram: int, cpu: int, disk: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ You are not authorized to deploy VPS.", ephemeral=True)
        return

    vps_name = f"VPS_{len(vps_list)+1}"
    username = generate_username()
    password = generate_password()
    vps_list[vps_name] = {
        "owner": user.id,
        "name": vps_name,
        "os": os,
        "ram": ram,
        "cpu": cpu,
        "disk": disk,
        "username": username,
        "password": password
    }

    embed = discord.Embed(title="✅ EAGLE NODE VPS Created Successfully!", color=0x2400ff)
    embed.add_field(name="👤 Username", value=username, inline=True)
    embed.add_field(name="🔒 Password", value=password, inline=True)
    embed.add_field(name="💾 RAM", value=f"{ram}GB", inline=True)
    embed.add_field(name="🔥 CPU", value=f"{cpu} cores", inline=True)
    embed.add_field(name="💽 Disk", value=f"{disk}GB", inline=True)
    embed.add_field(name="🧊 OS", value=os, inline=True)
    embed.add_field(name="🔑 SSH Connection Command",
                    value=f"```bash\nssh {username}@lon1.tmate.io\n```", inline=False)

    try:
        await user.send(embed=embed)
        await interaction.response.send_message(f"✅ VPS deployed and DM sent to {user.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("⚠️ Could not send DM to user.", ephemeral=True)

@bot.tree.command(name="list-all", description="(Admin) List all VPS instances")
async def list_all(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    if not vps_list:
        await interaction.response.send_message("No VPS found.", ephemeral=True)
        return

    embed = discord.Embed(title="📊 All VPS Instances", color=0x2400ff)
    for v in vps_list.values():
        embed.add_field(
            name=v["name"],
            value=f"👤 Owner: <@{v['owner']}>\n💾 {v['ram']}GB | 🔥 {v['cpu']} cores | 💽 {v['disk']}GB\nUsername: `{v['username']}`",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="delete-user-container", description="(Admin) Delete a VPS by ID")
async def delete_user_container(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    if container_id not in vps_list:
        await interaction.response.send_message("⚠️ VPS not found.", ephemeral=True)
        return
    del vps_list[container_id]
    await interaction.response.send_message(f"🗑️ VPS `{container_id}` deleted successfully.", ephemeral=True)

@bot.tree.command(name="remove", description="(Admin) Remove a VPS")
async def remove(interaction: discord.Interaction, container_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admins only.", ephemeral=True)
        return
    if container_id not in vps_list:
        await interaction.response.send_message("⚠️ VPS not found.", ephemeral=True)
        return
    del vps_list[container_id]
    await interaction.response.send_message(f"🚫 VPS `{container_id}` removed successfully.", ephemeral=True)

# -----------------------------
bot.run(TOKEN)
