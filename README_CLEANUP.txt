Stellaris Historian - Safe Folder Cleanup Utility

Installation:
Copy Organise_Historian.bat and Organise_Historian.ps1 into
G:\codex\StellarisHistorian\ (alongside start.bat).

Run:
Double-click Organise_Historian.bat and choose 1 to PREVIEW.
Read the report created in folder_reports.
Run again and choose 2 to APPLY, only if the plan looks correct.

Scope: Only explicit root-level old documentation, source ZIPs,
exporter ZIPs, two known utility extraction folders and named old
backup ZIPs are moved. No files are deleted, or overwritten.

DO NOT move: .venv, historian, assets, static, data, backups, logs,
start.bat, config files, migration scripts, or app.py.

Undo after Apply (replace path with the generated manifest):
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Organise_Historian.ps1" -Mode Undo -Manifest ".\folder_reports\Cleanup_Manifest_YYYYMMDD_HHMMSS_fff.json"
Undo will skip restoring a file if the original filename already exists.

This is NOT a replacement for a full backup.
Restart Historian: NOT required for the preview. For applying cleanup,
keep Historian stopped and restart only after the moves are complete.
