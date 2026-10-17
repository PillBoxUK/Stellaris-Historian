# Historical evidence and publication contract

**Primary authority:** original Ironman save files and traceable database evidence extracted from them. The database preserves the facts; the analytical pages investigate them; the Imperial Annals tell the story.

| Evidence | Permitted use |
| --- | --- |
| Exact native saved event | Publish at the directly supported date with qualified typed references |
| Direct snapshot state or transition | Publish supported transition, conservatively bounding unknown occurrence time |
| First observed in a later snapshot | First-observed language, **never** an invented exact occurrence date |
| Contextual correlation or suspected outcome | Forensic/diagnostic only unless an exact unique join validates it |
| Game files and localisation | Explain story context, meanings and possible paths; not event occurrence |
| **Screenshot or player recollection** | UI testing / investigation only; **not historical proof** |

## Preserve provenance
For every published historical fact, keep campaign ID, save SHA-256, date meaning, observation window, event/definition key, typed actor/target ID, raw value, extractor version and supporting database row/cache reference. Do not invent exact dates, counterpart identity, combat results or motives.

## Parser and chronology
- Preserve Clausewitz repeated keys and ordered objects; do not flatten away distinct entries.
- Stellaris game years are **360 days**, not Gregorian years, when computing game elapsed dates.
- Sort repeated-date archives by secondary capture order; equal dates do not make identical saves.
- `id=none` and dead-object placeholders are not proof of an entity's death or destruction; invalid sentinels are not real identities.
- Native war-win events give an outcome but not necessarily a unique war ID; correlate carefully with participants and windows.
- War exhaustion percentages and current war existence alone do not prove a victory.
- Policy permission is not proof that a permitted action occurred.
- A leader first observed entering service was not necessarily born then. Distinguish recruitment, appointment, assignment, promotion, trait changes and death.
- Publish major evidenced changes immediately; routine government **census** every four years is an editorial layout rule, not a game-election fact.
- No timeline event may be imported from screenshots, even when it matches a save by chance.

## Output boundaries
**Imperial Annals:** vivid, fluent, chronological prose whose content is fully visible without opening a card. **Research pages:** statistics, provenance, tables, uncertainties and diagnostics. **Database:** detailed recoverable observations.

Reference: https://deonchapman.co.uk/codex/Stellaris/Historian_Documentation/Ironman.html