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
ALL_TAGS_FILE = "all_tags.json"  # extra HOI4 names (democratic / neutral)

# IMPORTANT: Replace these with your real IDs
CHANNEL_ID = 1440130973650915378  # Reservation channel
LOG_CHANNEL_ID = 1440253011678199882  # Optional log channel (0 = disabled)

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# TIMEZONE MAP
# -------------------------
# Supported 3-letter timezone codes -> IANA zone names
TZ_CODE_MAP = {
    # UTC / GMT
    "UTC": "UTC",
    "GMT": "Etc/UTC",

    # UK / Ireland
    "BST": "Europe/London",

    # North America
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",

    # Central Europe
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",

    # Eastern Europe
    "EET": "Europe/Helsinki",
    "EEST": "Europe/Helsinki",

    # Some extras for safety
    "MSK": "Europe/Moscow",
    "IST": "Asia/Kolkata",
    "JST": "Asia/Tokyo",
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
}

# -------------------------
# LOAD TOKEN (ENVIRONMENT VARIABLE ONLY)
# -------------------------

TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise RuntimeError("BOT_TOKEN environment variable not set!")

# -------------------------
# JSON LOADING HELPERS
# -------------------------

def load_json(fp, default):
    """
    Load JSON safely.
    - If file does not exist OR is empty OR invalid JSON -> write default and return it.
    """
    if not os.path.exists(fp) or os.path.getsize(fp) == 0:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default

    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Repair broken/blank JSON file
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
# NAME RESOLUTION INDEX
# -------------------------

# name_index: normalized name string -> set of tags
name_index = {}

def _normalize_name(s: str) -> str:
    # Lowercase, strip, collapse spaces
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _add_name_for_tag(tag: str, name: str):
    """Add a single display name into the name_index for a given tag."""
    global name_index
    if not name:
        return
    norm = _normalize_name(name)
    if not norm:
        return
    if norm not in name_index:
        name_index[norm] = set()
    name_index[norm].add(tag)

def build_name_index():
    """
    Build reverse lookup from names -> tags using:
    - reservation_countries.json (display names)
    - all_tags.json (democratic + neutral names)
    """
    global name_index
    name_index = {}

    # Base display names
    for tag, data in countries.items():
        base_name = data.get("name", "")
        _add_name_for_tag(tag, base_name)

    # Extra HOI4 names (democratic / neutral) – only for tags we actually use
    for tag, data in all_tags.items():
        if tag not in countries:
            continue
        demo = data.get("democratic", "")
        neut = data.get("neutral", "")
        _add_name_for_tag(tag, demo)
        _add_name_for_tag(tag, neut)

    # Optional: some simple short aliases (like "uk" for ENG, "usa" for USA)
    # You can extend this dictionary as needed.
    aliases = {
        "uk": "ENG",
        "britain": "ENG",
        "great britain": "ENG",
        "england": "ENG",

        "usa": "USA",
        "united states": "USA",
        "united states of america": "USA",
    }
    for alias_name, alias_tag in aliases.items():
        if alias_tag in countries:
            _add_name_for_tag(alias_tag, alias_name)

build_name_index()

def resolve_country_input(user_input: str):
    """
    Resolve user input (tag / name / partial) into a tag.

    Returns:
        (tag, error_type, extra)

        tag: str or None
        error_type: None | "not_found" | "ambiguous"
        extra: list of suggestion tags (for ambiguous) or None
    """
    if not user_input or not user_input.strip():
        return None, "not_found", None

    raw = user_input.strip()
    candidate_tag = raw.upper()

    # Exact TAG match
    if candidate_tag in countries:
        return candidate_tag, None, None

    # Normalized text match
    norm = _normalize_name(raw)

    # Exact name match
    if norm in name_index:
        tags = list(name_index[norm])
        if len(tags) == 1:
            return tags[0], None, None
        else:
            # Multiple tags share that name string
            return None, "ambiguous", tags

    # Partial (substring) search – Option D:
    # collect tags where the name contains the input as substring.
    possible_tags = set()
    for name_str, tags_set in name_index.items():
        if norm in name_str:
            possible_tags.update(tags_set)

    if len(possible_tags) == 1:
        return next(iter(possible_tags)), None, None
    elif len(possible_tags) > 1:
        return None, "ambiguous", sorted(possible_tags)
    else:
        return None, "not_found", None

def pretty_country(tag: str) -> str:
    data = countries.get(tag, {})
    name = data.get("name", tag)
    return f"{tag} — {name}"

# -------------------------
# LOGGING FUNCTION
# -------------------------

async def log_action(text):
    if LOG_CHANNEL_ID == 0:
        return  # logging disabled

    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        try:
            await channel.send(text)
        except Exception:
            print("Could not send log message.")

# -------------------------
# BUILD RESERVATION EMBED
# -------------------------

def build_reservation_embed():
    locked = config.get("locked", False)
    status_text = "🔓 **Signups Open**" if not locked else "🔒 **Signups Locked**"

    # Show current reset config if set
    reset_time = config.get("reset_time")
    reset_tz_code = config.get("reset_tz_code")
    if reset_time and reset_tz_code:
        reset_line = f"• Daily reset at **{reset_time} {reset_tz_code}**\n"
    else:
        reset_line = "• Daily reset time **not configured**\n"

    embed = discord.Embed(
        title="🌍 Country Reservations",
        description=(
            f"{status_text}\n\n"
            "**📘 User Commands:**\n"
            "• **RESERVE <TAG or NAME>** — Claim a country\n"
            "• **RELEASE <TAG or NAME>** — Free your country\n"
            "• Example: `RESERVE GER`, `RESERVE Hungary`\n"
            "• In this channel you can also just type the country name or tag (e.g. `Hungary`, `HUN`).\n\n"
            "**⚙️ Admin Commands (summary):**\n"
            "• `!setreset HH:MM TZZ` — Set daily reset time (e.g. `!setreset 21:00 EST`)\n"
            "• `!timezones` — Show supported timezone codes\n\n"
            "**ℹ️ Notes:**\n"
            "• Each user may reserve **one** nation\n"
            "• If you reserve a new nation, you will be asked to swap\n"
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
                user_id = reservations[tag]
                lines.append(f"**{flag} {tag} — {name}** — <@{user_id}>")
            else:
                lines.append(f"**{flag} {tag} — {name}** — *Unclaimed*")

        if lines:
            embed.add_field(
                name=f"__{region}__",
                value="\n".join(lines),
                inline=False
            )

    return embed

# -------------------------
# EMBED POSTING / UPDATING
# -------------------------

async def update_embed():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("ERROR: Reservation channel not found")
        return

    message_id = config.get("embed_message_id")

    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=build_reservation_embed())
            return
        except Exception:
            pass

    msg = await channel.send(embed=build_reservation_embed())
    config["embed_message_id"] = msg.id
    save_config()

# -------------------------
# BOT READY EVENT
# -------------------------

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await update_embed()
    reset_watcher.start()

# -------------------------
# TIMEZONE-BASED DAILY RESET
# -------------------------

def get_next_reset_info():
    """
    Returns (should_reset: bool, today_str: str) based on config.
    - Uses reset_time (HH:MM) and reset_tz (IANA zone)
    - Ensures one reset per local day
    """
    reset_time = config.get("reset_time")
    reset_tz = config.get("reset_tz")
    if not reset_time or not reset_tz:
        return False, None

    try:
        hour_str, minute_str = reset_time.split(":")
        target_h = int(hour_str)
        target_m = int(minute_str)
    except Exception:
        return False, None

    try:
        tz = ZoneInfo(reset_tz)
    except Exception:
        return False, None

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)

    today_str = now_local.date().isoformat()
    target_today = now_local.replace(hour=target_h, minute=target_m, second=0, microsecond=0)

    last_reset_date = config.get("last_reset_date")

    # If we haven't reset today and the local time is at/after the target time, we should reset.
    if last_reset_date != today_str and now_local >= target_today:
        return True, today_str

    return False, today_str


@tasks.loop(minutes=1)
async def reset_watcher():
    """
    Runs every minute:
    - Checks if it's time to do the daily reset based on configured time & timezone.
    - Ensures reset happens at most once per local day.
    """
    should_reset, today_str = get_next_reset_info()
    if not should_reset:
        return

    # Perform reset
    reservations.clear()
    save_reservations()
    await update_embed()
    await log_action("🗑️ Daily reset completed — all nations unclaimed.")

    # Mark this day as reset so we don't double-fire
    config["last_reset_date"] = today_str
    save_config()


@reset_watcher.before_loop
async def before_reset_watcher():
    await bot.wait_until_ready()

# -------------------------
# RESERVATION HELPERS
# -------------------------

async def handle_reserve_request(message: discord.Message, country_text: str):
    """Core logic for reserving a country."""
    tag, err_type, extra = resolve_country_input(country_text)

    if tag is None:
        if err_type == "ambiguous" and extra:
            # Show possible matches
            suggestions = []
            for t in extra[:15]:  # safety cap
                suggestions.append(f"• **{pretty_country(t)}**")
            more = ""
            if len(extra) > 15:
                more = f"\n…and {len(extra) - 15} more."
            await message.reply(
                "❓ That matches multiple countries:\n"
                + "\n".join(suggestions)
                + more
                + "\n\nPlease type the **full country name** or its **3-letter tag**."
            )
        else:
            await message.reply(
                "❌ I couldn't find any country matching that.\n"
                "Please type the **full country name** (e.g. `Hungary`) or its **tag** (e.g. `HUN`)."
            )
        return

    # We now have a valid tag
    country_name = countries[tag]["name"]

    if config.get("locked", False):
        await message.reply("🔒 Signups are locked.")
        return

    # Check if user already owns a country
    current = None
    for t, uid in reservations.items():
        if uid == message.author.id:
            current = t
            break

    # If they already have one and want another → swap
    if current and current != tag:
        current_name = countries.get(current, {}).get("name", current)
        await message.reply(
            f"⚠️ You already have **{pretty_country(current)}**.\n"
            f"Type **YES** to swap to **{pretty_country(tag)}**, or **NO** to cancel."
        )

        def check(m: discord.Message):
            return (
                m.author.id == message.author.id
                and m.channel.id == message.channel.id
                and m.content.upper() in ["YES", "NO"]
            )

        try:
            reply = await bot.wait_for("message", check=check, timeout=20)
        except Exception:
            await message.reply("⏳ Swap timed out.")
            return

        if reply.content.upper() == "NO":
            await message.reply("❌ Swap canceled.")
            return

        # Perform swap
        del reservations[current]
        reservations[tag] = message.author.id
        save_reservations()
        await update_embed()
        await log_action(
            f"🔄 {message.author} swapped from **{pretty_country(current)}** "
            f"to **{pretty_country(tag)}**"
        )
        await message.reply(f"✔️ Swapped to **{pretty_country(tag)}**.")
        return

    # If someone else owns it
    if tag in reservations and reservations[tag] != message.author.id:
        await message.reply("❌ That nation is already reserved.")
        return

    # Reserve fresh or re-affirm same tag
    reservations[tag] = message.author.id
    save_reservations()
    await update_embed()
    await log_action(f"🟢 {message.author} reserved **{pretty_country(tag)}**")
    await message.reply(f"✔️ Reserved **{pretty_country(tag)}**.")


async def handle_release_request(message: discord.Message, country_text: str):
    """Core logic for releasing a country."""
    tag, err_type, extra = resolve_country_input(country_text)

    if tag is None:
        # For release, we can be a bit more direct
        await message.reply(
            "❌ I couldn't figure out which country you meant.\n"
            "Please use `RELEASE <TAG>` or `RELEASE <full name>`, e.g. `RELEASE HUN` or `RELEASE Hungary`."
        )
        return

    if tag not in reservations:
        await message.reply("❌ That nation is not reserved.")
        return

    if reservations[tag] != message.author.id:
        await message.reply("❌ You do not control that nation.")
        return

    del reservations[tag]
    save_reservations()
    await update_embed()
    await log_action(f"⚪ {message.author} released **{pretty_country(tag)}**")
    await message.reply(f"✔️ Released **{pretty_country(tag)}**.")

# -------------------------
# USER MESSAGE HANDLER
# -------------------------

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    raw = message.content.strip()
    if not raw:
        return

    upper = raw.upper()
    in_res_channel = (message.channel.id == CHANNEL_ID)

    # -------------------------
    # Explicit commands: RESERVE / RELEASE (work in any channel)
    # -------------------------
    if upper.startswith("RESERVE "):
        country_text = raw[8:].strip()
        await handle_reserve_request(message, country_text)
        return

    if upper.startswith("RELEASE "):
        country_text = raw[8:].strip()
        await handle_release_request(message, country_text)
        return

    # -------------------------
    # Bare messages in the reservation channel:
    # interpret as "reserve this" if not a bot command
    # -------------------------
    if in_res_channel and not raw.startswith("!"):
        # If they typed just a tag or name, treat as reserve attempt.
        await handle_reserve_request(message, raw)
        return

    # Let other bot commands run
    await bot.process_commands(message)

# -------------------------
# ADMIN COMMANDS
# -------------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def lock(ctx):
    config["locked"] = True
    save_config()
    await update_embed()
    await log_action(f"🔒 Admin {ctx.author} locked signups.")
    await ctx.reply("🔒 Signups locked.")


@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    config["locked"] = False
    save_config()
    await update_embed()
    await log_action(f"🔓 Admin {ctx.author} unlocked signups.")
    await ctx.reply("🔓 Signups unlocked.")


@bot.command()
@commands.has_permissions(administrator=True)
async def force(ctx, tag, user: discord.Member):
    tag = tag.upper()
    if tag not in countries:
        await ctx.reply("❌ Invalid tag.")
        return

    reservations[tag] = user.id
    save_reservations()
    await update_embed()
    await log_action(f"🛠️ Admin {ctx.author} forced **{pretty_country(tag)}** to {user.mention}")
    await ctx.reply(f"✔️ Forced {pretty_country(tag)} to {user.mention}")


@bot.command()
@commands.has_permissions(administrator=True)
async def unassign(ctx, tag):
    tag = tag.upper()
    if tag in reservations:
        del reservations[tag]
        save_reservations()
        await update_embed()
        await log_action(f"🛠️ Admin {ctx.author} unassigned **{pretty_country(tag)}**")
        await ctx.reply(f"✔️ Unassigned {pretty_country(tag)}")
    else:
        await ctx.reply("❌ Tag is not reserved.")


@bot.command()
@commands.has_permissions(administrator=True)
async def setreset(ctx, time_str: str, tz_code: str):
    """
    Set the daily reset time.
    Usage: !setreset 21:00 EST
    - time_str must be HH:MM in 24-hour format
    - tz_code must be one of the supported 3-letter codes (see !timezones)
    """
    # Validate time
    try:
        hour_str, minute_str = time_str.split(":")
        h = int(hour_str)
        m = int(minute_str)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except Exception:
        await ctx.reply("❌ Invalid time format. Use `HH:MM` in 24-hour format, e.g. `21:00`.")
        return

    # Validate timezone code
    tz_code_upper = tz_code.upper()
    if tz_code_upper not in TZ_CODE_MAP:
        await ctx.reply(
            "❌ Unknown timezone code.\n"
            "Use `!timezones` to see the list of supported codes."
        )
        return

    tz_name = TZ_CODE_MAP[tz_code_upper]

    # Save config
    config["reset_time"] = time_str
    config["reset_tz"] = tz_name
    config["reset_tz_code"] = tz_code_upper
    # Reset last_reset_date so it will trigger as soon as we hit the new target time
    config["last_reset_date"] = None
    save_config()

    await update_embed()
    await log_action(
        f"⏰ Admin {ctx.author} set daily reset to **{time_str} {tz_code_upper}** ({tz_name})."
    )
    await ctx.reply(
        f"✔️ Daily reset set to **{time_str} {tz_code_upper}**\n"
        f"Internally using timezone **{tz_name}**."
    )


@bot.command()
async def timezones(ctx):
    """
    Show the list of supported timezone codes.
    """
    # Build a simple list sorted by code
    lines = []
    for code in sorted(TZ_CODE_MAP.keys()):
        lines.append(f"**{code}** → `{TZ_CODE_MAP[code]}`")

    joined = "\n".join(lines)
    if len(joined) > 3800:
        chunks = [joined[i:i+3800] for i in range(0, len(joined), 3800)]
        for i, c in enumerate(chunks, start=1):
            embed = discord.Embed(
                title=f"🕒 Supported Timezones (Part {i})",
                description=c,
                color=0x5865F2
            )
            await ctx.reply(embed=embed)
    else:
        embed = discord.Embed(
            title="🕒 Supported Timezone Codes",
            description=joined,
            color=0x5865F2
        )
        await ctx.reply(embed=embed)

# -------------------------
# RUN BOT
# -------------------------

bot.run(TOKEN)
