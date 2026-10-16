# Stellaris Historian v0.0.66 — Shared-parser acceleration and evidence audit

## Included improvements

1. **Accelerated full-save parsing without discarding anything.** The shared `historian/core/stellaris_text.py` now scans Paradox `{ ... }` blocks by finding structural characters rather than interpreting every character in Python. It obtains numeric-record content/end positions in one pass instead of scanning twice.
2. **Bounded per-save indexes.** Ships, People, Worlds, Science and the other domains share a short-lived lookup cache for large named sections and repeated numeric record lookups. This preserves the full native gamestate, **including all AI countries, wars and fleets**. The index is created only during a cache miss/extension and is discarded automatically when the save is finished or fails. It does not persist across saves or modify `.sav` or `.historian_cache` formats.
3. **Safe planet lookups.** The Worlds planet-ID helper retains its direct-child indentation rule, but can reuse the same per-save index when repeatedly resolving science/leader/world planet names.
4. **Leader death diagnostic is historically accurate.** Previous Update History passes promoted four named deaths and stored them in SQLite. Later zero-new-confirmation passes overwrote the notification report with a misleading `0`. Incremental updates now show both confirmed historical notification-derived deaths **from the database** and newly promoted deaths **this pass**, keeping their provenance separate. The underlying confirmed history records are unchanged.
5. **Correct startup version.** `start.bat` displays v0.0.66, resolving the previous mismatch where it printed v0.0.64 while the Python server was newer.

## Measured impact and independent verification

Using the existing 3.66 MB `ironman-311.sav` (about 47 MB uncompressed game state), run in the same Python/container environment:

- Full evidence extraction using unchanged v0.0.65 code: **71.84 s**.
- Same extraction using v0.0.66 core/index code: **8.40 s**.
- **Serialized output SHA-256 identical** (`be31e253c07be25939d59af9184b2db9fad7d06340f7bd5bcbc895d9c17469d0`). This compares Empire Profile and all seven domain snapshots (Ships, People, Worlds, Science, Combat, Technology, Politics), not just record counts.
- A second independent `ironman-320.sav` sample matched the older evidence output byte-for-byte: v0.0.65 **72.98 s** vs v0.0.66 **10.10 s** (SHA-256 `4bcef21172d2e89a8fb9a504df7d7fec5ba0efd03e17c5c61ea06528219c419d`).
- `test_v0_0_66.py` tests nested braces, quoted/escaped delimiters, indexed numeric and direct-indented lookups, cleanup after the context exits, and historical death audit output.

These measurements are **not** promises for Windows/live workloads. First Contact refresh and journal generation are separate phases and are not made incremental by this parser change. Compare your own future `PERF MISS` lines and `Processing_Performance.jsonl` samples to establish actual gains; no snapshot reparse is required for installation.

## Safe installation — IMPORTANT

1. Finish the running Live History batch if desired; ideally wait for **Unprocessed Saves = 0**. Switch **Live History OFF**.
2. Close the **Historian server/terminal** before copying files. You can leave Stellaris open and play while Historian is stopped; monitoring/archiving is paused, so if using Ironman you may miss intermediate quarterlies until restarting.
3. Back up the application/source (`autobackups` or your preferred safe method). Do not delete or replace `data/`, `.historian_cache/`, original Ironman saves or your SQLite databases.
4. Open `G:\codex\StellarisHistorian`. Extract the v0.0.66 patch **there**, merging the `historian/`, `docs/` and other relative paths and replacing only matching source files. Do NOT create an extra nested `StellarisHistorian` folder.
5. Run `start.bat`. Confirm **v0.0.66** in BOTH console banner and dashboard.
6. Select the existing Commonwealth of Man campaign if needed; turn Live History ON when ready.
7. Use the next new quarterly save to verify `PERF MISS`, `PERF SAVE`. For corrected notification audit, click **Update History** even with zero saves pending; `diagnostics/Notification_Death_Evidence_Debug.txt` will report historical database confirmations separately from new ones.

**Server restart:** YES. **Review Campaign:** NO. **Construct Campaign:** NO. **Database migration:** NO. **Parsed cache invalidation:** NO. **Save files changed:** NO. **GitHub update:** NO.

## Rollback

Exit Historian; restore the previous version's patched source files from your protected backup, then launch `start.bat`. Neither `.sav` data nor database schema was migrated. New `Processing_Performance.jsonl` entries are append-only diagnostics, not historical state.
