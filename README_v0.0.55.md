STELLARIS HISTORIAN v0.0.55 - WAR JOURNAL OUTCOME AUDIT

This is a conservative presentation patch, not a blanket 63-battle result reversal.

CONFIRMED:
- v0.0.54 cache contains 312 processed snapshots and raw battle flags.
- The battle victory mapping remains disputed; holding an unverified outcome is safer than rewriting recorded history.
- The War Journal can show raw tactical player role + attacker_victory yes/no side by side.

CHANGES:
- Formal battle player result is now visibly UNVERIFIED with raw flag and tactical role.
- Combat-episode 'formal outcome' labels are flagged as under review.
- Commander names duplicated as fleet names are hidden in War Journal display.
- The source exporter creates autobackups/ and writes exports there, excluding itself from ZIPs.
- Version shown as 0.0.55. No database, save, migration or cache changes.

NOT YET FIXED:
- The fundamental Stellaris attacker_victory semantics remain to be independently verified.
- Combat episode grouping and broader fleet naming resolution need separate follow-up testing.
- Other historical views and diagnostic counts continue to reflect the cached 0/63 mapping; do not treat those values as independently verified.

INSTALL:
1. Stop Historian (close its start.bat server). Keep the game saved/paused.
2. Back up existing project files (especially app code and data) before extraction.
3. Extract ZIP into G:\codex\StellarisHistorian, preserving paths and replacing files.
4. Restart via start.bat; verify v0.0.55.
5. Open the War Journal and verify columns show Unverified and the raw fields.
6. Do NOT perform Review Campaign or Construct Campaign for this presentation-only patch.

Restart required: YES.
Database migration: NO.
Raw Ironman saves modified: NO.
GitHub publication: NO.
