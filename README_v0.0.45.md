# Stellaris Historian v0.0.45

## Notification-Derived Leader Deaths

v0.0.45 turns the notification-decoder evidence discovered in v0.0.44 into conservative, structured People-domain history.

The key discovery was that some Stellaris saves retain `message={...}` objects with:

- `type="LEADER_DEATH"`
- `localization="MESSAGE_LEADER_LOST_DESC"`
- a `LEADER` variable naming the dead leader
- exact notification date
- recorded age
- recorded time served
- optional `custom_message_text`

For the Sutharian Convocation campaign, this evidence is sufficient to confirm the deaths of Japra Tysala and Vuld Taras from the archived saves themselves.

### Promotion rule

Historian promotes an unresolved leader exit to `dead_confirmed` only when all of the following are true:

1. The retained message type is `LEADER_DEATH`.
2. The localisation key is `MESSAGE_LEADER_LOST_DESC`.
3. The message contains a `LEADER` variable.
4. That name uniquely matches exactly one known player leader.
5. That same leader has an unresolved disappearance/tombstone in the same first-absent archived snapshot.
6. The notification date is later than the leader's last confirmed presence and no later than the first archived state in which the leader is absent.

Ordinary notification timing, `save_on_death`, numeric-ID collisions, and unrelated player-event selections remain insufficient evidence.

### History changes

Validated notification-derived deaths now:

- change leader status to `dead_confirmed`
- preserve the exact notification date as the death date
- persist `death_evidence_kind=notification_leader_death_named`
- preserve retained `custom_message_text` as the death/cause text
- publish a `leader_death_recorded` career event
- include the notification's recorded age and service duration in the career-event body
- replace the contradictory unresolved-exit event for that leader/window
- flow into the shared Historical Event Layer
- appear as notable People events in Empire Timeline
- render as confirmed deaths rather than unexplained disappearances in the Evidence Journal and Scribes Chronicle

### New diagnostic

`diagnostics/Notification_Death_Evidence_Debug.txt`

This file lists:

- confirmed notification-derived deaths
- source notification ID
- exact death date
- recorded class
- recorded age
- recorded service duration
- retained custom death text
- evidence kind
- rejected/ambiguous death-message candidates
- raw-save read count/errors

### Existing decoder update

`Notification_Event_Decoder_Debug.txt` now also reports when a retained message's `LEADER` variable uniquely matches the leader being investigated. This is deliberately restricted to identity evidence; the v0.0.45 promotion rule still requires the full death-message and exit-window checks above.

### Performance / cache behaviour

People cache remains **v5**.

v0.0.45 does not invalidate the 299 parsed snapshots created by the earlier deep-evidence work. Review Campaign should therefore remain a cache-hit review plus a small number of targeted raw-save reads around unresolved exits.

## Install

1. Stop Stellaris Historian.
2. Extract the v0.0.45 patch ZIP over the existing Stellaris Historian folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.45`.
5. Run **Review Campaign** once.
6. Inspect/send `Notification_Death_Evidence_Debug.txt`, `Leader_Exit_Evidence_Debug.txt`, and `Character_Evidence_Debug.txt` if verification is needed.

The one-time migration backs up modified source files beneath:

`backups/v0.0.45/`

**Restart required:** YES  
**Review Campaign required:** YES  
**Construct Campaign required:** NO  
**Full People cache refresh required:** NO
