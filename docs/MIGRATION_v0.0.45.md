# Migration v0.0.45 — Notification-Derived Leader Deaths

## Purpose

Promote retained, uniquely attributable Stellaris `LEADER_DEATH` notifications into structured People-domain death history without weakening Historian's evidence rules.

## Changes

- Adds `historian/domains/people/notification_deaths.py`.
- Keeps People cache component at v5.
- No database schema changes.
- No archive-save changes.
- No processed-flag reset.
- Patches Review and Construct so notification-derived death promotion occurs before diagnostics, Historical Event synthesis and database replacement.
- Patches Update History so newly processed leader exits can be promoted without requiring a manual Construct.
- Updates Timeline, Journal, Scribes and People diagnostics to distinguish confirmed deaths from unresolved exits.
- Updates the notification decoder to display unique leader-name matches in retained death messages.

## Safety rule

A retained death message is promoted only when:

- `type=LEADER_DEATH`
- `localization=MESSAGE_LEADER_LOST_DESC`
- the `LEADER` variable uniquely matches one known player leader
- the same leader exits in that archived interval
- the notification date lies inside the interval from last confirmed presence to first confirmed absence

If any check fails, the leader remains unresolved.

## Backups

Before source files are modified, the migration preserves originals beneath `backups/v0.0.45/` using their repository-relative paths.

## Required action

Run **Review Campaign once** after installation. Construct Campaign is not required.
