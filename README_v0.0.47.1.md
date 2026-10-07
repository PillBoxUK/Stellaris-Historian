# Stellaris Historian v0.0.47.1

## Durable Incremental History Hotfix

This hotfix corrects a v0.0.47 failure mode where **Update History could replay already-written campaign history**.

### What happened

v0.0.47 added structured Politics/Diplomacy processing after the existing Ships, People, Worlds and normal history writes. The snapshot `processed=1` flag was still set only after that new Politics/Diplomacy stage.

If Politics/Diplomacy parsing or persistence failed, the normal history row could already be committed to SQLite while the snapshot remained marked unprocessed. The next Update History therefore selected the same snapshot again.

### What v0.0.47.1 changes

- Reconciles v0.0.47 snapshots that already have a durable `history_entries` row but are still marked `processed=0`.
- Core Historian progress is now marked processed independently of the additive Politics/Diplomacy stage.
- Politics/Diplomacy parser failures no longer invalidate the supported core history for the save.
- Politics/Diplomacy persistence warnings are reported separately instead of forcing the entire snapshot to replay.
- Review Campaign and Construct Campaign tolerate a missing Politics snapshot while retaining the supported domains.
- Update History requests a passive SQLite WAL checkpoint after each batch so committed pages are flushed into `data/historian.db` when possible.

### SQLite note

Historian uses SQLite WAL mode. While the application is running, some recently committed changes can temporarily reside in `historian.db-wal`; they are still committed SQLite data. v0.0.47.1 explicitly requests a checkpoint after Update History so the main `historian.db` file is kept current as well.

## Install

1. Stop Stellaris Historian.
2. Extract this ZIP directly over the existing v0.0.47 folder and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher reports `STELLARIS HISTORIAN v0.0.47.1`.
5. Select the Commonwealth campaign.
6. Leave Live History OFF for the first test and press **Update History** once.
7. The first run may report that already-written snapshots were **recovered from SQL**. That is expected.
8. Press **Update History** a second time. If no new archive has arrived, it should have nothing historical to replay.

**Restart required:** YES  
**Review Campaign required:** NO  
**Construct Campaign required:** NO  
**Full cache rebuild required:** NO
