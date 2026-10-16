# Migration v0.0.51 — Console Completion Banner & Workflow Clarity

This migration validates the new console workflow tracker and updates release metadata to v0.0.51.

## Behaviour change

Manual **Update History**, **Review Campaign** and **Construct Campaign** operations now end with a large success banner only after their final journal/refresh work has completed:

```text
==========================================
        ALL UPDATES ARE COMPLETED
==========================================
Operation: Review Campaign
Status: SUCCESS
Historian is ready for the next action.
==========================================
```

If the active manual workflow logs one or more errors, the final banner instead reports `PROCESS COMPLETED WITH ERRORS`.

Automatic **Live History** cycles deliberately do not print these banners.

## Data impact

- No SQLite schema change.
- No parsed-cache version change.
- No archived save rewrite.
- No processed-flag reset.
- No full cache rebuild required.

Restart Stellaris Historian with `start.bat` after installing this patch so the v0.0.51 source and migration are loaded.
