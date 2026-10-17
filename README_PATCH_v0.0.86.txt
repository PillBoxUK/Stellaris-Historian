STELLARIS HISTORIAN v0.0.86 — THE VERIFIED MILESTONES UPDATE
by PillBoxUK | Package prepared 17 October 2026

REQUIRES: an existing and working v0.0.85.1 installation.
DO NOT apply directly to an older version. Incremental patch overlay only.

WHAT THIS PATCH DOES
1. IMPERIAL ANNALS
   - Marks eligible, already-evidenced accomplishments with a golden MILESTONE tag.
   - Adds an interactive "Milestones" subject filter, including #milestones deep link.
   - Preserves the full event narration in the timeline and independent evidence
     plus dating limitations in the detail popup.
   - Recognises attested 1/5/10/15/20/25/50/75/100/150/200-year leader
     service spans from exact, hash-matched 1 January government censuses.
   - Ruler and council one-year spans receive their own timeline entries;
     longer spans are published for any leader. Shorter service spans for
     other people remain visible in the Annual Government Census register.
   - Publishes supported leader professional level gains already present in
     leader_career_events as a separate career development, not a victory.
2. PEOPLE & GOVERNMENT
   - Dated census profiles show verified service-anniversary labels.
   - Read-only career highlights include newly observed traits, advancement
     levels, and council appointments from actual leader_career_events.
   - Highlights stop at each census date. A future appointment or trait is
     never retrospectively inserted into an earlier year's biography.
   - A missing/unprocessed/invalid exact annual census interrupts the span.
   - The app NEVER assumes continuous employment between two observed saves.
3. PROFESSIONAL PRESENTATION
   - Imperial Annals, active Campaign and Annual Government Census get a
     project footer with author credit, the source repository, and a fan
     project disclaimer. Timeline offers print/PDF help.
   - A print margin footer gives a repeatable source credit in Chromium that
     supports CSS margin boxes; links in the document footer are clickable.
   - For no duplicate browser-added print headers/footers, users must untick
     "Headers and footers" in Chrome/Opera Print > More settings. CSS cannot
     guarantee changing a viewer's browser print preferences.
   - The timeline still has one canonical book-style heading. The browser's
     date/title/URL lines are independent of the webpage's own heading.

CRITICAL EVIDENCE RULES
- Campaign-specific claims are derived only from saved Ironman evidence,
  its matching parsed caches, and pre-existing Historian database records.
- NO screenshots, PDF exports, user recollections, or general game lore are
  treated as evidence that an event happened in this campaign.
- A 1-year or 5-year milestone means the SAME leader ID is present in ALL
  annual January rosters spanning those dates. It does NOT prove they were
  continuously in office between saves or joined exactly at the first census.
- Traits/level changes with first-observed dates are narrated as "By...",
  never as if the date of the actual promotion is exactly known.
- Milestone tags are a presentation classification of existing dated events,
  not independent new factual assertions.

INSTALLATION — NO MANUAL MIGRATIONS OR SCRIPTS REQUIRED
1. Turn Live History OFF, wait for the processing worker to become idle,
   and completely EXIT Stellaris Historian (console/Python process closed).
2. Back up your entire installation first, particularly the data directory
   and historian.db. Do not overwrite your evidence database with old copies.
3. Extract this ZIP INTO the existing Historian root, for example:
       G:\codex\StellarisHistorian\
   Choose overwrite/replace for matching files. Do not create a nested folder.
4. Restart the application with start.bat. Confirm v0.0.86 appears.
5. Select the campaign and choose YES in the recording-confirmation dialog
   if you want Live History enabled, as introduced in v0.0.85.1.
6. Open Empire Timeline. Existing processed saves are read and the timeline
   is generated anew. Choose "Milestones" to focus the history.
7. Open Annual Census to review exact-year badges and career highlights.
   To make a clean PDF: Print > More settings > untick "Headers and footers".

RESTART REQUIRED: YES — close Historian and restart with start.bat.
Restarting Stellaris itself: NO.

DATA SAFETY
- No migration, deletion, reprocessing, overwrite or alteration of the
  source .sav files, database, caches, or campaign archives is performed.
- This ZIP contains no database, user saves, logs, cached snapshots or
  screenshots and does not alter stored historical evidence.
- Does not reconstruct historical events missing from the Ironman saves.
- Does not alter the recording YES/NO guard or Live History scheduling.
- GitHub repository was NOT modified or pushed by this ZIP creation.
- This public GitHub repository appears not to include a licence file.
  Publicly accessible source is not necessarily legally open-source; choose
  and publish an appropriate licence separately before claiming that status.

VALIDATION PERFORMED (ISOLATED V0.0.85.1 PATCH BASE)
PASS Python syntax compilation for changed Python and app modules.
PASS v0.0.86 synthetic verified-span, missing-census and invalid ID tests.
PASS v0.0.86 synthetic read-only career highlights and date cutoff tests.
PASS v0.0.86 complete HTML timeline renderer smoke test with fake campaign.
PASS extracted canonical timeline JavaScript node --check.
PASS v0.0.85.1 backend recording-confirmation regression suite.
LIMITATION: End-to-end execution against an actual user's full Windows
installation and real campaign is untested; these patch-source directories
exclude several older, unchanged imported modules. Test a backed-up copy first.

PATCH FILES
 historian/__init__.py
 historian/timeline.py
 historian/annual_census.py
 historian/verified_milestones.py (new)
 historian_manifest.json
 start.bat
 static/campaign.html
 tests/test_v0_0_85_1.py (version-compatible test expectation)
 tests/test_v0_0_86.py (new)
 documentation/release_notes/README_v0.0.86.md (new)
 README_PATCH_v0.0.86.txt (new)
 SHA256SUMS_v0.0.86.txt
