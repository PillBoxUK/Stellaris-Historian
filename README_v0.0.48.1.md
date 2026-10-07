# Stellaris Historian v0.0.48.1 — Live History Route Hotfix

This hotfix repairs the v0.0.48 API-route regression.

- Restores `POST /api/live-history`.
- Restores the complete Update History / Live History / Review Campaign route block.
- Reapplies the intended v0.0.48 refresh-progress logic with route-scoped anchors.
- Keeps the v0.0.48 Politics/Diplomacy filtering and localisation changes.
- Does not alter SQLite campaign data or archived Stellaris saves.

## Install

1. Keep Stellaris paused.
2. Close Historian completely.
3. Extract this patch into `G:\codex\StellarisHistorian\` and replace `start.bat`.
4. Run `start.bat`.
5. Confirm the one-time **v0.0.48.1 Live History route hotfix** completes.
6. Select Commonwealth and test **Live History: ON**.

A full Historian restart is required.
