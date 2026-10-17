# Stellaris Historian v0.0.85 — The Imperial Annals: Evidence and Names

**Updates v0.0.84; requires its installed files.** This is a narrow, high-impact chronology quality release. It does not replace the database or your preserved archives and does not change the existing white-and-gold Imperial Annals layout, floating evidence cards or war rail.

## Fixes

1. Civilisation-neutral public language: removes hard-coded "Commonwealth service", "Commonwealth territory", "Commonwealth scholars" and Commonwealth-founder phrasing from general timeline and census publication. The Commonwealth's own special opening chapter remains specific to the Commonwealth.
2. Publication-only ship-name guarding: saves may supply placeholder names such as `PREFIX_NAME_FORMAT`. The timeline now describes such a vessel by its verified ship type rather than claiming the placeholder is its name. Government assignments similarly retain the ship *type* without fabricating a ship's name. Underlying source data is not edited or deleted.
3. Natural-language government rosters: the exact archive date, ruling institution, ruler, council, administration, envoys, posts and *then-observed* traits are described in flowing English. An unreadable later trait can never be projected into an older census; a missing 1 January snapshot remains unavailable.
4. People of Note now includes the **same-year recorded event** rather than only an empty name/class card, while not projecting later roles backward.
5. Present-edge summary explicitly comes from the last **processed** archive, not the latest queued/watched save. Current registry counts therefore cannot be forward-dated during catch-up.
6. Added a local, read-only CLI audit covering processed/unprocessed counts, exact annual census date coverage, generated timeline presence, visible unresolved tokens and inappropriate cross-empire Commonwealth references.
7. Synthetic regression tests for naming, governance and the audit, preserving existing annual-census tests.

## Strict historical rules

- Ironman saves are the primary evidence. Databases, derived historical caches and official game script/localisation supply traceable supporting information.
- PDFs and screenshots are visual output and debugging aids **only**, never authoritative campaign evidence.
- A native exact date is distinct from a first-observed save date. A first appearance does not prove the day a ship was built, leader was recruited, government changed or system was discovered.
- Being absent from leader records does not prove death. No invented motives, casualties, ship fates, spies, rumours, or galactic outcomes.
- Source/localisation tokens remain in raw diagnostic evidence when necessary but are never substituted with made-up proper names.
- This release does **not** newly reconstruct hidden espionage or first contact story choices: those require direct save parsers and evidence-specific tests.

## Installation

1. Leave the game alone if desired, but in Historian turn **Live History OFF** and wait until all processing is complete.
2. **Close Historian fully**, including the local Python/server process. Copy your entire project directory as a backup (especially `data/`).
3. Extract the ZIP **into the existing project root** (`G:\codex\StellarisHistorian`), preserving subdirectories and overwriting matching *program* files. Do not extract it into a newly nested folder.
4. **Restart Historian using `start.bat`**; ensure the banner and console say v0.0.85.
5. Use **Manage Campaign → Update Historical Timeline** when convenient to republish the current Annals. This is a publication fix; it **does not require constructing a new campaign**. Back up first. Live History thereafter continues updating as new save archives are processed.
6. Optional offline audit:

```bat
.venv\Scripts\python.exe scripts\audit_annals_v0_0_85.py --list-campaigns
.venv\Scripts\python.exe scripts\audit_annals_v0_0_85.py --campaign-id 8
```

Change `8` to your actual Veyran campaign ID. The read-only audit prints JSON to stdout, including gaps and warnings. It does not modify the database or the generated HTML. A missing Jan 1 observation is intentionally marked unavailable rather than filled from a later save.

## Verification and limits

`python tests/test_v0_0_85.py` and `python tests/test_v0_0_83_1.py` pass in the patch-only synthetic fixture environment. The older v0.0.83/v0.0.84 and Live History progress tests also pass. Full timeline integration against the installed Windows application and the Veyran Ironman archive must be checked after installation; those underlying archives were not supplied with this patch. The v0.0.82 test needs installed `historian.core` code not distributed in any of the available patch archives and cannot be run in this patch-only build tree.

No schema migration, archived source read/write changes, data folder replacements or GitHub pushes. **Historian restart required**, since Python modules load at process start. **Stellaris game restart not required**.
