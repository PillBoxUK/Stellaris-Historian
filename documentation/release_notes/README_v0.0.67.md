# Stellaris Historian v0.0.67 — Faster Live History follow-through

**Update from v0.0.66.** No database schema migration. No cache schema bump. No data deletion or rebuild.

The v0.0.66 parser was already processing fresh quarterly saves in roughly 7–8 seconds, but First Contact still ran a full historical decoder (40–55 seconds), and the notification-death audit reopened historical saves unnecessarily after most updates.

## Changes

- **Evidence-safe First Contact report reuse:** when the prior structured report is valid, all assignment windows have closed, all counterpart and owner identities are resolved, and no newly processed snapshot has a First Contact leader assignment, reuse the exact existing case/event evidence. Verify only newly added snapshots from their validated component caches. Update report watermarks and header counters using atomic file replacements. The historic raw/cache read counters explicitly describe the last full investigation, not an invented fresh scan.
- **Conservative full rebuild fallback:** force refresh/Review Campaign, active or new First Contact work, unresolved identities, missing or invalid cache, incorrect prior snapshot watermark, or raw-read failures always trigger the complete historical analysis. Do not change the established decoder revision because case/event logic is unchanged.
- **Window-bounded notification-death promotion:** check newly processed leader exits and the immediately preceding processed snapshot so notices retained in the following snapshot can still establish dates and causes. Previous confirmed historical deaths remain in SQLite and the corrected report. If the previous audit is missing or reported read failures, perform the original full audit instead.
- **Timings:** log `PERF DEATH AUDIT` with raw read count and duration, and append elapsed time to the Politics/Diplomacy structured-history diagnostic update message.
- **Version:** startup banner and runtime identify v0.0.67.

## Safety

- Original `.sav` archives are always retained. No raw-save rewriting.
- SQLite schema and contents are preserved. No migration or processed flag reset.
- All AI evidence and existing cached extracts remain retained.
- First Contact fast path never opens or reparses old archives. A missing cache forces normal complete analysis instead of assuming no new evidence.
- Full Review Campaign still runs First Contact with `force=True`; construct/review paths and war-aftercare remain unchanged.
- **Archive your entire `data` folder** for rollback; stop Historian so the SQLite WAL can be checkpointed first.

## Install

1. Wait until unprocessed saves reach 0 and switch Live History OFF.
2. Close the Historian server window entirely.
3. Back up the app to `autobackups` (especially the `data` folder); do not delete any existing app folders.
4. Extract this ZIP into `G:\codex\StellarisHistorian`, replacing only the matching files.
5. Run `start.bat`. Both the banner and the runtime should show **v0.0.67**.
6. Turn Live History ON and continue playing. Do not run Review or Construct Campaign merely to install this patch.

## Expected measurements

Compare `PERF MISS`, `PERF SAVE`, `PERF DEATH AUDIT`, the time-suffixed `Politics / diplomacy structured history updated`, and `PERF LIVE BATCH` with the v0.0.66 logs. A save with *no new First Contact assignments* and previously resolved/closed cases should spend very little time in First Contact. A genuinely new contact appropriately triggers a slower full investigation. Real timings depend on the PC and game state.

## Verification

- `python test_v0_0_67.py`: closed-case reuse, atomic header update, incremental watermark, full-scan fallback conditions, bounded and full death audit.
- `python test_v0_0_66.py`: save text reader reference parity and death report tests.
- `python test_v0_0_65.py`: First Contact raw-index parity against four real archived Stellaris saves.
- `python test_v0_0_64.py`: 11-system war territorial change and HTML tests.

**GitHub is not updated by this patch.**
