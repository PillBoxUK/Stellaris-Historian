STELLARIS HISTORIAN v0.0.87 — SHARED THEME AND CLOSE PATCH
by PillBoxUK · incremental patch for an installed v0.0.86

CHANGES
- Dark theme now defaults site-wide: ink-black backgrounds, teal/green/cyan highlights.
- New visible Dark mode / Light mode switch in Campaign and initial selection headers.
- One localStorage preference shared across app pages/tabs; no campaign data accessed.
- Styling attached to generated Imperial Annals, journals, census, people, research,
  war, civic, archive, and time-machine pages as well as static dashboard pages.
- New print safety rule preserves white-paper output regardless of UI theme.
- 'Close Historian' waits for successful shutdown acknowledgement, tries to close
  the current tab; standard manually opened tabs fall back to a blank page.
  Modern browsers DO NOT permit arbitrary website scripts to force-close tabs.
- A roadmap/ROADMAP.md directory records implementation vs future priorities.
- No change to history ingestion, parsing, recording consent or save processing.

INSTALL (stop and restart)
1. Toggle Live History OFF, wait until history processing is idle.
2. Exit the current application completely. Back up the Historian installation,
   especially data/historian.db and ALL archived campaign saves.
3. Extract the accompanying overlay ZIP directly into the existing installation
   root (e.g., G:\codex\StellarisHistorian\); overwrite matching SOURCE files.
   Do not remove old files or create a nested directory.
4. Start with start.bat. Confirm v0.0.87 in the window and browser.
5. Open Campaign, toggle Light/Dark, browse Imperial Annals, Census and Dashboard.
6. Close using Manage Campaign > Close Historian (or Close on start page).

RESTART HISTORIAN VIA start.bat: YES.
RESTART STELLARIS: NO.

PROTECTED DATA: This overlay includes NO *.sav, databases, parsed caches,
 archived campaigns, secrets, personal logs or source-evidence modifications.

LIMITATIONS
- Browser tabs opened by a human cannot reliably be closed by a website.
- Theme relies on /static/ resources served by running Historian; historical HTML
  exports viewed independently offline retain original built-in formatting.
- No real Opera/Chrome Windows visual inspection has been run in this sandbox.
- Browser tests are recommended before claiming every view is pixel-perfect.
- No GitHub push performed; review the overlay and publish from your local copy.
- The project must have a deliberate license to claim legal open-source status.
