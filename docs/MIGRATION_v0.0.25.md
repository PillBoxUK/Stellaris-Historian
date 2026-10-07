# v0.0.25 - Responsive Journal Layout

## Purpose

v0.0.25 changes only the generated Historical Journal presentation for on-screen use.

## Screen behaviour

- Journal/header width: up to 92% of the browser viewport, capped at 3000px.
- Register tables use the available journal width.
- Chronicle/event prose is capped at a 1600px reading width and centred.
- The founding narrative is capped at 1800px.
- Laptop and mobile breakpoints reduce padding and return the journal to full width.

## Print / PDF behaviour

`@media print` restores the previous 1040px document-style width and removes screen-only overflow behaviour. This keeps PDF exports stable while improving 4K browser viewing.

## Migration

The one-time migration performs no data conversion. It validates the v0.0.25 files, removes the now-obsolete `migrate_v0_0_24.py`, clears disposable Python cache folders, and records completion in `data/.migration_v0_0_25_complete`.

No `.sav` archive, database, campaign data, `.venv`, external backup, or `Updates and source` content is removed.
