## v0.0.80 — Machine-empire first-year repairs

**v0.0.82 — The Great Chronicle Rebuild:** A narrative-first founding chapter grounded in opening Ironman species/origin fields; native campaign milestones and dated war victories; direct war-level exhaustion evidence; one backed-up Update Historical Timeline action to re-derive history using versioned caches. Running a full rebuild may take several minutes or more on a large campaign.

The Imperial Annals now formats Stellaris leader gender-name alternatives correctly (including already indexed names), removes duplicate ship/Ancient Capsule project entries, writes machine-state introductions without human political assumptions, and keeps raw research totals out of the main narrative. Existing research progress stays in Research History. These are non-destructive rendering and low-cost ingest fixes. **Popup-only Shroud choices are not automatically recoverable from quarterly snapshots:** no selection or outcome is invented.

## v0.0.79 — Evidence-first research queues and fuller timeline prose

See `documentation/release_notes/README_v0.0.79.md` for the independent research-ledger and rewrite instructions.

## NEW in v0.0.78 — The Imperial Annals Rewritten
The campaign's **Manage Campaign** menu now includes **Use Game Texts** and **Rewrite Timeline**. Point the former at your local Stellaris installation folder to retrieve English project descriptions, then run the latter while Live History is OFF. Rewrite Timeline inspects every archived save metadata header and existing parsed cache without deleting databases, resets, or Ironman saves. It then regenerates the readable chronology. See `documentation/release_notes/README_v0.0.78.md` for details.

# Stellaris Historian

Stellaris Historian is a local companion application for **Stellaris** that watches Ironman save files and builds a historical record of your empire over time.

It is designed to turn a campaign into a living historical archive rather than just a collection of save files. Historian compares successive archived saves, extracts evidence, stores structured history, and produces readable journal/timeline output while deliberately avoiding unsupported conclusions.

## Current version

## Current release: v0.0.90 — The Readable Annals

A source-only editorial upgrade to the Imperial Annals: Highlights/Standard/Complete reading modes, month and year source-based extracts, explicit source-date labels, safer linked person/war chronologies, personal notes and pins isolated in the browser, selected-year HTML exports and new roadmap. No changes to the Ironman archives, databases, parser or worker. See [v0.0.90 release notes](docs/RELEASE_v0.0.90.md) and [the development roadmap](roadmap/ROADMAP.md). Historian must be restarted with `start.bat`; Stellaris need not be restarted.


### v0.0.77 — The Living Annals (approved timeline concept)

The canonical `/timeline` is now rebuilt in the approved parchment-and-starfield design. Every record passes through date-aware narrative logic: people entering service are separate from later observed assignments; major named ships are commissioned on verified dates and first-observed fleet postings appear on their own archived dates; battles are recounted as campaigns, with named systems, formations, commanders and retained aggregate losses, rather than a technical audit. War beginnings are individual clickable entries as well as multi-year bands. Historical qualifications, first-observation bounds, data-source identifiers and unconfirmed outcomes belong on the **back of a floating card**, never in a fabricated narrative. No made-up ship destruction, withdrawal, or survivor-return claims.

The design remains locally rendered from the current Historian SQLite archive. It includes clickable war/leader links, date jump, category filters, print output, and draggable/flippable details. No migration or save reprocessing required. See [v0.0.77 notes](documentation/release_notes/README_v0.0.77.md).

### v0.0.76 — Fleet Rolls, Story Threads & CSS Stability

The Empire Timeline now draws additional named major-vessel histories from the already-indexed ship registry, with first-sighting fleet/commander assignments only; previously recorded construction dates are distinguished from the later assignment observation. Recorded scientific situations and special projects enter a new **Story** category, but it does not fabricate event decisions or plot conclusions. Ruler/government-era voice changes are purely stylistic; volunteering, enlistment and motives are never inferred. The dashboard stylesheet has a new cache key and library/control layout fixes. No schema migration, Ironman reprocessing or private data changes. See [v0.0.76 notes](documentation/release_notes/README_v0.0.76.md).

### v0.0.75 — The Imperial Annals

The classic vertical Empire Timeline is now the primary chronology. Multi-year war rails run alongside the event list; event and war detail cards can open, flip, move, and link into the Empire Archive and War Journal. The timeline uses historical rather than player/debug narration and displays archived observation bounds without fabricating peace dates. The previous standalone Interactive Timeline has been retired from the interface and its bookmarked route redirects to `/timeline` (its internal evidence code remains available to the Time Machine). The campaign dashboard now has three simple top controls: Live History, Explore History and Manage Campaign. All existing archive views remain accessible in the Observatory. See [v0.0.75 release notes](documentation/release_notes/README_v0.0.75.md). No migration, save reprocessing or SQLite changes.


### v0.0.74 — Galactic Observatory: Time Machine & Nine-Chapter Scribes Chronicle

A large presentation and historical-provenance milestone. The **Empire Time Machine** steps through actual **processed archive dates**, with a date slider, playback, filtering, event dossiers and optional JSON export. It uses the existing reviewed timeline history plus durable SQLite government/ruler observations and first/last registry sighting windows; it **never presents those windows or latest attributes as a real-time historic census**. The Scribes Chronicle gains a dramatic astronomy-inspired cover (including in PDF), chapter contents and anchors, night reading mode, reading progress, a new **Chambers of Power** chapter based on published political history, and corrections for stale empire naming, colony founding/acquisition distinctions and supposed ruler signatures. The dashboard includes a Historical Observatory for all six local history views. **No database migration, cache invalidation, source-save rewrite, or Live History pipeline modification.** See [release notes](documentation/release_notes/README_v0.0.74.md).


### v0.0.73 — Interactive Empire Timeline

Use the dashboard **Timeline** button to open a fully interactive archive: play or drag through evidence-backed dates, search, choose event categories, inspect dated records with provenance, and export filtered data. Ground battles, federation and Galactic Community entries remain empty where the current save-derived history has not established them; the empire's internal council agenda is labelled separately. The existing printable PDF timeline stays available. This reads durable SQLite records, reviewed cached history and the existing First Contact JSON without re-opening game saves or changing Live History. See [v0.0.73 release notes](documentation/release_notes/README_v0.0.73.md).


### v0.0.72 — Empire Archive: Leaders, Worlds, Navy and Diplomacy

Adds an evidence-first, searchable **Empire Archive** separate from the War Journal. From the campaign dashboard, open a fast local record browser for the chronology, leadership careers, colonised worlds, fleets, individual ships and diplomacy. Browse record details with source dates, known observations and linked events; filter by year/search terms and optionally include technical events. CSV and JSON exports are generated in the browser. **Only pre-existing SQLite records are read**: no new raw save parsing, database migration, schema/cache invalidation or Live History slowdown. No screenshot annotations. See [v0.0.72 release notes](documentation/release_notes/README_v0.0.72.md).


### v0.0.71.1 — Save-Only War Journal Evidence

Removes the use of manually supplied screenshots and hard-coded outcome/name annotations from the War Journal and downloaded war briefs. Names are displayed only when recovered from native war records or the independently parsed diplomatic/combat caches. Outcomes not established by save evidence are left unverified, and end dates remain bounded by archive observations. The legacy annotation JSON files can remain on disk; this update no longer reads them. No saves, databases, archive caches or Live History processing are changed. See [v0.0.71.1 notes](documentation/release_notes/README_v0.0.71.1.md).


### v0.0.71 — Research Date Integrity & Wartime Coverage

Same-day Ironman snapshots now contribute one observation day to the completed-technology evidence ledger: no more impossible `after X and by X` acquisition intervals. Research progression uses an observed high-water level so a partially missing cache cannot imply that completed research was lost and re-acquired. The War Journal labels technology archive coverage and first-war boundary overlaps, and its TXT briefs retain those evidence caveats. The technology diagnostic reports duplicate-date and disagreement statistics. **No database migrations, save reparsing, cache version changes, or Live History processing changes.** See [v0.0.71 release notes](documentation/release_notes/README_v0.0.71.md).



### v0.0.70 — War Journal Navigation, Evidence Dossiers & Wartime Research

A larger War Journal usability and historical-evidence release: chronological jump index; bookmarkable per-war URLs; previous/next war navigation at both ends of each report; compact dated war chronologies and annual battle ledger; theatre-to-battle shortcuts; evidence-aware text dossier copy/download; collapsible investigation tables; and completed technologies first observed during each war using existing technology caches. Maintains v0.0.69 victory screenshot provenance and unverified exhaustion handling. **No SQLite schema changes, no save reparsing, and no revision to Live History processing.** See [README_v0.0.70.md](documentation/release_notes/README_v0.0.70.md).

### v0.0.69 — War Chronicle Verification and Progress

Adds screenshot-sourced victory notifications for the two verified Commonwealth wars, provenance-aware end windows, honest war-exhaustion labels, per-battle fatigue-field evidence, and a responsive background ground/starbase investigator with live progress and reuse of v0.0.68 military indexes. **Normal Live History and research-technology acquisition tracking are unchanged.** See [README_v0.0.69.md](documentation/release_notes/README_v0.0.69.md).

### v0.0.68 — Military History Evidence

Adds enemy-aware war titles, on-demand ground-battle and occupation analysis, and enemy-starbase combat-activity evidence without changing live-save processing or the database. See [README_v0.0.68.md](documentation/release_notes/README_v0.0.68.md) for limitations and installation.


### v0.0.54 — Processed Combat Diagnostic Synchronization

v0.0.54 fixes a live-testing gap exposed during the Commonwealth of Man / Hulfiran war. Normal History processing had current formal-war evidence in the per-snapshot cache, but the forensic combat text files could remain frozen at the snapshot count from the last full Review Campaign.

### What changed in v0.0.54

- **Processed-only combat diagnostic sync:** `Combat_Evidence_Debug.txt`, `Combat_Correlation_Debug.txt` and `Combat_Episode_Debug.txt` are regenerated from snapshots that completed normal History processing.
- **No raw-save reparse:** the synchronization is cache-only. If a processed cache is missing/stale, Historian leaves the existing diagnostic files unchanged and recommends Review Campaign rather than silently reopening Ironman saves.
- **Manual Update History can catch diagnostics up:** even with zero new saves, Update History will synchronize combat diagnostics when the queue is already at zero.
- **Queue-first Live History retained:** automatic combat-diagnostic synchronization runs only after the normal History queue is caught up.
- **Processed-only presentation cache input:** War Journal, Timeline and Scribes cache readers now ignore archived-but-unprocessed snapshots.
- No SQLite schema change, cache component version bump, archive rewrite or processed-flag reset is required.

### Code areas changed in v0.0.54

- `app.py` — triggers the cache-only combat diagnostic synchronization after manual/automatic History catch-up.
- `historian/history_processor.py` — adds the processed-snapshot combat diagnostic synchronization pass.
- `historian/snapshot_cache.py` — adds a cache-only load mode that refuses raw-save fallback.
- `historian/presentation_history.py` — limits cached presentation evidence to processed snapshots.
- `migrate_v0_0_54.py` — safe one-time source migration with backups and validation.
- `start.bat`, `README.md`, `docs/CHANGELOG.md` and `historian_manifest.json` — v0.0.54 release metadata.

## Recent development progress

| Version | Main change | Status |
| --- | --- | --- |
| **v0.0.72** | Searchable multi-domain Empire Archive with record inspections, source evidence and exports | Current development version |
| **v0.0.71.1** | Save-only War Journal facts and evidence provenance | Retained |
| **v0.0.71** | Research-date integrity, War Journal coverage and evidence-aware TXT briefs | Retained |
| **v0.0.70** | Navigation, wartime research and war evidence dossiers | Retained |
| **v0.0.54** | Processed-only combat diagnostic synchronization and presentation cache gating | Retained |
| **v0.0.53** | Queue-first Live History processing plus per-domain performance telemetry | Retained |
| **v0.0.52** | Dedicated evidence-led War Journal separating formal wars from combat episodes | Tested and retained |
| **v0.0.51** | Unmistakable manual workflow completion/error banner in the CMD window | Tested and retained |
| **v0.0.50.4** | Stellaris adjective inflection for generated First Contact names; owner diagnostic polish | Tested and retained |
| **v0.0.50.3** | Nested generated-name grammar, technical-key filtering and candidate diagnostics | Superseded by v0.0.50.4 |
| **v0.0.50.2** | Followed First Contact country IDs into later raw/diplomatic state | Superseded |
| **v0.0.50.1** | Added reciprocal counterpart → player completion detection | Retained |
| **v0.0.50** | Added structured First Contact decoder and Journal section | Retained |
| **v0.0.49** | Added Select New Campaign and First Contact evidence probe | Previous GitHub baseline before the v0.0.50.x development line |
| **v0.0.48.x** | Politics/Diplomacy filtering, refresh progress and Live History route fix | Retained |
| **v0.0.47.x** | Live History, structured Politics/Diplomacy and durable-history hotfix | Retained |

For the full code-level history, see [`docs/CHANGELOG.md`](docs/CHANGELOG.md).


## Features

- Watches Stellaris Ironman saves automatically.
- Archives save checkpoints without modifying the original Stellaris save.
- **Live History ON/OFF** can automatically process newly archived saves.
- **Select New Campaign** safely returns to campaign selection without refreshing the browser.
- **Update History** processes only new archived saves.
- **Review Campaign** re-reads the archive using the current Historian logic without discarding existing campaign data.
- **Construct Campaign** rebuilds generated history from the archived campaign when a full reconstruction is required.
- Tracks leaders, recruitment/service dates, assignments, traits, council roles, ruler state and evidence-backed exits/deaths.
- Tracks ships, fleets, commissioning evidence, fleet membership, commanders, refits/upgrades and build-site evidence.
- Tracks researched technologies and first-observed acquisition windows.
- Tracks colonies/worlds, founding evidence, population snapshots, designation and ownership changes.
- Tracks archaeology, special projects, situations and other science/exploration evidence conservatively.
- Tracks direct combat telemetry, exact ship combat-activity markers, combat correlations and synthesized combat episodes.
- Generates a searchable, non-war **Empire Archive** for leaders, worlds, fleets, ships, politics and diplomacy.
- Generates a dedicated **War Journal** that keeps formal wars separate from non-war combat episodes and preserves evidence confidence/loss semantics.
- Tracks structured Politics/Diplomacy evidence including government, authority, ruler, council agendas, traditions and diplomatic relation-state changes.
- Decodes structured First Contact cases by linking leader `first_contact_system` assignments to `first_contacts.contacts.<id>` save records.
- Checks First Contact completion evidence in both directions: player → counterpart and counterpart → player.
- Generates a Historical Journal, Empire Timeline and Scribes-style campaign narrative from evidence retained in the archive.
- Produces diagnostic files so historical claims can be audited against the underlying parsed evidence.
- Runs locally; no cloud service is required for normal Historian operation.

## Evidence-first design

Stellaris Historian deliberately distinguishes **what the save proves** from what merely looks likely.

Examples:

- A ship disappearing from one archived snapshot does **not** automatically mean it was destroyed.
- `last_combat_activity` proves an exact retained combat-activity date, but does not by itself prove the opponent, result or losses.
- A leader disappearing from the active leader record is not automatically recorded as dead unless stronger retained evidence exists.
- A First Contact assignment ending is not automatically treated as completion unless a counterpart-specific completion marker is retained.
- Quarterly archive boundaries are reported as observation windows when Stellaris does not retain an exact event date.

The aim is to make the final historical record readable without silently inventing missing facts.

## Main generated output

Historian currently produces or maintains outputs including:

- `Historical_Journal.html` — detailed evidence-backed campaign history.
- `War_Journal.html` — dedicated military-history view separating formal wars from reconstructed combat episodes.
- `Empire_Archive.html` — evidence-led searchable leader, world, fleet, ship and diplomacy records.
- Empire Timeline — chronological view of major historical events.
- Scribes Chronicle — flowing narrative presentation of the campaign.
- `historian.db` — local SQLite historical state.
- Campaign snapshot cache — parsed components used to avoid reopening every raw save unnecessarily.
- Diagnostic files under each campaign's `diagnostics` folder, including First Contact, Politics/Diplomacy, combat, science, technology, leader-exit and notification evidence.

## Requirements

- Windows
- Python 3
- Stellaris
- Steam version currently assumed by the default configuration

## Installation

1. Download the repository.
2. Extract it to a folder of your choice.
3. Copy `config.example.json`.
4. Rename the copy to `config.json`.
5. Edit `config.json` and set your Stellaris save location.

Example Steam save path:

```text
C:\Program Files (x86)\Steam\userdata\YOUR_STEAM_USER_ID\281990\remote\save games
```

6. Run `start.bat`.

Stellaris Historian will create its Python environment and install required dependencies if needed.

## Dashboard

Once running, the dashboard is available at:

```text
http://127.0.0.1:8766
```

The campaign screen provides Update History, Live History, Review Campaign, Construct Campaign, Historical Journal and War Journal access, plus campaign switching controls.

## Updating

If you downloaded the project using Git, update it with:

```text
git pull
```

Then restart Stellaris Historian when an update includes application code, migrations or startup changes. Patch notes and migration output state whether a restart or cache rebuild is required.

## Versioning and migrations

Historian uses small versioned migrations for changes that need to update release metadata or local application state. Migration logs are written under `logs` and migration markers are stored under `data`.

v0.0.71 adds conservative completed-technology date grouping and coverage reporting; v0.0.54 added cache-only combat diagnostic synchronization after History catch-up and restricts cached presentation evidence to processed snapshots. It does **not** change the SQLite schema or parsed-cache component versions, so no full cache rebuild is required.

## Data and privacy

Stellaris Historian runs locally on your computer.

Your personal `config.json`, Stellaris save files, campaign archives, logs, databases, backups and other runtime data are excluded from the GitHub repository. The project is designed to analyse local save data rather than upload campaign data to a hosted Historian service.

## Project status

Stellaris Historian is under active development. The codebase is being expanded in small, testable stages, with live campaign diagnostics used to validate evidence rules before features are promoted into public historical narrative.

Current development priorities include expanding the War Journal with safely linked wartime chronology, richer diplomacy/aftermath evidence, and continuing to turn retained Stellaris save evidence into a reliable long-form campaign history.

## Known limitations

- Stellaris does not retain every event or notification forever, so some exact historical details may be impossible to reconstruct from quarterly archives alone.
- Some dynamically generated names depend on localisation grammar, DLC/mod data and nested save variables; these are being expanded conservatively rather than guessed.
- v0.0.52 does not yet attribute ship commissioning, refits, technology gains or diplomatic aftermath to a specific war unless later evidence-linking rules can establish that connection safely.
- A disappearing object is not automatically treated as destroyed, dead, completed or failed unless stronger evidence exists.
- Steam is currently assumed by the default save-location configuration.
- The application is under active development and file formats/diagnostics may evolve.

## Author

**PillBoxUK**

## Important — use at your own risk

Stellaris Historian is experimental software and is provided **“as is”**, without warranty of any kind. You download, install and use it entirely at your own risk.

Please make backups of any Stellaris saves or other data that you consider important before using it. Although the program is intended to read and analyse Stellaris save data locally, bugs, compatibility problems, configuration errors or other unexpected behaviour may occur.

To the fullest extent permitted by applicable law, I accept no responsibility or liability for any loss, damage, corrupted saves, lost gameplay progress, lost data, software or system problems, or other direct or consequential damages resulting from the installation or use of Stellaris Historian. By using the software you accept responsibility for maintaining your own backups and recovery copies.

Nothing in this disclaimer excludes or limits liability where doing so would be prohibited by applicable law.
