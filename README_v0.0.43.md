# Stellaris Historian v0.0.43

## Event & Character History Deep Probe

v0.0.43 continues the evidence-expansion phase. It does not spend this release polishing Journal/Timeline prose. The target is the gap exposed by v0.0.42: Stellaris visibly reported leader deaths in-game, while the retained `dead_leader` structure was empty in all 299 Sutharian snapshots.

### New diagnostic

`diagnostics/Event_Character_Probe_Debug.txt`

The probe finds every leader-exit transition already reconstructed by the People domain and then inspects only a narrow raw-save window around that exit:

- previous archived save
- first archived save after the exit
- following archived save

For each exit it records:

- `last_notification_id` before/after and delta
- `last_event_id` before/after and delta
- `open_player_event_selection_history` count changes
- newly appearing `player_event` IDs
- event-like save-key count changes
- the last active leader's raw `available_trait`, `cooldown` and `delayed_event` evidence where present
- cached leader flags and variables
- exact-ID `saved_event_target` aliases and raw blocks
- event-adjacent raw references to the exact leader ID in the three-snapshot window

### Evidence rules

This is deliberately a **probe**, not a cause-of-death decoder.

A notification/event counter increase does not prove that a particular event killed a leader. A `player_event` ID, `saved_event_target`, delayed event, or nearby leader-ID reference remains correlation evidence until its semantics can be demonstrated from the save/script/localisation chain.

Historian therefore continues to record Japra Tysala, Vuld Taras, Kon Kap and other unresolved exits conservatively unless stronger evidence is found.

### Performance / cache behaviour

**People cache remains v5.**

v0.0.43 does **not** invalidate the 299 cached People snapshots created by v0.0.42. Review Campaign reads the existing cache to locate exits and only opens the small raw-save windows needed by the new probe.

This means the v0.0.43 review should be dramatically faster than the v0.0.42 one-hour cache extension on the same campaign.

### Install

1. Stop Stellaris Historian.
2. Extract the v0.0.43 patch ZIP over the existing Stellaris Historian folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.43`.
5. Run **Review Campaign** once.
6. Open the diagnostics folder and send `Event_Character_Probe_Debug.txt` for analysis.

The one-time v0.0.43 migration adds the probe hook to `app.py` and preserves the pre-patch file at `backups/v0.0.43/app.py.before_v0.0.43` before changing it.

**Restart required:** YES  
**Review Campaign required:** YES  
**Construct Campaign required:** NO  
**Full People cache refresh required:** NO
