# Changelog

## v0.0.45
- Added conservative promotion of retained `LEADER_DEATH` notifications into confirmed People-domain deaths.
- Promotion requires `MESSAGE_LEADER_LOST_DESC`, a unique exact `LEADER` name match, an unresolved exit in the same archive interval and an exact notification date inside that exit interval.
- Confirmed notification deaths now persist exact death date, retained custom death text and `death_evidence_kind=notification_leader_death_named`.
- Career history replaces the corresponding unresolved tombstone/disappearance event with a visible `leader_death_recorded` event containing retained age/service evidence.
- Added `Notification_Death_Evidence_Debug.txt` with confirmed and rejected/ambiguous candidates.
- Updated the Historical Event Layer and Empire Timeline so confirmed leader deaths are high-importance People events.
- Updated Evidence Journal and Scribes handling so confirmed deaths are not described as unexplained disappearances.
- Updated the v0.0.44 notification decoder to report unique leader-name matches as identity evidence.
- People cache remains v5; no database schema, archive-save or processed-flag reset is required.
- Review Campaign is required once; Construct Campaign is not required.

## v0.0.44
- Added targeted decoding of retained Stellaris `message={...}` objects around leader-exit windows.
- Records notification IDs, message type, localization key, dates, variables, typed targets and retained `custom_message_text`.
- Reports notification IDs allocated between saves even when their message payload has already expired from the archive.
- Preserves player-event selection IDs separately from scripted `event_id` values; no unproven mapping is invented.
- Only explicit typed leader references inside retained message objects can directly connect a message to a leader.
- Explicitly rejects generic `save_on_death` fields as proof of leader death because the field occurs on unrelated save objects.
- Reuses People cache v5 and only opens narrow raw-save windows around known leader exits.
- Adds `Notification_Event_Decoder_Debug.txt`.
- Review Campaign is required once; Construct Campaign and full cache refresh are not required.

## v0.0.43
- Added targeted previous/current/next raw-save probing around every reconstructed leader exit.
- Added `Event_Character_Probe_Debug.txt` with notification/event counter deltas, new player-event IDs, exact-ID saved-event-target blocks and event-adjacent raw leader references.
- Preserved raw `available_trait`, `cooldown` and `delayed_event` evidence where present.
- Kept People cache at v5 so the probe does not force a 299-save raw cache rebuild.
- Event/notification correlations remain non-causal until stronger evidence demonstrates their meaning.
- Review Campaign is required once; Construct Campaign is not required.

## v0.0.42
- Advanced People cache component from v4 to v5 for deep character evidence.
- Added species, portrait, gender, creator, tier, raw date/date-added/age, ethic, job, background-world, custom-description, bonus-skill, raw-key, flag and variable evidence to leader snapshots.
- Added conservative parsing of retained `dead_leader` records; death/date/cause are only promoted when explicit save fields support them.
- Added detection of temporary active-leader `<id>=none` tombstones as strong removal evidence without treating them as proof of death, retirement, dismissal or execution.
- Added exact-ID retained `saved_event_target` aliases for future character/event-chain interpretation.
- Added additive `leader_deep_evidence` database table.
- Added `Character_Evidence_Debug.txt` and `Raw_Evidence_Probe.txt`; upgraded `Leader_Exit_Evidence_Debug.txt`.
- Added discovery counts for event/notification persistence without claiming popup text is reconstructable yet.
- Existing Journal, Timeline and Scribes presentation intentionally left unchanged while evidence collection expands.
- Review Campaign is required once so archived saves can refresh the People v5 component.

## v0.0.41
- Rebuilt Empire Timeline on the shared Historical Event Layer rather than the old ad-hoc marker renderer.
- Timeline combat now promotes direct-anchored and selected high-confidence synthesized combat episodes instead of listing repetitive raw combat-activity markers.
- Added selective technology milestones to the Empire Timeline while leaving full technology evidence in the Historical Journal/diagnostics.
- Reworked Scribes Chapter V to consume the same synthesized combat episodes as the Timeline and compress weaker combat evidence into contextual summaries.
- Evolving retained combat telemetry is presented as changing observations of one retained combat state, not as separate casualty events.
- Suppressed unresolved generic `planet Station` labels from polished Timeline/Scribes output; unresolved low-value station evidence remains available in diagnostics.
- Expanded Historical Event structured attributes for combat, archaeology, projects, situations and people to support presentation-specific rendering without reparsing raw saves.
- Added `historian/presentation_history.py` as the shared presentation-history assembler for Timeline and Scribes.
- Launcher banner intentionally unchanged.
- No database schema, cache component version, archived-save, processed-flag, campaign-identity or folder-layout changes.
- Review Campaign is required once after installation to refresh the v0.0.41 Historical Event diagnostic.

## v0.0.40.1
- Fixed Combat Episode mutable telemetry so each direct combat key is tracked independently across archived snapshots.
- Later snapshots that update only some participating fleets now carry forward the latest retained state for missing participants when building the complete composite episode state.
- `Combat_Episode_Debug.txt` now reports snapshot record count, carried-forward participant count and complete composite totals separately.
- Historical Event combat prose now says a retained state is reconstructable by a date rather than falsely implying every participant row existed in that one snapshot.
- Added **Open Campaign Folder** and **Open Diagnostics Folder** controls to the active campaign page.
- Folder shortcuts open the existing local directories and deliberately do not rename identity-bearing campaign folders.
- No database schema, cache component version, archived-save, processed-flag or campaign-folder identity changes.
- Review Campaign is required once after installation to regenerate corrected combat episode/event diagnostics.

## v0.0.40
- Added Combat Episode Synthesis above direct fleet combat telemetry and correlated exact combat-activity markers.
- Added `Combat_Episode_Debug.txt` with episode boundaries, activity dates, systems, participants, direct opposing forces, formal outcomes and conservative nearby-loss context.
- Preserved direct `combat_stats` observations over archive time so mutable loss counters are visible instead of silently collapsing early and later retained states.
- Historical Event Layer now accepts synthesized combat episodes and can suppress low-information marker-only noise from the common event stream while leaving raw evidence in diagnostics.
- Added structured event attributes for future Timeline/Scribes renderers and removed renderer/game voice such as `Stellaris records...` from normalized event summaries.
- Generic combat participants such as `planet Station` are no longer emitted as polished historical subjects; resolved systems/fleets are preferred and unresolved low-value markers remain diagnostic-only.
- Corrected People-domain importance mappings to the actual leader event names, promoting ruler transitions, service entries and unconfirmed leader exits appropriately.
- Added `Leader_Exit_Evidence_Debug.txt` so disappearance is explicitly distinguished from an evidenced death/cause.
- No database schema changes, cache component version changes, archived-save deletions or processed-flag resets.
- Review Campaign is required once after installation to regenerate v0.0.40 episode/event diagnostics for existing archives.

## v0.0.39
- Added a dedicated per-campaign `diagnostics/` folder so debug/evidence text files no longer sit beside hundreds of archived Ironman saves.
- Review Campaign and Construct Campaign now print the exact diagnostics directory before writing diagnostic outputs.
- Added one-time safe relocation of legacy diagnostic files when the destination filename is not already occupied.
- Repaired the Windows launcher banner by displaying UTF-8 ASCII art from `assets/stellaris_banner.txt` with `type` instead of individual `echo` commands.
- Added `by PillBoxUK` to the preserved launcher banner file.
- No cache version, database schema, archive-save or processed-flag changes.

## v0.0.38
- Advanced the Combat cache component from v2 to v3.
- Added direct player fleet combat telemetry extraction from retained `combat` / `fleet_stats.combat_stats` records.
- Direct telemetry can preserve exact combat start date, player fleet, commander, system, opposing country/fleet and recorded ship-loss counters.
- Added conservative exact-date combat marker correlation across ship/starbase activity, adjacent snapshot state, relation-counter changes and possible ship disappearances.
- Added `Combat_Correlation_Debug.txt` with direct telemetry and correlated engagement candidates.
- Added directional relation `killed_ships` evidence without guessing counter semantics.
- Added `historian/historical_events.py`, a presentation-neutral Historical Event Layer foundation with source/confidence/date-kind metadata.
- Added `Historical_Event_Debug.txt`.
- Expanded the Scribes military chapter to prefer direct combat rolls where they survive, while refusing to invent victory/defeat, political cause or unsupported casualties.
- Existing non-Combat cache components remain valid; first Review Campaign extends Combat v3 only.
- No database schema changes, archive deletions or processed-flag resets.

## v0.0.37
- Expanded **As the Scribes Saw It** from a short overview into a fuller historical chronicle.
- Added an in-universe military-history chapter using formal wars/battles when available and exact combat-activity markers when formal war rolls do not survive.
- Added richer commander/general-staff treatment and long-service historical context.
- Added modular Technology evidence collection (`technology` cache component v1).
- Added `Technology_Evidence_Debug.txt` and technology counts to Review/Construct diagnostics.
- Added a Scribes technology chapter that names observed technological advances by year without inventing exact research-completion dates.
- Removed out-of-universe wording from the Scribes narrative; the civilization's chronicle now refers only to archives, rolls and surviving records.
- Added `by PillBoxUK` beneath the launcher ASCII banner.
- Existing domain caches remain valid and are extended with Technology on the first Review Campaign.
- No database schema changes, archived-save deletions or processed-flag resets.

# Stellaris Historian Changelog

## v0.0.48.1
- Hotfix: restores the `/api/live-history` endpoint accidentally removed by the v0.0.48 refresh-progress migration.
- Restores the complete Update History and Review Campaign route block from the automatic v0.0.47.1 backup, then reapplies the intended v0.0.48 refresh changes with route-scoped anchors.
- Keeps v0.0.48 Politics/Diplomacy filtering, refresh progress, localisation and diagnostic fixes intact.
- No SQLite schema/data migration and no archived `.sav` changes.

## v0.0.48
- Politics/Diplomacy publication filtering now keeps routine `council_agenda_progress` telemetry in SQL/diagnostics but removes it from public historical narrative.
- Actual council-agenda identity transitions remain publishable and receive readable titles.
- Raw `relations_manager` evidence is still retained, while strong pseudo-country/event-entity indicators are filtered from public diplomatic contact/state history.
- Politics/Diplomacy journal summary values now resolve through installed Stellaris/mod localisation with a readable fallback.
- Fixed Event_Character_Probe_Debug.txt cache tuple compatibility after the v0.0.47 Politics cache component was added.
- Fixed the invalid Python escape warning in the incremental Politics diagnostic path.
- Review Campaign and Construct Campaign now show numbered REFRESH progress, per-step timing, failures, and an overall refresh summary.
- Politics_Diplomacy_Probe_Debug.txt reports inner raw-sample scan progress during Review/Construct.
- Live History now explicitly logs Historical_Journal.html refresh completion and duration.
- Existing archived `.sav` files are not changed or deleted.

## v0.0.47.1
- Fixed Update History replaying snapshots whose normal history row had already been committed but whose `processed` flag was never reached after a Politics/Diplomacy failure.
- Update History now reconciles such half-finished v0.0.47 rows from durable `history_entries` before selecting work.
- Core history progress is marked processed independently of the additive Politics/Diplomacy persistence stage.
- Politics/Diplomacy parser failures no longer invalidate otherwise-supported snapshot history.
- Added a passive SQLite WAL checkpoint after each Update History batch so committed progress is flushed into `historian.db` when possible.
- Review/Construct tolerate unavailable Politics snapshots while preserving the supported domains.
- No archived `.sav` files are changed or deleted.

## v0.0.47
- Added a **Live History ON/OFF** toggle beside Update History. It is OFF by default and, when enabled, processes newly archived saves through the existing incremental history pipeline and refreshes `Historical_Journal.html` automatically.
- Added `politics_diplomacy` snapshot-cache component v1 so Politics/Diplomacy evidence shares the same raw-save read as the other structured domains.
- Added structured Politics/Diplomacy state and event persistence in `politics_states` and `politics_history_events`.
- Added conservative government-state changes, ruler identity observations, council-agenda field transitions, tradition first-observations, first archived appearance of diplomatic relation records, communications/hostility/neutral-state changes and relation-value changes.
- Relation-value transitions are retained but hidden from the normal public event stream to avoid chronology noise.
- Ruler identity is retained in Politics/Diplomacy, while the People domain remains authoritative for public ruler career/succession milestones.
- Added `diagnostics/Politics_History_Debug.txt`, a dedicated Politics & Diplomacy section in the Historical Journal, and integrated visible Politics/Diplomacy evidence into the shared Historical Event Layer used by Timeline and Scribes.
- Review Campaign and Construct Campaign require Live History to be OFF to avoid concurrent history rebuilds.
- Existing cache containers extend in place when the new Politics/Diplomacy component is first needed; no destructive cache reset is required.

## v0.0.46
- Added an evidence-only Politics & Diplomacy Deep Probe.
- Added `diagnostics/Politics_Diplomacy_Probe_Debug.txt`.
- Review Campaign now inventories retained player-government fields, candidate political keys, raw relation records and changes between selected raw-save samples.
- The probe uses all reviewed profile/government states plus adaptive raw-save sampling (maximum 64 raw archives) so mature comparison campaigns are not fully reparsed.
- Existing People ruler/heir/death milestones are included as cross-domain anchors without inventing election or succession causes.
- Raw relation keys/blocks are preserved literally; v0.0.46 does not yet infer alliances, treaties, factions, elections, rivalries or diplomatic outcomes from unfamiliar fields.
- No database schema changes and no parsed-cache component version changes.
- Review Campaign is required once after installation to generate the new diagnostic.

## v0.0.36
- Added a third historical reading surface: **Empire Timeline** (`/timeline`) for a deliberately simple year-by-year chronology.
- Timeline publication is selective: colony foundations, important leader milestones, named fleet appearances, support/exploration ship commissioning, selected science/archaeology and direct combat evidence can appear; routine trait churn, reinforcements and refit bookkeeping remain in the evidence ledger.
- Added optional grouped `last_combat_activity` timeline entries only when multiple same-date entities or a starbase marker make the activity historically useful; these are labelled combat activity, never promoted to a battle without stronger evidence.
- Added direct **Export PDF** for `As the Scribes Saw It`, generating `Scribes_Chronicle.pdf` with a title page, chapter pagination, footer and ruler-authored sign-off blocks.
- Added evidence-led chapter signatories. Historian reads the ruler recorded in the cached leader state at or immediately before each chapter's anchor date and presents the chapter as set down and signed by that ruler.
- The final Chronicle page is deliberately left unsigned because an active campaign has not ended; it marks only the present edge of the archive.
- Added Empire Timeline links to the Historical Journal and Scribes navigation.
- Added ReportLab as the PDF-generation dependency.
- No database schema, archived-save, parsed-cache version or processed-flag changes.

## v0.0.35
- Added the new **As the Scribes Saw It** narrative chronicle as a second, reader-facing history alongside the technical Historical Journal.
- Added `historian/scribes.py`, which composes deterministic long-form prose from existing supported evidence rather than exposing every event as a card/table.
- Added a prominent **As the Scribes Saw It** control to the Historical Journal navigation and a new `/scribes` route.
- The Scribes View uses natural uncertainty language inside the prose instead of database-style confidence labels, while preserving the same evidence-safety rules.
- The technical Historical Journal remains unchanged in purpose and continues to serve as the detailed evidence/debugging ledger.
- Added a UTF-8 `STELLARIS` ASCII launcher banner.
- No database schema, parser, cache, archived-save or processed-flag changes.

## v0.0.34
- Expanded the Combat domain to collect exact `last_combat_activity` markers from player mobile ships and starbase station ships.
- Added ship marker context for first-observed fleet, commander and system, while explicitly treating those fields as snapshot context rather than proof of the combat location/command state.
- Added starbase marker context with stable starbase ID, station ship ID and first-observed system.
- `Combat_Evidence_Debug.txt` now separates formal wars, formal battles, ship combat markers and starbase combat markers.
- Console summaries now distinguish formal battle records from ship/starbase combat activity.
- Bumped the independent `combat` cache component from version 1 to version 2; other valid domain cache components remain reusable.
- Combat remains diagnostic-only; no battle story, opponent, result or named casualty is inferred from `last_combat_activity` alone.
- No database schema, archived-save or processed-flag changes.

## v0.0.33
- Added modular `historian/domains/combat/` evidence foundation for Battles & Losses.
- Added `combat` parsed-snapshot cache component version `1`.
- Collects player-related active wars and direct player battle records retained by Stellaris.
- Records exact battle date, battle type, player side, recorded victory/defeat, aggregate player/opponent losses, and system/planet location where available.
- Review Campaign and Construct Campaign now generate `Combat_Evidence_Debug.txt`.
- Console snapshot summaries now show player-related Wars and direct Battles.
- Full rebuild summaries report unique combat wars, battles, victories and defeats.
- Combat remains diagnostic-only in v0.0.33; no battle narrative is published into the Historical Journal yet.
- Ship/fleet disappearance is never treated as proof of destruction.
- Existing cache containers remain valid and are extended with Combat v1 on first review; no database schema, archived-save or processed-flag changes.

## v0.0.32
- Kept every stable-vessel ship-design transition as hidden raw refit evidence.
- Reduced journal refit noise with selective publication rules.
- Added one-event naval modernisation waves when several named military fleets refit in the same archived interval.
- Kept substantial same-fleet refits grouped into one public event.
- Added compact support-fleet refit waves when three or more support vessels change design together.
- Routine isolated corvette/science/construction design changes remain internal rather than filling the journal.
- Isolated major military hull refits may still be published.
- Review/Construct console summaries now report raw refit evidence and published refit events separately.
- Ships cache remains version 2; no raw-save reparse is required solely for this patch.
- No database schema, archived-save or processed-flag changes.

## v0.0.31
- Added conservative ship refit/upgrade history using stable ship identity and cached ship design IDs.
- Added `historian/domains/ships/refits.py` so refit interpretation remains inside the Ships domain.
- Preserves every per-ship design transition internally as raw evidence.
- Groups simultaneous same-fleet design changes into one public `Fleet Refit Observed` journal event to avoid narrative spam.
- Publishes single-vessel refit observations when grouping is not appropriate.
- Living vessels and ship class/size transformations are not automatically described as ordinary refits.
- Exact component differences are deliberately not inferred yet.
- Build-site evidence is now shown only on commissioning/first-observed ship entries, so later refit events do not misleadingly repeat a vessel's birthplace.
- Ships cache remains `ship_fleet` version 2, so historical refits can be reconstructed from existing cache data during Review Campaign.
- No database schema, archived-save or processed-flag changes.

## v0.0.30
- Added a selective `Science, Exploration and Discoveries` chapter to the Historical Journal.
- Added `historian/domains/science/journal.py` so Science now owns its public journal presentation.
- Groups related Red Giant situation/project evidence into a readable story arc without inventing a final outcome.
- Publishes archaeology with preserved location, linked scientist and progress-marker evidence.
- Publishes special projects only when useful context survives (scientist, ship, location or meaningful multi-objective grouping).
- Publishes selected narrative situations such as Organic Singularity while leaving economic shortages, revolts and unresolved Observation Insight targets for future domains.
- Added a sticky `Science & Exploration` journal navigation link.
- Fixed special-project ID reuse: raw instance identity is now `(project ID, project key)`, preventing recycled numeric IDs from leaking scientist/ship/location evidence between unrelated projects.
- Science cache remains version 1; no database schema, archived-save or processed-flag changes.

## v0.0.29
- Added conservative Science evidence interpretation without publishing Science events into the Historical Journal yet.
- Added `historian/domains/science/history.py` for semantic project grouping and lifecycle interpretation.
- Special projects are now reported as raw instances plus semantic project families; raw IDs and peak concurrent instance counts are retained.
- Archaeology `completed` dates are explicitly treated as chapter/progress markers, not proof of whole-site completion.
- Repeated situations remain separate ID-based episodes, with type-level summaries for readability.
- Disappearance from the save is described only as "no longer observed"; completion/failure/cancellation/expiry are never inferred without direct evidence.
- Review Campaign and Construct Campaign now also generate `Science_Interpretation_Debug.txt`.
- Science cache component remains version 1, so v0.0.28 caches remain valid and should normally produce cache hits.
- No database schema changes, archived-save changes or processed-flag changes.

## v0.0.28
- Added modular Science / Expeditions evidence foundation under `historian/domains/science/`.
- Added persistent `science` cache component v1 without invalidating existing Ships/People/Worlds cache data.
- Collects player-related archaeological sites, active special projects, player situations and active anomaly IDs.
- Links archaeology evidence to excavating fleet/scientist when the save preserves that relationship.
- Review Campaign and Construct Campaign now generate `Science_Evidence_Debug.txt` for evidence inspection.
- Console snapshot summaries now include Dig sites, Projects and Situations.
- No Science/sidequest narrative is published yet; v0.0.28 is deliberately evidence-first.
- No database schema changes and no archived saves or processed flags are modified by the migration.

## v0.0.27
- Fixed opening ship/fleet registers leaking latest-known relationships backwards into the first archived state.
- Added immutable opening-state fields for ship names/types/fleet assignments/commanders and fleet names/classes/ship counts/home bases/commanders.
- Opening-register journal rendering now reads only those frozen baseline fields.
- Existing campaigns are hydrated from the cached opening snapshot during the one-time migration when available.
- Added a pre-migration database safety copy before schema changes.
- Snapshot cache format remains unchanged; archived saves and processed flags are untouched.

## v0.0.26
- Added a sticky in-journal navigation bar with jump links for Opening Record, Worlds & Expansion, People & Politics, Ships & Fleets and Archive Checkpoints.
- Added a persistent Back to Top control for long journals.
- Added a dedicated Print / PDF button that opens the browser print dialog.
- Reworked print media rules for paginated A4 landscape output instead of an oversized single-page capture.
- Print tables repeat their header row on new pages and avoid splitting normal rows where possible.
- Browser/4K responsive layout from v0.0.25 is preserved.
- No gameplay-history, parser, cache or database behaviour changes.

## v0.0.25
- Expanded the on-screen Historical Journal to use large and 4K displays more effectively.
- Register tables now use the available journal width instead of being constrained to the old 1040px page.
- Narrative chronicle cards retain a comfortable reading width rather than stretching across the whole monitor.
- Added responsive breakpoints for laptop/mobile widths.
- Added print-specific CSS so PDF/print output keeps the established document-style width.
- No gameplay-history, parsing, cache, or database behaviour changes.

## v0.0.24
- Migrated Worlds & Expansion into `historian/domains/worlds/`.
- Split world responsibilities into models, parsing, history, cache and journal-helper modules.
- Preserved `worlds` cache component version `2` for v0.0.23 cache compatibility.
- Added one-time safe cleanup for the obsolete `historian/world.py`.
- Fixed stale web UI version labels by reading the running backend version instead of hard-coding `v0.0.21`.
- Centralized Python application version reporting through `historian.__version__`.
- No intentional gameplay-history behaviour changes.

## v0.0.23
- Migrated Ships & Fleets into `historian/domains/ships/`.
- Split ship/fleet responsibilities into models, parsing, logical identity, provenance, history, cache and journal modules.
- Moved shared Stellaris text-block parsing helpers into `historian/core/stellaris_text.py`.
- Removed cross-domain dependence on private helpers from the old `ship_fleet.py`.
- Preserved `ship_fleet` cache component version `2` for v0.0.22 cache compatibility.
- Added one-time safe cleanup for the obsolete `historian/ship_fleet.py`.
- No intentional gameplay-history behaviour changes.

## v0.0.22
- Introduced modular domain architecture.
- Migrated People/leader parsing, models, career history, cache serialization and journal rendering into `historian/domains/people/`.
- People now owns its cache component version.
- Added managed-file manifest and one-time safe migration cleanup.
- Consolidated accumulated root step notes into `docs/`.
- No intentional gameplay-history behaviour changes.

## Earlier milestones
- v0.0.21: world register cleanup, founding dates, designations and population units.
- v0.0.20: world identity, colonies and expansion history.
- v0.0.19: commander assignment cleanup.
- v0.0.18: leader career narrative.
- v0.0.17: special/living vessel and evidence cleanup.
- v0.0.16: leader identity and career tracking.
- v0.0.15: workflow guards.
- v0.0.14: Construct Campaign.
- v0.0.13: parsed snapshot cache.
- v0.0.12: console progress logging.
- v0.0.11 and earlier: ship/fleet history, provenance, founding lore and campaign review foundations.
