import discord
from discord import app_commands
from discord.ext import commands
import subprocess, asyncio, os

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
ADMIN_ROLE_ID = 123456789012345678   # replace with your admin role id
EMBED_COLOR = 0x00AAFF

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------------------------------------------------
# Example helper stubs (replace with your own implementations)
# ------------------------------------------------------------------
OS_OPTIONS = {
    "ubuntu":  {"name": "Ubuntu",  "emoji": "🐧", "image": "ubuntu"},
    "debian":  {"name": "Debian",  "emoji": "📦", "image": "debian"},
    "alpine":  {"name": "Alpine",  "emoji": "🏔️", "image": "alpine"},
    "arch":    {"name": "Arch",    "emoji": "🌀", "image": "archlinux"},
    "kali":    {"name": "Kali",    "emoji": "💀", "image": "kalilinux/kali-rolling"},
    "fedora":  {"name": "Fedora",  "emoji": "🧢", "image": "fedora"},
}

async def is_admin_role_only(interaction: discord.Interaction) -> bool:
    role_ids = [r.id for r in interaction.user.roles]
    return ADMIN_ROLE_ID in role_ids

async def animate_message(title, embed, frames, loops):  # placeholder
    return
async def send_to_logs(msg):  # placeholder
    print(msg)
def add_to_database(user, container, ssh):  # placeholder
    pass
async def capture_ssh_session_line(proc):
    return "ssh user@123.45.67.89"

# ------------------------------------------------------------------
# /deploy  (updated)
# ------------------------------------------------------------------
@bot.tree.command(name="deploy", description="🚀 Deploy a VPS with custom specs.")
@app_commands.describe(
    user="The user to deploy for",
    os="Operating system (ubuntu, debian, alpine, arch, kali, fedora)",
    ram="RAM size in GB (e.g., 2, 4, 8)",
    cpu="CPU cores (e.g., 1, 2, 4)",
    disk="Disk size in GB (e.g., 20, 40, 100)"
)
async def deploy(interaction: discord.Interaction, user: discord.User,
                 os: str, ram: int, cpu: int, disk: int):

    if not await is_admin_role_only(interaction):
        await interaction.response.send_message(
            "🚫 Only admins can use this command.", ephemeral=True)
        return

    os = os.lower()
    if os not in OS_OPTIONS:
        await interaction.response.send_message(
            f"❌ Invalid OS. Available: {', '.join(OS_OPTIONS.keys())}",
            ephemeral=True)
        return

    os_data = OS_OPTIONS[os]
    embed = discord.Embed(
        title=f"Deploying {os_data['emoji']} {os_data['name']} for {user.display_name}",
        description=f"Specs → RAM {ram} GB | CPU {cpu} | Disk {disk} GB",
        color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)

    # --- simulate docker run ---
    await asyncio.sleep(2)
    container_id = os.urandom(6).hex()
    ssh_line = f"ssh root@{container_id}.example.net"

    add_to_database(str(user), container_id, ssh_line)
    success = discord.Embed(
        title="✅ VPS Ready!",
        description=f"**SSH:** `{ssh_line}`",
        color=0x00FF00)
    await interaction.followup.send(embed=success)
# ------------------------------------------------------------------
# Other commands (examples, keep yours)
# ------------------------------------------------------------------
@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Pong! {round(bot.latency*1000)} ms")

@bot.tree.command(name="help", description="Show all commands")
async def help_cmd(interaction: discord.Interaction):
    cmds = [
        "/deploy – Create VPS",
        "/list-all – List containers (admin)",
        "/delete-user-container – Remove container (admin)",
        "/list, /start, /stop, /restart, /remove, /regen-ssh, /resources, /ping"
    ]
    embed = discord.Embed(title="🤖 Bot Commands",
                          description="\n".join(cmds),
                          color=EMBED_COLOR)
    await interaction.response.send_message(embed=embed)

# ------------------------------------------------------------------
# Sync + run
# ------------------------------------------------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

bot.run(TOKEN)
