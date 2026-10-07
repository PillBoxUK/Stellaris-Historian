# Migration v0.0.39 - Diagnostics Housekeeping + Launcher Repair

This migration is intentionally small and non-destructive.

## Changes
- Creates a `diagnostics` folder inside each campaign archive when diagnostics are generated.
- Moves known legacy `*_Debug.txt` diagnostic files from a campaign archive root into its `diagnostics` subfolder when safe to do so.
- Review Campaign and Construct Campaign now write diagnostics to that folder going forward.
- The console prints the exact campaign diagnostics directory before writing files.
- The launcher ASCII banner is stored in `assets/stellaris_banner.txt` and displayed with `type`, preventing Windows `cmd.exe` from interpreting UTF-8 box-drawing characters as commands.

## Data safety
- No database schema changes.
- No archived `.sav` files are modified, renamed or removed.
- No parsed-cache versions change.
- No processed flags are reset.
- If a destination diagnostic filename already exists, the migration keeps both files rather than overwriting data.

## After installation
A restart is required because `start.bat` and Python code change. A Review Campaign is not required for data compatibility, but running Review once will refresh all diagnostics in the new folder.
