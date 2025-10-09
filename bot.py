import discord
from discord.ext import commands
from discord import app_commands

TOKEN = ""
ADMIN_IDS = [1405778722732376176]     # your Discord user ID
CYAN = 0x00EEFF

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

# ----------------------------------------------------
# Events
# ----------------------------------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ----------------------------------------------------
# Utility commands
# ----------------------------------------------------
@bot.tree.command(name="ping", description="Check bot latency")
async def ping(inter: discord.Interaction):
    await inter.response.send_message(f"🏓 Pong! `{round(bot.latency*1000)} ms`")

@bot.tree.command(name="help", description="Show command list")
async def help_cmd(inter: discord.Interaction):
    cmds = [c.name for c in bot.tree.get_commands()]
    text = "**Available Commands:**\n" + ", ".join(f"`/{c}`" for c in cmds)
    await inter.response.send_message(text)

# ----------------------------------------------------
# Admin-only commands (placeholders)
# ----------------------------------------------------
@bot.tree.command(name="deploy", description="Admin: deploy a VPS (placeholder)")
async def deploy(inter: discord.Interaction, user: discord.User, os: str, ram: int, cpu: int):
    if not is_admin(inter.user.id):
        return await inter.response.send_message("❌ You don't have permission.", ephemeral=True)
    # TODO: insert your provisioning logic here (Docker, etc.)
    await inter.response.send_message(f"🪐 Would deploy {os} VPS for {user.mention} ({ram} GB, {cpu} core)")

@bot.tree.command(name="delete-user-container", description="Admin: delete a user container")
async def delete_user_container(inter: discord.Interaction, container_id: str):
    if not is_admin(inter.user.id):
        return await inter.response.send_message("❌ No permission", ephemeral=True)
    # TODO: add container delete logic
    await inter.response.send_message(f"Deleted container `{container_id}` (placeholder)")

@bot.tree.command(name="remove", description="Admin: force-remove a container")
async def remove(inter: discord.Interaction, container_id: str):
    if not is_admin(inter.user.id):
        return await inter.response.send_message("❌ No permission", ephemeral=True)
    # TODO: add docker rm -f logic
    await inter.response.send_message(f"Force-removed `{container_id}` (placeholder)")

@bot.tree.command(name="list-all", description="Admin: list all containers")
async def list_all(inter: discord.Interaction):
    if not is_admin(inter.user.id):
        return await inter.response.send_message("❌ No permission", ephemeral=True)
    # TODO: replace with real docker ps output
    await inter.response.send_message("📊 System Overview (placeholder)")

# ----------------------------------------------------
# User commands (placeholders)
# ----------------------------------------------------
@bot.tree.command(name="list", description="List your containers and host info")
async def list_cmd(inter: discord.Interaction):
    await inter.response.send_message("📋 Your VPS list (placeholder)")

@bot.tree.command(name="resources", description="Show container resource usage")
async def resources(inter: discord.Interaction):
    await inter.response.send_message("📈 Resources (placeholder)")

@bot.tree.command(name="restart", description="Restart a container")
async def restart(inter: discord.Interaction, container_id: str):
    await inter.response.send_message(f"Restarted `{container_id}` (placeholder)")

@bot.tree.command(name="start", description="Start a container")
async def start(inter: discord.Interaction, container_id: str):
    await inter.response.send_message(f"Started `{container_id}` (placeholder)")

@bot.tree.command(name="stop", description="Stop a container")
async def stop(inter: discord.Interaction, container_id: str):
    await inter.response.send_message(f"Stopped `{container_id}` (placeholder)")

@bot.tree.command(name="regen-ssh", description="Regenerate SSH/Tmate session")
async def regen_ssh(inter: discord.Interaction, container_id: str):
    await inter.response.send_message(f"Regenerated SSH for `{container_id}` (placeholder)")

@bot.tree.command(name="port-add", description="Map internal port to external port")
async def port_add(inter: discord.Interaction, container_name: str, container_port: str):
    await inter.response.send_message(f"Added port `{container_port}` for `{container_name}` (placeholder)")

@bot.tree.command(name="port-http", description="Expose container port via HTTP")
async def port_http(inter: discord.Interaction, container_name: str, container_port: str):
    await inter.response.send_message(f"HTTP-exposed `{container_port}` for `{container_name}` (placeholder)")

# ----------------------------------------------------
# Run
# ----------------------------------------------------
bot.run(TOKEN)
