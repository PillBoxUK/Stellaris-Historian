# Migration v0.0.54 — Processed Combat Diagnostic Synchronization

## Purpose

v0.0.54 closes a live-testing gap found during the Commonwealth of Man / Hulfiran war. Normal History processing was already capturing formal-war and battle evidence in the persistent snapshot cache, but the forensic combat diagnostics could remain frozen at the snapshot count from the last full Review Campaign.

The migration adds a lightweight catch-up path for the three combat diagnostics without forcing a full archive review.

## Changed behaviour

After normal History processing reaches a zero-length queue, Historian can regenerate:

- `diagnostics/Combat_Evidence_Debug.txt`
- `diagnostics/Combat_Correlation_Debug.txt`
- `diagnostics/Combat_Episode_Debug.txt`

The synchronization reads **processed snapshots only** and uses the persistent parsed cache only.

### Cache-only safety rule

The new diagnostic synchronization never reparses raw `.sav` files. If any processed snapshot is missing a current required cache component, the synchronization aborts before replacing the existing combat diagnostic files. The console reports the problem and recommends **Review Campaign** as the repair/deep-forensics path.

### Manual Update History

When the History queue is zero, pressing **Update History** runs the combat diagnostic synchronization even if there are no new saves to process. This allows an existing campaign to catch its combat diagnostics up immediately after installing v0.0.54.

### Live History

Live History retains the queue-first behaviour introduced in v0.0.53. It processes archived saves first and runs the combat diagnostic synchronization only after the queue is caught up. First Contact and journal refreshes remain downstream of normal History catch-up.

### Presentation snapshot scope

The cached-evidence reader shared by War Journal, Empire Timeline and Scribes Chronicle now reads only snapshots that completed normal History processing. A newly archived but still-unprocessed snapshot can therefore no longer leak into those presentations.

## Data migration

There is no database or save-data migration in v0.0.54.

The migration does **not**:

- alter archived Stellaris saves;
- rewrite processed flags;
- change the SQLite schema;
- bump parsed-cache component versions;
- clear or rebuild the campaign cache.

Source files changed by the one-time migration are backed up under `backups/v0.0.54/` before modification.

## Restart requirement

A restart is required after installing the patch because `start.bat`, application code and migration logic change.

No full cache rebuild is required.

## First live test

For a caught-up campaign:

1. Start v0.0.54 and select the campaign.
2. Leave Live History OFF for a controlled test.
3. Press **Update History** once, even if there are zero waiting saves.
4. Confirm the console prints `COMBAT DIAGNOSTIC SYNC COMPLETE` with the current processed snapshot count.
5. Confirm the three combat diagnostics use the current processed archive rather than the previous Review Campaign snapshot count.

If the cache-only synchronization reports a missing/stale processed cache, do not delete data. Run **Review Campaign** to repair/rebuild deeper forensic evidence.
