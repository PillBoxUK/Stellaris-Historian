# Stellaris Historian v0.0.42

## Character & Leader Deep Evidence

v0.0.42 deliberately pauses presentation cleanup and expands what Historian can learn about people from archived Ironman saves.

### New evidence captured

- Species identity and resolved species name where available.
- Portrait key, gender, creator country and leader tier.
- Raw leader `date`, `date_added` and `age` values, preserved without assuming birth-date or biological-age semantics.
- Ethic, job, background-world reference and custom-description evidence.
- Bonus skill level plus complete observed top-level leader-record key inventory.
- Raw leader flags and variables for future interpretation.
- Retained leader `saved_event_target` aliases when they can be matched by exact leader ID.
- `dead_leader` records, including explicit death-date/reason fields if a save actually retains them.
- Active-leader `ID=none` tombstones, treated as strong evidence of removal from the active leader database but **not** proof of death, retirement, dismissal or execution.
- Global event/notification counters and player-event-selection history counts as discovery evidence for future event-text reconstruction.

### New diagnostics

- `Character_Evidence_Debug.txt` — deep per-character evidence register and service history summary.
- `Raw_Evidence_Probe.txt` — inventories leader keys, flags, variables, tombstones, dead-leader structures and retained event-target aliases.
- `Leader_Exit_Evidence_Debug.txt` — upgraded to distinguish confirmed dead-leader evidence, tombstoned exits and ordinary unexplained disappearance.

### Evidence rules

- `date` and `age` are raw save fields; v0.0.42 does not call them birth dates or current ages.
- A `none` tombstone proves removal from the active leader object table, not death.
- A leader is called dead only when retained `dead_leader` evidence explicitly supports that classification.
- Death cause is never inferred from a popup seen outside the save or from disappearance alone.
- Event-target aliases are preserved as identifiers/context, not automatically interpreted as biography.

### Data / cache changes

- People cache component: **v4 -> v5**.
- New database table: `leader_deep_evidence`.
- Existing archive saves are not modified, renamed or deleted.
- Existing Journal, Timeline and Scribes renderers are intentionally left alone in this release.

## Install

1. Stop Stellaris Historian.
2. Extract the v0.0.42 patch ZIP over the existing Stellaris Historian folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.42`.
5. Run **Review Campaign** once. The People cache component must be extended to v5 from the raw archived saves.
6. Open the campaign diagnostics folder and inspect the new character/probe diagnostics.

**Restart required:** YES  
**Review Campaign required:** YES  
**Construct Campaign required:** NO
