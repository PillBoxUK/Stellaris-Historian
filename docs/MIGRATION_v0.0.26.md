# Migration v0.0.26 - Journal Navigation and Print Fix

This migration is presentation-only. It does not alter campaign evidence, parsed snapshot caches, derived history tables, archived `.sav` files or `data/historian.db`.

## Changes

- Removes the previous one-time `migrate_v0_0_25.py` script after backing it up when present.
- Clears disposable Python `__pycache__` folders.
- Installs the v0.0.26 journal renderer, version metadata and documentation.
- Creates `data/.migration_v0_0_26_complete` so the migration runs once.
- Writes `logs/MIGRATION_v0.0.26.log`.

## Protected paths

The migration never intentionally deletes:

- `data/` (apart from writing its own migration marker)
- `backups/`
- `Updates and source/`
- `.venv/`
- campaign archive folders or archived `.sav` files

## PDF workflow

Use the `Print / PDF` button in the Historical Journal and choose the browser's `Save to PDF` destination. This activates the paginated print stylesheet. Browser features that capture an entire web page as one PDF/image may intentionally bypass print CSS and are not the supported export path.
