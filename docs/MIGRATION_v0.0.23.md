# v0.0.23 Migration - Ships & Fleets Domain

v0.0.23 performs the second controlled domain extraction in Stellaris Historian.

## What moves

The old `historian/ship_fleet.py` implementation is replaced by:

```text
historian/domains/ships/
  models.py       immutable ship/fleet/shipyard/build-order snapshot contracts
  parser.py       ship, fleet, shipyard and build-queue extraction
  identity.py     logical fleet identity across changing Stellaris fleet IDs
  provenance.py   construction-date and build-location evidence rules
  history.py      ship/fleet registry and event derivation
  cache.py        ship/fleet cache serialization
  journal.py      Ships and Fleets journal section
```

Generic Paradox/Stellaris text-block helpers that were previously hidden inside `ship_fleet.py` move to `historian/core/stellaris_text.py`, so People, Worlds and Ships can share them without depending on another gameplay domain.

## Behaviour and cache compatibility

This migration is intended to change code ownership only. The ship/fleet cache component remains `ship_fleet` version `2`, so existing v0.0.22 parsed snapshot caches remain valid. A Review Campaign after migration should therefore be able to use existing cache hits rather than reparsing the archive.

The migration does not intentionally change ship names, fleet identity, build-site provenance, living-vessel handling, commissioning logic or journal wording.

## Cleanup

On first v0.0.23 launch Historian validates the new files, makes a small code backup at `backups/pre_v0.0.23_code.zip`, then removes the obsolete `historian/ship_fleet.py` and the completed v0.0.22 migration script. Disposable Python bytecode folders are also cleared.

Campaign evidence is protected. The migration does not delete or modify `data/historian.db`, archived `.sav` files, campaign folders, `backups/`, `.venv/`, or `Updates and source/`.

A log is written to `logs/MIGRATION_v0.0.23.log` and completion is recorded in `data/.migration_v0_0_23_complete`.
