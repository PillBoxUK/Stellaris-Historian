# Migration v0.0.44

## Notification & Event Object Decoder

This migration installs the v0.0.44 targeted notification/event decoder.

### What changes

- Adds `historian/domains/people/notification_decoder.py`.
- Adds Review/Construct hooks that generate `diagnostics/Notification_Event_Decoder_Debug.txt`.
- Updates the application version and launcher to v0.0.44.
- Preserves the existing People cache component at version 5.

### What does not change

- No archived `.sav` file is edited, renamed or deleted.
- No processed-save flags are reset.
- No database schema migration is required.
- No cache component is invalidated.
- Journal, Timeline and Scribes presentation logic is not changed by this release.

### Safety

Before changing `app.py`, the migration preserves the original file at:

`backups/v0.0.44/app.py.before_v0.0.44`

### Required action

Run **Review Campaign** once after restarting so the new diagnostic is generated for the existing archive.

Construct Campaign is not required.
