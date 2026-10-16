# Stellaris Historian v0.0.65 — Performance Foundation

## What is improved

1. **First Contact section index:** When First Contact needs to revisit an older archived `.sav`, Historian reads the original native `country` and `first_contacts` blocks into an indexed, zlib-compressed derived cache under the campaign's `.historian_cache/first_contact_raw/`. On subsequent runs the same raw evidence can be read from this compact per-save index rather than repeatedly extracting the full game state. The original game saves are never modified. This preserves **all countries (including AI empires)** and **all First Contact records**; it is not a player-only filter.
2. **Report freshness check:** Routine Live History/Update History will reuse the completed `First_Contact_History` JSON and text reports if the processed-snapshot count, final snapshot ID, final SHA, decoder revision and both report files still match. An added snapshot, missing report, decoder revision or explicit Review/Construct triggers recomputation. Reports are not regenerated just for being opened.
3. **Performance telemetry:** Each new processed save writes a `PERF SAVE` console line with parse, transition, SQL and total durations. Small append-only JSONL samples are stored under `data/campaigns/<campaign>/diagnostics/Processing_Performance.jsonl` (one JSON object per newly processed snapshot). The live worker and manual Update History also log processing/diagnostic/First Contact/journal stage timings.
4. **No-work manual sync:** When Update History finds zero new snapshots, it no longer does the full combat diagnostic rescan merely because the user clicked the button. Normal combat diagnostic synchronization still runs after actually processing new history.

## Important scope and limitations

- All original `.sav` files, player and AI data, wars, combat evidence and historical logic remain intact. No AI data or raw event evidence is discarded. The new cache is derived and disposable; deleting **only** `.historian_cache/first_contact_raw` safely rebuilds it on demand (do not delete the main archive/database).
- The **first** First Contact refresh after this update will populate the new cache and can take about as long as earlier refreshes, possibly longer. **Subsequent** refreshes should benefit. Only real run timings will establish the overall improvement.
- This is the first performance milestone, not an indexed random-access format for all Stellaris save data. Full-save parsing still operates for new snapshots. More optimizations should follow actual timings, without trading away AI history or accuracy.
- Automatic skip is based on the processed snapshot sequence; Review and Construct always force an explicit full First Contact rebuild, to ensure deep rebuild semantics are preserved.
- The 66 formal battles remain unverified and the war's exact peace terms are not inferred.

## Install

1. Wait until **Unprocessed Saves = 0**, then toggle **Live History OFF**. Pause Stellaris.
2. Close the Historian server window. Backup application files to `autobackups`, ensuring `data/` and original archives remain intact.
3. Unzip `Stellaris_Historian_v0.0.65_PATCH.zip` into `G:\codex\StellarisHistorian`, merging directories and replacing **only matching code files**.
4. Restart with `start.bat` and confirm **v0.0.65** in the console and dashboard.
5. Turn Live History ON when ready and play until a new quarterly save is processed. In the console, look for `PERF SAVE` and `PERF LIVE BATCH`. Check the diagnostics folder for `Processing_Performance.jsonl`.
6. If you want to refresh First Contact immediately rather than waiting for another save, use **Review Campaign**, but this is **optional** and performs a slow full archive review. Routine installation does **not** require it.

## Restart and migration

- **Historian restart:** YES, to load updated Python code.
- **Review Campaign:** NO for installation (only optional if immediate full report refresh is wanted).
- **Construct Campaign:** NO.
- **Database schema migration:** NO.
- **Original save files altered:** NO.
- **GitHub updated:** NO.

## Validation

- Compiled modified Python modules and application.
- Ran v0.0.64 war regression: 11 verified controller changes and 0 losses at the 2278 peace window, zero changes in the 2266 control pair.
- Ran v0.0.65 First Contact regression on all four uploaded saves (`268`, `269`, `319`, `320`): native country/first-contact blocks match the projected records; cache build, warm hit and corruption fallback all succeeded.
- Checked unchanged report detection and performance diagnostic append logic.
- The Windows live process still needs timing and smoke checks after install. No speedup percentage is guaranteed.
