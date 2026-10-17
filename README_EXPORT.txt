STELLARIS HISTORIAN - ONE-CLICK SOURCE EXPORT

1. Copy Export_Historian_Source.bat AND Export_Historian_Source.ps1
   into G:\codex\StellarisHistorian (the folder containing app.py and start.bat).
2. Double-click Export_Historian_Source.bat.
3. Upload the new Historian_Source_YYYYMMDD_HHMMSS.zip from that folder.

The utility only reads project files. It DOES NOT stop/restart Historian,
modify live saves, change data, or upload anything itself.

Deliberately excluded: .venv, backups, data/campaigns, logs, payload,
Updates and source, ZIP files, .sav files, SQLite databases, config.json,
secrets and other non-source folders.

Review the resulting ZIP for custom secrets before uploading.
To include additional source directories, edit $folders in the PS1 file.
