STELLARIS HISTORIAN v0.0.87.1 — CONSOLE LOGO HOTFIX
by PillBoxUK

WHAT IS FIXED
- Rebuilds the large STELLARIS console startup banner as fixed-width,
  ASCII-only lettering with corrected and consistently spaced "A" and "R".
- Removes Unicode box corners that could show as stray diamonds or misalign
  in Windows Terminal depending on font/rendering settings.
- Keeps HISTORIAN and by PillBoxUK centered directly beneath the logo.
- Bumps displayed application, launcher and manifest versions to v0.0.87.1.

INSTALLATION (requires restart)
1. Switch Live History OFF and wait for active processing to finish.
2. Close Stellaris Historian completely (leave the Stellaris game running).
3. Recommended: back up your Historian installation, especially data/.
4. Extract this ZIP directly into G:\codex\StellarisHistorian\
   and overwrite the matching files. Do not create an extra nested folder.
5. Run start.bat. The large ASCII logo and version v0.0.87.1 should appear.
6. In the browser check the Campaign header displays v0.0.87.1.

RESTART HISTORIAN VIA start.bat: YES.
RESTART STELLARIS: NO.

FILES MODIFIED
- assets/stellaris_banner.txt (visual logo only)
- start.bat (version string only, existing launcher logic unchanged)
- historian/__init__.py (version only)
- historian_manifest.json (version and ASCII logo release metadata)
- tests/test_banner_v0_0_87_1.py (read-only regression test)

SAFETY
- This overlay contains no Ironman saves, SQLite databases, backups, logs,
  caches, app routes, or save-processing/parser changes.
- Campaign history remains based solely on verified save/database evidence.
- This patch DOES NOT alter the site styling or modify the recording prompt.
