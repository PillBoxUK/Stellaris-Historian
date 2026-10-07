# Stellaris Historian

Stellaris Historian is a local companion application for **Stellaris** that watches Ironman save files and builds a historical record of your empire over time.

It is designed to turn a campaign into a living historical archive rather than just a collection of save files. Historian compares successive archived saves, extracts evidence, stores structured history, and produces readable journal/timeline output while deliberately avoiding unsupported conclusions.

## Current version

### v0.0.50.4 — First Contact Adjective Inflection & Diagnostic Polish Hotfix

The current development line expands the original historian into structured Politics/Diplomacy and First Contact history. v0.0.50.4 is a narrowly scoped follow-up to the live v0.0.50.3 Commonwealth test: the generated-name structure was finally decoded correctly, but Stellaris' adjective suffix grammar still needed to turn roots such as `Hazar` into the in-game adjective `Hazaran`.

### What changed in v0.0.50.4

- Applies Stellaris' installed `adj_NN*` adjective suffix localisation rules inside `%ADJECTIVE%` generated empire names instead of treating the saved base noun as the final adjective.
- Fixes the live contact-91 result from `Stellar Hazar Council` to the expected generated form `Stellar Hazaran Council` when the installed Stellaris localisation contains the matching `r -> *ran` adjective rule.
- Mirrors Stellaris' one-at-a-time generated-name variable substitution and removes only unresolved numeric continuation placeholders after normal substitutions.
- Restores the First Contact diagnostic owner label from the selected campaign identity when the contact owner is the player country, preventing `Owner: Country 0` from replacing `Owner: Commonwealth of Man`.
- Retains v0.0.50.3 technical-name rejection, `NAME_*` cleanup, nested `%ADJ%` / `%ADJECTIVE%` rendering, later candidate scanning and reciprocal First Contact completion detection.
- Keeps accepted/rejected candidate diagnostics so generated-name decisions remain auditable.
- No SQLite schema change, parsed-cache version bump, archive rewrite or full cache rebuild is required.

### Code areas changed in v0.0.50.4

- `historian/domains/politics/first_contact_history.py` — Stellaris `adj_NN*` suffix rendering, generated-name placeholder semantics, player-owner diagnostic restoration and v0.0.50.4 diagnostics.
- `historian/domains/politics/first_contact_journal.py` — First Contact Journal description updated to reflect adjective-grammar rendering.
- `migrate_v0_0_50_4.py` — one-time release metadata migration and README/source validation.
- `start.bat` — v0.0.50.4 startup banner and migration hook.
- `README.md` — current-version notes, code-change details and development progress updated for v0.0.50.4.
- `docs/CHANGELOG.md` and `historian_manifest.json` — updated automatically by the migration with v0.0.50.4 release metadata.

## Recent development progress

| Version | Main change | Status |
| --- | --- | --- |
| **v0.0.50.4** | Stellaris adjective inflection for generated First Contact names; owner diagnostic polish | Current development version |
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

The campaign screen provides Update History, Live History, Review Campaign, Construct Campaign, Journal access and campaign switching controls.

## Updating

If you downloaded the project using Git, update it with:

```text
git pull
```

Then restart Stellaris Historian when an update includes application code, migrations or startup changes. Patch notes and migration output state whether a restart or cache rebuild is required.

## Versioning and migrations

Historian uses small versioned migrations for changes that need to update release metadata or local application state. Migration logs are written under `logs` and migration markers are stored under `data`.

The v0.0.50.x First Contact work does **not** change the SQLite schema or parsed-cache component version, so no full cache rebuild is required for v0.0.50.4.

## Data and privacy

Stellaris Historian runs locally on your computer.

Your personal `config.json`, Stellaris save files, campaign archives, logs, databases, backups and other runtime data are excluded from the GitHub repository. The project is designed to analyse local save data rather than upload campaign data to a hosted Historian service.

## Project status

Stellaris Historian is under active development. The codebase is being expanded in small, testable stages, with live campaign diagnostics used to validate evidence rules before features are promoted into public historical narrative.

Current development priorities include final validation of generated First Contact identity resolution, richer combat/war presentation, and continuing to turn retained Stellaris save evidence into a reliable long-form campaign history.

## Known limitations

- Stellaris does not retain every event or notification forever, so some exact historical details may be impossible to reconstruct from quarterly archives alone.
- Some dynamically generated names depend on localisation grammar, DLC/mod data and nested save variables; these are being expanded conservatively rather than guessed.
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
