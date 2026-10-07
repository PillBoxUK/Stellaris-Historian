# Stellaris Historian v0.0.40.1
## Combat Telemetry Composite Fix + Folder Shortcuts

This is a focused hotfix on top of v0.0.40.

### Fixed: evolving retained combat telemetry

Stellaris can retain/update the combat record for one participating fleet while omitting another fleet's row from a later snapshot. v0.0.40 treated only same-snapshot complete sets as complete, which made the 2241 Sila/Voidworm episode look unchanged even though later retained per-fleet evidence increased the known player loss total.

v0.0.40.1 tracks each direct combat key independently and carries forward the latest retained state for a participant when that key is absent from a later snapshot.

The episode diagnostic now distinguishes:

- records actually present in the current archived snapshot
- participant records carried forward from an earlier retained state
- the complete composite state reconstructable by that date
- whether the retained loss totals evolved

It still does **not** infer victory/defeat from loss counters and does **not** treat ship disappearance as proof of destruction.

### Folder shortcuts

The campaign page now has:

- **Open Campaign Folder**
- **Open Diagnostics Folder**

These open the actual local folders in Windows Explorer, so the ugly internal campaign directory no longer has to be found manually.

This hotfix does **not** rename the internal campaign directory. Renaming identity-bearing folders remains a separate migration so it can be done safely.

### Data safety

- No database schema changes.
- No cache component version changes.
- No archived saves are renamed/deleted/moved.
- No processed flags are reset.
- Existing campaign folder identity is unchanged.

### Install

1. Stop Stellaris Historian.
2. Extract this ZIP over `G:\codex\StellarisHistorian\` and allow overwrite.
3. Run `start.bat`.
4. Confirm the launcher shows **v0.0.40.1**.
5. Run **Review Campaign** once.
6. Check `Combat_Episode_Debug.txt`; the 2241 direct episode should now show evolving composite telemetry where the retained per-fleet evidence supports it.
7. Use **Open Diagnostics Folder** from the campaign page instead of searching through the campaign path manually.

**Restart required: YES.**
**Review Campaign required: YES.**
