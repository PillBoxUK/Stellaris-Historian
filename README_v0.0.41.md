# Stellaris Historian v0.0.41

## Shared historical presentation rebuild

v0.0.41 moves the Empire Timeline and the Scribes Chronicle onto the shared Historical Event Layer introduced in earlier releases.

### What changes

- Empire Timeline now renders selected events from the shared Historical Event Layer rather than rebuilding its own combat chronology from low-level marker evidence.
- Direct and high-confidence synthesized combat episodes become the public military-history entries.
- Repetitive `last_combat_activity` marker rows remain available in the Evidence Journal and diagnostics instead of flooding the Timeline.
- Technology milestones are now represented selectively in the Timeline.
- Scribes Chapter V consumes the same synthesized combat episodes and compresses weaker combat evidence into historical summaries.
- Evolving retained combat telemetry is narrated as changing observations of the same retained battle state. It is not added together as separate casualty events.
- Unresolved generic labels such as `planet Station` are suppressed from polished Timeline/Scribes output.
- The Historical Event Layer gains richer structured attributes for combat, archaeology, projects, situations and people so presentation renderers can stay evidence-led without parsing raw saves themselves.

### Evidence rules remain unchanged

- No victory or defeat is inferred from loss counters.
- Ship disappearance is not automatically called destruction.
- Leader disappearance is not automatically called death.
- First-observed dates are not promoted to exact event dates unless the source evidence supports that claim.
- The Scribes Chronicle remains in-universe and does not knowingly use game/parser/cache terminology.

### Data safety

v0.0.41 does **not** change the database schema, domain cache component versions, campaign identity, archive folder layout, archived Ironman saves or processed-save flags.

The launcher banner is intentionally unchanged.

## Install

1. Stop Stellaris Historian.
2. Extract the v0.0.41 patch ZIP directly over the existing Stellaris Historian folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.41`.
5. Run **Review Campaign** once so the shared Historical Event diagnostic is refreshed under v0.0.41.
6. Open **Empire Timeline** and **As the Scribes Saw It** to view the rebuilt presentation.

**Restart required:** YES  
**Review Campaign required:** YES  
**Construct Campaign required:** NO
