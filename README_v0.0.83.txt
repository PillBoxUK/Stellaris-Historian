STELLARIS HISTORIAN v0.0.83 — GOVERNMENT & DATABASE EXPLORER
================================================================
REQUIRES: Existing v0.0.82.1 installation with its Live History hotfix.

WHAT'S NEW
1) Historical Observatory > Government & People
   - Full campaign leader register, searchable by name, role, status and traits.
   - Recruitment and first/last appearance dates displayed separately.
   - Latest recorded traits, rank, occupation, assignments, council offices,
     personal backgrounds and evidence-aware career changes.
   - Confirmed deaths, native notification dates and recorded causes.
   - Unconfirmed departures never silently become deaths.
   - Observed succession of rulers plus council and planetary office registers.
   - Political and administrative evidence ledger with a search box.

2) Historical Observatory > Database Explorer
   - Local, read-only browser for historian.db and available campaign sidecars.
   - Browse SQLite tables with paging, search, field inspection and schema.
   - CSV export and a constrained SELECT/WITH SELECT console (200-row output).
   - The sidebar supports 'Active campaign only'; the SQL console is NOT
     automatically campaign filtered, so include WHERE campaign_id=... yourself.
   - SQL connections use mode=ro, PRAGMA query_only=ON, and deny SQL write
     instructions. Local requests only. No phpMyAdmin, web hosting or cloud.
   - The database is SQLite; MySQL/phpMyAdmin is not installed or required.

3) The Imperial Annals
   - Publish the native leader career milestones already stored in SQL:
     new traits (first-observed), council office appointments (first-observed),
     and confirmed deaths with recorded dates, age/cause when available.
   - The existing main chronological narrative, civilian history and combat
     history remain intact. New claims are derived only from saved evidence.
   - No later character traits are projected backwards to recruitment.

INSTALL (CLASSIC FLAT-ROOT ZIP)
1. Disable Live History; wait for active operations to finish.
2. Close Historian and its console completely.
3. Back up G:\codex\StellarisHistorian including data/.
4. Extract this ZIP into G:\codex\StellarisHistorian (NOT historian/).
5. Overwrite matching application files. Do NOT delete anything.
6. Restart using the ORIGINAL start.bat and confirm v0.0.83.
7. Select the Commonwealth campaign and use Explore History ↓ to open
   Government & People, then Database Explorer.
8. Open Empire Timeline to regenerate the narrative with added personnel
   milestones. No full archive reconstruction is needed for this patch.
9. Optional: Print/Save the timeline to PDF from your browser.

DIRECT LOCAL LINKS
http://127.0.0.1:8766/government-people
http://127.0.0.1:8766/database
http://127.0.0.1:8766/timeline

DATA PROTECTION
No campaign archives, .sav files, SQLite databases, config, game files,
user folders or backup copies are bundled. No database migration; SQL viewer
and government biographies are read-only. Existing processing and save watcher
unchanged. v0.0.82.1 Live History fix remains installed and is not replaced.

TESTED
- Uploaded Commonwealth historian.db passed PRAGMA quick_check.
- 38 named leaders, 346 career events, 9 death confirmations were read.
- Government overview, 3 observed rulers, office/planetary lists tested.
- Read-only table queries, parameterized search, schema, CSV and SQL SELECT
  against the uploaded database.
- Invalid DML/DDL and multiple statements rejected in simulated tests.
- Isolated historical-milestone function produced 116 dated entries from
  real stored leader history: 93 trait gains, 14 council changes, 9 deaths.
- Patched Python syntax and embedded Javascript syntax checked.
- Classic ZIP file layout and no-protected-file policy checked.

LIMITATIONS
The ZIP was not executed against your live Windows installation; this remains
our next test. Any missing/ambiguous historical evidence stays marked as such.
The local read-only viewer isn't a SQLite editor, and initial sidecar listing
supports the known research/civic sidecars only when their SQLite paths exist.
No GitHub changes were made.

RESTART REQUIRED: YES.
DB MIGRATION: NO.
