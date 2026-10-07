# Migration v0.0.32 - Refit Publication Cleanup

This migration is code-only and does not alter campaign evidence.

## What changes

- Every stable ship design-ID transition is still retained internally.
- Public refit publication is made selective to reduce journal noise.
- Multiple named military fleets modernising in one interval can be collapsed into one naval-modernisation event.
- Two or more ships in one named military fleet can be collapsed into one fleet-refit event.
- Three or more support vessels refitting together can be collapsed into one support-fleet event.
- Isolated major military hull refits may remain public; routine single-corvette and support-vessel refits remain internal evidence only.
- Console review summaries now distinguish raw refit evidence from published refit events.

## Safety

- `data/historian.db` is not deleted or migrated.
- Archived `.sav` files are not modified.
- Snapshot processed flags are not changed.
- Ships cache remains `ship_fleet` component version 2.
- Review Campaign can regenerate the cleaner publication layer from existing cache hits.
