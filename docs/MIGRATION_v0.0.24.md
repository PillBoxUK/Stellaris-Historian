# v0.0.24 - Worlds Modularisation

## Purpose

Move Worlds and Expansion out of the legacy `historian/world.py` module and into the domain architecture without intentionally changing historical interpretation.

## New ownership

`historian/domains/worlds/` now owns:

- `models.py` - immutable world snapshot/state contracts
- `parser.py` - planet/colony extraction, names, classes and designations
- `history.py` - world transitions and full expansion history
- `cache.py` - Worlds cache serialization
- `journal.py` - World-specific presentation helpers

The `worlds` cache component remains version `2`, so valid v0.0.23 cache data remains compatible.

## UI version label

The splash and campaign pages no longer hard-code a release number. They display the application version returned by the running Historian backend, preventing the stale `v0.0.21` label seen while v0.0.23 was running.

## Cleanup

The one-time migration validates the new modules before removing the obsolete `historian/world.py` and previous `migrate_v0_0_23.py`. A small code backup is written to `backups/pre_v0.0.24_code.zip` when obsolete files are present.

## Protected data

The migration never deletes campaign archives, `data/historian.db`, `.sav` evidence, `.venv`, `backups`, or `Updates and source`.
