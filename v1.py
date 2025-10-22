# bot.py
import os
import random
import string
import subprocess
import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Select, Button
from datetime import datetime, timedelta

# -------------------------
# Config (fill before run)
# -------------------------
TOKEN = ''  # <-- Put your bot token here
ADMIN_IDS = [1405778722732376176]  # Replace with admin Discord IDs (integers)
database_file = 'database.txt'
PUBLIC_IP = '138.68.79.95'
# -------------------------

intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix='/', intents=intents)

# -------------------------
# Utilities
# -------------------------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

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
    return (datetime.now() + timedelta(seconds=seconds_from_now)).strftime("%Y-%m-%d %H:%M:%S")

def add_to_database(user, container_name, ssh_command, ram_limit=None, cpu_limit=None, creator=None, expiry=None, os_type="Ubuntu 22.04"):
    with open(database_file, 'a') as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram_limit or '2'}|{cpu_limit or '1'}|{creator or user}|{os_type}|{expiry or 'None'}\n")

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

def get_user_servers(user):
    if not os.path.exists(database_file):
        return []
    out = []
    with open(database_file, 'r') as f:
        for line in f:
            if line.startswith(user + "|") or line.startswith(user):
                out.append(line.strip())
    return out

def get_container_record(container_id):
    if not os.path.exists(database_file):
        return None
    with open(database_file, 'r') as f:
        for line in f:
            if container_id in line:
                parts = line.strip().split('|')
                return parts
    return None

def update_ssh_in_db(container_id, new_ssh):
    if not os.path.exists(database_file):
        return
    lines = []
    with open(database_file, 'r') as f:
        lines = f.readlines()
    with open(database_file, 'w') as f:
        for line in lines:
            if container_id in line:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    parts[2] = new_ssh
                f.write('|'.join(parts) + '\n')
            else:
                f.write(line)

def get_docker_image_for_os(os_type):
    os_map = {
        "ubuntu": "ubuntu-22.04-with-tmate",
        "debian": "debian-with-tmate",
        "arch": "arch-with-tmate",
        "alpine": "alpine-with-tmate",
        "centos7": "centos7-with-tmate",
        "fedora38": "fedora38-with-tmate"
    }
    return os_map.get(os_type, "ubuntu-22.04-with-tmate")

async def run_tmate_and_get_ssh(container_name, timeout=30):
    """
    Run 'tmate -F' inside container and capture the 'ssh session:' line.
    Returns the SSH line string or None.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except Exception:
        return None

    # read lines until we find "ssh session:" or timeout
    try:
        line = await asyncio.wait_for(_read_until(proc.stdout, b"ssh session:"), timeout=timeout)
        if line:
            text = line.decode(errors='ignore').strip()
            # Find substring after "ssh session:"
            if "ssh session:" in text:
                return text.split("ssh session:")[-1].strip()
        return None
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except:
            pass
        return None

async def _read_until(stream, marker: bytes):
    """
    Helper to read lines from a StreamReader until a line containing marker is returned.
    """
    while True:
        raw = await stream.readline()
        if not raw:
            return None
        if marker in raw:
            return raw
    return None

def get_container_status(container_id):
    try:
        out = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Status}}", container_id]).decode().strip()
        return "🟢 Running" if out == "running" else "🔴 Stopped"
    except Exception:
        return "🔴 Stopped"

# -------------------------
# Status updater
# -------------------------
@tasks.loop(seconds=10)
async def change_status():
    try:
        cnt = len(get_all_containers())
        await bot.change_presence(activity=discord.Game(name=f"LP NODES {cnt} VPS"))
    except Exception:
        pass

@bot.event
async def on_ready():
    change_status.start()
    print("Bot ready:", bot.user)
    await bot.tree.sync()

# -------------------------
# Commands (existing kept)
# -------------------------
@bot.tree.command(name="ping", description="🏓 Check the bot's latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: {latency}ms")

@bot.tree.command(name="node", description="☠️ Shows system resource usage and VPS status")
async def node_stats(interaction: discord.Interaction):
    await interaction.response.defer()
    # minimal system stats
    try:
        free_out = subprocess.check_output(["free", "-m"]).decode().splitlines()
        mem_line = free_out[1].split()
        total_mem = mem_line[1]
        used_mem = mem_line[2]
    except Exception:
        total_mem = used_mem = "N/A"

    try:
        df = subprocess.check_output(["df", "-h", "/"]).decode().splitlines()
        disk_vals = df[1].split()
        total_disk = disk_vals[1]
        used_disk = disk_vals[2]
    except Exception:
        total_disk = used_disk = "N/A"

    containers = get_all_containers()
    embed = discord.Embed(title="📊 Node Dashboard", color=0x2400ff)
    embed.add_field(name="Memory", value=f"Used: {used_mem}MB / Total: {total_mem}MB", inline=False)
    embed.add_field(name="Disk", value=f"Used: {used_disk} / Total: {total_disk}", inline=False)
    embed.add_field(name="VPS count", value=str(len(containers)), inline=False)
    for rec in containers[:10]:
        parts = rec.split('|')
        if len(parts) >= 2:
            cid = parts[1]
            embed.add_field(name=cid, value=get_container_status(cid), inline=True)
    await interaction.response.send_message(embed=embed)

# -------------------------
# /list (existing)
# -------------------------
@bot.tree.command(name="list", description="📋 List all your VPS instances")
async def list_servers(interaction: discord.Interaction):
    user = str(interaction.user)
    servers = get_user_servers(user)
    await interaction.response.defer()
    if not servers:
        await interaction.followup.send(embed=discord.Embed(title="📋 Your VPS", description="You don't have any VPS instances. Use `/deploy` to create one.", color=0x2400ff))
        return

    embed = discord.Embed(title="📋 Your VPS", description=f"You have {len(servers)} VPS instance(s):", color=0x2400ff)
    for s in servers:
        parts = s.split('|')
        # user|container|ssh|ram|cpu|creator|os|expiry
        if len(parts) >= 8:
            _, cid, ssh, ram, cpu, creator, os_type, expiry = parts
            status = get_container_status(cid)
            embed.add_field(name=f"{cid} ({status})", value=f"RAM: {ram}GB • CPU: {cpu} cores\nOS: {os_type}\nExpires: {expiry}", inline=False)
        else:
            _, cid, ssh = parts[:3]
            status = get_container_status(cid)
            embed.add_field(name=f"{cid} ({status})", value=f"SSH: `{ssh}`", inline=False)
    await interaction.followup.send(embed=embed)

# -------------------------
# NEW: /vps_list (compact)
# -------------------------
@bot.tree.command(name="vps_list", description="🔹 Compact: show your VPS instances")
async def vps_list(interaction: discord.Interaction):
    user = str(interaction.user)
    servers = get_user_servers(user)
    if not servers:
        await interaction.response.send_message("You have no VPS instances.", ephemeral=True)
        return

    lines = []
    for s in servers:
        parts = s.split('|')
        if len(parts) >= 8:
            _, cid, ssh, ram, cpu, creator, os_type, expiry = parts
            status = get_container_status(cid)
            lines.append(f"`{cid}` — {status} — {ram}GB / {cpu} core(s) — {os_type}")
        else:
            _, cid, ssh = parts[:3]
            status = get_container_status(cid)
            lines.append(f"`{cid}` — {status}")

    text = "\n".join(lines)
    await interaction.response.send_message(embed=discord.Embed(title="Your VPS (compact)", description=text, color=0x00aaff), ephemeral=True)

# -------------------------
# Helper Views for /manage (buttons)
# -------------------------
class ManageView(View):
    def __init__(self, container_id, owner_user_str):
        super().__init__(timeout=300)
        self.container_id = container_id
        self.owner_user_str = owner_user_str

    @discord.ui.button(label="🟢 Start", style=discord.ButtonStyle.success)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # permission check
        if not (is_admin(interaction.user.id) or str(interaction.user) == self.owner_user_str):
            await interaction.response.send_message("❌ You don't have permission to manage this VPS.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            subprocess.run(["docker", "start", self.container_id], check=True, stderr=subprocess.DEVNULL)
            await interaction.followup.send(f"✅ Started `{self.container_id}`")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to start: {e}")

    @discord.ui.button(label="🔴 Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (is_admin(interaction.user.id) or str(interaction.user) == self.owner_user_str):
            await interaction.response.send_message("❌ You don't have permission to manage this VPS.", ephemeral=True); return
        await interaction.response.defer()
        try:
            subprocess.run(["docker", "stop", self.container_id], check=True, stderr=subprocess.DEVNULL)
            await interaction.followup.send(f"⏹️ Stopped `{self.container_id}`")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to stop: {e}")

    @discord.ui.button(label="🔁 Restart", style=discord.ButtonStyle.primary)
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (is_admin(interaction.user.id) or str(interaction.user) == self.owner_user_str):
            await interaction.response.send_message("❌ You don't have permission to manage this VPS.", ephemeral=True); return
        await interaction.response.defer()
        try:
            subprocess.run(["docker", "restart", self.container_id], check=True, stderr=subprocess.DEVNULL)
            await interaction.followup.send(f"🔁 Restarted `{self.container_id}`")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to restart: {e}")

    @discord.ui.button(label="🧱 Reinstall OS", style=discord.ButtonStyle.secondary)
    async def reinstall_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (is_admin(interaction.user.id) or str(interaction.user) == self.owner_user_str):
            await interaction.response.send_message("❌ You don't have permission to manage this VPS.", ephemeral=True); return

        # Launch OS selection view
        view = ReinstallSelectView(self.container_id, self.owner_user_str)
        await interaction.response.send_message("Select the OS to reinstall with:", view=view, ephemeral=True)

class ReinstallSelectView(View):
    def __init__(self, container_id, owner_user_str):
        super().__init__(timeout=60)
        self.container_id = container_id
        self.owner_user_str = owner_user_str

        # using a select for OS choices
        options = [
            discord.SelectOption(label="Ubuntu 22.04", value="ubuntu"),
            discord.SelectOption(label="Debian 12", value="debian"),
            discord.SelectOption(label="Arch Linux", value="arch"),
            discord.SelectOption(label="Alpine", value="alpine"),
            discord.SelectOption(label="CentOS 7", value="centos7"),
            discord.SelectOption(label="Fedora 38", value="fedora38"),
        ]
        select = Select(placeholder="Choose OS to reinstall", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=True)
        # perform reinstall: read record, remove container, create new with same specs, run tmate, update db
        rec = get_container_record(self.container_id)
        if not rec:
            await interaction.followup.send("❌ Container record not found in database.", ephemeral=True)
            return

        # rec fields: user|container|ssh|ram|cpu|creator|os|expiry
        user = rec[0]
        ram = rec[3] if len(rec) > 3 else "2"
        cpu = rec[4] if len(rec) > 4 else "1"
        expiry = rec[7] if len(rec) > 7 else None

        image = get_docker_image_for_os(selected)

        try:
            # stop & rm old container
            subprocess.run(["docker", "stop", self.container_id], check=False, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "rm", self.container_id], check=False, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        # create new container with same name and resources
        try:
            subprocess.check_output([
                "docker", "run", "-itd", "--privileged", "--cap-add=ALL",
                f"--memory={ram}g", f"--cpus={cpu}", "--name", self.container_id, image
            ])
        except subprocess.CalledProcessError as e:
            await interaction.followup.send(f"❌ Failed to create container: {e}", ephemeral=True)
            return

        # run tmate and capture ssh
        ssh_line = await run_tmate_and_get_ssh(self.container_id, timeout=30)
        if ssh_line:
            update_ssh_in_db(self.container_id, ssh_line)
            # DM the owner
            try:
                discord_user = await bot.fetch_user(int(user.split('#')[0]) if '#' in user else int(user) )
            except Exception:
                discord_user = None
            if discord_user:
                try:
                    dm = discord.Embed(title="🔁 Reinstall Complete", description=f"Your VPS `{self.container_id}` has been reinstalled with `{selected}`.", color=0x2400ff)
                    dm.add_field(name="🔑 SSH", value=f"```{ssh_line}```", inline=False)
                    await discord_user.send(embed=dm)
                except discord.Forbidden:
                    pass
            await interaction.followup.send(f"✅ Reinstalled `{self.container_id}` with `{selected}`. New SSH sent via DM if possible.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Reinstall succeeded but failed to get SSH session. Check container logs.", ephemeral=True)

# -------------------------
# /manage command
# -------------------------
@bot.tree.command(name="manage", description="🧩 Open management panel for a VPS (use container id/name)")
@app_commands.describe(container_id="Docker container name (container id)")
async def manage(interaction: discord.Interaction, container_id: str):
    rec = get_container_record(container_id)
    if not rec:
        await interaction.response.send_message("❌ Container not found in database.", ephemeral=True)
        return

    owner_user = rec[0]
    # permission check: user may manage own VPS, admins can manage any
    if not (is_admin(interaction.user.id) or str(interaction.user) == owner_user or interaction.user.id == int(owner_user) if owner_user.isdigit() else False):
        await interaction.response.send_message("❌ You don't have permission to manage this VPS.", ephemeral=True)
        return

    # build embed
    # rec format: user|container|ssh|ram|cpu|creator|os|expiry
    _, cid, ssh, ram, cpu, creator, os_type, expiry = (rec + [""] * 8)[:8]
    status = get_container_status(cid)
    embed = discord.Embed(title=f"VPS Management — {cid}", color=0x00aaff)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="RAM", value=f"{ram} GB", inline=True)
    embed.add_field(name="CPU", value=f"{cpu} cores", inline=True)
    embed.add_field(name="OS", value=os_type, inline=True)
    embed.add_field(name="Owner", value=owner_user, inline=True)
    embed.add_field(name="Expires", value=expiry or "None", inline=True)
    embed.set_footer(text="Use the buttons below to manage this VPS")

    view = ManageView(container_id, owner_user)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# -------------------------
# /regen-ssh by container id (new)
# -------------------------
@bot.tree.command(name="regen-ssh", description="🔄 Regenerate SSH session for a container (by container_id)")
@app_commands.describe(container_id="Docker container name")
async def regen_ssh_cmd(interaction: discord.Interaction, container_id: str):
    rec = get_container_record(container_id)
    if not rec:
        await interaction.response.send_message("❌ Container not found in database.", ephemeral=True)
        return

    owner_user = rec[0]
    # permission check
    if not (is_admin(interaction.user.id) or str(interaction.user) == owner_user or interaction.user.id == int(owner_user) if owner_user.isdigit() else False):
        await interaction.response.send_message("❌ You don't have permission to regenerate SSH for this VPS.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    ssh_line = await run_tmate_and_get_ssh(container_id, timeout=30)
    if ssh_line:
        update_ssh_in_db(container_id, ssh_line)
        # DM owner
        try:
            # owner_user may be a mention or an ID or string; try to fetch
            target = None
            if owner_user.isdigit():
                target = await bot.fetch_user(int(owner_user))
            else:
                # owner_user currently stored as str(interaction.user) for many cases, which includes '#'
                # we will DM the current requester as fallback if we can't parse owner_user
                try:
                    target = await bot.fetch_user(int(owner_user.split('#')[0]))
                except Exception:
                    target = None
            if not target:
                # fallback — send to the user who invoked
                target = interaction.user
            dm = discord.Embed(title="🔄 New SSH Session Generated", description="A new SSH session (tmate) has been created for your VPS.", color=0x2400ff)
            dm.add_field(name="🔑 SSH", value=f"```{ssh_line}```", inline=False)
            await target.send(embed=dm)
        except discord.Forbidden:
            # can't DM
            pass
        await interaction.followup.send("✅ New SSH session generated and sent via DM (if possible).", ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to generate new SSH session.", ephemeral=True)

# -------------------------
# Existing deploy & other admin commands (kept, simplified)
# -------------------------
@bot.tree.command(name="deploy", description="🚀 Admin: Deploy a new VPS instance")
@app_commands.describe(ram="RAM in GB", cpu="CPU cores", target_user="Discord user ID to assign the VPS to", container_name="Optional container name", expiry="Expiry e.g. 1d, 1M")
async def deploy(interaction: discord.Interaction, ram: int = 2, cpu: int = 1, target_user: str = None, container_name: str = None, expiry: str = None):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ Access Denied", ephemeral=True)
        return

    if ram > 100: ram = 100
    if cpu > 24: cpu = 24

    user_id = target_user if target_user else str(interaction.user.id)
    user_str = target_user if target_user else str(interaction.user)

    if not container_name:
        container_name = f"VPS_{interaction.user.name}_{generate_random_string(6)}"

    expiry_seconds = parse_time_to_seconds(expiry)
    expiry_date = format_expiry_date(expiry_seconds) if expiry_seconds else None

    # ask for OS via Select
    async def os_callback(inter, selected_os):
        await deploy_with_os(inter, selected_os, ram, cpu, user_id, user_str, container_name, expiry_date)

    view = View(timeout=60)
    select = Select(placeholder="Select OS", options=[
        discord.SelectOption(label="Ubuntu 22.04", value="ubuntu"),
        discord.SelectOption(label="Debian 12", value="debian")
    ])
    async def sel_cb(i):
        await os_callback(i, i.data["values"][0])
    select.callback = sel_cb
    view.add_item(select)
    await interaction.response.send_message("Select OS for new VPS:", view=view)

async def deploy_with_os(interaction, os_type, ram, cpu, user_id, user_str, container_name, expiry_date):
    await interaction.followup.send(f"Creating container `{container_name}`...", ephemeral=True)
    image = get_docker_image_for_os(os_type)
    try:
        subprocess.check_output([
            "docker", "run", "-itd", "--privileged", "--cap-add=ALL",
            f"--memory={ram}g", f"--cpus={cpu}",
            "--name", container_name, image
        ])
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f"❌ Error creating container: {e}", ephemeral=True)
        return

    ssh_line = await run_tmate_and_get_ssh(container_name, timeout=30)
    if ssh_line:
        add_to_database(user_id, container_name, ssh_line, ram_limit=str(ram), cpu_limit=str(cpu), creator=str(interaction.user), expiry=expiry_date, os_type=os_type)
        # DM the user
        try:
            target_user_obj = await bot.fetch_user(int(user_id))
        except Exception:
            target_user_obj = None
        if target_user_obj:
            dm = discord.Embed(title="✅ VPS Created", description=f"Your VPS `{container_name}` is ready.", color=0x2400ff)
            dm.add_field(name="🔑 SSH", value=f"```{ssh_line}```", inline=False)
            dm.add_field(name="RAM", value=f"{ram}GB", inline=True)
            dm.add_field(name="CPU", value=f"{cpu} cores", inline=True)
            await target_user_obj.send(embed=dm)
            await interaction.followup.send(f"✅ VPS created for <@{user_id}>. DM sent.", ephemeral=True)
        else:
            await interaction.followup.send(f"✅ VPS created as `{container_name}`, but couldn't DM the user.", ephemeral=True)
    else:
        # cleanup
        subprocess.run(["docker", "stop", container_name], check=False)
        subprocess.run(["docker", "rm", container_name], check=False)
        await interaction.followup.send("❌ Failed to obtain SSH session from container. Cleanup done.", ephemeral=True)

# -------------------------
# Delete and delete-all
# -------------------------
@bot.tree.command(name="delete", description="🗑️ Delete your VPS instance")
@app_commands.describe(container_name="The name of your container")
async def delete_server(interaction: discord.Interaction, container_name: str):
    user = str(interaction.user)
    rec = get_container_record(container_name)
    if not rec:
        await interaction.response.send_message("❌ Not found.", ephemeral=True); return
    owner = rec[0]
    if not (is_admin(interaction.user.id) or owner == user or (owner.isdigit() and int(owner) == interaction.user.id)):
        await interaction.response.send_message("❌ You don't have permission to delete this VPS.", ephemeral=True); return

    # confirm quickly via ephemeral reply and then remove
    await interaction.response.send_message(f"Deleting `{container_name}`...", ephemeral=True)
    try:
        subprocess.run(["docker", "stop", container_name], check=False, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "rm", container_name], check=False, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    remove_from_database(container_name)
    await interaction.followup.send(f"✅ `{container_name}` deleted.", ephemeral=True)

@bot.tree.command(name="delete-all", description="🗑️ Admin: Delete all VPS instances")
async def delete_all_servers(interaction: discord.Interaction):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ Access Denied", ephemeral=True); return
    records = get_all_containers()
    await interaction.response.send_message(f"Deleting all {len(records)} containers...", ephemeral=True)
    deleted = 0
    for r in records:
        parts = r.split('|')
        if len(parts) >= 2:
            cid = parts[1]
            try:
                subprocess.run(["docker", "stop", cid], check=False, stderr=subprocess.DEVNULL)
                subprocess.run(["docker", "rm", cid], check=False, stderr=subprocess.DEVNULL)
                deleted += 1
            except Exception:
                pass
    # clear db
    open(database_file, 'w').close()
    await interaction.followup.send(f"✅ Deleted {deleted} containers.", ephemeral=True)

# -------------------------
# help (auto-updated)
# -------------------------
@bot.tree.command(name="help", description="❓ Shows the help message")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="VPS Bot Help", description="Available commands", color=0x00aaff)
    embed.add_field(name="User commands", value="/list, /vps_list, /manage <container_id>, /regen-ssh <container_id>, /delete <container_name>, /port-add, /port-http, /ping", inline=False)
    if interaction.user.id in ADMIN_IDS:
        embed.add_field(name="Admin commands", value="/deploy, /node, /delete-all", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------------
# Port forwarding commands (kept simple)
# -------------------------
@bot.tree.command(name="port-add", description="🔌 Adds a port forwarding rule")
@app_commands.describe(container_name="Container name", container_port="Port inside container")
async def port_add(interaction: discord.Interaction, container_name: str, container_port: int):
    await interaction.response.send_message("Setting up port forwarding (this will attempt to call ssh inside container)...", ephemeral=True)
    public_port = random.randint(1025, 65535)
    cmd = f"ssh -o StrictHostKeyChecking=no -R {public_port}:localhost:{container_port} serveo.net -N -f"
    try:
        await asyncio.create_subprocess_exec("docker", "exec", container_name, "bash", "-c", cmd)
        await interaction.followup.send(embed=discord.Embed(title="Port Forwarding", description=f"Host: {PUBLIC_IP}\nPort: {public_port}", color=0x2400ff), ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}", ephemeral=True)

@bot.tree.command(name="port-http", description="🌐 Forward HTTP traffic to your container")
@app_commands.describe(container_name="Container name", container_port="Port in container")
async def port_http(interaction: discord.Interaction, container_name: str, container_port: int):
    await interaction.response.send_message("Setting up HTTP forwarding...", ephemeral=True)
    try:
        proc = await asyncio.create_subprocess_exec("docker", "exec", container_name, "ssh", "-o", "StrictHostKeyChecking=no", "-R", f"80:localhost:{container_port}", "serveo.net", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        line = await asyncio.wait_for(_read_until(proc.stdout, b"Forwarding HTTP traffic from"), timeout=10)
        if line:
            text = line.decode().strip()
            url = text.split()[-1]
            await interaction.followup.send(embed=discord.Embed(title="HTTP Forwarding", description=f"URL: https://{url}", color=0x2400ff), ephemeral=True)
        else:
            await interaction.followup.send("Failed to get forwarding URL.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}", ephemeral=True)

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Please set the TOKEN variable in the script before running.")
    else:
        bot.run(TOKEN)
