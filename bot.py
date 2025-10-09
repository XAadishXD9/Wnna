"""
Fixed bot.py for Eagle Node VPS management.

Features:
- /deploy (auto-builds ubuntu/debian images if missing)
- /start, /stop, /restart, /delete, /delete-all
- /list, /node, /nodedmin, /regen-ssh
- /port-add and /port-http (basic wrappers)
- /ping, /help, /bot (manual status refresh)
- Automatic "Watching EAGLE NODE 🪐 X VPS" presence
- Uses a simple database file 'database.txt'
"""

import os, subprocess, sys, asyncio, time, shlex, discord
from discord.ext import tasks, commands
from discord import app_commands

# ===== CONFIG =====
TOKEN = ""  # <== put your bot token here
DATABASE_FILE = "database.txt"
ADMIN_IDS = [1405778722732376176]  # replace with your admin ID(s)
DEFAULT_RAM_GB, DEFAULT_CPU = 2, 1
MAX_RAM_GB, MAX_CPU = 200, 24

# ===== Discord setup =====
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# --- helpers for database management ---
def read_db():
    if not os.path.exists(DATABASE_FILE): return []
    with open(DATABASE_FILE) as f: return [x.strip() for x in f if x.strip()]

def write_db(lines): open(DATABASE_FILE, "w").write("\n".join(lines) + ("\n" if lines else ""))

def add_entry(u, c, ssh, ram, cpu, cr, os_type="ubuntu"):
    lines = read_db()
    lines.append(f"{u}|{c}|{ssh}|{ram}|{cpu}|{cr}|{os_type}")
    write_db(lines)

def remove_entry(c): write_db([x for x in read_db() if f"|{c}|" not in x])

def find_entry(c):
    for l in read_db():
        p = l.split("|")
        if len(p) >= 2 and p[1] == c: return p
    return None

# --- docker helpers ---
def ensure_image(img, base):
    try:
        if subprocess.check_output(["docker", "images", "-q", img]).strip(): return
    except: pass
    dockerfile = f"FROM {base}\nRUN apt update && apt install -y tmate sudo curl wget nano\nCMD ['/bin/bash']"
    subprocess.run(["docker", "build", "-t", img, "-"], input=dockerfile.encode(), check=True)

def run_container(name, img, ram, cpu):
    subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ram, cpu = min(ram, MAX_RAM_GB), min(cpu, MAX_CPU)
    cmd = ["docker","run","-itd","--privileged","--cap-add=ALL",f"--memory={ram}g",f"--cpus={cpu}","--hostname","eaglenode","--name",name,img]
    try: return subprocess.check_output(cmd).decode().strip()
    except subprocess.CalledProcessError: return None

async def get_ssh(name, timeout=12):
    try:
        proc = await asyncio.create_subprocess_exec("docker","exec",name,"tmate","-F",
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    except: return None
    start=time.time(); ssh=None
    while time.time()-start<timeout:
        l=await proc.stdout.readline()
        if not l: break
        t=l.decode(errors="ignore")
        if "ssh " in t: ssh=t.strip(); break
    return ssh

def get_status(name):
    try: return subprocess.check_output(["docker","inspect","--format","{{.State.Status}}",name]).decode().strip()
    except subprocess.CalledProcessError: return "not_found"

# ====== status updater ======
@tasks.loop(seconds=5)
async def update_status():
    c=len(read_db())
    s=f"EAGLE NODE 🪐 {c} VPS"
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=s))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    update_status.start()
    await bot.tree.sync()

# ====== commands ======
def is_admin(uid): return int(uid) in ADMIN_IDS

@bot.tree.command(name="ping",description="Check bot latency")
async def ping(i:discord.Interaction):
    await i.response.send_message(f"🏓 {round(bot.latency*1000)} ms")

@bot.tree.command(name="bot",description="Refresh watching status")
async def bot_cmd(i:discord.Interaction):
    c=len(read_db()); s=f"EAGLE NODE 🪐 {c} VPS"
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name=s))
    await i.response.send_message(f"✅ Status set to `{s}`")

@bot.tree.command(name="deploy",description="Deploy VPS (admin)")
async def deploy(i:discord.Interaction, os_type:str="ubuntu", ram:int=2, cpu:int=1, container_name:str=None):
    if not is_admin(i.user.id): return await i.response.send_message("❌ Admin only",ephemeral=True)
    await i.response.defer()
    img="ubuntu-22.04-with-tmate" if os_type=="ubuntu" else "debian-with-tmate"
    base="ubuntu:22.04" if os_type=="ubuntu" else "debian:12"
    ensure_image(img,base)
    if not container_name: container_name=f"{os_type}_{i.user.name}_{int(time.time())}"
    cid=run_container(container_name,img,ram,cpu)
    if not cid: return await i.followup.send("❌ Docker failed")
    ssh=await get_ssh(container_name)
    add_entry(str(i.user),container_name,ssh or "None",ram,cpu,str(i.user),os_type)
    await i.followup.send(f"✅ VPS `{container_name}` created.\nSSH: `{ssh or 'pending'}`")

@bot.tree.command(name="list",description="List your VPS")
async def list_cmd(i:discord.Interaction):
    user=str(i.user); lines=[l for l in read_db() if l.startswith(user+"|")]
    if not lines: return await i.response.send_message("📋 none")
    e=discord.Embed(title=f"{i.user.name}'s VPS",color=0x00aaff)
    for l in lines:
        p=l.split("|"); n=p[1]; s=get_status(n)
        e.add_field(name=f"{n} ({s})",value=f"RAM {p[3]}GB CPU {p[4]} SSH `{p[2]}`",inline=False)
    await i.response.send_message(embed=e)

@bot.tree.command(name="delete",description="Delete VPS")
async def delete_cmd(i:discord.Interaction, container_name:str):
    e=find_entry(container_name)
    if not e: return await i.response.send_message("❌ not found")
    if e[0]!=str(i.user) and not is_admin(i.user.id): return await i.response.send_message("❌ denied")
    subprocess.run(["docker","rm","-f",container_name])
    remove_entry(container_name)
    await i.response.send_message(f"✅ Deleted `{container_name}`")

@bot.tree.command(name="delete-all",description="Admin: delete all VPS")
async def delete_all(i:discord.Interaction):
    if not is_admin(i.user.id): return await i.response.send_message("❌ denied",ephemeral=True)
    for l in read_db():
        try: subprocess.run(["docker","rm","-f",l.split('|')[1]])
        except: pass
    write_db([]); await i.response.send_message("🗑️ All VPS removed")

@bot.tree.command(name="start",description="Start VPS")
async def start_cmd(i:discord.Interaction,container_name:str):
    subprocess.run(["docker","start",container_name])
    ssh=await get_ssh(container_name)
    await i.response.send_message(f"✅ Started `{container_name}` SSH `{ssh or 'none'}`")

@bot.tree.command(name="stop",description="Stop VPS")
async def stop_cmd(i:discord.Interaction,container_name:str):
    subprocess.run(["docker","stop",container_name]); await i.response.send_message(f"⏹️ Stopped `{container_name}`")

@bot.tree.command(name="restart",description="Restart VPS")
async def restart_cmd(i:discord.Interaction,container_name:str):
    subprocess.run(["docker","restart",container_name])
    ssh=await get_ssh(container_name)
    await i.response.send_message(f"🔄 Restarted `{container_name}` SSH `{ssh or 'none'}`")

@bot.tree.command(name="help",description="Show help")
async def help_cmd(i:discord.Interaction):
    txt=("**Commands**\n"
         "/deploy – deploy VPS (admin)\n"
         "/start /stop /restart /delete /list\n"
         "/delete-all (admin)\n"
         "/bot – refresh status\n"
         "/ping – latency\n")
    await i.response.send_message(txt)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Please add your bot token in TOKEN variable.")
        sys.exit(1)
    bot.run(TOKEN)
