# Migration v0.0.48

## Purpose

Refine Politics/Diplomacy publication after v0.0.47.1 live and 299-save Review Campaign testing, while improving review/construct refresh visibility.

## Source changes

- `historian/domains/politics/history.py`
  - marks routine agenda progress as diagnostic-only
  - distinguishes actual agenda identity changes
  - filters strong pseudo-country/event-entity relation records from public diplomacy while retaining raw evidence
- `historian/domains/politics/journal.py`
  - uses readable/localised summary values
  - omits agenda progress from the public summary
- `historian/localisation.py`
  - adds a conservative generic localisation-key resolver
- `historian/domains/people/event_probe.py`
  - accepts the v0.0.47 Politics component in the snapshot-cache return tuple
- `historian/domains/politics/probe.py`
  - adds optional raw-sample progress callback support
- `historian/history_processor.py`
  - fixes the invalid escape in the live Politics diagnostic path
- `app.py`
  - adds numbered refresh progress/timing for Review and Construct
  - adds inner Politics probe scan progress
  - adds explicit Live History journal-refresh completion logging

## Existing database cleanup

If `data/historian.db` already contains `politics_history_events`, the migration:

- hides existing events whose raw field is `council_agenda_progress`
- renames those event types to `council_agenda_progress_changed`
- hides existing diplomatic rows matching the strongest pseudo-country/event-entity indicators found during Sutharian testing

This cleanup does not delete structured evidence. Review Campaign can then reconstruct the full domain using v0.0.48 logic.

## Backups

Changed source files are copied to `backups/v0.0.48/` before modification.

## Restart

Required. Stop Historian and start it again using the patched `start.bat`.
