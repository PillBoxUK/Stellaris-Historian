# Stellaris Historian v0.0.38
## Combat Reconstruction + Historical Event Layer

v0.0.38 returns to the core Historian problem: reconstructing what actually happened from the evidence retained across Ironman saves.

### Direct combat evidence
Historian now reads player fleet `combat` / `fleet_stats.combat_stats` records when Stellaris retains them. These can directly preserve:
- exact combat start date;
- player fleet and commander;
- system identity/name where resolvable;
- opposing country and fleet;
- player fleet ship count and recorded ship losses;
- opposing fleet ship count and recorded ship losses.

This evidence is stronger than `last_combat_activity` alone and is published to `Combat_Correlation_Debug.txt` before being trusted by higher-level narrative views.

### Correlation
Historian also groups exact ship/starbase combat dates and compares the surrounding archived snapshots. Ship disappearances are recorded only as **possible losses** unless stronger evidence proves destruction. Relation `killed_ships` counters are preserved in both directions without guessing what each direction means.

### Historical Event Layer
`Historical_Event_Debug.txt` is a new presentation-neutral event stream. It normalizes supported empire, colony, leader, naval, science, technology and combat events with source/confidence/date-kind metadata. Future Timeline and Scribes work can consume one common historical layer instead of each presentation independently reinterpreting raw evidence.

### Scribes Chronicle
The military chapter now gives precedence to direct fleet combat rolls. Where preserved, the Chronicle can name the opposing force, participating formations, commanders, system and recorded fleet losses. It still does **not** invent a victory, defeat, battle name, motive or wider war when no surviving evidence establishes one.

### Cache behaviour
- Combat cache advances from v2 to v3.
- People, Ships, Worlds, Science and Technology caches remain valid.
- Run **Review Campaign once** after installation so each archived save is extended with Combat v3.
- No database schema change, archive deletion or processed-flag reset is performed.

### Install
1. Stop Stellaris Historian.
2. Extract this patch over `G:\codex\StellarisHistorian\`.
3. Run `start.bat`.
4. Run **Review Campaign** once.
5. Inspect `Combat_Correlation_Debug.txt` and `Historical_Event_Debug.txt` before treating newly reconstructed engagements as final history.

**Restart required: YES.**
