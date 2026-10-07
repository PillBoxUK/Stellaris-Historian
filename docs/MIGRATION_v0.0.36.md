# Migration v0.0.36 - Empire Timeline, Scribes Signatures and PDF Export

This is a presentation-only release.

The one-time validation checks that the v0.0.36 Python, documentation and dependency files are present and compile correctly, then records `data/.migration_v0_0_36_complete` and writes `logs/MIGRATION_v0.0.36.log`.

It does **not** modify:

- `data/historian.db`
- archived Stellaris `.sav` files
- parsed snapshot cache component versions
- processed/unprocessed snapshot flags
- derived historical rows

New presentation outputs are generated on demand:

- `Empire_Timeline.html` via `/timeline`
- `Scribes_Chronicle.html` via `/scribes`
- `Scribes_Chronicle.pdf` via `/scribes/pdf`

Scribes chapter signatories are resolved only from dated ruler observations already present in the parsed leader cache. The sign-off therefore represents who the archive records as ruler at or immediately before the chapter's anchor date; it is not a fabricated quotation or handwritten signature. The final open-ended chapter remains unsigned by design.
