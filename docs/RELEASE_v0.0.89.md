# Stellaris Historian v0.0.89 — Editorial, Intelligence & Print

**Author:** PillBoxUK. **Base:** v0.0.88.

The Imperial Annals is the flagship narrative. This release changes only
presentation and a dedicated campaign-local intelligence evidence sidecar;
it does not alter the canonical archive or SQLite historical event data.

## Changes

- Opening/four-year/extraordinary exact-January government census publishing.
  Annual source evidence remains accessible in the full census explorer.
- Same-duration, same-date career anniversaries grouped in the Annals, without
  erasing individuals' evidence trails or implying unbroken service.
- Native player-owned `spy_networks` retained under a new read-only
  `/intelligence-history` register. Automatic/passive network records are
  classified honestly; no operations, choices, target identities or outcomes
  are fabricated. Record hashes attach to saved observations.
- British English date presentation and correct indefinite articles for
  founding species and government names.
- High-contrast, white-background print rules applied even when the reading
  theme is dark. Duplicate People of Note cards are suppressed only on paper.
- Launcher and release version aligned to `0.0.89`, roadmap updated and
  regression tests extended.

## Verification

- `PYTHONPATH=. pytest -q tests`: **23 passed, 15 subtests passed**.
- Python compilation succeeded.
- A historic user-supplied Ironman archive was read (not modified) to
  smoke-test player-ownership scoping for spy networks.
- Complete browser print/PDF rendering is not verified on Windows Opera; the
  print stylesheet and source-level checks passed.

## Safe installation

Stop Historian and its Live History worker; save and back up local source and
SQLite, overlay ZIP files on top of v0.0.88, and restart `start.bat`. No need
to stop/restart Stellaris. Use existing **Update Historical Timeline** to
backfill native spy-network observations in the v4 civic ledger, then re-enable
Live History.

The source ZIP has **no campaign saves, credentials, config, databases or
other user-local data**. No GitHub push is performed by packaging this patch.
