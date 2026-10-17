STELLARIS HISTORIAN v0.0.84 — IMPERIAL SITUATION DASHBOARD
============================================================

BASE RELEASE: v0.0.83.1 Annual Government Census
PATCH FORMAT: Classic flat-root, preserve relative paths.

INSTALLATION
1. Turn Live History OFF and allow the current batch to complete.
2. Close Historian fully.
3. Back up G:\codex\StellarisHistorian, especially the data folder.
4. Extract every file in this ZIP into G:\codex\StellarisHistorian and
   overwrite matching application files. Do not flatten internal folders.
5. Restart using the original start.bat and check the console version 0.0.84.
6. Visit the new highlighted tile on Campaign -> Explore History or directly
   open http://127.0.0.1:8766/imperial-dashboard in a browser.

WHAT'S NEW
• New polished, responsive sci-fi Imperial Situation Room.
• Eight latest-archive readouts: population, colonies, controlled systems,
  charted systems, stations, technologies, fleets and ships.
• Six charts across historical saves: population, frontier/colonies,
  technology, fleets/ships, infrastructure, leadership roster.
• Most populous worlds; current ruler, government, ethics, civics and council.
• Recent-event feed with categories, date windows and search.
• 10/25/50/all year views, interactive chart tooltips, CSV-free client-side
  chart rendering, source coverage indicators and manual Refresh.
• Read-only 90-second polling when the dashboard tab is visible.
• No internet connection, hosted assets, cloud databases or new dependencies.
• Source-checked cached observations: original Ironman saves never parsed
  from this page, no SQLite writes, no invented missing data.

HISTORICAL EVIDENCE RULES
Population values are displayed as the raw values extracted from Stellaris
world records. Their display is intentionally not converted to 'pops' or
other units without evidence of the correct version-specific scale.
Controlled-system counts are backed by observed player-owned starbases.
Known systems are observed discovery flags, not confirmed completed surveys.
Trend gaps indicate unavailable/invalid data. Duplicate-date saves are kept
in snapshot order, not silently discarded.
Recent events are dated as in the recorded evidence; save-observed changes
are not assumed to have occurred at an exact timestamp.

The complete historical caches live in the installed campaign archive; the
standalone historian.db is not sufficient to reconstruct population charts.
For old/missing caches, Manage Campaign -> Update Historical Timeline may
help restore evidence (this is NOT required if those caches already exist).
Do NOT use Construct Campaign merely to initialise the dashboard.

IMPERIAL ANNALS
No timeline module, timeline HTML, narrative style or Scribes file is
changed. This dashboard is a separate, secondary analytical page.

DATA / INSTALLATION
No personal saves, databases, caches or config shipped in this patch.
No database schema migration. Existing campaign archives are unchanged.
No GitHub push. Restart is required to load Python routes and templates.

TESTING
python tests\test_v0_0_84.py
Runs synthetic regression checks in a temporary directory, does not modify
campaign data. Local desktop and mobile rendering tests also passed during
patch construction. The full installed Windows application requires validation.
