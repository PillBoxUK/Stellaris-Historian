# Migration v0.0.46 — Politics & Diplomacy Deep Probe

## Purpose

Add a bounded, evidence-only raw-save probe for politics and diplomacy before introducing a persistent interpreted Politics domain.

## Changes

- Adds `historian/domains/politics/`.
- Adds `Politics_Diplomacy_Probe_Debug.txt` under each campaign's diagnostics folder.
- Hooks the probe into Review Campaign.
- Uses existing reviewed government/profile entries and People ruler/heir/death milestones as safe anchors.
- Opens at most 64 raw archived saves for a mature campaign, prioritizing the recent edge and known political transition windows.
- Does not change any existing parsed-cache component version.
- Does not change the database schema.
- Does not reset processed flags.
- Does not modify archived `.sav` files.

## Evidence rule

Raw candidate fields are reported literally. v0.0.46 does not infer or publish a treaty, alliance, election, faction, rivalry, succession cause, first-contact outcome or diplomatic state solely from an unfamiliar raw field name.

## Backups

Before source files are modified, the migration preserves originals beneath `backups/v0.0.46/` using repository-relative paths.

## Required action

After installation, continue the new Earth/UNE test long enough to create several archived states, then run Update History if required and Review Campaign once.

Construct Campaign is not required.
