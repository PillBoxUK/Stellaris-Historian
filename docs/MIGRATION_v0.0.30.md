# Migration v0.0.30 - Science Story Arcs & Journal Publication

## Purpose

Promote selected Science / Expeditions evidence into `Historical_Journal.html` without changing the raw Science cache contract.

## Safety

This migration does not modify:

- archived `.sav` files;
- `data/historian.db`;
- processed/unprocessed snapshot flags;
- existing `.historian_cache` JSON files.

Science remains cache component `science` version `1`.

## Functional changes

- Added `historian/domains/science/journal.py`.
- Added the `Science, Exploration and Discoveries` journal section and navigation link.
- Added conservative Red Giant story-arc grouping.
- Added archaeology and linked research-project publication.
- Added selected narrative situation publication.
- Fixed special-project identity to include both numeric project ID and project key, preventing recycled numeric IDs from mixing evidence between unrelated projects.

## One-time cleanup

The previous `migrate_v0_0_29.py` helper is backed up and removed after validation. Disposable bytecode folders are cleaned.
