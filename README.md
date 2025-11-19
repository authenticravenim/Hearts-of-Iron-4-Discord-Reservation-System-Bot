===========================================
HOI4 RESERVATION BOT — HELP & COMMANDS
===========================================

GENERAL USAGE
-------------
• Type any country name or tag directly into the reservation channel.
• All messages auto-delete after 5 seconds.
• The bot silently updates the reservation list.
• The reservation embed always shows the live status.
• Logs for all actions are posted in the reservation-log channel.

USER COMMANDS
-------------
(You do NOT need to use commands for normal reservations.)

Reserve a country:
  Simply type the country name or tag.
  Example: germany   OR   GER

Release a country:
  "release germany"
  OR
  "release GER"

Swap countries:
  Type a new country name or tag.
  The bot will automatically release your old nation
  and assign you the new one, as long as it is free.

ADMIN COMMANDS
--------------

Lock or unlock signups:
  !lock
  !unlock

Force assign a country:
  !force TAG @user
  Example: !force FRA @John

Unassign a country:
  !unassign TAG
  Example: !unassign USA

Set a DAILY reset:
  !setreset HH:MM TZZ
  Example: !setreset 21:00 EST

• Daily resets occur EVERY day at the specified time.
• Resets clear all claimed countries.
• The next daily reset only happens if no one-time reset is active.

Set a ONE-TIME reset:
  !setresetdate YYYY-MM-DD HH:MM TZZ
  Example: !setresetdate 2025-02-10 18:00 PST

• The one-time reset will occur ONCE at the exact date and time.
• Daily reset is automatically PAUSED while a one-time reset is pending.
• When the one-time reset executes:
    - All reservations are wiped
    - The daily reset is automatically unpaused
    - The one-time reset is cleared from config

List supported timezones:
  !timezones


SILENT MODE
-----------
• No messages appear in the reservation channel except the embed.
• All user/admin inputs are deleted after 5 seconds.
• Confirmation messages are NOT sent in the channel.
• All actions are logged privately in the reservation-log channel.

LOGGING
-------
Every important action is logged:
  • Reservations
  • Releases
  • Swaps
  • Forced assignments
  • Daily resets
  • One-time reset scheduling
  • One-time reset execution

NOTES
-----
• Only one country can be held at a time.
• The bot prevents stealing another user's country.
• Country names and tags are flexible and accept partial matches.
• If multiple countries match a name, the bot silently ignores it.
