# Release, source safety and GitHub checklist

## Inputs
- [ ] Receive and inspect actual latest clean source ZIP exported from installed v0.0.86.
- [ ] Confirm protected game saves, user configuration, secrets, logs, database, caches, archived patches and backups are excluded from source/GitHub.
- [ ] Preserve source checksum and existing versioned manifest.
- [ ] Obtain consistent application database copy with the app **stopped**, or use SQLite's backup API (do not copy an active WAL-backed DB file alone).
- [ ] Test against representative start/middle/end archived Ironman files, not screenshots.

## Development
- [ ] Exact native event dates distinguished from first-observed archive dates.
- [ ] All direct traditions/perks and direct war exhaustion reconciled to saved-game records.
- [ ] Same-date captures, repeated keys, identity types and null IDs validated.
- [ ] Rebuild and incremental ingestion verified deterministic and non-destructive.
- [ ] Existing tests and new independent fixtures pass, plus UI smoke tests.
- [ ] No personal or runtime data are bundled in user patch or GitHub code.
- [ ] Include safe rollback steps and an accurate file-by-file change manifest.
- [ ] State **restart requirement** explicitly (code changes require stopping and restarting with `start.bat`); state DB migration and Review/Construct requirements.
- [ ] No application version bump before working code has passed the checks.

## GitHub
- [ ] Reconcile local v0.0.86 source with GitHub v0.0.70 baseline **before** uploading code.
- [ ] Publish code to reviewed feature branch and PR, with tests and provenance.
- [ ] Never force overwrite `main` using an incomplete partial patch.
- [ ] Verify no secrets or campaign data entered the changes.
- [ ] Update main README, changelog and version only when release is ready.
- [ ] Choose an explicit licence before claiming full open-source reuse rights; a public repo alone is not an open-source licence.
- [ ] Merge/tag only after independent evidence and regression checks.

## Stop conditions
Missing latest source ZIP; unclear parser provenance; risk to existing database, archives or saves; unsupported exact dates; tests not run; or inability to reconcile branch and installed code.

**Next input needed:** `G:\codex\StellarisHistorian\autobackups\Historian_Source_20261017_020550.zip` (or newer exported ZIP).

This document is a planning artifact, **not a completed v0.0.87 code patch**.