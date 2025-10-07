import discord
from discord import app_commands
from discord.ext import commands
import subprocess, asyncio, os, random, string
from datetime import datetime, timedelta

# ======================================
# 🔧 CONFIGURATION
# ======================================
TOKEN = "YOUR_BOT_TOKEN_HERE"  # Paste your bot token here
ADMIN_IDS = [1405778722732376176]  # Replace with your Discord ID(s)
database_file = "database.txt"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)


# ======================================
# 🧩 HELPER FUNCTIONS
# ======================================
def generate_random_string(length=6):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def parse_time_to_seconds(time_str):
    if not time_str:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "M": 2592000, "y": 31536000}
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


def add_to_database(user, container_name, ssh_command, ram_limit, cpu_limit, creator, expiry, os_type):
    with open(database_file, "a") as f:
        f.write(f"{user}|{container_name}|{ssh_command}|{ram_limit}|{cpu_limit}|{creator}|{os_type}|{expiry}\n")


def remove_from_database(container_id):
    if not os.path.exists(database_file):
        return
    with open(database_file, "r") as f:
        lines = f.readlines()
    with open(database_file, "w") as f:
        for line in lines:
            if container_id not in line:
                f.write(line)


def get_all_containers():
    if not os.path.exists(database_file):
        return []
    with open(database_file, "r") as f:
        return [line.strip() for line in f.readlines()]


def get_system_stats():
    try:
        mem = subprocess.check_output(["free", "-m"]).decode().splitlines()[1].split()
        total_mem, used_mem = mem[1], mem[2]
        disk = subprocess.check_output(["df", "-h", "/"]).decode().splitlines()[1].split()
        total_disk, used_disk = disk[1], disk[2]
        return {"total_memory": f"{total_mem}MB", "used_memory": f"{used_mem}MB",
                "total_disk": total_disk, "used_disk": used_disk}
    except Exception:
        return {"total_memory": "N/A", "used_memory": "N/A", "total_disk": "N/A", "used_disk": "N/A"}


async def capture_ssh_session_line(process):
    while True:
        output = await process.stdout.readline()
        if not output:
            break
        line = output.decode("utf-8").strip()
        if "ssh session:" in line:
            return line.split("ssh session:")[1].strip()
    return None


def get_docker_image_for_os(os_type):
    return {"ubuntu": "ubuntu-with-tmate", "debian": "debian-with-tmate"}.get(os_type, "ubuntu-with-tmate")


def os_type_to_display_name(os_type):
    return {"ubuntu": "Ubuntu 22.04", "debian": "Debian 12"}.get(os_type, "Unknown OS")


def ensure_docker_image(os_type):
    image = get_docker_image_for_os(os_type)
    try:
        subprocess.run(["docker", "image", "inspect", image], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        base_image = "ubuntu:22.04" if "ubuntu" in os_type else "debian:12"
        dockerfile = f"FROM {base_image}\nRUN apt update && apt install -y tmate openssh-client sudo\nCMD ['/bin/bash']"
        with open("Dockerfile.tmp", "w") as f:
            f.write(dockerfile)
        subprocess.run(["docker", "build", "-t", image, "-f", "Dockerfile.tmp", "."], check=True)
        os.remove("Dockerfile.tmp")
    return image


# ======================================
# 🤖 DISCORD BOT EVENTS
# ======================================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()


# ======================================
# 🚀 BOT COMMANDS
# ======================================

@bot.tree.command(name="deploy", description="Deploy a new VPS for a user (Ubuntu/Debian)")
@app_commands.describe(user="Discord user ID", os="Operating system (ubuntu/debian)")
async def deploy(interaction: discord.Interaction, user: str, os: str):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
        return

    os = os.lower()
    if os not in ["ubuntu", "debian"]:
        await interaction.response.send_message("⚠️ OS must be ubuntu or debian.", ephemeral=True)
        return

    ram, cpu = 4, 2
    container_name = f"VPS_{generate_random_string(6)}"
    expiry_date = None

    await interaction.response.defer()
    image = ensure_docker_image(os)

    subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        container_id = subprocess.check_output([
            "docker", "run", "-itd",
            "--cap-add=NET_ADMIN",
            "--security-opt", "apparmor=unconfined",
            f"--memory={ram}g", f"--cpus={cpu}",
            "--hostname", "eaglenode",
            "--name", container_name, image
        ]).strip().decode()
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f"❌ Docker error: {e}")
        return

    exec_cmd = await asyncio.create_subprocess_exec("docker", "exec", container_name, "tmate", "-F",
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    ssh_line = await capture_ssh_session_line(exec_cmd)

    if ssh_line:
        add_to_database(user, container_name, ssh_line, ram, cpu, str(interaction.user), expiry_date, os_type_to_display_name(os))
        await interaction.followup.send(f"✅ VPS created for <@{user}> with OS **{os}**. SSH: `{ssh_line}`")
    else:
        subprocess.run(["docker", "rm", "-f", container_name])
        await interaction.followup.send("❌ Failed to initialize SSH session.")


@bot.tree.command(name="start", description="Start a container")
async def start(interaction: discord.Interaction, container_id: str):
    subprocess.run(["docker", "start", container_id])
    await interaction.response.send_message(f"▶️ Started `{container_id}`")


@bot.tree.command(name="stop", description="Stop a container")
async def stop(interaction: discord.Interaction, container_id: str):
    subprocess.run(["docker", "stop", container_id])
    await interaction.response.send_message(f"⏹️ Stopped `{container_id}`")


@bot.tree.command(name="restart", description="Restart a container")
async def restart(interaction: discord.Interaction, container_id: str):
    subprocess.run(["docker", "restart", container_id])
    await interaction.response.send_message(f"🔄 Restarted `{container_id}`")


@bot.tree.command(name="delete-user-container", description="Delete a container")
async def delete_container(interaction: discord.Interaction, container_id: str):
    subprocess.run(["docker", "rm", "-f", container_id])
    remove_from_database(container_id)
    await interaction.response.send_message(f"🗑️ Deleted `{container_id}`")


@bot.tree.command(name="list", description="List all containers")
async def list(interaction: discord.Interaction):
    containers = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Names}} | {{.Status}}"]).decode().splitlines()
    await interaction.response.send_message("📋 Containers:\n````" + "\n".join(containers) + "```")


@bot.tree.command(name="resources", description="Show system resources")
async def resources(interaction: discord.Interaction):
    stats = get_system_stats()
    await interaction.response.send_message(f"💾 RAM: {stats['used_memory']} / {stats['total_memory']}\n💽 Disk: {stats['used_disk']} / {stats['total_disk']}")


@bot.tree.command(name="ping", description="Check latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! {latency}ms")


bot.run(TOKEN)
