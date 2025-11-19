📘 HOI4 Reservation Bot — README / HELP FILE

This bot manages country reservations for HOI4 multiplayer games.
The reservation channel stays completely clean — only the embed is visible.
All user messages in the reservation channel are deleted automatically after 5 seconds.

⭐ How It Works (For Players)
1. Reserving a country

Just type the country name or tag in the reservation channel:

hungary
germany
usa
HUN
GER
USA


If the country is available, your name will appear beside it in the embed.

No confirmation message appears (silent mode).
Check the embed to see your reservation.

2. Releasing a country

Use the release command:

release hungary
release HUN


The country becomes unassigned again.

3. Changing countries (swap)

If you already own a country and try to reserve a different one:

If the target is free, your old country is released.

If the target is taken, the swap is blocked silently.

⭐ How It Works (For Admins)

Admins can use the following commands in any channel, BUT if they use them in the reservation channel, the messages will still auto-delete (silent mode).

Lock signups
!lock


Prevents new reservations.
Players with existing reservations keep them.

Unlock signups
!unlock


Allows reservations again.

Force assign a country to a player
!force GER @player


Gives the country directly to that player.

Unassign a country
!unassign GER


Removes the reservation from that country.

Set daily reset time
!setreset HH:MM TZ


Examples:

!setreset 05:00 EST
!setreset 12:00 UTC
!setreset 18:30 CET

Show available timezones
!timezones

⭐ Daily Reset System

The bot can automatically clear all reservations once per day.

After the reset:

All countries become unclaimed

The embed updates

A log entry is posted in the reservation logs channel

⭐ Silent Mode Behavior

The reservation channel is silent:

No bot replies

No DM messages

No errors shown

No admin command messages shown

User messages auto-delete after 5 seconds

Admin commands auto-delete after 5 seconds

Only the embed stays permanently

This prevents clutter and keeps the channel clean.

⭐ Logging System

All important actions are sent to the log channel:

Reservations

Releases

Swaps

Forced assignments

Unassigns

Daily resets

Nothing appears in the reservation channel.

⭐ File Overview
File	Description
main.py	Main bot code
reservations.json	Stores current reservations
config.json	Stores bot settings (embed ID, reset time, etc.)
reservation_countries.json	Country list + flags + regions
all_tags.json	Extra HOI4 alternate name mappings
⭐ Notes

The reservation channel must allow the bot to delete messages.

The log channel must allow the bot to post messages.

Admin commands require the Administrator permission.