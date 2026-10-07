# Stellaris Historian v0.0.46

## Politics & Diplomacy Deep Probe

v0.0.46 begins the next evidence domain without guessing what unfamiliar Stellaris save fields mean.

The new probe is deliberately diagnostic-only. It combines already-reviewed government/profile history with targeted raw-save inspection so we can learn how normal democratic politics, elections, factions, first contact and diplomatic relations are retained in a standard Earth/UNE campaign while keeping the Sutharian Convocation campaign as a regression comparison.

### New diagnostic

`diagnostics/Politics_Diplomacy_Probe_Debug.txt`

The diagnostic records:

- government type, authority, origin, ethics and civics across all reviewed archived states
- every already-supported ruler/heir/death milestone from the People domain
- direct player-country political candidate keys retained in selected raw saves
- direct government scalar fields
- player `relations_manager` relation records, including literal scalar fields and nested block names
- relation-record changes between selected raw samples
- raw marker counts for candidate election/faction/federation/first-contact structures
- key-frequency summaries to show which fields are stable enough for later interpretation

### Adaptive raw-save sampling

If a campaign has 64 or fewer archived saves, the probe reads all of them.

For mature campaigns it remains bounded at a maximum of 64 raw reads. It prioritizes:

- the opening and latest saves
- the most recent 24 saves
- evenly spaced historical samples
- windows around known government/profile changes
- windows around supported ruler/heir/death milestones

This allows the new Earth run to be examined in detail without making the 299-save Sutharian comparison campaign perform another full raw reconstruction on every Review.

### Evidence rule

v0.0.46 does **not** publish alliances, treaties, elections, factions, rivalries, succession causes or diplomatic outcomes into the Historical Event Layer.

Raw field names and values are preserved literally until we have enough real save evidence to establish their semantics. Existing People evidence remains authoritative for ruler/heir/death milestones.

### Performance / cache behaviour

No parsed cache component version changes are made in v0.0.46.

The existing Ships, People, Worlds, Science, Combat and Technology caches remain valid.

## Install

1. Stop Stellaris Historian.
2. Extract the v0.0.46 patch ZIP over the existing v0.0.45 folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.46`.
5. Continue playing the new Earth/UNE campaign for a while so several archived states exist.
6. Run **Update History** if saves are waiting, then **Review Campaign** once.
7. Send `Politics_Diplomacy_Probe_Debug.txt` for interpretation.

**Restart required:** YES  
**Review Campaign required:** YES, after enough new-game saves exist  
**Construct Campaign required:** NO  
**Full cache rebuild required:** NO
