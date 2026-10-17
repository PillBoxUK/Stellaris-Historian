# Stellaris Historian v0.0.90 — The Readable Annals

**Created for:** PillBoxUK  
**Base application:** v0.0.89  
**Nature of release:** Source-only, non-destructive presentation overlay.  
**Primary objective:** Make the Imperial Annals easier to read without compromising the original Ironman evidence.

## 1. Delivered improvements

### Narrative structure and reading levels

- Adds **Highlights, Standard and Complete** reading levels on `/timeline`.
- `Highlights` focuses on historically prominent events (including explicitly identified firsts, government crises and wartime turning points); `Standard` retains more everyday activity; `Complete` reveals all dated events. **Nothing is removed from the source or database.**
- Adds dated **monthly sections** and short editorial extracts taken only from existing event body text. A headline or excerpt is never treated as a new occurrence.
- The original chronological event cards remain inline and clickable, with full prose preserved inside the cards. Complete mode shows everything.
- Adds short **yearly extracts** in Highlights mode. These are existing paragraphs, not invented summaries or interpretations.
- The chosen reading level is a browser preference and can be changed at any time.

### Historical evidence and source dates

- Event details differentiate **Dated event**, **First recorded by**, **Already recorded at the opening**, **Date evidence varies**, and **Archival date**.
- Labels use the event's existing `date_kind` metadata. Unknown date kinds remain unverified; they are never silently promoted to exact dates.
- The optional flipped card retains the original evidence notes. No dates or outcomes are generated from screenshots, player observations or missing saves.

### Connected histories and wars

- Where events have the **same saved leader ID**, their other dated entries appear together in a detail card. Names alone are not used to join records.
- War cards show additional dated entries *only when their `war_id` was securely joined by the existing historical layer*.
- Active/last-observed wars and native starts retain their respective status; no unverified peace treaty, war conclusion or victory is invented.

### Personal editions and chapter exports

- Users may **pin** dated entries, **annotate** an event, and give a year a **personal chapter title**.
- Personal writing and pins stay only in the browser's local storage for the selected campaign ID. They do **not** write to the campaign database, historical records, or Ironman archive. They do not synchronise to other devices.
- Exports a **standalone HTML selection of years**, retaining all dated underlying entries in that range and including browser-authored notes in visually separate **PERSONAL ANNOTATION — NOT SOURCE EVIDENCE** sections.
- The HTML can be opened independently and printed to PDF using the browser. Existing *Print / PDF* remains available.
- Theme-appropriate, colour-contrasting styles are supplied for light and dark mode and white-paper printing.

## 2. Relation to the ten editorial priorities

| Editorial priority | v0.0.90 status |
| --- | --- |
| Consistent historical prose | Existing source text preserved, editorial extracts only; full style rewrite remains open |
| Government-appropriate vocabulary | Existing v0.0.89 behaviour preserved; fuller cross-authority vocabulary work remains open |
| Monthly and yearly narrative | Monthly headings and verbatim narrative extracts; annual extracts in Highlights mode |
| Event versus observation dating | Explicit conservative date labels and source notes |
| Reading levels | Highlights, Standard, Complete |
| Circumstantial event importance | Conservative, non-evidentiary presentation ranking; browser pins |
| Connected people, places and institutions | Same-ID people links and existing archive links; other identity joins remain open |
| Complete war narrative | Dated, already-linked war chronology; unknown outcomes remain unknown |
| Verified units and policy meaning | No new unsupported statistics; validation and rights-vs-practice analysis remain open |
| Personal annotations and exports | Notes, pins, chapter titles and selected-year HTML export |

This is the *editorial foundation*, not a claim that every outstanding evidence domain has been decoded.

## 3. Data integrity and scope

- **No changes** to original `.sav` files, database structure, cache components, parser, `app.py`, watcher, live processing, or game state.
- Source-only patch; user's `data/`, databases, credentials, installation config, `.venv`, and archives are **not supplied or replaced**.
- Reading-level visibility and user notes have no authority over history. The `.sav` evidence and derived data remain the source of truth.
- Historical event dates remain on the **Stellaris game calendar**. This patch does not apply Gregorian intervals to game events.

## 4. Installation — restart required

1. With the game paused or running, turn Historian Live History **OFF** and wait for any active job to complete. Close the Historian server and browser page.
2. Back up the installation folder and your campaign SQLite database/archive separately.
3. Extract `Stellaris_Historian_Patch_v0.0.90.zip` **into the existing source root**, e.g. `G:\codex\StellarisHistorian\`, preserving the folders. Select overwrite for the included source files. **Do not extract it into an extra nested folder.**
4. Launch `start.bat` and check the console reads **Stellaris Historian v0.0.90**.
5. Select the campaign and choose **YES — Start Live History** if required. Confirm the dashboard shows ON before playing.
6. Open **Empire Timeline / Imperial Annals**. Switch between reading modes, open a dated entry, add a personal note or pin it, then export a test year to HTML.
7. Check both light and dark mode, then print a short chapter to PDF if desired.

**Restart Historian:** **YES**, via `start.bat`.  
**Restart Stellaris:** **NO**.  
**Historical rebuild / database migration:** **NOT REQUIRED**.  
**GitHub:** Source is ready for a commit, but creating this ZIP does not push to GitHub.

## 5. Verification

- Isolated automated tests: **28 passed, 15 subtests passed**.
- Python module compilation and JavaScript syntax checked.
- Rendered a local sample Imperial Annals page with two synthetic **test fixture** events. This fixture checks HTML generation only and is not source evidence for a campaign.
- The full user's SQLite and Ironman archives were **not included** in the source backup, so real-campaign interactive browser validation, Windows browser storage persistence and PDF output require local verification.

## 6. Known limitations

- Monthly extracts use original event prose; they do not yet produce independent, richly connected historical chapters. Some prose can be repeated as a reading aid.
- Browser-local notes may be lost when site data are cleared. Export important annotations to HTML; future optional user-authored annotations backup is a roadmap item.
- Existing underlying event classification and extraction coverage are unchanged.
- `Complete` is the authoritative complete visible archive **for the evidence already recovered and published**, not proof that every event in the game was saved.
- User-entered chapter titles are personal and should never be confused with official Stellaris event names.
