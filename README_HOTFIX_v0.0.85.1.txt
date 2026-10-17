STELLARIS HISTORIAN v0.0.85.1 — RECORDING CONFIRMATION HOTFIX
by PillBoxUK

REQUIRES existing Stellaris Historian v0.0.85.
Do NOT apply this to older versions or to another application's folder.

WHAT CHANGES
- Selecting ANY civilisation from the Ironman campaign chooser leaves Live History OFF
  and causes an unavoidable YES/NO popup on the campaign page.
- YES: enables Live History for this selected campaign and starts processing its
  already archived, unprocessed saves by the existing background worker.
- NO: leaves Live History disabled and displays a persistent, conspicuous warning.
- OFF status remains visible whenever Live History is disabled, including if it
  stops unexpectedly or after the user turns it off manually.
- A dashboard button reopens the YES/NO confirmation without changing campaigns.
- Switching civilisation creates a brand-new pending confirmation.
- The backend verifies the campaign ID supplied with the choice and rejects stale
  confirmations from earlier selections.
- Existing manual Live History button remains fully functional.
- If the local status endpoint fails, the banner announces that recording cannot
  be verified, rather than silently assuming success.

HOW TO INSTALL
1. Turn Live History OFF and wait for any busy history processing to finish.
2. EXIT HISTORIAN COMPLETELY, closing its console window or Python process.
3. Back up your ENTIRE Historian application folder, especially the data/ folder.
4. Extract this zip into G:\codex\StellarisHistorian\ (or your actual project root).
   Preserve paths and OVERWRITE matching application files.
   Don't extract into a newly nested folder.
5. Restart Historian via start.bat and confirm the banner reads v0.0.85.1.
6. Select a civilisation from the campaign chooser.
   Verify the large popup asks whether to start recording.
   Choose YES to begin Live History, or NO to retain the persistent warning.

IMPORTANT
- Historian must be RESTARTED with start.bat. Refreshing only the browser is
  INSUFFICIENT: this hotfix changes Python routes and their in-memory states.
- Stellaris itself does NOT need restarting.
- This hotfix does NOT create missing historical records, reprocess existing
  data, rebuild the timeline, change census logic, or repair archive gaps.
- A later save does not necessarily preserve events missed in earlier saves.
- The Ironman archives and the historian.db evidence database remain the source
  of truth; screenshots and exported PDFs are not campaign evidence.
- Live History OFF does not itself stop the watcher from making raw save archives.
  It stops automatic historical processing; missing intervals may be unrecoverable.
- App restarts forget the selected campaign and will require selecting it again,
  which triggers a fresh recording confirmation.

FILES REPLACED
 app.py
 historian/__init__.py
 historian_manifest.json
 start.bat
 static/campaign.html

FILES ADDED
 static/recording-guard.css
 static/recording-guard.js
 tests/test_v0_0_85_1.py
 tests/test_recording_guard_v0_0_85_1.js
 documentation/release_notes/README_v0.0.85.1.md

TESTS RUN ON THE ISOLATED PATCH TREE
 PASS python tests/test_v0_0_85_1.py
 PASS node tests/test_recording_guard_v0_0_85_1.js
 PASS python -m py_compile app.py
 PASS node --check static/recording-guard.js
 Existing v0.0.84/v0.0.85 integrated fixture tests require full application
 files (e.g. historian.local_database_browser) not included in the previously
 distributed incremental patch zips. Full installation-level test is pending.

NO DATA/ DB/ ARCHIVE/ MIGRATION/ CACHE/ USER SAVE FILES INCLUDED.
NO SCRIPT IS NEEDED TO REBUILD OR ALTER YOUR HISTORICAL DATA.
NO GITHUB PUSH WAS PERFORMED.
