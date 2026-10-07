# Stellaris Historian v0.0.37
## Expanded Scribes Chronicle + Technology Evidence

This patch returns Historian to evidence collection while also making **As the Scribes Saw It** read like a fuller historical work.

### New evidence
- Added modular `historian/domains/technology/` evidence collection.
- Reads completed technologies from the player country `tech_status` record.
- Opening technologies are treated as inherited knowledge, not discoveries of 2200.01.01.
- A technology that first appears between archived snapshots is recorded as acquired **after the previous archive and by the current archive**; the exact completion day is not invented.
- Research queue entries are excluded until they become completed technology entries.
- Review/Construct writes `Technology_Evidence_Debug.txt`.

### Scribes Chronicle expansion
- Added a substantial military-history chapter built from formal war/battle evidence and exact ship/starbase combat-activity dates.
- Added a technology chapter naming observed advances across the campaign.
- Expanded leaders/commanders so long-serving military and scientific figures can appear as historical personalities rather than isolated register entries.
- Expanded naval development and scientific/archaeological continuity.
- Scribes prose now stays strictly in-universe: it speaks of surviving archives, rolls, chronicles and records, never of Stellaris, save files or game mechanics.
- Combat activity remains cautious until opponent, outcome and casualties are independently established.

### Cache behaviour
- Added `technology` cache component v1.
- Existing People, Ships, Worlds, Science and Combat cache components remain valid.
- The first Review Campaign after installing v0.0.37 will normally show **CACHE EXTEND** while the technology component is added to each archived snapshot.
- No database schema change, archive deletion or processed-flag reset is performed.

### Install
1. Stop Stellaris Historian.
2. Extract the patch over `G:\codex\StellarisHistorian\`.
3. Run `start.bat`.
4. Run **Review Campaign** once so the technology component is populated across the archive.
5. Open **As the Scribes Saw It** and, if desired, regenerate the PDF.

**Restart required: YES.**
