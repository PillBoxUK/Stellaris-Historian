# Stellaris Historian — Roadmap

> Planning baseline: installed local v0.0.86 (17 October 2026). The current GitHub main README and manifest still show v0.0.70. This is **planning documentation only**, not an implemented release.

## Mission
Stellaris Historian transforms archived Ironman save evidence into an engaging, chronologically accurate, month-by-month history of a civilisation. The timeline is the heart of the project.

**Evidence rule:** campaign history originates in original Ironman saves and a traceable database generated from them. Screenshots and recollections are investigation/QA prompts, **not historical proof**. Game scripts and localisation explain what events mean, not whether they happened.

## Proposed development phases

| Phase | Versions (targets) | Goal |
| --- | --- | --- |
| **1. Evidence integrity** | **0.0.87–0.0.89** | Fix native dated events, traditions, exhaustion, IDs/names, dates and safe reconstruction |
| 2. Living Chronicle | 0.0.90–0.0.94 | Natural continuous historical prose; full meaning on the main timeline |
| 3. People and government | 0.0.95–0.0.99 | Careers, achievements, politics, economy, society |
| 4. Galactic history | 0.1.0–0.1.4 | Military conflicts, diplomacy, discovery, institutions |
| 5. Historical library | 0.1.5–0.1.9 | Searchable archives, rich navigation, PDF/EPUB publications |
| 6. Public release | 1.0 | Stable migrations, tests, installation, licensing, reliable provenance |

Proposed versions are **not dates, guarantees or completion claims**.

## This folder
- [Phase One — evidence integrity](PHASE_01_EVIDENCE_INTEGRITY.md) details work and acceptance gates.
- [Evidence contract](EVIDENCE_CONTRACT.md) defines publishable and non-publishable data.
- [Release checklist](RELEASE_CHECKLIST.md) covers installation, GitHub, tests and safety.

## Government census
Routine public government censuses run **every four in-game years** from the opening campaign year, with exceptional publication for evidenced leadership deaths or political transformations. Preserve annual/quarterly internal observations and meaningful transitions. This is an **editorial presentation policy**, not a claim that Stellaris conducts censuses every four years.

## Dependency: latest source code
A local screenshot reports a clean source-export ZIP with **267 files, 0.68 MB**, at **G:\codex\StellarisHistorian\autobackups\Historian_Source_20261017_020550.zip**. This file has not been uploaded to the conversation. It excludes saves, databases, virtual environments, logs, backups, personal configuration and credentials. Upload and inspect the actual ZIP before coding or replacing newer source on GitHub. The cleanup screenshot reports **zero files moved** and no deletions.

Research: [Ironman archive reference](https://deonchapman.co.uk/codex/Stellaris/Historian_Documentation/Ironman.html).