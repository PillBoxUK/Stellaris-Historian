# Migration v0.0.52 — War Journal Foundation

This migration installs the first dedicated War Journal presentation without rebuilding campaign evidence.

## Changes

- Adds `historian/war_journal.py`.
- Adds the local `/war-journal` route.
- Adds a **War Journal** button to the active campaign dashboard.
- Separates formal war objects from reconstructed combat episodes.
- Preserves formal battle outcome/loss rows only when retained by the save evidence.
- Uses existing reviewed snapshot cache and shared presentation history; no silent Ironman reparse is performed.

## Data impact

- No SQLite schema change.
- No parsed-cache component version change.
- No archived save rewrite.
- No processed flag reset.
- No full cache rebuild required.

The migration backs up any source/UI file it changes under `backups/v0.0.52/`.
