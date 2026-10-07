# Migration v0.0.50.4

The v0.0.50.4 hotfix changes generated First Contact adjective rendering, diagnostic owner display, release metadata and README current-version details.

It does not modify archived `.sav` files, campaign IDs, SQLite history rows, processed flags or parsed-cache component versions.

The patch replaces the First Contact history/journal modules and root `README.md`. The one-time migration updates `historian/__init__.py`, `docs/CHANGELOG.md` and `historian_manifest.json`, then records `data/.migration_v0_0_50_4_complete`.

A restart with `start.bat` is required because Python application code and startup migration logic changed. A full cache rebuild is not required.
