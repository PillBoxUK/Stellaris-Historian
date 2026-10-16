# Stellaris Historian v0.0.69 — War Chronicle Verification & Responsive Investigations

Upgrade from **v0.0.68**. Large military-history milestone; **no database migration, no Review Campaign, and no Construct Campaign**.

## What this patch changes

1. **Dated, source-labelled victories**. A player-supplied screenshot dated 2300.08.15 confirms a victory notification against Hulfiran United Stars; a screenshot dated 2303.02.14 confirms the Silicron Interface victory notification. These are stored as source-scoped annotations for the Commonwealth of Man, the specific war ID and start date, and are displayed only when that date lies within the save-confirmed ending window. The precise peace execution day, every treaty term, and the permanent ownership effect of all transferred holdings **remain unverified independently of the screenshot**. No source file path from the local machine is needed.
2. **Clearer war exhaustion**. `Not verified from archived war` replaces ambiguous `Not retained`. The actual save structure was inspected: `attacker_war_exhaustion` and `defender_war_exhaustion` are inside individual native battle entries. The on-demand report now lists those literal battle values with battle indices and observation date; it does not sum them or promote them to live war-wide exhaustion percentages. A dated in-game war-screen screenshot would be required for a verified current exhaustion reading.
3. **Responsive military investigations**. Clicking **Investigate ground and starbase evidence** launches one background job, polls live progress (completed/total snapshots and latest game date), and prevents duplicate concurrent scans of the same war. The original synchronous API remains for compatibility. Jobs are in memory and are lost on restart, but their atomic per-save evidence caches persist.
4. **Existing evidence preserved and reused**. If the 0.0.68 per-save military evidence index is valid and matches save SHA-256, war ID and participants, v0.0.69 reuses that planet/starbase/army evidence and extracts only the new battle fields. It writes an independent v2 index, keeping the v1 cache intact. When new processed archives arrive, a new investigation is allowed; otherwise completed evidence is reused.
5. **Ground/space scope remains evidence-first**. Ground records with placeholder date `0.01.01` are still presented as undated; planet owner versus controller remain separate. Opposing starbase activity cannot establish specific damage-causing weapons. Only the latest up to 48 relevant processed archives are scanned, with truncation disclosed.

## Installation

1. Let Historian reach **0 unprocessed saves** and turn **Live History OFF**.
2. Fully exit Historian, allowing the SQLite WAL checkpoint to finish.
3. Back up the full `G:\codex\StellarisHistorian` installation including `data` into a dated folder inside `autobackups` (avoid nesting a full backup inside itself).
4. Extract `Stellaris_Historian_v0.0.69_PATCH.zip` directly into `G:\codex\StellarisHistorian` and replace matching application files only. **Do not delete data, save archives, SQLite, autobackups, or .historian_evidence.**
5. Restart via `start.bat` and verify the banner **v0.0.69**.
6. Visit **War Journal → Formal Wars**. Check the Hulfiran and Silicron screenshot-confirmed notification dates beside their archive end windows.
7. Run **Investigate ground and starbase evidence** on one war; the progress should update until the tables display. Existing 0.0.68 caches are reused.
8. Turn Live History ON and continue your Ironman campaign. **Research technology completions continue tracking as before**; the patch does not yet expose an automatic current-research queue.

## Validation

- All `test_v0_0_69.py` tests passed with actual uploaded saves, including native battle-exhaustion parity, cache-migration parity and warm cache, dated screenshot scoping, ground placeholder and progress callbacks.
- `test_v0_0_68.py`, `test_v0_0_67.py`, `test_v0_0_66.py` passed. Older full-suite tests were not completed in this release cycle; no claims about them are made.
- FastAPI import and registration of both new endpoints passed with a temporary local config.
- ZIP integrity and file whitelist verified after packaging.

**No GitHub changes. No migrations. No modifications to the original save files.**
