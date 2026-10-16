# Migration v0.0.53 — Live History Queue-First Performance

The one-time v0.0.53 migration updates only application source/metadata.

It:

- changes Live History scheduling so unprocessed saves remain the highest-priority work;
- adds a processed-snapshot database query;
- prevents the structured First Contact rebuild from parsing unprocessed saves;
- adds per-domain cache miss/extension timing telemetry;
- updates the changelog and manifest.

The migration backs up changed source files under `backups/v0.0.53/` before rewriting them.

It does **not** delete or rewrite archived Stellaris `.sav` files, rebuild the full parsed cache, reset processed flags, or change the SQLite schema.
