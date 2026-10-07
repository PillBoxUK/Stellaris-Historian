# Stellaris Historian v0.0.40
## Combat Episode Synthesis + Clean Historical Events

v0.0.40 adds a historical layer above raw combat markers without weakening Historian's evidence rules.

### Combat Episode Synthesis

Historian now builds `CombatEpisode` records from direct fleet combat telemetry plus compatible exact combat-activity markers. A direct telemetry event can be extended by later activity only when location/fleet context and temporal continuity support treating the records as one episode.

This is intended to turn evidence such as repeated 2241 fighting in one system into a coherent historical episode while keeping every underlying date available in diagnostics.

### Mutable combat telemetry

Retained `combat_stats` values can change in later saves. v0.0.40 preserves those observations over time instead of silently treating the latest counter as if it were the only state ever recorded.

`Combat_Episode_Debug.txt` shows:

- episode start/end dates
- direct combat dates
- exact activity dates
- system, fleets, commanders and opposing force where directly supported
- first/later retained loss observations
- whether telemetry changed
- formal outcome only when a formal battle record actually establishes one
- nearby ship disappearances only as possible losses

Loss counters alone never establish victory or defeat.

### Historical Event Layer cleanup

`HistoricalEvent` now supports structured attributes and receives synthesized combat episodes rather than dumping every publishable combat marker into the common event stream.

The event layer also removes renderer/game voice such as `Stellaris records...` and avoids exposing generic `planet Station` participants in historical event prose. Low-information marker-only combat remains available in diagnostics rather than cluttering the historical stream.

Leader event importance mappings were corrected to the actual People-domain event names, so ruler transitions, service entries and unconfirmed leader exits can be ranked properly for future Timeline/Scribes presentation.

### Leader exit / death evidence probe

`Leader_Exit_Evidence_Debug.txt` audits leaders who disappear from the archived player-leader record. The current normalized evidence proves disappearance only. It does **not** invent a death, execution, dismissal, exact death date or cause unless future raw evidence explicitly supplies it.

This is important for cases where the player sees an on-screen death notification but the surviving saves may retain only the leader's disappearance.

### Cache / database behaviour

- No database schema changes.
- No cache component version changes.
- No archived saves are renamed or deleted.
- No processed flags are reset.
- Existing Evidence Journal and Scribes presentation code remains in place.

### Install

1. Stop Stellaris Historian.
2. Extract this ZIP over `G:\codex\StellarisHistorian\`.
3. Run `start.bat`.
4. Let the one-time v0.0.40 validation complete.
5. Run **Review Campaign** once.
6. Inspect the campaign `diagnostics\` folder, especially `Combat_Episode_Debug.txt`, `Leader_Exit_Evidence_Debug.txt`, and `Historical_Event_Debug.txt`.

**Restart required: YES.**  
**Review Campaign required: YES** to generate/rebuild the v0.0.40 episode/event diagnostics for existing archives.
