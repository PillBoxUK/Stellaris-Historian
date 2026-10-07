# Migration v0.0.43

## Purpose

Add a targeted event/character deep probe without invalidating the People v5 parsed cache.

## Changes

- Application version advances to `0.0.43`.
- Adds `historian/domains/people/event_probe.py`.
- Adds `diagnostics/Event_Character_Probe_Debug.txt` during Review Campaign and Construct Campaign.
- The probe uses cached leader history to locate exits and reads only previous/current/next raw saves around each exit.
- Adds evidence for event/notification deltas, `player_event` IDs, raw exact-ID event targets, event-adjacent leader references, and the currently unmapped leader fields `available_trait`, `cooldown`, and `delayed_event`.
- People cache remains v5.
- No database schema change.
- No archived save is modified.
- No processed flag is changed by the migration.

## app.py hook

The one-time migration installs the Review/Construct probe hook into `app.py`. Before changing that file it preserves a copy at:

`backups/v0.0.43/app.py.before_v0.0.43`

The migration aborts instead of guessing if the expected v0.0.42 application anchors cannot be found.

## Required user action

Restart Historian and run **Review Campaign once** to generate the new diagnostic. Because People v5 is unchanged, the campaign should use cache hits rather than repeating the v0.0.42 raw cache extension.
