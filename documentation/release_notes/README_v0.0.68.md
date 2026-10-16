# Stellaris Historian v0.0.68 — Military History Evidence

**Upgrade from v0.0.67.** This patch changes presentation and adds a **read-only, on-demand** military archive investigator. It does not rebuild existing history and does not change the main database schema, game saves, or parsed domain-cache revisions.

## What is new

1. **Enemy-aware formal war titles.** Historian constructs `War of <goal> against <opponent>` when it can associate the opponent's country ID from a retained war with a verified country name in cached combat/diplomacy evidence. The user-confirmed name **Hulfiran United Stars** is also recorded as an explicitly scoped display annotation for Commonwealth of Man / war ID `83886080` / war start `2293.04.26` / opponent country ID `16777226`. The previous screenshot-confirmed `Human–Lilarobian War of Conquest` title remains unchanged. The source label distinguishes native titles, screenshot titles, cached evidence and generated titles. Do not pretend the generated title is a native Stellaris war name.
2. **Ground warfare investigation.** Each formal war gains an **Investigate ground and starbase evidence** button. An on-demand, read-only report reads original archived Stellaris `war.battles` entries of type `armies`, even when their native date is the placeholder `0.01.01`. It publishes **first observed archive**, colony/planet, tactical countries, raw losses and unverified winner flag separately. It does not invent the day of a ground battle or identify a winner from an unverified flag.
3. **Planetary occupation evidence.** The same report compares planet records with a retained `colony`, separating planet `owner` and `controller` across two processed snapshots. For **Thrus-Sanguur**, ownership remains Hulfiran and controller changes to Commonwealth between **2298.04.01 and 2298.07.01**. Planetary occupations are not automatically annexations or peace terms.
4. **Enemy starbase activity.** The investigator resolves an opposing station's owner using the fleet to which its station ship belongs, cross-checked against the country-owned fleet list. It records dates from station `last_combat_activity`, station ID, controller and system; this can highlight **Mubblar** involvement without attributing every Commonwealth ship loss to the installation. The ordinary War Journal ship-loss and outcome counts are deliberately not reclassified.
5. **Performance preserved.** Normal `Live History`, `Update History`, and `Historical_Journal.html` operation does not run any of these forensic raw-save scans. The user starts an investigation explicitly. Per-save extracted evidence is cached by original save SHA-256, war ID and code revision in the campaign's `.historian_evidence` directory, using atomic writes. Reopening the same investigation reuses it; new archived saves contribute new entries. The most recent **48** relevant archived snapshots are examined per investigation; the report explicitly notes when older history was not examined.

## Safety and limits

- **No SQLite migration**. No changes to `.sav`, `data`, or existing processed snapshot caches; no `Review Campaign` or `Construct Campaign` required.
- Native army battle placeholder dates remain undated. Combat station involvement is evidence of *activity*, not causation or enemy ship casualty interpretation.
- A full historical ground-war reconstruction of arbitrarily old wars is NOT claimed: the on-demand report examines only its disclosed bounded archive window. A later milestone can add a full indexed ground/army registry and army formation/casualty tracking.
- Names outside the verified war/party scope are not guessed; unknown entities remain described generically.
- Reports appear on clicking the button; **they do not automatically populate the main History database**. The on-demand forensic cache can safely be regenerated if deleted.
- The first on-demand investigation may take tens of seconds if its archive evidence has not yet been indexed.

## Installation

1. Allow unprocessed saves to reach **0**; turn Live History **OFF**.
2. Close Historian completely (stop its server) to checkpoint the SQLite WAL safely.
3. Back up the *entire* installation, including the `data` directory, to your `autobackups` folder.
4. Extract `Stellaris_Historian_v0.0.68_PATCH.zip` into `G:\codex\StellarisHistorian`, replacing matching application files. **Do not delete any existing folders or files.**
5. Restart with `start.bat`; both banner and runtime should show `v0.0.68`.
6. Open War Journal -> **Formal Wars**. The newer war should read **War of Humiliation against Hulfiran United Stars**. Click **Investigate ground and starbase evidence** and wait for the report.
7. Once satisfied, return to the campaign and turn Live History ON. No full rebuild needed.

## Regression evidence

- `test_v0_0_68.py` checks genuine `.sav` archives **394, 395, 396, 398, 399 and 401** including the army battle placeholder, owner/controller transition, Mubblar station dates, scoped title, signature caching and deterministic repeat results.
- v0.0.66 parser integrity and v0.0.67 incremental First Contact / leader-death safeguards pass.
- v0.0.65 First Contact cache parity passes on four old saves.
- War aftermath calculation, DB schema and old war datasets were *not modified* by this patch.

GitHub has not been updated.
