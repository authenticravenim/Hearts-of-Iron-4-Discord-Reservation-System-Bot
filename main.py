import discord
from discord.ext import commands, tasks
import json
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# -------------------------
# CONFIGURATION
# -------------------------

COUNTRY_FILE = "reservation_countries.json"
RESERVATION_FILE = "reservations.json"
CONFIG_FILE = "config.json"
ALL_TAGS_FILE = "all_tags.json"

CHANNEL_ID = 1440496073377579120      # Reservation channel
LOG_CHANNEL_ID = 1440253011678199882  # Log channel

DELETE_DELAY = 5  # Seconds before deleting user message

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# TIMEZONE MAP
# -------------------------

TZ_CODE_MAP = {
    "UTC": "UTC",
    "GMT": "Etc/UTC",
    "BST": "Europe/London",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",
    "EET": "Europe/Helsinki",
    "EEST": "Europe/Helsinki",
    "MSK": "Europe/Moscow",
    "IST": "Asia/Kolkata",
    "JST": "Asia/Tokyo",
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
}

# -------------------------
# LOAD TOKEN
# -------------------------

TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise RuntimeError("BOT_TOKEN environment variable not set!")

# -------------------------
# JSON LOADING
# -------------------------

def load_json(fp, default):
    if not os.path.exists(fp) or os.path.getsize(fp) == 0:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default

reservations = load_json(RESERVATION_FILE, {})
config = load_json(CONFIG_FILE, {})
countries = load_json(COUNTRY_FILE, {})
all_tags = load_json(ALL_TAGS_FILE, {})

def save_reservations():
    with open(RESERVATION_FILE, "w", encoding="utf-8") as f:
        json.dump(reservations, f, indent=4, ensure_ascii=False)

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# -------------------------
# NAME RESOLUTION
# -------------------------

name_index = {}

def _normalize(s: str) -> str:
    s = s.strip().lower()
    return re.sub(r"\s+", " ", s)

def _add_name(tag, name):
    if not name:
        return
    norm = _normalize(name)
    if norm not in name_index:
        name_index[norm] = set()
    name_index[norm].add(tag)

def build_name_index():
    name_index.clear()
    for tag, data in countries.items():
        _add_name(tag, data.get("name", ""))
    for tag, data in all_tags.items():
        if tag not in countries:
            continue
        _add_name(tag, data.get("democratic", ""))
        _add_name(tag, data.get("neutral", ""))

    aliases = {
        "uk": "ENG",
        "england": "ENG",
        "britain": "ENG",
        "usa": "USA",
        "united states": "USA",
        "united states of america": "USA",
    }
    for name, tag in aliases.items():
        if tag in countries:
            _add_name(tag, name)

build_name_index()

def resolve_country_input(inp: str):
    if not inp:
        return None, "not_found", None

    raw = inp.strip()
    up = raw.upper()
    norm = _normalize(raw)

    if up in countries:
        return up, None, None

    if norm in name_index:
        tags = list(name_index[norm])
        if len(tags) == 1:
            return tags[0], None, None
        return None, "ambiguous", tags

    possible = set()
    for name_str, tags in name_index.items():
        if norm in name_str:
            possible.update(tags)

    if len(possible) == 1:
        return list(possible)[0], None, None
    elif len(possible) > 1:
        return None, "ambiguous", list(possible)
    else:
        return None, "not_found", None

def pretty(tag):
    return f"{tag} — {countries[tag]['name']}"

# -------------------------
# LOGGING
# -------------------------

async def log_action(text):
    chan = bot.get_channel(LOG_CHANNEL_ID)
    if chan:
        try:
            await chan.send(text)
        except:
            pass

# -------------------------
# EMBED
# -------------------------

def build_embed():
    locked = config.get("locked", False)
    status = "🔒 **Signups Locked**" if locked else "🔓 **Signups Open**"

    reset_time = config.get("reset_time")
    reset_tz = config.get("reset_tz_code")
    if reset_time and reset_tz:
        reset_line = f"• Reset at **{reset_time} {reset_tz}**"
    else:
        reset_line = "• Reset time not configured"

    embed = discord.Embed(
        title="🌍 Country Reservations",
        description=(
            f"{status}\n\n"
            "Type a country name or tag.\n"
            "All messages auto-delete after 5 seconds.\n\n"
            f"{reset_line}"
        ),
        color=0x2b2d31
    )

    regions = ["Europe", "Asia", "MEA", "NA", "SA"]
    for region in regions:
        lines = []
        for tag, data in countries.items():
            if data["region"] != region:
                continue
            flag = data["flag"]
            name = data["name"]
            if tag in reservations:
                uid = reservations[tag]
                lines.append(f"**{flag} {tag} — {name}** — <@{uid}>")
            else:
                lines.append(f"**{flag} {tag} — {name}** — *Unclaimed*")
        embed.add_field(name=f"__{region}__", value="\n".join(lines), inline=False)

    return embed

async def update_embed():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("Reservation channel missing.")
        return

    msg_id = config.get("embed_message_id")
    if msg_id:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=build_embed())
            return
        except:
            pass

    msg = await channel.send(embed=build_embed())
    config["embed_message_id"] = msg.id
    save_config()

# -------------------------
# BOT READY
# -------------------------

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    await update_embed()
    reset_watcher.start()

# -------------------------
# DAILY RESET
# -------------------------

def get_next_reset_info():
    rt = config.get("reset_time")
    tz = config.get("reset_tz")
    if not rt or not tz:
        return False, None
    try:
        h, m = rt.split(":")
        h = int(h); m = int(m)
    except:
        return False, None
    try:
        zone = ZoneInfo(tz)
    except:
        return False, None

    now = datetime.now(timezone.utc).astimezone(zone)
    today = now.date().isoformat()
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)

    last = config.get("last_reset_date")

    if last != today and now >= target:
        return True, today
    return False, today

@tasks.loop(minutes=1)
async def reset_watcher():
    do_reset, today = get_next_reset_info()
    if not do_reset:
        return

    reservations.clear()
    save_reservations()
    await update_embed()
    await log_action("🗑️ Daily reset complete.")

    config["last_reset_date"] = today
    save_config()

@reset_watcher.before_loop
async def before_reset():
    await bot.wait_until_ready()

# -------------------------
# RESERVATION & RELEASE (SILENT MODE)
# -------------------------

async def handle_reserve(message, text):
    tag, err, extra = resolve_country_input(text)

    if tag is None:
        # SILENT MODE: no reply
        return

    if config.get("locked", False):
        return

    # Check if user already has one
    current = None
    for t, uid in reservations.items():
        if uid == message.author.id:
            current = t
            break

    # Swap blocked if target is taken
    if current and current != tag:
        if tag in reservations and reservations[tag] != message.author.id:
            return
        del reservations[current]
        reservations[tag] = message.author.id
        save_reservations()
        await update_embed()
        await log_action(f"🔄 {message.author} swapped {pretty(current)} → {pretty(tag)}")
        return

    # If someone else owns it
    if tag in reservations and reservations[tag] != message.author.id:
        return

    # Fresh claim
    reservations[tag] = message.author.id
    save_reservations()
    await update_embed()
    await log_action(f"🟢 {message.author} reserved **{pretty(tag)}**")

async def handle_release(message, text):
    tag, err, extra = resolve_country_input(text)

    if tag is None:
        return

    if tag not in reservations:
        return

    if reservations[tag] != message.author.id:
        return

    del reservations[tag]
    save_reservations()
    await update_embed()
    await log_action(f"⚪ {message.author} released **{pretty(tag)}**")

# -------------------------
# MESSAGE HANDLER (FULL SILENT MODE)
# -------------------------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    raw = message.content.strip()
    if not raw:
        return

    upper = raw.upper()
    in_res = (message.channel.id == CHANNEL_ID)

    # RESERVE
    if upper.startswith("RESERVE "):
        await handle_reserve(message, raw[8:].strip())
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    # RELEASE
    if upper.startswith("RELEASE "):
        await handle_release(message, raw[8:].strip())
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    # BARE MESSAGE -> RESERVE ATTEMPT
    if in_res and not raw.startswith("!"):
        await handle_reserve(message, raw)
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    # ADMIN COMMANDS IN RESERVATION CHANNEL: delete them too
    if in_res and raw.startswith("!"):
        await bot.process_commands(message)
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    # Normal commands elsewhere
    await bot.process_commands(message)

# -------------------------
# ADMIN COMMANDS
# (Still functional, but silent in reservation channel)
# -------------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def lock(ctx):
    config["locked"] = True
    save_config()
    await update_embed()
    await log_action(f"🔒 Admin {ctx.author} locked signups.")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    config["locked"] = False
    save_config()
    await update_embed()
    await log_action(f"🔓 Admin {ctx.author} unlocked signups.")

@bot.command()
@commands.has_permissions(administrator=True)
async def force(ctx, tag, user: discord.Member):
    tag = tag.upper()
    if tag in countries:
        reservations[tag] = user.id
        save_reservations()
        await update_embed()
        await log_action(f"🛠️ Admin {ctx.author} forced {pretty(tag)} to {user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unassign(ctx, tag):
    tag = tag.upper()
    if tag in reservations:
        del reservations[tag]
        save_reservations()
        await update_embed()
        await log_action(f"🛠️ Admin {ctx.author} unassigned {pretty(tag)}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setreset(ctx, time_str, tz_code):
    try:
        h, m = time_str.split(":")
        int(h); int(m)
    except:
        return

    tz_code = tz_code.upper()
    if tz_code not in TZ_CODE_MAP:
        return

    config["reset_time"] = time_str
    config["reset_tz"] = TZ_CODE_MAP[tz_code]
    config["reset_tz_code"] = tz_code
    config["last_reset_date"] = None
    save_config()

    await update_embed()
    await log_action(f"⏰ Reset time set to {time_str} {tz_code}")

@bot.command()
async def timezones(ctx):
    lines = [f"**{c}** → `{TZ_CODE_MAP[c]}`" for c in sorted(TZ_CODE_MAP)]
    await ctx.reply("\n".join(lines))

# -------------------------
# RUN
# -------------------------

bot.run(TOKEN)
