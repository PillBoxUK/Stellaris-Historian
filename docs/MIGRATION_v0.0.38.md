# Migration v0.0.38 - Combat Reconstruction + Historical Event Layer

## Purpose
Extend the Combat domain from exact entity activity markers to stronger direct fleet-combat evidence and conservative cross-snapshot correlation.

## Data safety
This migration does not delete or rewrite archived saves, reset processed flags, or change the SQLite schema.

## Cache change
- `combat` cache component: v2 -> v3
- all other component versions unchanged

The first Review Campaign after installation therefore extends the Combat component for archived snapshots while reusing valid Ships, People, Worlds, Science and Technology components.

## New diagnostics
- `Combat_Correlation_Debug.txt`
- `Historical_Event_Debug.txt`

## Evidence rules
- Direct `combat_stats` fields are treated as direct evidence for the fields they explicitly preserve.
- A direct fleet loss counter does not by itself establish victory/defeat or the wider political cause of the fighting.
- `last_combat_activity` remains exact date evidence only.
- Same-date grouping is a reconstruction and carries correlation confidence.
- A disappearing ship is a possible loss, never automatically a destroyed ship.
- Relation `killed_ships` values are retained in both directional records; their semantic direction is not guessed in v0.0.38.
