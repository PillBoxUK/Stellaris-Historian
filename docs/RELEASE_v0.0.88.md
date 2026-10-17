# v0.0.88 — Revolt and civic crisis chronology

Historian now stores player-owned active situations from each observed Ironman save alongside the already indexed colony crime and stability observations. Each stored value is linked to the originating hash and game-date observation. The Imperial Annals receives evidence-limited, readable entries for **observed revolt threats, changes of situation stage, and disappearance from the active situation list**. Neither absence nor a stage change is evidence of a particular outcome.

## Evidence boundaries

- Screenshots do not enter the database.
- Raw type and approach keys are retained for localisation/script verification, not printed as fictional event narrative.
- Target references must resolve to the user's owned colony/planet or directly to the selected empire, avoiding other empires' situations.
- The `Civic_Frontier_History.sqlite3` sidecar increments its parser to v3. Older observations remain readable; running the built-in historical timeline update re-indexes old raw archives to add v3 evidence.
- Snapshot observation windows remain bounds, not occurrence dates. Same-date snapshot capture order remains preserved via snapshot IDs.
- A disappeared situation might have ended, transformed, or lost save retention. It does **not** prove riot, independence, suppression, arrests or a peaceful settlement.

## Verification

Run: `python -m pytest -q tests` in the installed project if pytest is available. Tests cover scope, foreign-country exclusion, target resolution, native type parsing despite nested `target.type`, chronological state transitions, reused IDs, legacy v2 ledger reads, CSV export and HTML evidence. An older archive from the Veyran campaign was tested for parser compatibility; 2222 outcomes remain unverified until new saves are inspected.
