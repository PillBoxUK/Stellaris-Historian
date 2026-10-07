# Stellaris Historian v0.0.47

## Live History + Structured Politics/Diplomacy

v0.0.47 turns the v0.0.46 Politics/Diplomacy probe into the first structured evidence domain and adds an opt-in **Live History ON/OFF** control beside **Update History**.

### Live History

Live History is **OFF by default** every time Historian starts or a campaign is selected.

When switched ON, Historian continues to use the normal save watcher. As soon as a stable Ironman save has been archived, the existing incremental **Update History** pipeline processes any waiting archived saves and refreshes `Historical_Journal.html` automatically.

This does not modify the Stellaris Ironman save. Historian still works from its archived copies.

If automatic history processing reports an error, Live History turns itself OFF and leaves the failed save available for inspection/retry rather than repeatedly processing it.

While Live History is ON, manual **Update History**, **Review Campaign**, and **Construct Campaign** are disabled/blocked to prevent concurrent history rebuilds.

### Structured Politics/Diplomacy v1

The new cache component is:

`politics_diplomacy` — version 1

It records, conservatively:

- government type, authority, ethics and civics state
- ruler identity observed in the same archived state
- direct retained council-agenda fields and their changes
- retained tradition keys and first archived observations
- first archived appearance of player `relations_manager` records
- literal communications / hostility / neutral-state field or block changes
- literal relation-value changes

Ruler identity is retained in Politics/Diplomacy, but the **People** domain remains authoritative for public ruler/succession career events. This avoids duplicate ruler-history entries.

Relation-value changes are stored as evidence but are not normally published into the public historical event stream because they can be very noisy.

### Evidence rule

v0.0.47 does **not** infer an election, treaty, alliance, rivalry, faction, war cause, succession cause, diplomatic motive or other political meaning unless the retained evidence actually establishes it.

A relation record first appearing means exactly that: it is the first archived state in which Historian found that relation record. It is not automatically treated as the exact first-contact date.

### Cache behaviour

Existing v0.0.46 cache files are preserved.

When an older cached snapshot is needed, Historian extends that cache in place with the new `politics_diplomacy` component. No destructive cache reset is required.

For newly archived saves, Politics/Diplomacy parsing shares the same raw-save read already used by the other structured domains.

### New diagnostic

`diagnostics/Politics_History_Debug.txt`

This records the structured Politics/Diplomacy transitions, including hidden evidence such as relation-value changes and the Politics-side ruler mirror. The Historical Journal also gains a dedicated **Politics & Diplomacy** section that refreshes during Live History processing.

The v0.0.46 forensic diagnostic remains available:

`diagnostics/Politics_Diplomacy_Probe_Debug.txt`

## Install

1. **Stop Stellaris Historian.**
2. Extract the v0.0.47 patch ZIP over your existing **v0.0.46** Historian folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.47`.
5. Select the Commonwealth campaign.
6. Click **Live History: OFF** once so it becomes **Live History: ON**.
7. Play normally. As Stellaris writes new stable Ironman saves, Historian will archive and process them automatically.

For the live Commonwealth test, **Review Campaign is not required before you start playing**.

If you later want v0.0.47 Politics/Diplomacy reconstructed across older archived saves from an existing campaign, turn Live History OFF and run **Review Campaign** once. Older caches will extend in place as needed.

**Restart required:** YES  
**Review Campaign required:** NO for new/live saves; YES only if you want the new Politics/Diplomacy domain reconstructed across older archives  
**Construct Campaign required:** NO  
**Full cache rebuild required:** NO
