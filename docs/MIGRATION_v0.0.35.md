# Migration v0.0.35 - Scribes Narrative View

This is a presentation-only release.

The one-time validation checks that the v0.0.35 Python and documentation files are present and compile correctly, then records `data/.migration_v0_0_35_complete` and writes `logs/MIGRATION_v0.0.35.log`.

It does **not** modify:

- `data/historian.db`
- archived Stellaris `.sav` files
- parsed snapshot cache components or cache versions
- processed/unprocessed snapshot flags
- derived historical rows

The new `Scribes_Chronicle.html` file is generated on demand when `/scribes` is opened.
