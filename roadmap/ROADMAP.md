# Stellaris Historian — Development Roadmap

**Editorial principle:** The Imperial Annals are the final story; recoverable facts belong in the supporting evidence database. Source authority is the archived Ironman save, with general game data providing context but never proof of a campaign event.

## Completed through v0.0.90

- Ironman watcher and incremental Live History, explicit YES/NO recording guard.
- Campaign archive, processing state, research, world, ship, leader, combat and political evidence domains.
- Native history reconstruction, war start records, conservative war outcome correlation, source date bounds and source hashing.
- Four-year January government census in the Annals; annual full census remains available for investigations.
- Grouped leader service milestones and identified player-side spy networks.
- British English editorial conventions and reading-safe light/dark/print themes.
- Highlights / Standard / Complete reading levels, dated monthly/yearly extracts, linked people/war facts, local reader annotations and HTML chapter export.

## Next: historical completeness and editorial maturity

1. **Month-by-month historical synthesis:** Generate self-contained, nonrepetitive, naturally connected text from ordered events with source-level provenance; never add motives or chronology unsupported by saves.
2. **Civilisation and government vocabulary:** Authority-sensitive narrative grammar including individualistic machines, hive minds, oligarchies, democracies and corporations. Derive classification from save data.
3. **Identity-based archives:** Stable, campaign-scoped IDs, historical renames and dated records for worlds, ships, fleets, leaders, federations and foreign empires.
4. **War campaign chapters:** Authenticated participating entities, battles, occupations, source-backed outcomes, ongoing chronology and explicit record gaps.
5. **Economy and policy validation:** Correct units/scales for population, housing, jobs, monthly balances and war exhaustion; distinguish policy permission from actual practice.
6. **Event importance policy:** Contextual firsts versus routine repeats; user ranking overrides remain isolated from evidence.
7. **Personal writing archival format:** Optional portable JSON import/export of annotations with campaign ID and explicit author-only provenance. No automatic authority over historical text.
8. **PDF/book exports:** Dedicated period/chapter selection, offline page design and live-user browser tests.
9. **Civic crises and intelligence:** Deeper save-backed situation/decision changes and documented operations; no popup/screenshot conclusions or guessed successful operations.
10. **Performance and completeness audit:** Hundreds of game years, thousands of archives, duplicate game dates, missing/corrupt snapshots, absent metadata and source-to-publication coverage checks.

## Research reference

[Project Ironman save investigation](https://deonchapman.co.uk/codex/Stellaris/Historian_Documentation/Ironman.html) — documents native dated events, Clausewitz structures, saved war-level exhaustion, budgets, repeated keys, native identities and interpretive limits. Findings are a separate reference, not evidence for other campaigns.

## Non-negotiable rules

- No screenshots, oral reports or speculative lore become historical evidence.
- No inferred casualties, leader deaths, mission success, colonisation, peace treaties, crimes or policy application.
- Preserve old archives, SQLite databases and source hashes. Flag and explain unsupported dates.
- Render historical narrative directly in the timeline; advanced identifiers stay in diagnostics.
- Restart instructions and safe patch boundaries required for each release.
