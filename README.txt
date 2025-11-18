HOI4 Country Reservation Bot
============================

Files
-----
main.py                    – The bot code
token.txt                  – Your bot token (Pella will load this)
reservation_countries.json – List of displayed countries
all_tags.json              – Full list of additional tags (not displayed)
reservations.json          – Auto-generated (user reservations)
config.json                – Auto-generated (embed ID, lock state, reset time, etc.)

Requirements
------------
pip install discord.py

Put your bot token in:
token.txt

Set your channel IDs in main.py:
CHANNEL_ID = <reservation channel>
LOG_CHANNEL_ID = <log channel or 0 to disable>

Commands – User
----------------
RESERVE <TAG>
    Claim a country. If you already have one, the bot will offer a swap.

RELEASE <TAG>
    Release your country.

Commands – Admin
----------------
!force <TAG> @user
    Force a user into a country.

!unassign <TAG>
    Free a country.

!lock
    Lock reservations.

!unlock
    Unlock reservations.

!setreset HH:MM TZ
    Configure daily reset time.
    Example:    !setreset 21:00 EST
    Supported TZ codes: run !timezones

!timezones
    Show all valid 3-letter timezone codes.

Automatic Reset
---------------
The bot performs exactly one reset per local day at the configured time.

Config fields:
    reset_time      – "HH:MM"
    reset_tz        – IANA timezone name (auto from code)
    reset_tz_code   – Original 3-letter code
    last_reset_date – Local date of last reset

Hosting on Pella
----------------
Upload all files.
Set BOT_TOKEN in environment → read from token.txt or env.
Bot automatically recreates empty JSON files if wiped or invalid.

Run
---
python main.py
