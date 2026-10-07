# Stellaris Historian v0.0.48

This patch refines the v0.0.47/0.0.47.1 Politics & Diplomacy feature after live testing against the Commonwealth of Man and the 299-save Sutharian Convocation 4 archive.

## What changes

- Routine `council_agenda_progress` changes remain retained in structured SQL/diagnostics but are no longer published as historical events.
- Actual council-agenda identity changes remain publishable and get clearer readable titles.
- Strong pseudo-country / event-entity relation records are retained internally but filtered out of public diplomatic history.
- Politics & Diplomacy summary values use installed Stellaris/mod localisation where available, with a readable fallback.
- Fixes `Event_Character_Probe_Debug.txt` failing with `too many values to unpack (expected 8)` after the Politics cache component was added.
- Fixes the Python invalid-escape warning for the Politics diagnostic path.
- Review Campaign and Construct Campaign now report numbered refresh progress and timing, for example `REFRESH [04/05] Politics_Diplomacy_Probe_Debug.txt...`.
- The Politics/Diplomacy deep probe reports inner sample progress while it scans raw saves.
- Live History now logs when `Historical_Journal.html` has actually finished refreshing.

## Safety

The migration does not modify or delete archived Stellaris `.sav` files. Existing source files changed by the migration are backed up under `backups/v0.0.48/` before replacement.

Existing Politics/Diplomacy database rows are conservatively cleaned so old agenda-progress spam and the strongest pseudo-country records stop appearing publicly immediately. A later Review Campaign rebuilds the Politics/Diplomacy history completely using the v0.0.48 rules.

## Installation

1. Close Stellaris Historian completely.
2. Extract this patch into the Stellaris Historian folder, replacing `start.bat` when asked.
3. Run `start.bat`.
4. The one-time v0.0.48 migration runs automatically.
5. After the app starts, run **Review Campaign** on Sutharian Convocation 4 to rebuild and validate the refined Politics/Diplomacy history.

## Restart requirement

**A full Historian stop/restart is required.** The patch changes Python source, the launcher, migration state, diagnostic generation and public-history filtering. It does not take effect in an already-running Historian process.
