STELLARIS HISTORIAN v0.0.82.1 — LIVE HISTORY PROGRESS HOTFIX
=======================================================
Base version required: v0.0.82

CAUSE
historian/history_processor.py process_unprocessed() referenced an
undefined variable named progress before entering its per-save try block.
Both automatic Live History and manual Update History called this function,
causing a NameError as soon as an unprocessed save was encountered.

CHANGE
Provide an optional, keyword-only progress callback with default None,
matching review_campaign()'s existing callback convention. Current callers
need not pass a callback; save processing proceeds without it.

This is a one-line functional change to history_processor.py.
It does not alter archive enumeration, processing flags, deduplication,
chronology, save parsing, SQLite schemas, databases or event publication.
Two saves on the same game date are NOT necessarily identical and continue
to be treated as separate snapshots by the existing code.
The included __init__.py, start.bat and historian_manifest.json only
update version metadata and displayed version strings.

INSTALLATION
1. Turn Live History OFF and wait until idle.
2. CLOSE Historian and its console completely.
3. Make a backup of the installation and data/ directory.
4. Extract this ZIP directly into G:\codex\StellarisHistorian,
   preserving folders and replacing matching files.
5. Restart using the ORIGINAL start.bat.
6. Confirm the splash/console shows v0.0.82.1.
7. With Live History OFF, use Manage Campaign > Update Historical Timeline
   and verify ironman-519.sav and ironman-520.sav no longer produce
   "name 'progress' is not defined".
8. Once the queue is empty, optionally turn Live History back ON.

DO NOT EXTRACT DIRECTLY INTO THE historian/ SUBFOLDER.
No campaign files, .sav files, databases or personal configuration included.
No database migration. No GitHub changes.

TEST COVERAGE
- Python syntax compilation for the patched module and regression test.
- Isolated execution of process_unprocessed() against two mocked archived
  snapshots with distinct hashes but the same in-game date.
- Default call with no progress callback and optional callback supplied.
- Verified both snapshots are marked processed, independently of game date.
- Verified the ZIP's exact file layout after creation.

LIMITATION
Tests use simulated save processing. Windows execution against your real
Commonwealth saves still needs confirmation after installation.
