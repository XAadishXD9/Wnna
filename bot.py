import discord
from discord.ext import commands, tasks
from discord import app_commands
import subprocess, os, asyncio, random, string
from datetime import datetime, timedelta
from typing import Literal

# ---------------- CONFIG ----------------
TOKEN = ""  # 🔐 Your Discord bot token here
ADMIN_IDS = [1405778722732376176]  # Replace with your Discord user ID(s)
database_file = "database.txt"
# ----------------------------------------

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------- Helpers ----------
def is_admin(user_id): return user_id in ADMIN_IDS
def randstr(n=6): return ''.join(random.choices(string.ascii_letters + string.digits, k=n))
def os_name(t): return {"ubuntu": "Ubuntu 22.04", "debian": "Debian 12"}.get(t, "Unknown")
def docker_image(t): return {"ubuntu": "ubuntu-22.04-with-tmate", "debian": "debian-with-tmate"}.get(t, "ubuntu-22.04-with-tmate")

def parse_time(s):
    if not s: return None
    m = {"s": 1, "m": 60, "h": 3600, "d": 86400, "M": 2592000, "y": 31536000}
    u = s[-1]; n = s[:-1]
    if u in m and n.isdigit(): return int(n) * m[u]
    if s.isdigit(): return int(s) * 86400
    return None

def expiry_fmt(sec):
    if not sec: return None
    return (datetime.now() + timedelta(seconds=sec)).strftime("%Y-%m-%d %H:%M:%S")

async def capture_tmate(proc):
    while True:
        l = await proc.stdout.readline()
        if not l: break
        l = l.decode().strip()
        if "ssh session:" in l: return l.split("ssh session:")[1].strip()
    return None

def save_db(u, c, s, ram, cpu, creator, exp, os):
    with open(database_file, "a") as f:
        f.write(f"{u}|{c}|{s}|{ram}|{cpu}|{creator}|{os}|{exp or 'None'}\n")

def all_db():
    return open(database_file).read().splitlines() if os.path.exists(database_file) else []

# ---------- Status ----------
@bot.event
async def on_ready():
    print(f"🚀 Logged in as {bot.user}")
    change_status.start()
    await bot.tree.sync()

@tasks.loop(seconds=5)
async def change_status():
    try:
        c = len(all_db())
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"🪐 EAGLE NODE {c} VPS"))
    except Exception as e:
        print("Status error:", e)

# ---------- Commands ----------

@bot.tree.command(name="deploy", description="🚀 Admin: Deploy a VPS")
@app_commands.describe(user="User", os="ubuntu or debian", ram="RAM in GB", cpu="CPU cores", expiry="e.g. 1d,7d")
async def deploy(inter, user: discord.User, os: Literal["ubuntu", "debian"], ram: int, cpu: int, expiry: str = None):
    if not is_admin(inter.user.id):
        return await inter.response.send_message("❌ No permission", ephemeral=True)

    ram = min(ram, 200)
    cpu = min(cpu, 100)
    secs = parse_time(expiry)
    exp = expiry_fmt(secs)
    cname = f"VPS_{user.name}_{randstr()}"
    img = docker_image(os)

    emb = discord.Embed(title="⚙️ Creating VPS",
        description=f"👤 {user.mention}\n🐧 {os_name(os)}\n💾 {ram} GB RAM  🔥{cpu} CPU\n⌚ Expiry {exp or 'None'}",
        color=0x2400ff)
    await inter.response.send_message(embed=emb)

    try:
        docker_cmd = [
            "docker", "run", "-itd",
            "--privileged", "--cap-add=ALL",
            f"--memory={ram}g",
            "--hostname", "eaglenode",
            "--name", cname
        ]
        # 🧩 Debian-safe CPU fix
        if os == "debian":
            docker_cmd += [f"--cpuset-cpus=0-{max(cpu - 1, 0)}", img, "bash", "-c", "tmate -F || bash"]
        else:
            docker_cmd += [f"--cpus={cpu}", img, "bash", "-c", "tmate -F || bash"]

        try:
            cid = subprocess.check_output(docker_cmd, stderr=subprocess.STDOUT).decode().strip()
        except subprocess.CalledProcessError:
            print("⚠️ Docker run failed, retrying without CPU/memory limits...")
            docker_cmd = [
                "docker", "run", "-itd",
                "--privileged", "--cap-add=ALL",
                "--hostname", "eaglenode",
                "--name", cname,
                img, "bash", "-c", "tmate -F || bash"
            ]
            cid = subprocess.check_output(docker_cmd, stderr=subprocess.STDOUT).decode().strip()

        proc = await asyncio.create_subprocess_exec("docker", "exec", cname, "tmate", "-F",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        ssh = await capture_tmate(proc)
        if not ssh: raise Exception("SSH not generated")

        save_db(str(user), cname, ssh, ram, cpu, str(inter.user), exp, os_name(os))
        dm = discord.Embed(title="✅ VPS Ready", description="Your VPS details:", color=0x2400ff)
        dm.add_field(name="💾 RAM", value=f"{ram} GB")
        dm.add_field(name="🔥 CPU", value=f"{cpu}")
        dm.add_field(name="🐧 OS", value=os_name(os))
        dm.add_field(name="🔑 SSH", value=f"```{ssh}```", inline=False)
        dm.add_field(name="💠 Container", value=cname, inline=False)
        dm.set_footer(text="🔒 Powered by EAGLE NODE")
        try:
            await user.send(embed=dm)
        except:
            await inter.followup.send(f"⚠️ DM closed for {user.mention}")
        await inter.followup.send(f"🎉 VPS created for {user.mention}")

    except Exception as e:
        await inter.followup.send(f"❌ Error: {e}")

# --- User Commands ---
@bot.tree.command(name="list", description="📋 List your VPS and system health")
async def list_vps(inter):
    user = str(inter.user)
    lines = [l for l in all_db() if l.startswith(user)]
    cpu_usage = subprocess.getoutput("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'")
    mem_total = subprocess.getoutput("free -h | awk '/Mem:/ {print $2}'")
    mem_used = subprocess.getoutput("free -h | awk '/Mem:/ {print $3}'")
    disk_usage = subprocess.getoutput("df -h / | awk 'NR==2 {print $3\" / \"$2}'")
    cpu = float(cpu_usage) if cpu_usage else 0
    health = "🌟 Excellent system health!" if cpu < 70 else "⚠️ Moderate load" if cpu < 90 else "🚨 High CPU usage!"
    embed = discord.Embed(title="📊 Host System Resources", color=0x00ff88)
    embed.add_field(name="🟢 CPU Usage", value=f"`{cpu_usage.strip()} %`", inline=False)
    embed.add_field(name="🟢 Memory", value=f"`{mem_used} / {mem_total}`", inline=False)
    embed.add_field(name="🟢 Disk Space", value=f"`{disk_usage.strip()}`", inline=False)
    embed.add_field(name="System Health", value=health, inline=False)
    if not lines:
        embed.add_field(name="💾 Your VPS", value="You have no VPS yet.")
    else:
        msg = "\n".join([f"• {l.split('|')[1]} ({l.split('|')[6]})" for l in lines])
        embed.add_field(name="💾 Your VPS", value=msg, inline=False)
    await inter.response.send_message(embed=embed)

@bot.tree.command(name="port-add", description="🔌 Map your container port to a random host port")
async def port_add(inter, container_name: str, container_port: int):
    try:
        result = subprocess.getoutput(f"docker port {container_name} {container_port}")
        if result.strip():
            return await inter.response.send_message(f"⚠️ Port {container_port} already mapped:\n```{result}```")
        random_port = random.randint(10000, 65000)
        subprocess.run(["docker", "container", "update", "--publish-add", f"{random_port}:{container_port}", container_name], check=True)
        await inter.response.send_message(f"✅ Port {container_port} added → Host Port `{random_port}`")
    except Exception as e:
        await inter.response.send_message(f"❌ Error: {e}")

@bot.tree.command(name="port-http", description="🌐 Expose your container HTTP port")
async def port_http(inter, container_name: str, container_port: int):
    try:
        subprocess.run(["docker", "container", "update", "--publish-add", f"0.0.0.0:{container_port}:{container_port}", container_name], check=True)
        ip = subprocess.getoutput("hostname -I | awk '{print $1}'")
        await inter.response.send_message(f"🌐 HTTP port exposed: http://{ip}:{container_port}")
    except Exception as e:
        await inter.response.send_message(f"❌ Error: {e}")

@bot.tree.command(name="resources", description="📈 Show resource usage")
async def resources(inter):
    usage = subprocess.getoutput("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'")
    await inter.response.send_message(f"```\n{usage}\n```")

@bot.tree.command(name="ping", description="🏓 Ping latency")
async def ping(inter):
    await inter.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)} ms")

@bot.tree.command(name="help", description="🆘 Show commands")
async def help_cmd(inter):
    cmds = [c.name for c in bot.tree.get_commands()]
    await inter.response.send_message("**Available Commands:**\n" + ", ".join(f"`/{c}`" for c in cmds))

# ---------- Run ----------
bot.run(TOKEN)
