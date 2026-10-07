# v0.0.28 Science Evidence Foundation

This release adds the first modular Science / Expeditions evidence collector.

## What changes

- Adds `historian/domains/science/`.
- Adds a versioned `science` component to the persistent parsed-snapshot cache.
- Collects player-relevant archaeological-site evidence, active special projects,
  player situations, and active anomaly IDs.
- Links archaeology and some projects to known ships/scientists when the save
  contains enough evidence.
- Review Campaign and Construct Campaign write `Science_Evidence_Debug.txt`
  beside the campaign journal.
- Console progress now shows Dig sites / Projects / Situations counts.

## Deliberate limitation

v0.0.28 does **not** publish science/sidequest stories into the Historical Journal.
The collector is intentionally evidence-first. The diagnostic file lets us see
what Stellaris actually preserves across the surviving archive before deciding
which transitions can be narrated without inventing outcomes.

## Cache behavior

Existing v0.0.27 cache files remain reusable. On the first Review Campaign under
v0.0.28, old cache containers should normally show `CACHE EXTEND`: Historian
keeps the existing profile/Ships/People/Worlds components and reads each raw save
once to add Science v1. After that, another Review should return cache hits.

No archived `.sav` file, campaign database record, or processed/unprocessed flag
is removed or reset by this migration.
