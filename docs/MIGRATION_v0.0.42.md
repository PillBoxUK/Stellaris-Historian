# Migration Notes - v0.0.42

## Scope

v0.0.42 expands the People domain with deep character evidence and conservative death/exit probing. It does not redesign the Journal, Timeline or Scribes output.

## Automatic startup migration

On first startup `migrate_v0_0_42.py` validates/compiles the People-domain changes and creates the `leader_deep_evidence` table/index in an existing Historian database. It writes:

- marker: `data/.migration_v0_0_42_complete`
- log: `logs/MIGRATION_v0.0.42.log`

No archived save is modified or deleted.

## Cache compatibility

The People cache component advances from v4 to **v5**. Other component versions are unchanged:

- People: v5
- Ships: v2
- Worlds: v2
- Science: v1
- Combat: v3
- Technology: v1

The snapshot cache is component-versioned, so Review Campaign reuses valid non-People components while reopening archived saves as needed to refresh leader evidence.

## Required user action

After installing and restarting, run **Review Campaign once**. Construct Campaign is not required.

The review creates/refreshes:

- `Character_Evidence_Debug.txt`
- `Raw_Evidence_Probe.txt`
- `Leader_Exit_Evidence_Debug.txt`

## Death evidence rule

`dead_leader` data is treated as stronger direct evidence than disappearance. A temporary `leaders` tombstone such as `<leader id>=none` proves removal from the active leader table but does not establish why. Exact date/cause claims require explicit retained fields.

## Rollback note

The new database table is additive. Older builds can ignore it. Rolling code back does not require restoring archived saves; v5 People cache files may simply be refreshed again by the version in use.
