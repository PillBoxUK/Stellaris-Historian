STELLARIS HISTORIAN v0.0.89 — EDITORIAL, INTELLIGENCE & PRINT RELEASE
by PillBoxUK | Source-only overlay for v0.0.88

WHAT IS INCLUDED
1. FOUR-YEAR GOVERNMENT CENSUSES — the Imperial Annals now contain the
   opening census, every four years where the exact archived January roster
   exists, and extraordinary source-backed censuses after established political
   upheavals. The detailed Government Census page still retains every year.
2. GROUPED SERVICE MILESTONES — one dated entry for all people reaching the
   same service anniversary, with names and roles; each person's original
   fingerprint trail remains in the evidence notes and census history.
3. INTELLIGENCE REGISTER — new /intelligence-history page, showing SHA-linked
   player-owned saved network structures. A passive network is NOT an active
   spy operation; raw foreign identifiers are not invented country names.
4. BRITISH ENGLISH — human-readable dates (1 January 2202), 'an avian',
   'an executive committee' and more natural trait/ranked-skill descriptions.
5. PRINT/PDF LEGIBILITY — dark theme no longer forces dark-background event
   blocks onto white paper. Duplicate People of Note cards are hidden ONLY
   in print, not deleted from the main historical evidence.
6. Added tests, roadmap entry, versioned manifest and launcher checks.

EVIDENCE POLICY
No screenshots, hand-entered events or assumptions are historical facts.
No claims of riot outcomes, deaths, spy operation results or battle victories
are made by these changes. Existing save/SQLite/caches are not packaged.

INSTALL — HISTORIAN MUST BE RESTARTED
1. Stop Live History in the Historian dashboard and wait for all processing to
   finish. Close Historian fully. Stellaris may remain open or paused.
2. Back up your SOURCE directory, historian.db and campaign archive.
3. Extract this ZIP's contents directly into:
   G:\codex\StellarisHistorian\
   Overwrite matching program/source files; DO NOT create a nested folder.
   DO NOT delete data, .venv, saves or old archives.
4. Run start.bat and confirm the console reads v0.0.89.
5. Select your civilisation and choose YES to start Live History. Always check
   that the dashboard actually reports Live History: ON.
6. To BACKFILL historic intelligence network observations, turn Live History
   OFF, let processing finish, select Manage Campaign > Update Historical
   Timeline, allow the safe non-destructive audit/rebuild to finish, then turn
   Live History ON again. Existing native evidence is preserved.
7. Open Imperial Annals to see grouped anniversaries and four-year censuses;
   open Intelligence in the Annals navigation to inspect the network register.
8. To make a PDF, use Print/PDF. In browser printing, disable browser
   'Headers and footers', set Destination = Save as PDF, and inspect a page.

TESTS
23 automated tests and 15 subtests passed on the provided code fixture.
One older Ironman save was smoke-tested as a read-only intelligence parser
input. Its passive network was NOT promoted into an invented operation.
The browser-print CSS was statically verified; a complete Windows Opera PDF
render has NOT been performed here.

DATA SAFETY
No user savegame, historian.db, campaign archive, configuration, or token is
included. No main-database migration. Civic sidecar parser v4 is additive and
can still read existing v1/v2/v3 records. Native Ironman files never rewritten.

RESTART HISTORIAN: YES, use start.bat after install.
RESTART STELLARIS: NO.
GITHUB: This ZIP is GitHub-ready source; no remote push is included.
