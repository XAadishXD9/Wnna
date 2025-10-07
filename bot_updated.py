
# EagleNode updated bot.py
# GENERATED: includes admin management, VPS management, DM behavior, and requested commands.
import random
import logging
import subprocess
import sys
import os
import re
import time
import asyncio
import string
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Button, View, Select

# ---------- Configuration ----------
TOKEN = ''  # <-- set your bot token here
RAM_LIMIT = '6g'
SERVER_LIMIT = 1
database_file = 'database.txt'
admins_file = 'admins.txt'
PUBLIC_IP = '138.68.79.95'
EMBED_COLOR = 0x2400ff

# Default admins (will be loaded from file if available)
ADMIN_IDS = []

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# ---------- Helper functions ----------
def load_admins():
    global ADMIN_IDS
    ADMIN_IDS = []
    if os.path.exists(admins_file):
        with open(admins_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    ADMIN_IDS.append(int(line))
    # keep unique
    ADMIN_IDS = list(dict.fromkeys(ADMIN_IDS))

def save_admins():
    with open(admins_file, 'w') as f:
        for aid in ADMIN_IDS:
            f.write(str(aid) + '\\n')

def is_admin(user_id):
    return user_id in ADMIN_IDS

def add_admin_to_file(user_id):
    if user_id not in ADMIN_IDS:
        ADMIN_IDS.append(user_id)
        save_admins()
        return True
    return False

def remove_admin_from_file(user_id):
    if user_id in ADMIN_IDS:
        ADMIN_IDS.remove(user_id)
        save_admins()
        return True
    return False

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_random_port(): 
    return random.randint(1025, 65535)

def parse_time_to_seconds(time_str):
    if not time_str:
        return None
    units = {'s':1,'m':60,'h':3600,'d':86400,'M':2592000,'y':31536000}
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

def add_to_database(user, container_name, ssh_command, ram_limit=None, cpu_limit=None, creator=None, expiry=None, os_type="Ubuntu 22.04", suspended=False):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram_limit or '2048'}|{cpu_limit or '1'}|{creator or user}|{os_type}|{expiry or 'None'}|{suspended}\\n")

def remove_from_database(container_id):
    if not os.path.exists(database_file):
        return False
    removed = False
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if container_id not in line:
                f.write(line)
            else:
                removed = True
    return removed

def update_database_entry(container_id, updater):
    # updater is a function that takes list(parts) and returns updated parts or None to skip
    if not os.path.exists(database_file):
        return False
    changed = False
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if container_id in line:
                parts = line.strip().split('|')
                new_parts = updater(parts)
                if new_parts:
                    f.write('|'.join(new_parts) + '\\n')
                    changed = True
                else:
                    f.write(line)
            else:
                f.write(line)
    return changed

def get_all_containers():
    if not os.path.exists(database_file):
        return []
    with open(database_file, 'r') as f:
        return [line.strip() for line in f.readlines()]

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

def get_vps_record(container_id):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if container_id in line:
                return line.strip().split('|')
    return None

def get_container_stats(container_id):
    try:
        mem_stats = subprocess.check_output(["docker", "stats", container_id, "--no-stream", "--format", "{{.MemUsage}}"]).decode().strip()
        cpu_stats = subprocess.check_output(["docker", "stats", container_id, "--no-stream", "--format", "{{.CPUPerc}}"]).decode().strip()
        status = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Status}}", container_id]).decode().strip()
        return {"memory": mem_stats, "cpu": cpu_stats, "status": "🟢 Running" if status == "running" else "🔴 Stopped"}
    except Exception:
        return {"memory": "N/A", "cpu": "N/A", "status": "🔴 Stopped"}

def get_system_stats():
    try:
        total_mem = subprocess.check_output(["free", "-m"]).decode().strip()
        mem_lines = total_mem.split('\\n')
        if len(mem_lines) >= 2:
            mem_values = mem_lines[1].split()
            total_mem = mem_values[1]
            used_mem = mem_values[2]
        disk_usage = subprocess.check_output(["df", "-h", "/"]).decode().strip()
        disk_lines = disk_usage.split('\\n')
        if len(disk_lines) >= 2:
            disk_values = disk_lines[1].split()
            total_disk = disk_values[1]
            used_disk = disk_values[2]
        return {"total_memory": f"{total_mem}MB", "used_memory": f"{used_mem}MB", "total_disk": total_disk, "used_disk": used_disk}
    except Exception as e:
        return {"total_memory": "N/A", "used_memory": "N/A", "total_disk": "N/A", "used_disk": "N/A", "error": str(e)}

async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        output = output.decode('utf-8').strip()
        if "ssh session:" in output or "ssh -p" in output or "ssh " in output:
            return output
    return None

async def capture_output(process, keyword):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        line = output.decode('utf-8').strip()
        if keyword in line:
            return line
    return None

# ---------- Views / Buttons ----------
class ConfirmView(View):
    def __init__(self, container_id=None, action='delete', user_to_notify=None):
        super().__init__(timeout=60)
        self.container_id = container_id
        self.action = action
        self.user_to_notify = user_to_notify

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            if self.action == 'delete' and self.container_id:
                subprocess.run(["docker", "stop", self.container_id], check=False, stderr=subprocess.DEVNULL)
                subprocess.run(["docker", "rm", self.container_id], check=False, stderr=subprocess.DEVNULL)
                removed = remove_from_database(self.container_id)
                await interaction.followup.send(embed=discord.Embed(title="✅ VPS Deleted", description=f"{self.container_id} deleted.", color=EMBED_COLOR))
                if self.user_to_notify:
                    try:
                        await self.user_to_notify.send(f"Your VPS `{self.container_id}` has been deleted by an admin.")
                    except:
                        pass
            elif self.action == 'suspend' and self.container_id:
                subprocess.run(["docker", "stop", self.container_id], check=False)
                def updater(parts):
                    parts[8] = 'True' if len(parts) > 8 else 'True'
                    return parts
                update_database_entry(self.container_id, updater)
                await interaction.followup.send(embed=discord.Embed(title="✅ VPS Suspended", description=f"{self.container_id} suspended.", color=EMBED_COLOR))
                if self.user_to_notify:
                    try:
                        await self.user_to_notify.send(f"Your VPS `{self.container_id}` has been suspended by an admin.")
                    except:
                        pass
            elif self.action == 'unsuspend' and self.container_id:
                subprocess.run(["docker", "start", self.container_id], check=False)
                def updater(parts):
                    parts[8] = 'False' if len(parts) > 8 else 'False'
                    return parts
                update_database_entry(self.container_id, updater)
                await interaction.followup.send(embed=discord.Embed(title="✅ VPS Unsuspended", description=f"{self.container_id} unsuspended.", color=EMBED_COLOR))
                if self.user_to_notify:
                    try:
                        await self.user_to_notify.send(f"Your VPS `{self.container_id}` has been unsuspended by an admin.")
                    except:
                        pass
            else:
                await interaction.followup.send("Unknown action.")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Operation cancelled.", ephemeral=True)
        for child in self.children:
            child.disabled = True

class ManageVPSView(View):
    def __init__(self, container_id, owner_user):
        super().__init__(timeout=120)
        self.container_id = container_id
        self.owner_user = owner_user

    @discord.ui.button(label="Start", style=discord.ButtonStyle.success)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            subprocess.run(["docker", "start", self.container_id], check=True)
            await interaction.followup.send(embed=discord.Embed(title="▶️ VPS Started", description=f"{self.container_id} started.", color=EMBED_COLOR))
            # notify owner
            if self.owner_user:
                try:
                    await self.owner_user.send(f"Your VPS `{self.container_id}` has been started by an admin.")
                except:
                    pass
        except Exception as e:
            await interaction.followup.send(f"Error starting VPS: {e}")

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            subprocess.run(["docker", "stop", self.container_id], check=True)
            await interaction.followup.send(embed=discord.Embed(title="⏹️ VPS Stopped", description=f"{self.container_id} stopped.", color=EMBED_COLOR))
            if self.owner_user:
                try:
                    await self.owner_user.send(f"Your VPS `{self.container_id}` has been stopped by an admin.")
                except:
                    pass
        except Exception as e:
            await interaction.followup.send(f"Error stopping VPS: {e}")

    @discord.ui.button(label="Restart", style=discord.ButtonStyle.primary)
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            subprocess.run(["docker", "restart", self.container_id], check=True)
            await interaction.followup.send(embed=discord.Embed(title="🔄 VPS Restarted", description=f"{self.container_id} restarted.", color=EMBED_COLOR))
            if self.owner_user:
                try:
                    await self.owner_user.send(f"Your VPS `{self.container_id}` has been restarted by an admin.")
                except:
                    pass
        except Exception as e:
            await interaction.followup.send(f"Error restarting VPS: {e}")

    @discord.ui.button(label="Regen SSH", style=discord.ButtonStyle.secondary)
    async def regen_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", self.container_id, "tmate", "-F", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            ssh_line = await capture_ssh_session_line(exec_cmd)
            if ssh_line:
                update_database_entry(self.container_id, lambda parts: parts[:2] + [ssh_line] + parts[3:])
                await interaction.followup.send(embed=discord.Embed(title="🔑 SSH Regenerated", description=f"New SSH: `{ssh_line}`", color=EMBED_COLOR))
                if self.owner_user:
                    try:
                        await self.owner_user.send(f"Your VPS `{self.container_id}` has a new SSH command:\\n``{ssh_line}``")
                    except:
                        pass
            else:
                await interaction.followup.send("Failed to generate SSH session.")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please confirm deletion.", view=ConfirmView(self.container_id, action='delete', user_to_notify=self.owner_user))

# ---------- Bot Events ----------
@bot.event
async def on_ready():
    load_admins()
    change_status.start()
    print(f"🚀 Bot ready as {bot.user}. Admins: {ADMIN_IDS}")
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Sync failed:", e)

@tasks.loop(seconds=10)
async def change_status():
    try:
        instances = get_all_containers() if os.path.exists(database_file) else []
        instance_count = len(instances)
        status = f"EagleNode {instance_count} VPS"
        await bot.change_presence(activity=discord.Game(name=status))
    except Exception as e:
        print('Status update failed:', e)

# ---------- Admin Commands ----------
@bot.tree.command(name="list_admins", description="List all admins for EagleNode")
async def list_admins(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can use this.', color=EMBED_COLOR), ephemeral=True)
    load_admins()
    if not ADMIN_IDS:
        return await interaction.response.send_message(embed=discord.Embed(title='Admins', description='No admins configured.', color=EMBED_COLOR))
    desc = '\\n'.join([f"<@{aid}> ({aid})" for aid in ADMIN_IDS])
    await interaction.response.send_message(embed=discord.Embed(title='👑 EagleNode Admins', description=desc, color=EMBED_COLOR))

@bot.tree.command(name="add_admin", description="Add a new admin")
@app_commands.describe(user="User ID of the new admin")
async def add_admin(interaction: discord.Interaction, user: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can add admins.', color=EMBED_COLOR), ephemeral=True)
    # try to parse mention or ID
    user_id = re.sub(r"\D", "", user)
    if not user_id.isdigit():
        return await interaction.response.send_message('Please provide a valid user id or mention.')
    user_id = int(user_id)
    added = add_admin_to_file(user_id)
    if added:
        await interaction.response.send_message(embed=discord.Embed(title='✅ Admin Added', description=f'<@{user_id}> has been added as admin.', color=EMBED_COLOR))
    else:
        await interaction.response.send_message(embed=discord.Embed(title='ℹ️ Already Admin', description=f'<@{user_id}> is already an admin.', color=EMBED_COLOR))

@bot.tree.command(name="remove_admin", description="Remove an admin")
@app_commands.describe(user="User ID of the admin to remove")
async def remove_admin(interaction: discord.Interaction, user: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can remove admins.', color=EMBED_COLOR), ephemeral=True)
    user_id = re.sub(r"\D", "", user)
    if not user_id.isdigit():
        return await interaction.response.send_message('Please provide a valid user id or mention.')
    user_id = int(user_id)
    if user_id == interaction.user.id:
        return await interaction.response.send_message('You cannot remove yourself.')
    removed = remove_admin_from_file(user_id)
    if removed:
        await interaction.response.send_message(embed=discord.Embed(title='✅ Admin Removed', description=f'<@{user_id}> removed from admins.', color=EMBED_COLOR))
    else:
        await interaction.response.send_message(embed=discord.Embed(title='❌ Not Found', description=f'<@{user_id}> is not an admin.', color=EMBED_COLOR))

@bot.tree.command(name="admin_stats", description="Show admin and system stats")
async def admin_stats(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can use this.', color=EMBED_COLOR), ephemeral=True)
    load_admins()
    containers = get_all_containers()
    stats = get_system_stats()
    embed = discord.Embed(title='📊 Admin Stats', color=EMBED_COLOR)
    embed.add_field(name='Total VPS', value=str(len(containers)))
    embed.add_field(name='Total Admins', value=str(len(ADMIN_IDS)))
    embed.add_field(name='Memory', value=f"{stats.get('used_memory')}/{stats.get('total_memory')}", inline=False)
    embed.add_field(name='Disk', value=f"{stats.get('used_disk')}/{stats.get('total_disk')}", inline=False)
    await interaction.response.send_message(embed=embed)

# ---------- VPS Commands ----------
@bot.tree.command(name="create_vps", description="Create a VPS quickly (admin only)")
@app_commands.describe(memory="Memory in GB for the VPS (integer)","user_id":"Discord user id to assign (optional)")
async def create_vps(interaction: discord.Interaction, memory: int, user_id: str = None):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can create VPS.', color=EMBED_COLOR), ephemeral=True)
    await interaction.response.defer()
    # simple cpu allocation heuristic
    cpu = max(1, min(4, memory // 2))
    target_user_id = interaction.user.id if not user_id else int(re.sub(r"\D","", user_id))
    container_name = f"VPS_{interaction.user.name}_{generate_random_string(6)}"
    image = "ubuntu-22.04-with-tmate"
    try:
        container_id = subprocess.check_output(["docker", "run", "-itd", "--privileged", "--cap-add=ALL", f"--memory={memory}g", f"--cpus={cpu}", "--name", container_name, image]).strip().decode('utf-8')
    except Exception as e:
        return await interaction.followup.send(embed=discord.Embed(title='❌ Error', description=str(e), color=EMBED_COLOR))
    # try starting tmate to get ssh line
    try:
        exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_name, "tmate", "-F", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        ssh_line = await capture_ssh_session_line(exec_cmd)
    except Exception:
        ssh_line = 'ssh-not-available'
    add_to_database(str(target_user_id), container_name, ssh_line, ram_limit=str(memory), cpu_limit=str(cpu), creator=str(interaction.user), expiry=None, os_type="Ubuntu 22.04")
    dm_embed = discord.Embed(title='✅ VPS Created', description=f'Your VPS has been created: `{container_name}`', color=EMBED_COLOR)
    dm_embed.add_field(name='🔑 SSH', value=f'```{ssh_line}```', inline=False)
    dm_embed.add_field(name='💾 RAM', value=f'{memory} GB', inline=True)
    dm_embed.add_field(name='🔥 CPU', value=f'{cpu} cores', inline=True)
    try:
        target_user = await bot.fetch_user(int(target_user_id))
        await target_user.send(embed=dm_embed)
    except Exception:
        await interaction.followup.send(embed=discord.Embed(title='⚠️ Could not DM user. VPS created.', description=f'`{container_name}` created but DM failed.', color=EMBED_COLOR))
        return await interaction.followup.send(embed=discord.Embed(title='✅ VPS Created', description=f'`{container_name}` created for <@{target_user_id}>', color=EMBED_COLOR))
    await interaction.followup.send(embed=discord.Embed(title='✅ VPS Created', description=f'`{container_name}` created for <@{target_user_id}>', color=EMBED_COLOR))

@bot.tree.command(name="delete_vps", description="Delete a VPS by id (admin only)")
@app_commands.describe(vps_id="Container name or id to delete")
async def delete_vps(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can delete VPS.', color=EMBED_COLOR), ephemeral=True)
    record = get_vps_record(vps_id)
    owner = None
    if record:
        owner_id = int(record[0]) if record[0].isdigit() else None
        if owner_id:
            try:
                owner = await bot.fetch_user(owner_id)
            except:
                owner = None
    await interaction.response.send_message(embed=discord.Embed(title='⚠️ Confirm Deletion', description=f'Are you sure you want to delete `{vps_id}`?', color=EMBED_COLOR), view=ConfirmView(vps_id, action='delete', user_to_notify=owner))

@bot.tree.command(name="suspend_vps", description="Suspend a VPS (admin only)")
@app_commands.describe(vps_id="Container name or id to suspend")
async def suspend_vps(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can suspend VPS.', color=EMBED_COLOR), ephemeral=True)
    record = get_vps_record(vps_id)
    owner = None
    if record:
        owner_id = int(record[0]) if record[0].isdigit() else None
        if owner_id:
            try:
                owner = await bot.fetch_user(owner_id)
            except:
                owner = None
    await interaction.response.send_message(embed=discord.Embed(title='⚠️ Confirm Suspend', description=f'Confirm suspend `{vps_id}`?', color=EMBED_COLOR), view=ConfirmView(vps_id, action='suspend', user_to_notify=owner))

@bot.tree.command(name="unsuspend_vps", description="Unsuspend a VPS (admin only)")
@app_commands.describe(vps_id="Container name or id to unsuspend")
async def unsuspend_vps(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can unsuspend VPS.', color=EMBED_COLOR), ephemeral=True)
    record = get_vps_record(vps_id)
    owner = None
    if record:
        owner_id = int(record[0]) if record[0].isdigit() else None
        if owner_id:
            try:
                owner = await bot.fetch_user(owner_id)
            except:
                owner = None
    await interaction.response.send_message(embed=discord.Embed(title='⚠️ Confirm Unsuspend', description=f'Confirm unsuspend `{vps_id}`?', color=EMBED_COLOR), view=ConfirmView(vps_id, action='unsuspend', user_to_notify=owner))

@bot.tree.command(name="change_ssh_password", description="Change SSH password in VPS (admin only)")
@app_commands.describe(vps_id="Container name or id to change password to a random one")
async def change_ssh_password(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can change passwords.', color=EMBED_COLOR), ephemeral=True)
    new_pass = generate_random_string(12)
    try:
        subprocess.run(["docker","exec", vps_id, "bash", "-lc", f"echo 'root:{new_pass}' | chpasswd"], check=True)
        # notify owner
        record = get_vps_record(vps_id)
        owner = None
        if record:
            owner_id = int(record[0]) if record[0].isdigit() else None
            if owner_id:
                try:
                    owner = await bot.fetch_user(owner_id)
                except:
                    owner = None
        if owner:
            try:
                await owner.send(embed=discord.Embed(title='🔒 SSH Password Changed', description=f'Your VPS `{vps_id}` password has been changed by an admin.', color=EMBED_COLOR).add_field(name='New Password', value=f'`{new_pass}`', inline=False))
            except:
                pass
        await interaction.response.send_message(embed=discord.Embed(title='✅ Password Changed', description=f'New password set for `{vps_id}`.', color=EMBED_COLOR))
    except Exception as e:
        await interaction.response.send_message(embed=discord.Embed(title='❌ Error', description=str(e), color=EMBED_COLOR))

@bot.tree.command(name="vps_stats", description="Show VPS stats (admin only)")
@app_commands.describe(vps_id="Container name or id to show stats for")
async def vps_stats(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can view stats.', color=EMBED_COLOR), ephemeral=True)
    stats = get_container_stats(vps_id)
    embed = discord.Embed(title=f'📊 VPS Stats: {vps_id}', color=EMBED_COLOR)
    embed.add_field(name='Status', value=stats.get('status'))
    embed.add_field(name='Memory', value=stats.get('memory'))
    embed.add_field(name='CPU', value=stats.get('cpu'))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vps_list", description="List all VPS instances (admin)")
async def vps_list(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can view this.', color=EMBED_COLOR), ephemeral=True)
    containers = get_all_containers()
    if not containers:
        return await interaction.response.send_message(embed=discord.Embed(title='📋 VPS List', description='No VPS instances found.', color=EMBED_COLOR))
    embed = discord.Embed(title='📋 All VPS Instances', color=EMBED_COLOR)
    for line in containers:
        parts = line.split('|')
        name = parts[1] if len(parts) > 1 else 'unknown'
        owner = parts[0] if len(parts) > 0 else 'unknown'
        ssh = parts[2] if len(parts) > 2 else 'n/a'
        suspended = parts[8] if len(parts) > 8 else 'False'
        embed.add_field(name=f'{name} ({"suspended" if suspended=="True" else "active"})', value=f'Owner: <@{owner}>\\nSSH: ` {ssh} `', inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="manage_vps", description="Open management panel for a VPS (admin only)")
@app_commands.describe(vps_id="Container name or id to manage")
async def manage_vps(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        return await interaction.response.send_message(embed=discord.Embed(title='❌ Access Denied', description='Only admins can manage VPS.', color=EMBED_COLOR), ephemeral=True)
    record = get_vps_record(vps_id)
    owner = None
    owner_id = None
    ssh = 'n/a'
    if record:
        owner = None
        owner_id = int(record[0]) if record[0].isdigit() else None
        try:
            owner = await bot.fetch_user(owner_id) if owner_id else None
        except:
            owner = None
        ssh = record[2] if len(record) > 2 else 'n/a'
    embed = discord.Embed(title=f'🛠️ Manage: {vps_id}', color=EMBED_COLOR)
    embed.add_field(name='Owner', value=f'<@{owner_id}>' if owner_id else 'Unknown', inline=True)
    embed.add_field(name='SSH', value=f'`{ssh}`', inline=False)
    embed.add_field(name='Status', value=get_container_stats(vps_id).get('status'), inline=True)
    view = ManageVPSView(vps_id, owner)
    await interaction.response.send_message(embed=embed, view=view)

# ---------- User Commands (keep existing list) ----------
@bot.tree.command(name="list", description="List all your VPS instances")
async def list_servers(interaction: discord.Interaction):
    user = str(interaction.user.id)
    servers = get_user_servers(user)
    await interaction.response.defer()
    if not servers:
        return await interaction.followup.send(embed=discord.Embed(title='📋 Your VPS', description='You do not have any VPS instances.', color=EMBED_COLOR))
    embed = discord.Embed(title='📋 Your VPS', description=f'You have {len(servers)} VPS instance(s).', color=EMBED_COLOR)
    for server in servers:
        parts = server.split('|')
        container_id = parts[1]
        status = '🔴 Stopped'
        try:
            container_info = subprocess.check_output(["docker","inspect","--format","{{.State.Status}}",container_id]).decode().strip()
            status = '🟢 Running' if container_info == 'running' else '🔴 Stopped'
        except:
            status = '🔴 Stopped'
        embed.add_field(name=f'{container_id} ({status})', value=f'RAM: {parts[3]}GB | CPU: {parts[4]} | OS: {parts[6]}', inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="help", description="Help for EagleNode bot")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title='🆘 EagleNode Help', color=EMBED_COLOR)
    embed.add_field(name='Admin commands', value='/list_admins, /add_admin <user>, /remove_admin <user>, /create_vps <memory>, /delete_vps <vps_id>, /suspend_vps <vps_id>, /unsuspend_vps <vps_id>, /change_ssh_password <vps_id>, /vps_stats <vps_id>, /vps_list, /admin_stats, /manage_vps <vps_id>', inline=False)
    embed.add_field(name='User commands', value='/list, /help', inline=False)
    await interaction.response.send_message(embed=embed)

# ---------- Start the bot ----------
if __name__ == '__main__':
    load_admins()
    # Ensure files exist
    open(database_file, 'a').close()
    open(admins_file, 'a').close()
    bot.run(TOKEN)
