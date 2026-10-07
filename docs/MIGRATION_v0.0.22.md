# v0.0.22 Migration

This is a one-time code-layout migration.

## Installation

1. Close Stellaris Historian.
2. Extract the v0.0.22 patch into the existing `StellarisHistorian` folder and allow files to be replaced.
3. Run `start.bat` normally.
4. On the first start, `start.bat` runs `migrate_v0_0_22.py` before launching Historian.

The migration validates the new Python files before deleting anything. It also creates a small backup of obsolete code/documentation in `backups/pre_v0.0.22_code.zip` when those files exist.

## What is removed

Only the explicit legacy files listed in `migrate_v0_0_22.py` are removed. This includes the old `historian/leader.py`, which is replaced by `historian/domains/people/`, and accumulated step README files in the application root that are superseded by the consolidated `docs/` documentation.

Python `__pycache__` folders are also removed because they are disposable and will be regenerated automatically.

## What is protected

The migration does not delete or alter:

- `.venv/`
- `data/`
- `data/historian.db`
- archived `.sav` files
- `backups/`
- `Updates and source/`
- campaign journals/debug output

A migration log is written to `logs/MIGRATION_v0.0.22.log` and a completion marker is stored under `data/` so the cleanup is not repeated on every launch.

## Validation target

For the Sutharian Convocation 4 test campaign immediately before this migration, Historian reconstructed approximately 58 historical ships, 37 fleets, 15 leaders and 3 worlds. v0.0.22 should reproduce those same results before further feature development.
