# Stellaris Historian v0.0.44

## Notification & Event Object Decoder

v0.0.44 continues the evidence-first investigation opened by v0.0.42 and v0.0.43. The previous probe established that leader exits can coincide with new notification IDs and player-event selections, but those counters alone do not reveal what the notification actually said.

This release decodes the retained Stellaris `message={...}` objects themselves in narrow raw-save windows around leader exits.

### New diagnostic

`diagnostics/Notification_Event_Decoder_Debug.txt`

For each leader exit, the decoder records:

- the notification-ID range allocated between the previous and first post-exit save
- which message/notification objects are still retained
- notification ID
- message type
- localization key
- message date and expiry date
- receiver
- message variables
- typed targets such as `target_planet`, `target_fleet` or explicit leader/governor/ruler references
- retained `custom_message_text`
- new player-event selection records and chosen option index where retained
- newly present scripted `event_id` values
- notification IDs whose payload has already expired from the save

### Important evidence rules

A notification counter increment is not proof that the notification caused a leader exit.

Historian only directly links a retained message to a leader when the message itself preserves an explicit typed reference to that exact leader ID, for example `leader=110` or a typed `type=leader / id=110` reference.

If a notification ID was allocated but its message payload no longer survives in the first post-exit or following save, Historian reports that fact and does not reconstruct the missing text.

`player_event` selection IDs are kept separate from scripted `event_id` keys unless a future parser proves a mapping.

The generic `save_on_death` field is explicitly **not** treated as leader-death evidence. Stellaris also stores this field on unrelated objects such as countries and planets.

### Performance

People cache remains **v5**.

The decoder reuses the existing parsed cache to locate leader exits and opens only the previous/current/next raw archived saves around those exits. It does not invalidate the 299-save People cache.

### Install

1. Stop Stellaris Historian.
2. Extract the v0.0.44 patch ZIP over the existing Stellaris Historian folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.44`.
5. Run **Review Campaign** once.
6. Open the diagnostics folder and inspect/send `Notification_Event_Decoder_Debug.txt`.

The one-time migration preserves the pre-patch `app.py` at:

`backups/v0.0.44/app.py.before_v0.0.44`

**Restart required:** YES  
**Review Campaign required:** YES  
**Construct Campaign required:** NO  
**Full People cache refresh required:** NO
