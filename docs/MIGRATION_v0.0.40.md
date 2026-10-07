# Migration v0.0.40

v0.0.40 adds Combat Episode Synthesis and a cleaner Historical Event Layer.

The one-time migration is validation-only. It does **not** change the SQLite schema, cached parser component versions, archived Ironman saves, campaign identity, or processed flags.

It validates that the new episode/event modules compile and then writes `data/.migration_v0_0_40_complete` plus `logs/MIGRATION_v0.0.40.log`.

After installation, run **Review Campaign** once for each campaign you want refreshed. Review generates the new episode and leader-exit diagnostics from existing archived saves/caches and rebuilds `Historical_Event_Debug.txt` using the v0.0.40 event model.

New diagnostics:

- `Combat_Episode_Debug.txt`
- `Leader_Exit_Evidence_Debug.txt`

Existing diagnostics remain available and unchanged in purpose.
