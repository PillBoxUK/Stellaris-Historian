# Stellaris Historian v0.0.39
## Diagnostics Housekeeping + Launcher Repair

v0.0.39 is a small housekeeping patch after the v0.0.38 combat reconstruction release.

### Campaign diagnostics folder
Review Campaign and Construct Campaign now write diagnostic files into:

`<campaign archive>\diagnostics\`

The folder contains the current evidence/debug outputs, including:
- `Science_Evidence_Debug.txt`
- `Science_Interpretation_Debug.txt`
- `Combat_Evidence_Debug.txt`
- `Combat_Correlation_Debug.txt`
- `Historical_Event_Debug.txt`
- `Technology_Evidence_Debug.txt`

The console prints the exact diagnostics directory each time these files are generated.

### Legacy file housekeeping
The one-time v0.0.39 migration looks for existing diagnostic files sitting beside archived `.sav` files and moves them into that campaign's `diagnostics` folder when the destination filename is free. It never overwrites an existing diagnostic file.

### Launcher repair
The UTF-8 STELLARIS banner is no longer emitted through individual Windows `echo` commands. `start.bat` now uses `type assets\stellaris_banner.txt`, avoiding `cmd.exe` interpreting box-drawing characters as commands.

### Cache / database behaviour
- No cache component versions change.
- No database schema changes.
- No archived saves are renamed or deleted.
- No processed flags are reset.
- A Review Campaign is optional for compatibility, but recommended once if you want every diagnostic refreshed in the new folder.

### Install
1. Stop Stellaris Historian.
2. Extract this patch over `G:\codex\StellarisHistorian\`.
3. Run `start.bat`.
4. Optional but recommended: run **Review Campaign** once.
5. Open the diagnostics folder path printed in the console.

**Restart required: YES.**
