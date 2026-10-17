STELLARIS HISTORIAN v0.0.83.1 — ANNUAL GOVERNMENT CENSUS
==========================================================
REQUIRES: Existing v0.0.83 Government & Database Explorer installation.

WHAT'S NEW
1. OPENING GOVERNMENT CENSUS: The Imperial Annals include a dated
   government/service census from the first archived observation (normally
   2200.01.01). The founding census is placed just after the origins entry.
2. YEARLY CENSUS: A distinct 1 January entry for each game year when an exact,
   processed 1 January save and its verified leader cache are present.
   It names the ruler, governing councillors, administrators and remaining
   service leaders, their offices/assignments and traits at THAT DATE.
3. ANNUAL CENSUS PAGE: New searchable /government-census with year selector,
   categories, names, assignments, traits and provenance. Its linked section
   is reachable from the annual entry's related-archive link.
4. CAMPAIGN LIBRARY: A new Annual Government Census tile under Explore History;
   a navigation link also appears in Government & People and the Annals.

EVIDENCE RULES
- Uses only the matching year's exact-date processed leader cache, never a
  current/latest leader registry row projected into earlier years.
- Checks save SHA, archive size, mtime, cache component version and dated
  leader snapshot before publishing. Different captures on the same game
  date are not assumed duplicates; uses the final archived state that date.
- Trait and post information refers to the archive's state on that date.
  Absence in later years does NOT prove death or resignation.
- For non-January campaigns, the opening census follows the earliest retained
  date; other year records require an exact 1 January snapshot.
- Missing/incompatible caches are flagged as unavailable on the census page,
  rather than filled in from later dates or fabricated.
- No reparse, migration, or change to save watchers or combat processing.

COMMONWEALTH EXPECTATIONS
The uploaded Commonwealth historian.db contains 521 processed saves and an
EXACT 1 January observation for ALL 128 years, 2200 through 2327.
Actual available censuses depend on the existing .historian_cache files being
present on the Windows PC with matching source saves. The uploaded database
alone cannot reconstruct every historic trait/office state: it stores a
leader's latest profile and selected changes, not every annual full roster.

INSTALLATION (CLASSIC FLAT-ROOT ZIP)
1. Turn Live History OFF and wait for processing to finish.
2. Close Historian completely (including the console).
3. Back up the installation and the data folder.
4. Extract this ZIP INTO G:\codex\StellarisHistorian, not into historian/.
5. Overwrite matching files. Do not delete any existing files.
6. Run the ORIGINAL start.bat, confirm v0.0.83.1.
7. Visit Explore History > Annual Government Census or the direct local URL:
   http://127.0.0.1:8766/government-census
8. Open Empire Timeline; the dated censuses are generated automatically.
   No full reconstruction is needed unless caches were previously cleaned.

LIMITS AND TESTING
- Synthetic integration tests: exact 1 January, opening roster, same-day
  distinct captures, changed traits, council and planetary assignments,
  missing year, campaign isolation, stale cache refusal.
- HTML/Javascript syntactically checked, browser rendered and selection tested.
- Python modules compiled; patch ZIP installation overlay validated.
- Cannot run against the live Commonwealth save caches on your Windows PC.
- This patch does NOT add a new SQLite census table. It derives historical
  rosters from the existing hash-indexed per-save evidence caches.
- Caches missing after cleanup? Rebuild using Update Historical Timeline.
- SQLite and campaign archives are not modified by any census view.

RESTART REQUIRED: YES (close and restart via start.bat).
DATABASE MIGRATION: NONE.
HISTORY REBUILD: NOT REQUIRED if pre-existing source caches still match.
GITHUB: NOT PUSHED.
