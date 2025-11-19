# ============================================
# HOI4 RESERVATION BOT (FINAL VERSION)
# Silent Mode + Auto-Delete + Daily Reset + One-Time Reset
# MUTUAL EXCLUSIVITY PATCH FULLY APPLIED
# Optional Startup Reset Enabled by Default
# Wispbyte-Compatible (.env)
# ============================================

import discord
from discord.ext import commands, tasks
import json
import os
import re
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Load .env
load_dotenv()


# ==============================================================
# FILE PATHS
# ==============================================================

COUNTRY_FILE = "reservation_countries.json"
RESERVATION_FILE = "reservations.json"
CONFIG_FILE = "config.json"
ALL_TAGS_FILE = "all_tags.json"

CHANNEL_ID = 1440496073377579120       # Reservation channel
LOG_CHANNEL_ID = 1440253011678199882   # Log channel
DELETE_DELAY = 5


# ==============================================================
# DISCORD SETUP
# ==============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ==============================================================
# TIMEZONE MAP
# ==============================================================

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


# ==============================================================
# TOKEN LOAD
# ==============================================================

TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise RuntimeError("BOT_TOKEN missing in .env")


# ==============================================================
# JSON LOAD/SAVE HELPERS
# ==============================================================

def load_json(fp, default):
    if not os.path.exists(fp) or os.path.getsize(fp) == 0:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default


reservations = load_json(RESERVATION_FILE, {})
config = load_json(CONFIG_FILE, {})
countries = load_json(COUNTRY_FILE, {})
all_tags = load_json(ALL_TAGS_FILE, {})

# Create startup reset flag if missing
if "startup_reset" not in config:
    config["startup_reset"] = True


def save_reservations():
    with open(RESERVATION_FILE, "w", encoding="utf-8") as f:
        json.dump(reservations, f, indent=4)


def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


# ==============================================================
# NAME RESOLUTION
# ==============================================================

name_index = {}

def _normalize(s):
    s = s.strip().lower()
    return re.sub(r"\s+", " ", s)

def _add_name(tag, name):
    if name:
        name_index.setdefault(_normalize(name), set()).add(tag)

def build_name_index():
    name_index.clear()
    for tag, data in countries.items():
        _add_name(tag, data.get("name", ""))

    for tag, data in all_tags.items():
        if tag in countries:
            _add_name(tag, data.get("democratic"))
            _add_name(tag, data.get("neutral"))

    aliases = {
        "uk": "ENG",
        "england": "ENG",
        "britain": "ENG",
        "usa": "USA",
        "united states": "USA",
    }
    for name, tag in aliases.items():
        if tag in countries:
            _add_name(name, tag)

build_name_index()

def resolve_country_input(inp):
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
    if possible:
        return None, "ambiguous", list(possible)
    return None, "not_found", None

def pretty(tag):
    return f"{tag} — {countries[tag]['name']}"


# ==============================================================
# LOG
# ==============================================================

async def log_action(text):
    chan = bot.get_channel(LOG_CHANNEL_ID)
    if chan:
        try:
            await chan.send(text)
        except:
            pass


# ==============================================================
# EMBED BUILDER WITH MUTUAL EXCLUSIVITY
# ==============================================================

def build_embed():
    locked = config.get("locked", False)
    status = "🔒 **Signups Locked**" if locked else "🔓 **Signups Open**"

    # Reset display logic (exclusive)
    one_date = config.get("reset_once_date")
    one_time = config.get("reset_once_time")
    one_tz = config.get("reset_once_tz_code")

    daily_time = config.get("reset_time")
    daily_tz = config.get("reset_tz_code")

    if one_date and one_time and one_tz:
        reset_line = f"• One-time reset on **{one_date} at {one_time} {one_tz}**"
    elif daily_time and daily_tz:
        reset_line = f"• Daily reset at **{daily_time} {daily_tz}**"
    else:
        reset_line = "• No reset configured"

    embed = discord.Embed(
        title="🌍 Country Reservations",
        description=(
            f"{status}\n\n"
            "Type any country name or tag.\n"
            "To release a nation type 'Release TAG'.\n"
            "Ensure the country code is correct.\n"
            "All messages auto-delete after 5 seconds.\n\n"
            "**Admin Commands:**\n"
            "• `!setreset HH:MM TZZ`\n"
            "• `!setresetdate YYYY-MM-DD HH:MM TZZ`\n"
            "• `!timezones`\n\n"
            f"{reset_line}"
        ),
        color=0x2b2d31,
    )

    for region in ["Europe", "Asia", "MEA", "NA", "SA"]:
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
                lines.append(f"**{flag} {tag} — {name}** — Unclaimed")
        embed.add_field(name=f"__{region}__", value="\n".join(lines), inline=False)

    return embed


async def update_embed():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
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


# ==============================================================
# BOT READY — OPTIONAL STARTUP RESET
# ==============================================================

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")

    if config.get("startup_reset", True):
        reservations.clear()
        save_reservations()

        config["embed_message_id"] = None
        save_config()

        await update_embed()
        await log_action("🔄 Startup reset — reservation list wiped.")
    else:
        await update_embed()

    reset_watcher.start()


# ==============================================================
# RESET SCHEDULER
# ==============================================================

def check_daily_reset():
    rt = config.get("reset_time")
    tz_name = config.get("reset_tz")
    if not rt or not tz_name:
        return False, None

    try:
        h, m = map(int, rt.split(":"))
        zone = ZoneInfo(tz_name)
    except:
        return False, None

    now = datetime.now(timezone.utc).astimezone(zone)
    today = now.date().isoformat()
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)

    last = config.get("last_reset_date")

    if last != today and now >= target:
        return True, today
    return False, None


@tasks.loop(minutes=1)
async def reset_watcher():

    # DAILY RESET (only if not paused by one-time reset)
    if not config.get("daily_paused", False):
        do_reset, today = check_daily_reset()
        if do_reset:
            reservations.clear()
            save_reservations()
            await update_embed()
            await asyncio.sleep(5)
            await update_embed()
            await log_action("🗑️ Daily reset complete.")
            config["last_reset_date"] = today
            save_config()

    # ONE-TIME RESET
    date_str = config.get("reset_once_date")
    time_str = config.get("reset_once_time")
    tz_name = config.get("reset_once_tz")

    if date_str and time_str and tz_name:
        try:
            y, mo, d = map(int, date_str.split("-"))
            h, m = map(int, time_str.split(":"))
            zone = ZoneInfo(tz_name)
        except:
            return

        now = datetime.now(timezone.utc).astimezone(zone)
        target = datetime(y, mo, d, h, m, tzinfo=zone)

        if now >= target:
            reservations.clear()
            save_reservations()
            await update_embed()
            await asyncio.sleep(5)
            await update_embed()

            await log_action(
                f"🗑️ One-time reset executed for {date_str} at {time_str}"
            )

            # Remove scheduled reset & unpause daily
            config["reset_once_date"] = None
            config["reset_once_time"] = None
            config["reset_once_tz"] = None
            config["reset_once_tz_code"] = None
            config["daily_paused"] = False
            save_config()


# ==============================================================
# RESERVATION HANDLING
# ==============================================================

async def handle_reserve(message, text):
    tag, err, extra = resolve_country_input(text)
    if tag is None:
        return

    if config.get("locked", False):
        return

    # Check if user already has a country
    current = None
    for t, uid in reservations.items():
        if uid == message.author.id:
            current = t
            break

    # Swap
    if current and current != tag:
        if tag in reservations and reservations[tag] != message.author.id:
            return
        del reservations[current]
        reservations[tag] = message.author.id
        save_reservations()
        await update_embed()
        await log_action(f"🔄 {message.author} swapped {pretty(current)} → {pretty(tag)}")
        return

    # Already taken by someone else
    if tag in reservations and reservations[tag] != message.author.id:
        return

    reservations[tag] = message.author.id
    save_reservations()
    await update_embed()
    await log_action(f"🟢 {message.author} reserved {pretty(tag)}")


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
    await log_action(f"⚪ {message.author} released {pretty(tag)}")


# ==============================================================
# SILENT MODE MESSAGE FILTER
# ==============================================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    raw = message.content.strip()
    if not raw:
        return

    upper = raw.upper()
    in_res = (message.channel.id == CHANNEL_ID)

    if upper.startswith("RESERVE "):
        await handle_reserve(message, raw[8:].strip())
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    if upper.startswith("RELEASE "):
        await handle_release(message, raw[8:].strip())
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    if in_res and not raw.startswith("!"):
        await handle_reserve(message, raw)
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    if in_res and raw.startswith("!"):
        await bot.process_commands(message)
        try: await message.delete(delay=DELETE_DELAY)
        except: pass
        return

    await bot.process_commands(message)


# ==============================================================
# ADMIN COMMANDS
# ==============================================================

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
    # Daily reset (exclusive)
    try:
        h, m = map(int, time_str.split(":"))
    except:
        return

    tz_code = tz_code.upper()
    if tz_code not in TZ_CODE_MAP:
        return

    # Enable daily reset
    config["reset_time"] = time_str
    config["reset_tz"] = TZ_CODE_MAP[tz_code]
    config["reset_tz_code"] = tz_code
    config["last_reset_date"] = None

    # **Mutual exclusivity:** Remove one-time reset immediately
    config["reset_once_date"] = None
    config["reset_once_time"] = None
    config["reset_once_tz"] = None
    config["reset_once_tz_code"] = None
    config["daily_paused"] = False

    save_config()
    await update_embed()
    await log_action(f"⏰ Daily reset set to {time_str} {tz_code}")

@bot.command()
async def timezones(ctx):
    lines = [f"**{c}** → `{TZ_CODE_MAP[c]}`" for c in sorted(TZ_CODE_MAP)]
    await ctx.reply("\n".join(lines))

@bot.command()
@commands.has_permissions(administrator=True)
async def setresetdate(ctx, date_str, time_str, tz_code):
    # One-time reset (exclusive)
    try:
        y, mo, d = map(int, date_str.split("-"))
        _ = datetime(y, mo, d)
    except:
        return

    try:
        h, m = map(int, time_str.split(":"))
    except:
        return

    tz_code = tz_code.upper()
    if tz_code not in TZ_CODE_MAP:
        return

    # Set one-time reset
    config["reset_once_date"] = date_str
    config["reset_once_time"] = time_str
    config["reset_once_tz"] = TZ_CODE_MAP[tz_code]
    config["reset_once_tz_code"] = tz_code

    # Pause daily reset
    config["daily_paused"] = True

    # **Mutual exclusivity:** remove daily reset settings immediately
    config["reset_time"] = None
    config["reset_tz"] = None
    config["reset_tz_code"] = None
    config["last_reset_date"] = None

    save_config()
    await update_embed()
    await log_action(f"📅 One-time reset scheduled for {date_str} at {time_str} {tz_code}")

# ==============================================================
# RUN BOT
# ==============================================================

bot.run(TOKEN)
