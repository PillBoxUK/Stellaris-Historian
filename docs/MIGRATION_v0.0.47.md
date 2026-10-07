# Migration v0.0.47

## Purpose

v0.0.47 adds the opt-in Live History worker and promotes conservative Politics/Diplomacy evidence into a structured cached/history domain.

## One-time migration

`migrate_v0_0_47.py` is run automatically by `start.bat` when:

`data/.migration_v0_0_47_complete`

does not yet exist.

The migration:

- changes the application version to 0.0.47
- adds `politics_states` and `politics_history_events` database tables
- integrates `politics_diplomacy` cache component v1
- integrates incremental, Review Campaign and Construct Campaign Politics/Diplomacy processing
- integrates visible Politics/Diplomacy events into the shared Historical Event Layer
- adds the Live History API/worker and dashboard toggle
- updates documentation, manifest and changelog

## Safety

The migration does not delete or rewrite archived Stellaris `.sav` files.

Before changing an existing source file, the migration writes the original version under:

`backups/v0.0.47/`

Existing parsed cache containers are not deleted. They are extended with the new Politics/Diplomacy component when first needed.

## Live History behaviour

Live History defaults to OFF on application start and whenever a campaign is selected.

When enabled, it watches the database for newly archived unprocessed saves, processes them through the ordinary incremental history pipeline, and refreshes `Historical_Journal.html`.

If processing fails, Live History disables itself and reports the error instead of repeatedly retrying the same failure.

Manual Update History, Review Campaign and Construct Campaign are blocked while Live History is ON.

## Post-migration action

No Construct Campaign or full cache rebuild is required.

For a new/current Commonwealth live test, simply enable Live History and continue playing.

Run Review Campaign only if you want structured v0.0.47 Politics/Diplomacy evidence rebuilt across older archived saves.
