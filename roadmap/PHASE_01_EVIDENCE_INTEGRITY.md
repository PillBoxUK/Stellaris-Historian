# Phase One — Evidence integrity (v0.0.87–v0.0.89 proposal)

**Status: NOT IMPLEMENTED / NOT VERIFIED.** Source ZIP and representative original archived saves must be inspected; do not treat screenshots or plausible output as evidence.

## v0.0.87 — Extractor correctness
1. **Native timeline:** Decode the player's direct `country/<player>/timeline_events` and preserve exact event date, definition key, typed IDs, target references, source file SHA-256 and original path. Do not ascribe a native war victory to an arbitrary war ID.
2. **Traditions / perks:** Collect the player's complete direct `traditions` block including repeated keys and preserve every token. Reconcile with stale cached `politics_diplomacy` state; store ascension perks separately; retain adopted versus completed meaning.
3. **War exhaustion:** Parse only direct `attacker_war_exhaustion` and `defender_war_exhaustion` children from war records. Retain fractional values, war identity, source, date and attacker/defender orientation; never infer outcome from exhaustion.
4. **Name resolution:** Preserve typed entity references, raw name expressions, localisation status and fallbacks. Reject nested unrelated names, technical tokens and null IDs.
5. **Colony and construction chronology:** Investigate repeated completion milestones, entity joins, deduplication keys and exact versus first-seen dates. Changed names or cached state alone do not prove new construction.
6. **Archive ordering:** Sort by native in-game date *and stable capture order*. Same-date archives may differ. Keep SHA-256 and do not treat ZIP CRC as cryptographic proof of authentic Ironman history.

## v0.0.88 — Full native history recovery
- Enrich the historical event layer with native dated milestones, joined IDs and provenance.
- Preserve separate exact dates / first-observed intervals for recruitment, traits, shipbuilding, technology and archaeological findings.
- Correlate only unambiguous native identity references; unresolved candidates stay diagnostic.
- Maintain database evidence and source-matched caches without modifying original saves.
- Keep screenshots exclusively for interface QA and investigation.

## v0.0.89 — Safe reconstruction and consistency
- Rebuild from existing archives without deleting durable evidence or replaying already processed saves.
- Validate idempotence and deterministic event counts under repeat runs.
- Check Live History ON/OFF, crash recovery, campaign change and Review/Construct.
- Publish meaningful natural prose while offering provenance in advanced views.
- Store frequent observations internally but publish a routine **four-year government census** plus exceptional reports for directly evidenced events.
- Career landmarks (1/5/10/25/50 years) require observed continuity or clearly delimited observed-census wording, not invented service.
- Leaders first **enter service** unless birth is explicitly recorded.

## Acceptance gates
- [ ] Inspect 267-file latest source ZIP; compare to installed v0.0.86 and hash protected files.
- [ ] Use a **consistent** DB backup with the application stopped or SQLite's backup API.
- [ ] Independently verify native timeline, full direct tradition list, ascension perks and direct war exhaustion from raw saved-game fixtures.
- [ ] Prove correct entity/colony namespaces, typed invalid sentinels and repeated Clausewitz keys.
- [ ] Preserve observation intervals, exact dates and same-day captures without misdating.
- [ ] Rebuild twice; verify no duplicate events and stable chronology.
- [ ] Test established Live History workflows, manual reconstruction and existing regressions.
- [ ] Verify no screenshot has ever become a campaign-history source.
- [ ] Run independent tests and interface smoke tests. Record failures honestly before release.

### Why these fixes?
The [512-save Commonwealth of Man Ironman survey](https://deonchapman.co.uk/codex/Stellaris/Historian_Documentation/Ironman.html) observed native dated timeline records, direct-child war exhaustion, and a cache that omitted most tradition tokens. The survey identified targets for repair; it did not implement them.

**Do not synchronise code from the older GitHub baseline over the newer local installation.**