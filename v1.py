import random
import logging
import subprocess
import sys
import os
import re
import time
import concurrent.futures
import discord
from discord.ext import commands, tasks
import docker
import asyncio
from discord import app_commands
from discord.ui import Button, View, Select
import string
from datetime import datetime, timedelta
from typing import Optional, Literal

# -----------------------
# Basic config
# -----------------------
TOKEN = ''  # put your bot token here
RAM_LIMIT = '6g'
SERVER_LIMIT = 1
database_file = 'database.txt'
PUBLIC_IP = '138.68.79.95'

# Admin user IDs - add your admin user IDs here
ADMIN_IDS = [1368602087520473140]  # Replace with actual admin IDs

intents = discord.Intents.default()
intents.messages = False
intents.message_content = False

bot = commands.Bot(command_prefix='/', intents=intents)
client = docker.from_env()

# -----------------------
# Helper functions
# -----------------------
def is_admin(user_id):
    return user_id in ADMIN_IDS

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_random_port(): 
    return random.randint(1025, 65535)

def parse_time_to_seconds(time_str):
    """Convert time string like '1d', '2h', '30m', '45s', '1y', '3M' to seconds"""
    if not time_str:
        return None
    
    units = {
        's': 1,               # seconds
        'm': 60,              # minutes
        'h': 3600,            # hours
        'd': 86400,           # days
        'M': 2592000,         # months (30 days)
        'y': 31536000         # years (365 days)
    }
    
    unit = time_str[-1]
    if unit in units and time_str[:-1].isdigit():
        return int(time_str[:-1]) * units[unit]
    elif time_str.isdigit():
        return int(time_str) * 86400  # Default to days if no unit specified
    return None

def format_expiry_date(seconds_from_now):
    """Convert seconds from now to a formatted date string"""
    if not seconds_from_now:
        return None
    
    expiry_date = datetime.now() + timedelta(seconds=seconds_from_now)
    return expiry_date.strftime("%Y-%m-%d %H:%M:%S")

def add_to_database(user, container_name, ssh_command, ram_limit=None, cpu_limit=None, creator=None, expiry=None, os_type="Ubuntu 22.04"):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram_limit or '2048'}|{cpu_limit or '1'}|{creator or user}|{os_type}|{expiry or 'None'}\n")

def remove_from_database(container_id):
    if not os.path.exists(database_file):
        return
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if container_id not in line:
                f.write(line)

def get_all_containers():
    if not os.path.exists(database_file):
        return []
    with open(database_file, 'r') as f:
        return [line.strip() for line in f.readlines()]

def get_container_stats(container_id):
    try:
        # Get memory usage
        mem_stats = subprocess.check_output(["docker", "stats", container_id, "--no-stream", "--format", "{{.MemUsage}}"]).decode().strip()
        
        # Get CPU usage
        cpu_stats = subprocess.check_output(["docker", "stats", container_id, "--no-stream", "--format", "{{.CPUPerc}}"]).decode().strip()
        
        # Get container status
        status = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Status}}", container_id]).decode().strip()
        
        return {
            "memory": mem_stats,
            "cpu": cpu_stats,
            "status": "🟢 Running" if status == "running" else "🔴 Stopped"
        }
    except Exception:
        return {"memory": "N/A", "cpu": "N/A", "status": "🔴 Stopped"}

def get_system_stats():
    try:
        # Get total memory usage
        total_mem = subprocess.check_output(["free", "-m"]).decode().strip()
        mem_lines = total_mem.split('\n')
        if len(mem_lines) >= 2:
            mem_values = mem_lines[1].split()
            total_mem = mem_values[1]
            used_mem = mem_values[2]
            
        # Get disk usage
        disk_usage = subprocess.check_output(["df", "-h", "/"]).decode().strip()
        disk_lines = disk_usage.split('\n')
        if len(disk_lines) >= 2:
            disk_values = disk_lines[1].split()
            total_disk = disk_values[1]
            used_disk = disk_values[2]
            
        return {
            "total_memory": f"{total_mem}GB",
            "used_memory": f"{used_mem}GB",
            "total_disk": total_disk,
            "used_disk": used_disk
        }
    except Exception as e:
        return {
            "total_memory": "N/A",
            "used_memory": "N/A",
            "total_disk": "N/A",
            "used_disk": "N/A",
            "error": str(e)
        }

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output:
            return output.split("ssh session:")[1].strip()
        # the tmate output may also include "ssh" or "web" lines — pick the ssh line if present
        if output.startswith("ssh ") or "ssh " in output:
            # return the whole output (fall back)
            return output.strip()
    return None

def get_ssh_command_from_database(container_id):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if container_id in line:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    return parts[2]
    return None

def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    servers = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user):
                servers.append(line.strip())
    return servers

def count_user_servers(user):
    return len(get_user_servers(user))

def get_container_id_from_database(user, container_name=None):
    servers = get_user_servers(user)
    if servers:
        if container_name:
            for server in servers:
                parts = server.split('|')
                if len(parts) >= 2 and container_name in parts[1]:
                    return parts[1]
            return None
        else:
            return servers[0].split('|')[1]
    return None

def os_type_to_display_name(os_type):
    """Convert OS type to display name"""
    os_map = {
        "ubuntu": "Ubuntu 22.04",
        "debian": "Debian 12"
    }
    return os_map.get(os_type, "Unknown OS")

def get_docker_image_for_os(os_type):
    """Get Docker image name for OS type"""
    os_map = {
        "ubuntu": "ubuntu-22.04-with-tmate",
        "debian": "debian-with-tmate"
    }
    return os_map.get(os_type, "ubuntu-22.04-with-tmate")

# -----------------------
# Background status changer
# -----------------------
@bot.event
async def on_ready():
    change_status.start()
    print(f'🚀 Bot is ready. Logged in as {bot.user}')
    await bot.tree.sync()

@tasks.loop(seconds=5)
async def change_status():
    try:
        if os.path.exists(database_file):
            with open(database_file, 'r') as f:
                lines = f.readlines()
                instance_count = len(lines)
        else:
            instance_count = 0

        status = f" LP NODES {instance_count} VPS"
        await bot.change_presence(activity=discord.Game(name=status))
    except Exception as e:
        print(f"Failed to update status: {e}")

# -----------------------
# Admin: nodedmin
# -----------------------
@bot.tree.command(name="nodedmin", description="📊 Admin: Lists all VPSs, their details, and SSH commands")
async def nodedmin(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        embed = discord.Embed(
            title="❌ Access Denied",
            description="You don't have permission to use this command.",
            color=0x2400ff
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()

    if not os.path.exists(database_file):
        embed = discord.Embed(
            title="VPS Instances",
            description="No VPS data available.",
            color=0x2400ff
        )
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(
        title="All VPS Instances",
        description="Detailed information about all VPS instances",
        color=0x2400ff
    )
    
    with open(database_file, 'r') as f:
        lines = f.readlines()
    
    embeds = []
    current_embed = embed
    field_count = 0
    
    for line in lines:
        parts = line.strip().split('|')
        
        if field_count >= 25:
            embeds.append(current_embed)
            current_embed = discord.Embed(
                title="📊 All VPS Instances (Continued)",
                description="Detailed information about all VPS instances",
                color=0x2400ff
            )
            field_count = 0
        
        if len(parts) >= 8:
            user, container_name, ssh_command, ram, cpu, creator, os_type, expiry = parts
            stats = get_container_stats(container_name)
            
            current_embed.add_field(
                name=f"🖥️ {container_name} ({stats['status']})",
                value=f"🪩 **User:** {user}\n"
                      f"💾 **RAM:** {ram}GB\n"
                      f"🔥 **CPU:** {cpu} cores\n"
                      f"🌐 **OS:** {os_type}\n"
                      f"👑 **Creator:** {creator}\n"
                      f"🔑 **SSH:** `{ssh_command}`",
                inline=False
            )
            field_count += 1
        elif len(parts) >= 3:
            user, container_name, ssh_command = parts
            stats = get_container_stats(container_name)
            
            current_embed.add_field(
                name=f"🖥️ {container_name} ({stats['status']})",
                value=f"👤 **User:** {user}\n"
                      f"🔑 **SSH:** `{ssh_command}`",
                inline=False
            )
            field_count += 1
    
    if field_count > 0:
        embeds.append(current_embed)
    
    if not embeds:
        await interaction.followup.send("No VPS instances found.")
        return
        
    for embed in embeds:
        await interaction.followup.send(embed=embed)

# -----------------------
# node (system stats)
# -----------------------
@bot.tree.command(name="node", description="☠️ Shows system resource usage and VPS status")
async def node_stats(interaction: discord.Interaction):
    await interaction.response.defer()
    
    system_stats = get_system_stats()
    containers = get_all_containers()
    
    embed = discord.Embed(
        title="📊 Panel Node Dashboard",
        description="📡 lp nodes",
        color=0x2400ff
    )
    
    embed.add_field(
        name="🔥 Memory Usage",
        value=f"Used: {system_stats['used_memory']} / Total: {system_stats['total_memory']}",
        inline=False
    )
    
    embed.add_field(
        name="💾 Storage Usage",
        value=f"Used: {system_stats['used_disk']} / Total: {system_stats['total_disk']}",
        inline=False
    )
    
    embed.add_field(
        name=f"💙 VPS ({len(containers)})",
        value="List of all VPS instances and their status:",
        inline=False
    )
    
    for container_info in containers:
        parts = container_info.split('|')
        if len(parts) >= 2:
            container_id = parts[1]
            stats = get_container_stats(container_id)
            embed.add_field(
                name=f"{container_id}",
                value=f"Status: {stats['status']}\nMemory: {stats['memory']}\nCPU: {stats['cpu']}",
                inline=True
            )
    
    await interaction.followup.send(embed=embed)

# -----------------------
# Deploy (instant) - replaced interactive version
# -----------------------
@bot.tree.command(name="deploy", description="🚀 Admin: Instantly deploy a VPS")
@app_commands.describe(
    user="The Discord user to assign the VPS to",
    os="Operating system (ubuntu or debian)",
    ram="RAM in GB (e.g. 4)",
    cpu="CPU cores (e.g. 2)"
)
async def deploy(interaction: discord.Interaction, user: discord.User, os: str, ram: int, cpu: int):
    # Admin check
    if interaction.user.id not in ADMIN_IDS:
        embed = discord.Embed(
            title="❌ Access Denied",
            description="You don't have permission to use this command.",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    os = os.lower()
    if os not in ["ubuntu", "debian"]:
        await interaction.response.send_message("❌ Invalid OS. Choose `ubuntu` or `debian`.", ephemeral=True)
        return

    # Validate limits
    if ram > 100:
        ram = 100
    if cpu > 24:
        cpu = 24

    # Generate container name
    container_name = f"VPS_{user.name}_{generate_random_string(6)}"
    expiry_date = None
    image = get_docker_image_for_os(os)

    embed = discord.Embed(
        title="⚙️ Creating VPS Instance",
        description=f"👤 **User:** {user.mention}\n🐧 **OS:** {os}\n💾 **RAM:** {ram}GB\n🔥 **CPU:** {cpu} cores",
        color=0x2400ff
    )
    await interaction.response.send_message(embed=embed)

    try:
        # Create docker container
        container_id = subprocess.check_output([
            "docker", "run", "-itd",
            "--privileged", "--cap-add=ALL",
            f"--memory={ram}g",
            f"--cpus={cpu}",
            "--name", container_name,
            image
        ]).strip().decode("utf-8")

        # Run tmate for SSH
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        ssh_session_line = await capture_ssh_session_line(exec_cmd)

        if not ssh_session_line:
            raise Exception("Failed to generate SSH session")

        # Save to database
        add_to_database(
            str(user), container_name, ssh_session_line,
            ram_limit=ram, cpu_limit=cpu,
            creator=str(interaction.user),
            expiry=expiry_date, os_type=os_type_to_display_name(os)
        )

        # Send details via DM
        dm_embed = discord.Embed(
            title="✅ VPS Created Successfully!",
            description="Here are your VPS details:",
            color=0x2400ff
        )
        dm_embed.add_field(name="🔑 SSH Command", value=f"```{ssh_session_line}```", inline=False)
        dm_embed.add_field(name="💾 RAM", value=f"{ram} GB", inline=True)
        dm_embed.add_field(name="🔥 CPU", value=f"{cpu} cores", inline=True)
        dm_embed.add_field(name="🐧 OS", value=os_type_to_display_name(os), inline=True)
        dm_embed.add_field(name="🧊 Container Name", value=container_name, inline=False)
        dm_embed.set_footer(text="🔐 Powered by LP Nodes")

        try:
            await user.send(embed=dm_embed)
            success_embed = discord.Embed(
                title="✅ VPS Created",
                description=f"Successfully created VPS for {user.mention}. Check your DMs for details.",
                color=0x2400ff
            )
            await interaction.followup.send(embed=success_embed)
        except discord.Forbidden:
            error_embed = discord.Embed(
                title="⚠️ DM Failed",
                description=f"VPS created for {user.mention}, but I couldn’t DM them. DMs may be disabled.",
                color=0xffa500
            )
            error_embed.add_field(name="🔑 SSH Command", value=f"```{ssh_session_line}```", inline=False)
            await interaction.followup.send(embed=error_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Deployment Failed",
            description=f"Error: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)

# -----------------------
# port-add (forwarding)
# -----------------------
@bot.tree.command(name="port-add", description="🔌 Adds a port forwarding rule")
@app_commands.describe(container_name="The name of the container", container_port="The port in the container")
async def port_add(interaction: discord.Interaction, container_name: str, container_port: int):
    embed = discord.Embed(
        title="🔄 Setting Up IPV4 Forwarding",
        description="Setting up port forwarding. This might take a moment...",
        color=0x2400ff
    )
    await interaction.response.send_message(embed=embed)

    public_port = generate_random_port()

    # Set up port forwarding inside the container using serveo or similar
    command = f"ssh -o StrictHostKeyChecking=no -R {public_port}:localhost:{container_port} serveo.net -N -f"

    try:
        await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "bash", "-c", command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )

        success_embed = discord.Embed(
            title="✅ Get IPV4 Successful",
            description=f"Your service is now accessible from the internet.",
            color=0x2400ff
        )
        success_embed.add_field(
            name="🌐 Connection Details",
            value=f"**Host:** {PUBLIC_IP}\n**Port:** {public_port}",
            inline=False
        )
        await interaction.followup.send(embed=success_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An unexpected error occurred: {e}",
            color=0x2400ff
        )
        await interaction.followup.send(embed=error_embed)

# -----------------------
# port-http (HTTP forward)
# -----------------------
async def capture_output(process, keyword):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if keyword in output:
            return output
    return None

@bot.tree.command(name="port-http", description="🌐 Forward HTTP traffic to your container")
@app_commands.describe(container_name="The name of your container", container_port="The port inside the container to forward")
async def port_forward_website(interaction: discord.Interaction, container_name: str, container_port: int):
    embed = discord.Embed(
        title="🔄 Setting Up HTTP Forwarding",
        description="Setting up HTTP forwarding. This might take a moment...",
        color=0x2400ff
    )
    await interaction.response.send_message(embed=embed)
    
    try:
        exec_cmd = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "ssh", "-o", "StrictHostKeyChecking=no", "-R", f"80:localhost:{container_port}", "serveo.net",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        url_line = await capture_output(exec_cmd, "Forwarding HTTP traffic from")
        
        if url_line:
            url = url_line.split(" ")[-1]
            success_embed = discord.Embed(
                title="✅ HTTP Forwarding Successful",
                description=f"Your web service is now accessible from the internet.",
                color=0x2400ff
            )
            success_embed.add_field(
                name="🌐 Website URL",
                value=f"[{url}](https://{url})",
                inline=False
            )
            await interaction.followup.send(embed=success_embed)
        else:
            error_embed = discord.Embed(
                title="❌ Error",
                description="Failed to set up HTTP forwarding. Please try again later.",
                color=0x2400ff
            )
            await interaction.followup.send(embed=error_embed)
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An unexpected error occurred: {e}",
            color=0x2400ff
        )
        await interaction.followup.send(embed=error_embed)

# -----------------------
# manage (control panel)
# -----------------------
@bot.tree.command(name="manage", description="🧩 Manage an existing VPS container")
@app_commands.describe(container_id="The container name or ID to manage")
async def manage(interaction: discord.Interaction, container_id: str):
    await interaction.response.defer()

    # Find the VPS in the database
    vps_list = get_all_containers()
    vps_data = None
    for vps in vps_list:
        if container_id in vps:
            vps_data = vps.split('|')
            break

    if not vps_data:
        embed = discord.Embed(
            title="❌ Not Found",
            description=f"No VPS found with ID or name `{container_id}`.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    user, container_name, ssh_command, ram, cpu, creator, os_type, expiry = (
        vps_data + ["Unknown"] * (8 - len(vps_data))
    )

    # Get container status
    stats = get_container_stats(container_name)

    # Create the embed
    embed = discord.Embed(
        title=f"🖥️ VPS Management - {container_name}",
        description=f"Managing container for **{user}**",
        color=0x2400ff
    )
    embed.add_field(
        name="📊 Resources",
        value=f"**Plan:** Custom\n"
              f"**Status:** {stats['status']}\n"
              f"**RAM:** {ram}GB\n"
              f"**CPU:** {cpu} cores\n"
              f"**Storage:** ∞\n"
              f"**OS:** {os_type}",
        inline=False
    )
    embed.add_field(
        name="🎮 Controls",
        value="Use the buttons below to manage your VPS",
        inline=False
    )
    embed.set_footer(text=f"LP Nodes VPS Manager • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create buttons
    class ManageView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @discord.ui.button(label="🔁 Reinstall", style=discord.ButtonStyle.danger)
        async def reinstall_button(self, interaction2: discord.Interaction, button: discord.ui.Button):
            # For safety, only allow admins or the owner to reinstall
            # owner check: container owner is `user`
            caller = str(interaction2.user)
            if not (is_admin(interaction2.user.id) or caller == user):
                await interaction2.response.send_message("❌ You don't have permission to perform this action.", ephemeral=True)
                return

            await interaction2.response.send_message("🔄 Reinstalling VPS (restarting)...", ephemeral=True)
            subprocess.run(["docker", "restart", container_name], check=False)
            await interaction2.followup.send("✅ VPS reinstalled successfully!", ephemeral=True)

        @discord.ui.button(label="▶️ Start", style=discord.ButtonStyle.success)
        async def start_button(self, interaction2: discord.Interaction, button: discord.ui.Button):
            caller = str(interaction2.user)
            if not (is_admin(interaction2.user.id) or caller == user):
                await interaction2.response.send_message("❌ You don't have permission to perform this action.", ephemeral=True)
                return

            await interaction2.response.send_message("🚀 Starting VPS...", ephemeral=True)
            subprocess.run(["docker", "start", container_name], check=False)
            await interaction2.followup.send("✅ VPS started successfully!", ephemeral=True)

        @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.secondary)
        async def stop_button(self, interaction2: discord.Interaction, button: discord.ui.Button):
            caller = str(interaction2.user)
            if not (is_admin(interaction2.user.id) or caller == user):
                await interaction2.response.send_message("❌ You don't have permission to perform this action.", ephemeral=True)
                return

            await interaction2.response.send_message("🛑 Stopping VPS...", ephemeral=True)
            subprocess.run(["docker", "stop", container_name], check=False)
            await interaction2.followup.send("✅ VPS stopped successfully!", ephemeral=True)

        @discord.ui.button(label="🔑 SSH", style=discord.ButtonStyle.primary)
        async def ssh_button(self, interaction2: discord.Interaction, button: discord.ui.Button):
            # Anyone allowed to view this embed can request SSH command (ephemeral)
            await interaction2.response.send_message(
                f"🔐 SSH Command:\n```{ssh_command}```", ephemeral=True
            )

    view = ManageView()
    await interaction.followup.send(embed=embed, view=view)

# -----------------------
# delete (single) and delete-all (admin)
# -----------------------
@bot.tree.command(name="delete", description="Delete your VPS instance")
@app_commands.describe(container_name="The name of your container")
async def delete_server(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    container_id = get_container_id_from_database(user, container_name)

    if not container_id:
        embed = discord.Embed(
            title="❌ Not Found",
            description="No instance found with that name for your user.",
            color=0x2400ff
        )
        await interaction.response.send_message(embed=embed)
        return

    # Stop and remove container
    try:
        subprocess.run(["docker", "stop", container_id], check=False)
        subprocess.run(["docker", "rm", container_id], check=False)
        remove_from_database(container_id)
        embed = discord.Embed(
            title=" VPS Deleted",
            description=f"Successfully deleted VPS instance `{container_name}`.",
            color=0x2400ff
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to delete VPS instance: {e}",
            color=0x2400ff
        )
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="delete-all", description="🗑️ Admin: Delete all VPS instances")
async def delete_all_servers(interaction: discord.Interaction):
    if interaction.user.id not in ADMIN_IDS:
        embed = discord.Embed(
            title="**❌ Access Denied**",
            description="**You don't have permission to use this command.**",
            color=0x2400ff
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    containers = get_all_containers()
    confirm_embed = discord.Embed(
        title="**⚠️ Confirm Mass Deletion**",
        description=f"**Are you sure you want to delete ALL {len(containers)} VPS instances? This action cannot be undone.**",
        color=0x2400ff
    )
    
    # Quick confirm via two-step buttons
    class ConfirmAllView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
        
        @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction2: discord.Interaction, button: discord.ui.Button):
            if interaction2.user.id not in ADMIN_IDS:
                await interaction2.response.send_message("❌ You are not allowed to perform this action.", ephemeral=True)
                return
            await interaction2.response.defer()
            deleted_count = 0
            for container_info in containers:
                parts = container_info.split('|')
                if len(parts) >= 2:
                    container_id = parts[1]
                    try:
                        subprocess.run(["docker", "stop", container_id], check=False, stderr=subprocess.DEVNULL)
                        subprocess.run(["docker", "rm", container_id], check=False, stderr=subprocess.DEVNULL)
                        deleted_count += 1
                    except Exception:
                        pass
            # Clear DB
            with open(database_file, 'w') as f:
                f.write('')
            await interaction2.followup.send(f"✅ Deleted {deleted_count} VPS instances.")
        
        @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction2: discord.Interaction, button: discord.ui.Button):
            await interaction2.response.send_message("Operation cancelled.", ephemeral=True)
    
    view = ConfirmAllView()
    await interaction.response.send_message(embed=confirm_embed, view=view)

# -----------------------
# list (user's VPS)
# -----------------------
@bot.tree.command(name="list", description="📋 List all your VPS instances")
async def list_servers(interaction: discord.Interaction):
    user = str(interaction.user)
    servers = get_user_servers(user)

    await interaction.response.defer()

    if not servers:
        embed = discord.Embed(
            title="📋 Your VPS",
            description="**You don't have any VPS instances. Use `/deploy` to create one!**",
            color=0x2400ff
        )
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(
        title="📋 Your VPS",
        description=f"**You have {len(servers)} VPS instance(s)**",
        color=0x2400ff
    )

    for server in servers:
        parts = server.split('|')
        container_id = parts[1]
        
        # Get container status
        try:
            container_info = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Status}}", container_id]).decode().strip()
            status = "🟢 Running" if container_info == "running" else "🔴 Stopped"
        except:
            status = "🔴 Stopped"
        
        # Get resource limits and other details
        if len(parts) >= 8:
            ram_limit, cpu_limit, creator, os_type, expiry = parts[3], parts[4], parts[5], parts[6], parts[7]
            
            embed.add_field(
                name=f"🖥️ {container_id} ({status})",
                value=f"💾 **RAM:** {ram_limit}GB\n"
                      f"🔥 **CPU:** {cpu_limit} cores\n"
                      f"💾 **Storage:** 10000 GB (Shared)\n"
                      f" 🧊**OS:** {os_type}\n"
                      f"👑 **Created by:** {creator}\n"
                      f"⏱️ **Expires:** {expiry}",
                inline=False
            )
        else:
            embed.add_field(
                name=f"🖥️ {container_id} ({status})",
                value=f"💾 **RAM:** 16GB\n"
                      f"🔥 **CPU:** 40 core\n"
                      f"💾 **Storage:** 10000 GB (Shared)\n"
                      f"🧊 **OS:** Ubuntu 22.04",
                inline=False
            )

    await interaction.followup.send(embed=embed)

# -----------------------
# ping
# -----------------------
@bot.tree.command(name="ping", description="🏓 Check the bot's latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=0x00ff00
    )
    await interaction.response.send_message(embed=embed)

# -----------------------
# create (reward system) - kept
# -----------------------
def get_invite_rewards(invite_count):
    if invite_count >= 15:
        return {"ram": 32, "cpu": 9}
    elif invite_count >= 8:
        return {"ram": 8, "cpu": 2}
    else:
        return None

def get_boost_rewards(boost_count):
    if boost_count >= 2:
        return {"ram": 31, "cpu": 4}
    else:
        return None

class RewardSelectView(View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=60)
        self.user = user
        self.add_item(Select(
            placeholder="Select your reward method",
            options=[
                discord.SelectOption(label="Invite Reward", value="invite", emoji="✉️"),
                discord.SelectOption(label="Boost Reward", value="boost", emoji="🎁")
            ]
        ))

    @discord.ui.select()
    async def select_callback(self, interaction: discord.Interaction, select: Select):
        choice = select.values[0]

        if choice == "invite":
            invites = await interaction.guild.invites()
            user_invites = sum(i.uses for i in invites if i.inviter == self.user)
            reward = get_invite_rewards(user_invites)
            if reward:
                await send_vps_request(interaction, self.user, "Invite", reward, user_invites)
            else:
                await interaction.response.send_message(f"❌ You have only **{user_invites} invites**. You need at least **8** to claim.", ephemeral=True)

        elif choice == "boost":
            boost_count = self.user.premium_since is not None and interaction.guild.premium_subscriber_count or 0
            reward = get_boost_rewards(boost_count)
            if reward:
                await send_vps_request(interaction, self.user, "Boost", reward, boost_count)
            else:
                await interaction.response.send_message(f"❌ You need at least **2 boosts** to claim. Current: {boost_count}", ephemeral=True)

@bot.tree.command(name="create", description="🎁 Request a VPS via Invite or Boost rewards")
async def create(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ You must use this in a server.", ephemeral=True)
        return

    view = RewardSelectView(interaction.user)
    embed = discord.Embed(
        title="🎉 VPS Reward Selection",
        description="Please select your reward method below.",
        color=0x2400ff
    )
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def send_vps_request(interaction, user, method, reward, count):
    # send to admin channel for approvals — update channel ID as needed
    channel = bot.get_channel(1390545538239299608)
    if not channel:
        await interaction.response.send_message("❌ VPS channel not found.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🚀 VPS Request Submitted",
        description=f"User: {user.mention}\nMethod: {method} Reward",
        color=0x2400ff
    )
    embed.add_field(name="📊 RAM", value=f"{reward['ram']} GB", inline=True)
    embed.add_field(name="🔥 CPU", value=f"{reward.get('cpu', 2)} cores", inline=True)
    embed.set_footer(text=f"{count} {'invites' if method == 'Invite' else 'boosts'}")
    await channel.send(embed=embed)
    await interaction.response.send_message("✅ Your VPS request has been sent for approval!", ephemeral=True)

# -----------------------
# help (updated)
# -----------------------
@bot.tree.command(name="help", description="❓ Shows the help message")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="**🌟 VPS Bot Help**",
        description="** Here are all the available commands:**",
        color=0x00aaff
    )
    
    # User commands
    embed.add_field(
        name="📋 User Commands",
        value="Commands available to all users:",
        inline=False
    )
    embed.add_field(name="/list", value="List all your VPS instances", inline=True)
    embed.add_field(name="/delete <container_name>", value="Delete your VPS instance", inline=True)
    embed.add_field(name="/port-add <container_name> <port>", value="Forward a random public port", inline=True)
    embed.add_field(name="/port-http <container_name> <port>", value="Forward HTTP traffic", inline=True)
    embed.add_field(name="/ping", value="Check bot latency", inline=True)
    embed.add_field(name="/create", value="Request a VPS via rewards (invite/boost)", inline=True)
    embed.add_field(name="/manage <container_id>", value="Open VPS control panel (Start/Stop/Reinstall/SSH)", inline=True)
    embed.add_field(name="/help", value="Show this help menu", inline=True)
    
    # Admin commands
    if interaction.user.id in ADMIN_IDS:
        embed.add_field(
            name="👑 Admin Commands",
            value="Commands available only to admins:",
            inline=False
        )
        embed.add_field(name="/deploy user:@user os:ubuntu ram:4 cpu:2", value="Instantly deploy a VPS", inline=True)
        embed.add_field(name="/node", value="View system resource usage", inline=True)
        embed.add_field(name="/nodedmin", value="List all VPS instances with details", inline=True)
        embed.add_field(name="/delete-all", value="Delete all VPS instances", inline=True)
    
    await interaction.response.send_message(embed=embed)

# -----------------------
# Run bot
# -----------------------
if __name__ == "__main__":
    # basic logging
    logging.basicConfig(level=logging.INFO)
    if not TOKEN:
        print("ERROR: TOKEN is empty. Please set TOKEN variable in v2.py")
        sys.exit(1)
    bot.run(TOKEN)
