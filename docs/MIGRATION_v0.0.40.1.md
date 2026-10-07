# Migration v0.0.40.1

This hotfix validates the combat telemetry composite-state correction and local folder shortcuts.

## Data safety

- No database schema changes.
- No parsed-cache version changes.
- No archived `.sav` files are renamed, moved or deleted.
- No processed flags are reset.
- Existing campaign folder identities are unchanged.

## Behaviour change

Combat episode retained telemetry is now tracked independently per direct combat key. If a later archived snapshot updates only some participating fleet records, Historian keeps the last retained state for the missing participants when constructing the latest complete composite state.

This prevents a later partial snapshot from hiding genuine telemetry evolution such as the 2241 Sila/Voidworm episode.

## Folder shortcuts

The active campaign page now contains **Open Campaign Folder** and **Open Diagnostics Folder** buttons. These open the existing on-disk folders directly; this hotfix deliberately does not rename campaign directories.

## After installation

Run **Review Campaign** once so `Combat_Episode_Debug.txt` and `Historical_Event_Debug.txt` are regenerated under the corrected v0.0.40.1 logic.
