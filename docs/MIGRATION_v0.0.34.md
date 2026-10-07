# Migration v0.0.34 - Combat Activity Evidence

v0.0.34 extends the Combat cache contract from version 1 to version 2.

## Added evidence

- exact `last_combat_activity` dates for player mobile ships
- exact `last_combat_activity` dates for player starbase station ships
- first-observed fleet, commander and system context for ship markers
- first-observed system context for starbase markers

The exact combat date comes directly from Stellaris. Contextual fields are deliberately labelled as snapshot observations and are not treated as proof of the battle location, commander or fleet at the exact combat moment.

## Cache behaviour

Existing cache containers remain valid. Because only the `combat` component version changes, the first Review Campaign or Construct Campaign extends that component while preserving valid Ships, People, Worlds and Science cache components.

## Safety

- no database schema changes
- no archived saves are changed or deleted
- no processed flags are reset
- no combat events are published into the Historical Journal yet
- ship/fleet disappearance remains insufficient evidence of destruction

Restart Stellaris Historian after applying the patch.
