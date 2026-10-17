# Stellaris Historian v0.0.71 — Research Date Integrity & Wartime Evidence Audit

**Upgrade from v0.0.70.** This is a narrow additive patch; it does not replace your installation, cached Ironman saves, database, or historical record.

## Why this patch exists

Previously, two cached technology snapshots sharing an in-game date could generate the impossible claim “after 2294.04.01 and by 2294.04.01”. A technology that temporarily disappeared from a cached record could also be reported as researched again, even though completed research is normally permanent.

## What changes

- Groups all technology cache snapshots by game date, retaining the **highest completed level actually observed** on each date. This is not a claim about the order of saves within that date.
- A new research acquisition or repeatable technology increase requires a level higher than any earlier observed level. Missing or incomplete snapshots no longer generate phantom re-acquisitions.
- Historical windows use **two distinct archived dates**. The code also handles legacy same-day or inverted bounds conservatively rather than printing logically impossible “after / by” claims.
- Adds a read-only **Technology Archive Audit** section in the War Journal, with distinct date counts, additional same-day saves, date disagreement days, invalid dates and observed new research levels.
- The War Journal shows the number and range of cached research observation dates within each war's archived window, missing-date coverage and explicitly identified windows that cross the start of the war's archive presence.
- War Brief Copy / Save includes the research coverage notes and the individual event caveats.
- `Technology_Evidence_Debug.txt` includes the number of repeated same-day archives, date-disagreement days, invalid-date records, and unique archive dates.
- README links now point to the organised `documentation/release_notes` directory.

## Important limitations

A first observation **is not the exact day of research completion**, even if its saved date is known. Being observed during a war does not prove that the war caused the research. A window that starts before the first retained wartime archive can include prewar research. A missing technology cache cannot prove the research did not occur. The system still does **not** track technology currently in the research queue.

Same-day conflict detection is a provenance warning, not an automatic repair of parsed source data. The source `.sav` files, databases and cache payloads stay unchanged; this release affects only in-memory derivation, rendering and diagnostic reporting.

## Install / backup

1. Wait until **Unprocessed Saves = 0**. Switch **Live History OFF** and completely close Historian.
2. Make sure your existing installation is **v0.0.70**. Keep your data, saves, database, `.historian_cache`, `.historian_evidence`, `.venv` and `autobackups` intact.
3. Extract the patch ZIP into `G:\codex\StellarisHistorian`. It creates a `Stellaris_Historian_v0.0.71_Update` folder rather than overwriting live files.
4. Launch `Stellaris_Historian_v0.0.71_Update\APPLY_PATCH.bat` from within the Historian installation. The updater checks the installed version, verifies payload hashes and saves backups of every target file under `autobackups` **before** changing application files.
5. If the updater reports success, restart Historian using your original `start.bat`. Confirm it reports v0.0.71; open the War Journal and check Research advances on one of your wars.
6. Resume Live History when ready. **No Review Campaign, Construct Campaign or migration required.** The existing War Journal HTML is regenerated when you open it; existing standalone HTML files created before the upgrade are not rewritten automatically.

The updater makes no Git commits or GitHub pushes. Re-running it after a successful install is blocked by version checks.

## Test coverage

`test_v0_0_71.py` uses synthetic data and mock campaign archives to verify duplicate dates, conflicting same-day states, missing-level reappearance, repeatable-level increases, invalid/inverted legacy bounds, wartime boundary labels, no within-war research cache, HTML escaping, and TXT brief wording. Existing v0.0.70 browser/navigation tests remain compatible.
