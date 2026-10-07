# Migration v0.0.47.1

The migration is a non-destructive source/database-behaviour hotfix.

It does not delete or alter archived Stellaris `.sav` files.

The migration:

- adds database helpers to reconcile already-written history rows with missing processed flags;
- makes Politics/Diplomacy cache serialization nullable so a new evidence-domain parser failure cannot block core history;
- changes incremental history processing so core snapshot progress is durable before optional Politics persistence;
- checkpoints SQLite WAL after Update History;
- updates the application version to v0.0.47.1.

Backups of modified source files are retained under `backups/v0.0.47.1/`.
