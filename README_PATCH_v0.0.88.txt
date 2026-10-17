STELLARIS HISTORIAN v0.0.88 — CIVIC CRISIS & REVOLT CHRONICLE
by PillBoxUK | Installation overlay for v0.0.87.1 or v0.0.87.2

THE IMPERIAL ANNALS REMAINS THE MAIN PRODUCT.

WHAT CHANGED
* Native player-owned situations are now retained with their exact native type, target, stage, progress, current approach, archive date and source save hash.
* When a directly recorded situation key identifies a revolt crisis, Historian publishes chronological changes in the Imperial Annals: initial observed threat, newly observed phase, and first observed disappearance.
* No false claims that a revolt occurred, was defeated, caused deaths, or resulted in independence. The exact original popup text is not reconstructed from save data.
* Civic & Frontier History now displays a dated, save-backed crisis evidence register and offers the full CSV evidence ledger in the campaign archive folder.
* Source-ledger parser updated from v2 to v3; prior v1/v2 records remain readable. No migration or deletion of the main historian.db is required.
* Historical dates remain first-observed unless a real native occurrence date exists.
* Same aligned ASCII Windows Terminal banner retained.

INSTALLATION — HISTORIAN STOP/RESTART REQUIRED
1. Save Stellaris normally (Ironman automatic), and optionally pause it. Stellaris does not have to be closed.
2. In Historian, turn Live History OFF and wait for active processing to finish. Exit Historian fully.
3. Back up G:\codex\StellarisHistorian\data\historian.db and the selected campaign folder.
4. Extract all ZIP contents into G:\codex\StellarisHistorian\. Allow overwriting matching SOURCE files. Do not put the contents in a new nested folder.
5. Restart Historian with start.bat and confirm v0.0.88 is displayed.
6. Select Veyran Shadow Concord 2; answer YES to the recording prompt and confirm Live History ON before continuing play.
7. For past observations, temporarily turn Live History OFF, wait for processing, use Manage Campaign > Update Historical Timeline to re-index previously archived saves, and turn Live History ON again.
8. Use The Imperial Annals for dated crisis developments; Civic & Frontier History for the full evidence record. The CSV is written alongside Civic_Frontier_History.html when that page is opened.

CURRENT GAMEPLAY
The current screenshots of Veyra Prime revolt are *investigation leads only*. The source files provided for testing include one older Ironman archive at 2214.04.01, which does not contain a current player-owned revolt situation. Therefore no 2222 revolt is claimed or inserted into the present user's history by this patch. Future saves, when processed locally, supply the evidence.

SAFETY
ZIP contains source, tests and documentation ONLY. It contains no gamestates, archives, databases, account settings or other user data. The save is never changed by the new extractor. Roll back source files using your source export/backup if required. No GitHub upload was made.

RESTART Historian: YES (start.bat). RESTART Stellaris: NO.
