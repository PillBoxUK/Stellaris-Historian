# Migration v0.0.50 - Structured First Contact Decoder

## Purpose

Promote the v0.0.49 First Contact evidence foundation into a structured decoder and an evidence-first Historical Journal section.

## Source changes

The migration updates `app.py`, `historian/journal.py`, `historian/__init__.py`, `README.md`, `docs/CHANGELOG.md`, and `historian_manifest.json` in place. New decoder and journal modules are supplied by the patch payload.

Backups of source files changed by the migration are preserved under `backups/v0.0.50/`.

## Data safety

No archived `.sav` files are modified or deleted. No SQLite schema changes are made. Processed flags are not reset. The parsed snapshot cache component versions are unchanged.

## Required validation

Run Review Campaign on Commonwealth of Man and inspect `First_Contact_History_Debug.txt` plus the First Contact section of `Historical_Journal.html`. The Hazaran case should resolve only from direct retained contact/country evidence, and any completion date should remain interval-based unless an exact retained completion date is explicitly present.
