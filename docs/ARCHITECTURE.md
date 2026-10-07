# Stellaris Historian Architecture

## Direction

Historian uses a domain-based architecture. Gameplay subjects own their parsing, historical interpretation, cache serialization and journal contribution. Shared infrastructure remains outside domains.

```text
historian/
  core/
    stellaris_text.py     shared Paradox/Stellaris text-block parsing helpers
  domains/
    people/               leaders and careers
    ships/                ships, fleets, shipyards, refits and construction provenance
    worlds/               planets, colonies and expansion history
    science/              science, archaeology and special-project history
    combat/               wars and direct battle evidence
    events/               game/event history (future)
    technology/           research history (future)
    diplomacy/            contacts and relations (future)
    wars/                 broader war outcomes and military history (future)
```

## People domain

`historian/domains/people/` owns leader models, parsing, career transitions, cache serialization and People journal rendering.

Cache component: `leaders`, version `4`.

## Ships domain

`historian/domains/ships/` owns ship/fleet models, parsing, fleet identity, build provenance, refit interpretation, historical transitions, cache serialization and Ships/Fleets journal rendering.

Cache component: `ship_fleet`, version `2`.

## Worlds domain - v0.0.24

`historian/domains/worlds/` owns:

- `models.py` - planet/colony state and snapshot contracts
- `parser.py` - world identity, generated names, system/class/designation and colony extraction
- `history.py` - colony founding, control, rename/capital transitions and full world history
- `cache.py` - Worlds cache serialization
- `journal.py` - World-specific presentation helpers such as player-facing population units

Cache component: `worlds`, version `2`.

Generic raw save-block helpers remain in `historian/core/stellaris_text.py`, allowing People, Ships and Worlds to share infrastructure without importing private helpers from another gameplay domain.

## Version reporting

`historian.__version__` is the Python source of truth for the running application. Web pages render the version returned by backend APIs rather than hard-coding a release number in HTML.

## Journal presentation - v0.0.25 / v0.0.26

The generated Historical Journal uses a responsive screen layout. On large displays, register tables can use up to 92% of the viewport (capped at 3000px), while narrative chronicle cards are constrained to a comfortable reading width.

v0.0.26 adds a sticky section navigator and explicit `Print / PDF` action. The print path is deliberately separate from the responsive screen layout: print media uses paginated A4 landscape pages, hides on-screen navigation controls, repeats table headers where supported and avoids splitting normal table/event rows where possible. The intended PDF workflow is to use the journal's `Print / PDF` button and then choose the browser's `Save to PDF` printer.

## Safety principles

1. Archived `.sav` files are evidence and are never modified or deleted by code-layout migrations.
2. `data/historian.db` is persistent state and is never deleted by code-layout migrations.
3. Domain cache versions are independent. Structural refactors do not bump a cache version unless the serialized data contract changes.
4. The raw chronicle remains greedy; the published journal remains selective.
5. Refactors must reproduce pre-refactor history before new gameplay features are added.


## Opening-state immutability - v0.0.27

Ship and fleet registry rows contain both mutable latest-known fields and immutable opening-state fields. The latter are populated only from the baseline archived snapshot and are never overwritten by later snapshots. Journal sections explicitly labelled as opening registers must render the opening-state fields. This prevents a commander recruited decades later, a later fleet assignment, rebase, rename or reinforcement from being projected backwards into the founding record.
## Science / Expeditions evidence domain (v0.0.28)

`historian/domains/science/` owns evidence collection for archaeological sites,
active special projects, player situations and active anomaly IDs. Its first
release is intentionally diagnostic-only: parsed evidence is cached and can be
reviewed in `Science_Evidence_Debug.txt`, but it is not yet promoted into the
public Historical Journal. This preserves the project rule that the collector
may be greedy while the published journal remains selective and evidence-led.


## Science evidence interpretation - v0.0.29

Science keeps two deliberately separate layers:

1. **Evidence cache (`science` v1)** - raw per-snapshot archaeological sites,
   special-project instances, situations and anomaly IDs.
2. **Interpretation layer** - conservative cross-snapshot grouping in
   `historian/domains/science/history.py`.

Special projects are grouped by project key for semantic review, but raw project
IDs remain attached and peak concurrent instances are reported. This is
important for chains such as multi-target triangulation where many same-key
records may be simultaneously legitimate rather than parser duplicates.

Situation IDs are never collapsed merely because their title/type matches;
repeated Food Shortage or Observation Insight records remain separate historical
episodes. Archaeology `completed` records are treated as chapter/progress marker
dates unless stronger evidence later proves whole-site completion.

The interpretation layer currently writes `Science_Interpretation_Debug.txt`
and does not publish to the journal. This keeps the collector greedy while the
future narrative layer remains selective and evidence-safe.


## Science journal publication - v0.0.30

Science now has three explicit layers:

1. **Evidence cache (`science` v1)** - greedy per-snapshot collection.
2. **Interpretation** - conservative cross-snapshot grouping in `history.py`.
3. **Journal publication** - selective story presentation in `journal.py`.

The journal layer deliberately omits weakly contextualised evidence. Related Red Giant records may be grouped into one story arc; archaeology may include linked scientists and preserved progress markers; special projects are published only when useful contextual evidence survives. Disappearance remains evidence of absence only, never automatic proof of success/failure.

v0.0.30 also treats a special-project raw instance as `(project ID, project key)`. Stellaris can recycle numeric project IDs, so numeric ID alone is not a safe historical identity across a long campaign.


## Ship refit history - v0.0.31

`historian/domains/ships/refits.py` interprets design-ID changes for a stable ship identity across adjacent archived states. The evidence model is deliberately split in two:

1. **Greedy raw evidence** - every surviving ship whose recorded design ID changes is preserved internally as a hidden `ship_design_changed` event, including the old and new internal design IDs.
2. **Selective journal evidence** - ordinary non-living vessels with unchanged ship class/size can produce public refit observations. Two or more same-fleet changes in one transition are grouped into one fleet-refit event; otherwise Historian publishes a single-vessel refit event.

A design change is treated as strong evidence of a refit/upgrade, but v0.0.31 does not infer which components changed. The Ships cache remains version `2` because design IDs were already part of the serialized ship state.

## Selective refit publication - v0.0.32

The Ships domain keeps refit evidence and journal publication as separate layers. Every stable-vessel design-ID transition remains a hidden `ship_design_changed` record. The public journal now promotes only historically useful refit summaries: coordinated multi-fleet naval modernisation waves, substantial same-fleet refits, broad support-fleet waves, and isolated major-warship refits. Routine single-corvette and utility-ship churn remains queryable internally without dominating the published chronicle.


## Combat evidence domain - v0.0.33

`historian/domains/combat/` begins the Battles & Losses work with an evidence-first layer. The domain owns per-snapshot player-related war state and direct player battle records retained inside Stellaris war data.

Cache component: `combat`, version `1`.

The first release deliberately stops short of journal publication. Review/Construct writes `Combat_Evidence_Debug.txt` containing exact battle dates, direct player side, recorded victory/defeat, aggregate attacker/defender losses, battle type and location where resolvable.

Combat follows a stricter loss rule than ordinary presence tracking: a ship or fleet disappearing from the next archive is not proof of destruction. Named vessel losses will only be promoted later when disappearance windows can be correlated with direct combat evidence strongly enough to avoid invented casualties.


## Combat activity evidence - v0.0.34

The Combat domain now has two independent evidence channels:

1. **Formal war evidence** - player-related `war` records and direct player battle records retained by Stellaris.
2. **Entity combat-activity evidence** - exact `last_combat_activity` dates retained on player mobile ships and starbase station ships.

Cache component: `combat`, version `2`.

`last_combat_activity` is treated as exact date evidence that the entity participated in combat. It does not by itself establish the opponent, result, losses or battle location. Fleet, commander and system attached to a marker are stored as the context in the first archived snapshot where Historian observes that marker. This prevents later interpretation from silently promoting snapshot context into unsupported battle facts.

The domain remains diagnostic-only in v0.0.34. Battle correlation, kill-counter interpretation, named-loss reconstruction and Historical Journal publication remain later stages.

## Dual journal presentation - v0.0.35

Historian now has two deliberately different reading surfaces over the same derived evidence:

1. **Historical Journal** - the technical evidence ledger. It remains detailed, segmented and explicit about dates, confidence, registers and archive checkpoints. This is the primary debugging and audit surface.
2. **As the Scribes Saw It** - a deterministic narrative chronicle generated by `historian/scribes.py`. It selects and groups supported evidence into flowing chapters and uses natural uncertainty language rather than technical evidence labels.

The Scribes layer does not replace or mutate derived history. It is a presentation layer only. It may paraphrase supported facts and connect them with conservative transitions, but it must not invent speeches, motives, births, deaths, battle outcomes, project completions or other facts that the evidence layer has not established.

The `/scribes` route renders `Scribes_Chronicle.html` on demand from the current database and cache state. This keeps the narrative synchronized with Review/Update/Construct output without adding a new persistence schema or cache version.

## Triple historical presentation - v0.0.36

Historian now exposes three intentionally different views over the same derived evidence:

1. **Historical Journal** - the forensic/audit ledger, with registers, confidence and detailed evidence.
2. **As the Scribes Saw It** - a flowing narrative history that groups supported facts into readable chapters.
3. **Empire Timeline** - a sparse chronological view that answers the simple question: what mattered in this year?

The Timeline is not a duplicate of the Journal. Its collector is selective and suppresses routine trait gains, reinforcements, refit churn and other bookkeeping. Formal battle records can appear directly when Stellaris preserves them. Entity `last_combat_activity` markers may appear only as cautious grouped combat-activity entries; they never imply opponent, result or casualties.

### Scribes authority model

Scribes chapter sign-off uses the cached People-domain state. For a chapter anchor date, Historian selects the latest archived snapshot on or before that date with an explicitly recorded ruler and renders a sign-off such as `Entered into the Chronicle under the authority of ...`. This is an archival attribution, not a claim that the leader literally wrote the prose. Historian does not invent speeches, signatures, succession causes or titles that are not supported by the save.

The final Chronicle chapter is deliberately unsigned while the campaign remains active. Its purpose is to mark the present boundary of the archive rather than imply the civilization's story has ended.

### Direct Scribes PDF

`historian/scribes.py` now owns both HTML and direct PDF rendering. `/scribes/pdf` generates `Scribes_Chronicle.pdf` using ReportLab from the same evidence-led chapter text used by the HTML view. The PDF is independent of browser print support and includes a cover, chapter pagination, ruler authority blocks and page footers.

No domain cache version changes are required for v0.0.36.

## Technology evidence and fuller chronicle - v0.0.37

`historian/domains/technology/` owns researched-technology evidence. The domain reads completed entries from the player country's `tech_status`, serialises them as cache component `technology` v1, and derives first-observed acquisition windows across adjacent archived snapshots. Opening-state technologies are baseline knowledge rather than discoveries; queued research is not promoted until completion appears in the researched list.

The Scribes presentation now consumes Technology and Combat evidence directly. Its military chapter may describe exact dated combat activity, formal wars and formal battles where available, but must not infer an opponent, casualty, victory, defeat or battle name from activity markers alone. Its technology chapter may name the year/archive interval in which an advance first becomes visible, but does not invent an exact completion day.

Scribes is an in-universe chronicle. User-facing prose must not mention Stellaris, save files, parsers, cache components or other game/software concepts. Those details remain in the Evidence Journal and diagnostics.



## Direct combat reconstruction and Historical Event Layer - v0.0.38

Combat now has three evidence strengths that remain distinct:

1. **Formal war/battle records** - strongest direct war/result evidence when retained.
2. **Direct fleet combat telemetry** - player fleet `combat` / `fleet_stats.combat_stats` records that can retain exact start date, formations, commander, system, opposing force and per-fleet loss counters.
3. **Entity combat-activity markers** - ship/starbase `last_combat_activity` dates, correlated conservatively with adjacent snapshots.

`historian/domains/combat/correlation.py` collapses repeated direct telemetry into episodes and separately groups exact entity combat dates into correlated candidates. Relation `killed_ships` values remain directional raw evidence until their engine semantics are independently proven. A ship disappearance is never automatically promoted to destruction.

`historian/historical_events.py` introduces a presentation-neutral event stream. Supported facts from Worlds, People, Ships, Science, Technology and Combat are normalized into `HistoricalEvent` objects carrying source, confidence, date-kind and importance. This layer is diagnostic-first in v0.0.38 and is intended to become the common source for the Evidence Journal, Empire Timeline and Scribes Chronicle so each presentation stops independently reinterpreting evidence.

The Scribes military chapter may consume direct combat episodes because those records explicitly name the opposing force and loss tallies. It remains forbidden from inventing battle names, motives, war declarations or victory/defeat where no direct record establishes them.

## Campaign diagnostics layout - v0.0.39

Diagnostic outputs are now separated from archived Ironman saves. Every campaign archive may contain a `diagnostics/` child directory. Review Campaign and Construct Campaign pass this directory to all diagnostic writers rather than passing the archive root directly.

Current diagnostic outputs include science evidence/interpretation, combat evidence/correlation, the Historical Event Layer stream and technology evidence. This is a presentation/debugging organization change only; no domain cache versions are altered.

The launcher also separates the UTF-8 banner from batch syntax. `start.bat` switches to UTF-8 code page 65001 and renders `assets/stellaris_banner.txt` with `type`, which prevents Windows command parsing from interpreting box-drawing glyphs as commands.


## Combat Episode Synthesis and neutral event facts - v0.0.40

v0.0.40 adds a layer above the v0.0.38 direct/correlated combat evidence. `historian/domains/combat/episodes.py` builds `CombatEpisode` records without discarding the lower-level evidence.

A direct combat episode is the strongest anchor. Exact `last_combat_activity` engagements may extend that episode only when stable system/fleet context and temporal continuity support doing so. Remaining publishable markers are clustered conservatively and never gain an opponent or outcome merely because they occur near another marker.

### Mutable retained combat state

Fleet `combat_stats` is not assumed to be an immutable battle snapshot. The same combat key can be observed again in later archived saves with different retained loss counters. v0.0.40 stores those archive observations as `CombatLossObservation` values and distinguishes first complete retained state from later complete retained state. A changed counter is described as evolving retained telemetry rather than a second independent loss event.

Loss counters do not establish victory/defeat. Ship disappearance remains a possible loss unless stronger evidence proves destruction. Formal outcome is populated only from a direct formal battle record.

### Historical Event Layer

`HistoricalEvent` now includes optional structured `attributes`. The common event stream consumes synthesized combat episodes instead of automatically emitting every publishable correlated marker. This keeps granular evidence in diagnostics while allowing future Timeline/Scribes renderers to work from higher-level historical facts.

The normalized layer is presentation-neutral. It may describe evidence provenance, but it should not speak as Stellaris, as Historian, or as an in-universe scribe. Those voices belong to the individual presentation layers.

### Leader exits

`Leader_Exit_Evidence_Debug.txt` makes the current People-domain limitation explicit: disappearance from the archived player-leader set proves that the leader left the surviving record, but the normalized evidence does not currently carry an explicit death date, death cause, dismissal reason or execution reason. Presentation code must therefore not turn disappearance into death unless future raw-save evidence independently establishes it.

No database or cache component version changes are required for v0.0.40.


## Per-fleet retained combat state and folder shortcuts - v0.0.40.1

v0.0.40.1 corrects an important retained-telemetry edge case. Direct combat records are keyed per player fleet, and Stellaris can stop repeating one participant while later saves continue to update another participant from the same episode. The episode layer therefore maintains the latest retained state independently for each direct combat key.

For each archive observation, Historian records how many participant rows are physically present in that snapshot and how many participant states are carried forward from prior retained evidence. A complete composite state exists once every expected direct combat key has been observed at least once. This lets the historical layer compare an initial complete composite against a later complete composite without treating an omitted row as a zero or as evidence that the fleet's earlier state vanished.

Composite loss totals remain retained telemetry only. They never establish victory or defeat, and disappearances remain possible losses unless direct evidence proves destruction.

The campaign UI also exposes local-only folder shortcuts for the active campaign root and its `diagnostics/` child. These are convenience controls over the existing directory structure; v0.0.40.1 intentionally does not rename campaign folders or alter campaign identity.


## Shared presentation history - v0.0.41

`historian/presentation_history.py` is the common assembly point for reader-facing historical views. It loads already-reviewed domain snapshot components from the campaign cache, derives combat correlations/direct telemetry/synthesized episodes, and passes those facts into `synthesize_historical_events()`. The returned `PresentationHistory` object is the shared source used by the Empire Timeline and the Scribes Chronicle.

This does **not** make the presentation layer a second parser. Raw Ironman saves are still parsed during archive/review work by the domain collectors. Timeline and Scribes operate on reviewed database/cache evidence, so presentation changes cannot silently invent facts by performing independent raw-save interpretation.

### Empire Timeline

The Timeline is now a selective chronology over `HistoricalEvent` records. Opening-state context, major expansion, notable service/command events, archaeology/origin situations, selected technology milestones and meaningful combat episodes are eligible for publication. Low-value bookkeeping and isolated combat markers remain in the Evidence Journal or diagnostics.

Direct-anchored combat episodes receive priority. High-confidence non-direct episodes may be published when system, opponent or fleet context makes the episode historically meaningful. Medium/weak marker clusters are deliberately excluded from the main Timeline.

### Scribes Chronicle

The Scribes combat chapter consumes the same synthesized combat episodes. Direct episodes receive narrative treatment; high-confidence correlated episodes are compressed by year/context; weaker evidence is acknowledged only in aggregate. This keeps the Chronicle historical rather than diagnostic while preserving the underlying evidence elsewhere.

Evolving retained `combat_stats` telemetry is rendered as a progression of observations of the same retained episode state. Earlier and later tallies are not added together. Loss counters still do not establish victory or defeat.

### Presentation sanitation

Presentation renderers must not expose unresolved generic subjects such as `planet Station` as if they were meaningful historical names. Such raw labels remain diagnostic evidence. Timeline and Scribes also avoid game/parser voice such as `Stellaris records...`; the Evidence Journal may continue to use technical provenance language where appropriate.

v0.0.41 changes no database schema or domain cache component version. Existing reviewed evidence remains valid; Review Campaign is requested once so the v0.0.41 Historical Event diagnostic is regenerated consistently.
