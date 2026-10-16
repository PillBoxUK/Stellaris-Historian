# Stellaris Historian v0.0.70 — War Journal Mega Update

A substantial interface-and-evidence milestone on top of v0.0.69. **Upgrade from v0.0.69 only.** This is a narrow replacement ZIP containing nine files, **not** a new installation and not a replacement for the `data` folder.

## New War Journal features

1. **War index and deep links.** Chronological index above the three current formal wars. Each war has its own stable link `#war-<numeric ID>`, safe to bookmark even if displayed titles change. Native names, screenshot-confirmed names and generated enemy-aware titles keep their existing provenance.
2. **Previous / Next War above and below every war.** Links show the *destination war's actual title*, keep the user on the local War Journal and return to the index. Unavailable directions are disabled at the ends. Outside text fields/buttons, `[` navigates to the previous war and `]` to the next.
3. **War chronology and year-by-year battle ledger.** Uses only the preserved native war start, dated formal battle records, first/last archive appearances, and separate screenshot victory notifications. Lists annual battle counts, locations, observed date spans and complete/incomplete native loss tallies. No military victories or permanent ownership are inferred from tactical flags or vanished ships.
4. **Notable recorded loss entries.** Up to three highest *native formal-battle* Commonwealth loss tallies with recorded locations/dates. These are not verified loss causes, not verified ship identities and not ranked battle importance.
5. **Wartime completed research.** Uses Historian's existing cached technology snapshots to list completed technologies first observed while the war appears in the archive. Acquisition is bounded by snapshots; its exact day and any connection to the war remain unknown. **Current research queues are NOT yet automatically monitored.** Empty/missing caches produce a conservative explanation, not a claim that research stopped.
6. **Less scrolling, faster drill-down.** War battle tables are expandable. The theatre breakdown has per-location *View battles* buttons that open and filter the correct war's table, with Reset Filters. Ground/starbase investigation tables are grouped in individual expandable panels; short tables open automatically.
7. **Copy / Save War Brief.** Browser-based text export provides the war identity and source boundaries, recorded start/ending evidence, battlefield totals, screenshot notification, dated milestones and cached research findings. The copy function uses the browser clipboard where allowed; Save uses a local `.txt` download. No upload to the internet.
8. **Corrected click handling.** The normal territorial-change listener no longer binds to the military-investigation button; both buttons retain their independent endpoints.

## Preserved evidence and limitations

- `War of Humiliation against Hulfiran United Stars` and `War of Conquest against Silicron Interface` retain screenshot-confirmed victory notification dates separately from the quarterly save-derived ending intervals.
- War-wide attacker/defender exhaustion remains **not verified**; battle-local exhaustion is never summed into a fictional total.
- Ground battles with `0.01.01` remain undated in native save evidence. Enemy-station activity cannot prove which weapons or stations caused losses.
- Complete army regiments, active research queues, exact peace day, permanent planet ownership after occupation, and exact war-wide fatigue still require better evidence. This release does not claim to solve them.
- Built entirely from previously processed snapshot caches and existing War Journal context; it does **not** parse historical `.sav` files on page render or change the fast Live History pipeline.

## Safe installation

1. Allow **Unprocessed Saves = 0**, switch **Live History OFF**, then fully close Historian.
2. Make a dated backup of the current installation (especially `data`, SQLite and the save archive) under `autobackups`, taking care not to copy `autobackups` into itself.
3. Extract `Stellaris_Historian_v0.0.70_PATCH.zip` directly into `G:\codex\StellarisHistorian`, replacing matching application files only.
4. **Never remove or overwrite** `data`, `.sav` archives, `.historian_cache`, `.historian_evidence` or `autobackups` as part of installation.
5. Restart with `start.bat`; confirm **v0.0.70**. Open **War Journal → Formal Wars**. The new jump index appears above the first war. Try Next War / Previous War, View Battles and Save War Brief.
6. Resume Live History when ready. **No migration, Review Campaign or Construct Campaign required.** No GitHub changes.

## Release testing

- New v0.0.70 tests verify war chronology ordering, first/later archive boundaries, screenshot source scoping, annual loss-table completeness, no fictitious dates, escaping of hostile save text, three-war index, both-direction navigation, and cached wartime technology evidence.
- Full rendered HTML and JavaScript were validated, and a real Chromium browser test clicked index/pager links, used bracket navigation, filtered and reset battle tables, and downloaded the `.txt` brief.
- Existing v0.0.64–v0.0.69 regressions passed independently on the available archived Stellaris saves, including the Thrus-Sanguur ground battle, Hulfiran station evidence and existing war-aftermath territorial transfers.
- Windows installation and live processing must still be confirmed on the user's machine.
