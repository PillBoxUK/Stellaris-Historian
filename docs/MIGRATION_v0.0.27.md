# Migration v0.0.27 - Opening-State Integrity

The v0.0.27 migration adds immutable opening-state evidence columns to the derived ship and fleet registry.

It creates `backups/pre_v0.0.27_historian.db` before changing an existing database and also keeps a small code backup when an obsolete migration script is removed.

For existing campaigns, Historian attempts to hydrate the new opening fields from the cached first archived snapshot. If that cache is unavailable or incompatible, the new fields remain unclaimed rather than copying latest-known values backwards; running **Review Campaign** once will rebuild them from the archived campaign.

No archived `.sav` file, campaign archive membership, or processed/unprocessed flag is changed.

The migration writes `logs/MIGRATION_v0.0.27.log` and is guarded by `data/.migration_v0_0_27_complete`.
