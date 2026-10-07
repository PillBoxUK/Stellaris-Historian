# v0.0.31 Migration - Ship Refit History

This release adds conservative ship refit/upgrade history to the modular Ships domain.

## What changes

- Adds `historian/domains/ships/refits.py`.
- Compares stable ship identities across adjacent archived snapshots.
- Preserves every ship design-ID transition internally as raw evidence.
- Groups two or more simultaneous design changes in the same named fleet into one public fleet-refit journal event.
- Publishes a single-vessel refit event when a safe group cannot be formed.
- Excludes living vessels and ship-class/size transformations from public refit interpretation.
- Does not infer exact weapons, armour, utilities or other component changes yet.

## Cache impact

The Ships cache stays at `ship_fleet` version `2`. Existing cached snapshots already contain ship design IDs, so a Review Campaign can reconstruct historical refit evidence without reparsing every `.sav` file.

## Data safety

The migration does not alter archived saves, `historian.db`, parsed snapshot caches or processed/unprocessed flags. It only validates the new code, removes the obsolete previous migration helper, clears disposable bytecode and writes the migration marker/log.
