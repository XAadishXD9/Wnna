import random
import subprocess
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import string
from datetime import datetime, timedelta
from typing import Literal

TOKEN = ''  # 🧩 Put your bot token here
database_file = 'database.txt'
PUBLIC_IP = '138.68.79.95'
ADMIN_IDS = [1405778722732376176]  # Add your admin IDs here

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)

# ---------------- Helper functions ----------------

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def parse_time_to_seconds(time_str):
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
        return None
    expiry_date = datetime.now() + timedelta(seconds=seconds_from_now)
    return expiry_date.strftime("%Y-%m-%d %H:%M:%S")

def add_to_database(user, container_name, ssh_command, ram_limit=None, cpu_limit=None, creator=None, expiry=None, os_type="Ubuntu 22.04"):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram_limit or '2048'}|{cpu_limit or '1'}|{creator or user}|{os_type}|{expiry or 'None'}\n")

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output:
            return output.split("ssh session:")[1].strip()
    return None

def os_type_to_display_name(os_type):
    return {"ubuntu": "Ubuntu 22.04", "debian": "Debian 12"}.get(os_type, "Unknown OS")

def get_docker_image_for_os(os_type):
    return {"ubuntu": "ubuntu-22.04-with-tmate", "debian": "debian-with-tmate"}.get(os_type, "ubuntu-22.04-with-tmate")

# ---------------- Bot Ready + Status ----------------

@bot.event
async def on_ready():
    change_status.start()
    print(f"🚀 Bot is ready. Logged in as {bot.user}")
    await bot.tree.sync()

@tasks.loop(seconds=5)
async def change_status():
    try:
        if os.path.exists(database_file):
            with open(database_file, 'r') as f:
                count = len(f.readlines())
        else:
            count = 0
        status = f"🪐 EAGLE NODE {count} VPS"
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=status))
    except Exception as e:
        print("Status update error:", e)

# ---------------- Deploy Command ----------------

@bot.tree.command(name="deploy", description="🚀 Admin: Deploy a new VPS instance")
@app_commands.describe(
    user="The Discord user who will own this VPS",
    os="Operating System (ubuntu or debian)",
    ram="RAM allocation in GB (max 200)",
    cpu="CPU cores (max 100)",
    expiry="Time until expiry (e.g. 1d, 2h, 30m, 1y)"
)
async def deploy(interaction: discord.Interaction, user: discord.User, os: Literal["ubuntu", "debian"], ram: int, cpu: int, expiry: str = None):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message(embed=discord.Embed(title="❌ Access Denied", description="You don't have permission to use this command.", color=0xff0000), ephemeral=True)
        return

    ram, cpu = min(ram, 200), min(cpu, 100)
    expiry_seconds = parse_time_to_seconds(expiry)
    expiry_date = format_expiry_date(expiry_seconds) if expiry_seconds else None
    container_name = f"VPS_{user.name.replace(' ', '_')}_{generate_random_string(6)}"
    image = get_docker_image_for_os(os)

    embed = discord.Embed(
        title="⚙️ Creating VPS Instance",
        description=f"👤 **User:** {user.mention}\n🐧 **OS:** {os_type_to_display_name(os)}\n💾 **RAM:** {ram} GB\n🔥 **CPU:** {cpu} cores\n⌚ **Expiry:** {expiry_date or 'None'}",
        color=0x2400ff
    )
    await interaction.response.send_message(embed=embed)

    try:
        container_id = subprocess.check_output([
            "docker", "run", "-itd",
            "--privileged", "--cap-add=ALL",
            f"--memory={ram}g", f"--cpus={cpu}",
            "--hostname", "eaglenode",
            "--name", container_name,
            image
        ]).decode().strip()

        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        ssh_session_line = await capture_ssh_session_line(exec_cmd)
        if not ssh_session_line:
            raise Exception("Failed to get SSH session line.")

        add_to_database(str(user), container_name, ssh_session_line, ram, cpu, str(interaction.user), expiry_date, os_type_to_display_name(os))

        dm = discord.Embed(title="✅ VPS Deployed Successfully", description="Your VPS is ready! Here are your details:", color=0x2400ff)
        dm.add_field(name="💾 RAM", value=f"{ram} GB")
        dm.add_field(name="🔥 CPU", value=f"{cpu} cores")
        dm.add_field(name="🐧 OS", value=os_type_to_display_name(os))
        dm.add_field(name="🔑 SSH Command", value=f"```{ssh_session_line}```", inline=False)
        dm.add_field(name="💠 Container Name", value=container_name, inline=False)
        dm.set_footer(text="🔒 Powered by EAGLE NODE")

        try:
            await user.send(embed=dm)
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Cannot DM {user.mention} (DMs closed).")

        await interaction.followup.send(embed=discord.Embed(title="🎉 VPS Created", description=f"VPS successfully created for {user.mention}", color=0x00ff00))

    except Exception as e:
        await interaction.followup.send(embed=discord.Embed(title="❌ Deployment Failed", description=f"Error: {e}", color=0xff0000))

# ---------------- Run ----------------
bot.run(TOKEN)
    
