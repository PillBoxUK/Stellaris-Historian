from __future__ import annotations

from pathlib import Path
import time

from .console import activity, error, format_duration, warning
from .db import Database
from .domains.people.history import derive_full_leader_history, leader_transition_data
from .domains.people.notification_deaths import (
    apply_notification_deaths,
    promote_notification_deaths_in_database,
    write_notification_death_diagnostic,
)
from .domains.people.exit_diagnostic import write_leader_exit_diagnostic
from .domains.people.evidence_diagnostic import (
    character_evidence_summary,
    write_character_evidence_diagnostic,
    write_raw_evidence_probe,
)
from .save_reader import EmpireProfile, read_empire_profile
from .domains.ships.history import derive_full_history, transition_data
from .snapshot_cache import campaign_cache_dir, clear_campaign_cache, load_or_parse_snapshot
from .domains.worlds.history import derive_full_world_history, world_transition_data
from .domains.science.diagnostic import (
    science_evidence_summary,
    write_science_diagnostic,
    write_science_interpretation_diagnostic,
)
from .domains.combat.diagnostic import (
    combat_evidence_summary,
    write_combat_diagnostic,
)
from .domains.combat.correlation import (
    correlation_summary,
    derive_correlated_engagements,
    derive_direct_combat_episodes,
)
from .domains.combat.correlation_diagnostic import (
    write_combat_correlation_diagnostic,
)
from .domains.combat.episodes import (
    combat_episode_summary,
    derive_combat_episodes,
    write_combat_episode_diagnostic,
)
from .historical_events import (
    synthesize_historical_events,
    write_historical_event_diagnostic,
)
from .domains.technology import (
    technology_evidence_summary,
    write_technology_diagnostic,
)


def _diagnostics_dir(archive_dir: Path) -> Path:
    """Return/create the per-campaign diagnostics directory."""
    path = Path(archive_dir) / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _humanise(raw: str | None) -> str | None:
    if not raw:
        return None
    prefixes = ("gov_", "auth_", "origin_", "civic_", "ethic_")
    value = raw
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value.replace("_", " ").strip().title()


def _join_human(values: tuple[str, ...]) -> str | None:
    human = [_humanise(value) for value in values if value]
    human = [value for value in human if value]
    return ", ".join(human) if human else None


def _founding_body(profile: EmpireProfile) -> str:
    parts = [
        f"The surviving historical record for {profile.empire_name} "
        f"begins on {profile.game_date}."
    ]
    government = _humanise(profile.government_type)
    authority = _humanise(profile.authority)
    origin = _humanise(profile.origin)
    ethics = _join_human(profile.ethics)
    civics = _join_human(profile.civics)
    if government and authority:
        parts.append(f"The state was recorded as {government} under {authority} authority.")
    elif government:
        parts.append(f"The government was recorded as {government}.")
    elif authority:
        parts.append(f"The governing authority was {authority}.")
    if ethics:
        parts.append(f"Its recorded ethics were {ethics}.")
    if civics:
        parts.append(f"Its recorded civics were {civics}.")
    if origin:
        parts.append(f"Its origin was {origin}.")
    return " ".join(parts)


def _checkpoint_body(profile: EmpireProfile, archive_filename: str) -> str:
    return (
        f"Historian processed {archive_filename}, preserving the state of "
        f"{profile.empire_name} on {profile.game_date}."
    )


def _build_entry(snapshot, profile: EmpireProfile | None = None) -> dict:
    if profile is None:
        profile = read_empire_profile(Path(snapshot["archive_path"]))
    if snapshot["kind"] == "start":
        entry_type = "founding"
        title = "The Opening of the Surviving Record"
        body = _founding_body(profile)
    else:
        entry_type = "checkpoint"
        title = "Historical Archive Checkpoint"
        body = _checkpoint_body(profile, snapshot["archive_filename"])
    return {
        "snapshot_id": int(snapshot["id"]),
        "game_date": profile.game_date,
        "entry_type": entry_type,
        "title": title,
        "body": body,
        "government_type": _humanise(profile.government_type),
        "authority": _humanise(profile.authority),
        "origin": _humanise(profile.origin),
        "ethics": _join_human(profile.ethics),
        "civics": _join_human(profile.civics),
    }


def _campaign_context(db: Database, campaign_id: int):
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")
    return (
        campaign,
        Path(campaign["source_save"]),
        campaign_cache_dir(Path(campaign["archive_dir"])),
    )


def _cache_counter() -> dict[str, int]:
    return {
        "hit": 0,
        "extend": 0,
        "miss": 0,
    }


def _record_cache_status(
    counters: dict[str, int],
    status: str,
) -> None:
    counters[status] = counters.get(status, 0) + 1


def _cache_summary(
    counters: dict[str, int],
) -> str:
    return (
        f"Cache {counters.get('hit', 0)} hit / "
        f"{counters.get('extend', 0)} extend / "
        f"{counters.get('miss', 0)} miss"
    )


def process_unprocessed(db: Database, campaign_id: int) -> dict:
    started = time.perf_counter()
    snapshots = db.unprocessed_snapshots(campaign_id)
    campaign, source_save, cache_dir = _campaign_context(db, campaign_id)
    campaign_name = campaign["empire_name"]
    total = len(snapshots)
    activity(f"UPDATE HISTORY START - {campaign_name} - {total} unprocessed save(s)")

    processed = 0
    errors: list[str] = []
    cache = _cache_counter()
    parsed_in_run: dict[int, tuple] = {}

    for index, snapshot in enumerate(snapshots, start=1):
        activity(
            f"[{index:02d}/{total:02d}] {snapshot['game_date']} - "
            f"{snapshot['archive_filename']}"
        )

        try:
            snapshot_id = int(snapshot["id"])

            (
                profile,
                current_state,
                current_leaders,
                current_worlds,
                current_science,
                current_combat,
                current_technology,
                current_cache_status,
            ) = load_or_parse_snapshot(
                archive_path=Path(snapshot["archive_path"]),
                source_save=source_save,
                source_sha256=snapshot["sha256"],
                snapshot_id=snapshot_id,
                cache_dir=cache_dir,
            )

            parsed_in_run[snapshot_id] = (
                profile,
                current_state,
                current_leaders,
                current_worlds,
                current_science,
                current_combat,
                current_technology,
            )
            _record_cache_status(
                cache,
                current_cache_status,
            )

            entry = _build_entry(
                snapshot,
                profile=profile,
            )

            previous_row = db.previous_snapshot(
                campaign_id,
                snapshot_id,
            )

            previous_state = None
            previous_leaders = None
            previous_worlds = None
            previous_science = None
            previous_combat = None
            previous_technology = None

            if previous_row is not None:
                previous_id = int(
                    previous_row["id"]
                )

                if previous_id in parsed_in_run:
                    (
                        _,
                        previous_state,
                        previous_leaders,
                        previous_worlds,
                        previous_science,
                        previous_combat,
                        previous_technology,
                    ) = parsed_in_run[
                        previous_id
                    ]
                else:
                    (
                        previous_profile,
                        previous_state,
                        previous_leaders,
                        previous_worlds,
                        previous_science,
                        previous_combat,
                        previous_technology,
                        previous_cache_status,
                    ) = load_or_parse_snapshot(
                        archive_path=Path(
                            previous_row["archive_path"]
                        ),
                        source_save=source_save,
                        source_sha256=previous_row["sha256"],
                        snapshot_id=previous_id,
                        cache_dir=cache_dir,
                    )

                    parsed_in_run[previous_id] = (
                        previous_profile,
                        previous_state,
                        previous_leaders,
                        previous_worlds,
                        previous_science,
                        previous_combat,
                        previous_technology,
                    )

                    _record_cache_status(
                        cache,
                        previous_cache_status,
                    )

            ship_fleet_delta = transition_data(
                previous_state,
                current_state,
                baseline=(snapshot["kind"] == "start"),
            )

            leader_delta = leader_transition_data(
                previous_leaders,
                current_leaders,
                baseline=(snapshot["kind"] == "start"),
            )

            world_delta = world_transition_data(
                previous_worlds,
                current_worlds,
                baseline=(snapshot["kind"] == "start"),
            )

            activity(
                "         "
                f"CACHE {current_cache_status.upper()} | "
                f"Ships {len(current_state.ships)} | "
                f"Fleets {len(current_state.fleets)} | "
                f"Shipyards {len(current_state.shipyards)} | "
                f"Leaders {len(current_leaders.leaders)} | "
                f"Worlds {len(current_worlds.worlds)} | "
                f"Dig sites {len(current_science.archaeology_sites)} | "
                f"Projects {len(current_science.special_projects)} | "
                f"Situations {len(current_science.situations)} | "
                f"Wars {len(current_combat.wars)} | "
                f"Formal battles {len(current_combat.battles)} | "
                f"Ship combat {len(current_combat.ship_activity)} | "
                f"Starbase combat {len(current_combat.starbase_activity)} | "
                f"Techs {len(current_technology.technologies)} | "
                f"Queued builds {len(current_state.build_orders)}"
            )

            db.add_history_entry(
                campaign_id=campaign_id,
                snapshot_id=entry["snapshot_id"],
                game_date=entry["game_date"],
                entry_type=entry["entry_type"],
                title=entry["title"],
                body=entry["body"],
                government_type=entry["government_type"],
                authority=entry["authority"],
                origin=entry["origin"],
                ethics=entry["ethics"],
                civics=entry["civics"],
            )

            db.apply_ship_fleet_delta(
                campaign_id,
                ship_fleet_delta,
            )

            db.apply_leader_delta(
                campaign_id,
                leader_delta,
            )

            db.apply_world_delta(
                campaign_id,
                world_delta,
            )

            db.mark_processed(
                snapshot_id
            )
            processed += 1

        except Exception as exc:
            message = f"{snapshot['archive_filename']}: {exc}"
            errors.append(message)
            error(f"UPDATE HISTORY - {message}")

    try:
        notification_death_incremental = promote_notification_deaths_in_database(
            db,
            campaign_id,
        )
        write_notification_death_diagnostic(
            _diagnostics_dir(Path(campaign["archive_dir"])),
            notification_death_incremental,
        )
        if notification_death_incremental.get("confirmed", 0):
            activity(
                "Notification-derived leader deaths promoted - "
                f"{notification_death_incremental['confirmed']} confirmed"
            )
    except Exception as exc:
        error(f"NOTIFICATION-DERIVED LEADER DEATHS - {exc}")

    remaining = db.unprocessed_count(
        campaign_id
    )

    activity(
        f"UPDATE HISTORY COMPLETE - {processed}/{total} processed - "
        f"{remaining} remaining - {_cache_summary(cache)} - "
        f"{format_duration(time.perf_counter() - started)}"
    )

    return {
        "processed": processed,
        "errors": errors,
        "remaining": remaining,
        "cache_hits": cache["hit"],
        "cache_extends": cache["extend"],
        "cache_misses": cache["miss"],
    }

def review_campaign(db: Database, campaign_id: int) -> dict:
    """Rebuild derived history without changing processed snapshot flags."""
    started = time.perf_counter()
    snapshots = db.all_snapshots(campaign_id)
    campaign, source_save, cache_dir = _campaign_context(db, campaign_id)
    campaign_name = campaign["empire_name"]
    total = len(snapshots)
    activity(f"REVIEW START - {campaign_name} - {total} archived save(s)")

    entries: list[dict] = []
    ship_fleet_snapshots = []
    leader_snapshots = []
    world_snapshots = []
    science_snapshots = []
    combat_snapshots = []
    technology_snapshots = []
    errors: list[str] = []
    cache = _cache_counter()

    for index, snapshot in enumerate(snapshots, start=1):
        activity(
            f"[{index:02d}/{total:02d}] {snapshot['game_date']} - "
            f"{snapshot['archive_filename']}"
        )

        try:
            (
                profile,
                parsed_snapshot,
                leader_snapshot,
                world_snapshot,
                science_snapshot,
                combat_snapshot,
                technology_snapshot,
                cache_status,
            ) = load_or_parse_snapshot(
                archive_path=Path(snapshot["archive_path"]),
                source_save=source_save,
                source_sha256=snapshot["sha256"],
                snapshot_id=int(snapshot["id"]),
                cache_dir=cache_dir,
            )

            _record_cache_status(
                cache,
                cache_status,
            )

            entries.append(
                _build_entry(
                    snapshot,
                    profile=profile,
                )
            )

            ship_fleet_snapshots.append(
                parsed_snapshot
            )
            leader_snapshots.append(
                leader_snapshot
            )
            world_snapshots.append(
                world_snapshot
            )
            science_snapshots.append(
                science_snapshot
            )
            combat_snapshots.append(
                combat_snapshot
            )
            technology_snapshots.append(
                technology_snapshot
            )

            activity(
                "         "
                f"CACHE {cache_status.upper()} | "
                f"Ships {len(parsed_snapshot.ships)} | "
                f"Fleets {len(parsed_snapshot.fleets)} | "
                f"Shipyards {len(parsed_snapshot.shipyards)} | "
                f"Leaders {len(leader_snapshot.leaders)} | "
                f"Worlds {len(world_snapshot.worlds)} | "
                f"Dig sites {len(science_snapshot.archaeology_sites)} | "
                f"Projects {len(science_snapshot.special_projects)} | "
                f"Situations {len(science_snapshot.situations)} | "
                f"Wars {len(combat_snapshot.wars)} | "
                f"Formal battles {len(combat_snapshot.battles)} | "
                f"Ship combat {len(combat_snapshot.ship_activity)} | "
                f"Starbase combat {len(combat_snapshot.starbase_activity)} | "
                f"Techs {len(technology_snapshot.technologies)} | "
                f"Queued builds {len(parsed_snapshot.build_orders)}"
            )

        except Exception as exc:
            message = f"{snapshot['archive_filename']}: {exc}"
            errors.append(message)
            error(f"REVIEW - {message}")

    if errors:
        activity(
            f"REVIEW ABORTED - {len(errors)} error(s) - "
            f"{_cache_summary(cache)} - "
            f"{format_duration(time.perf_counter() - started)}"
        )

        return {
            "reviewed": len(entries),
            "total": len(snapshots),
            "errors": errors,
            "rebuilt": False,
        }

    activity(
        f"Snapshot cache - {_cache_summary(cache).removeprefix('Cache ')}"
    )
    activity(
        f"Analysing {len(ship_fleet_snapshots)} parsed snapshot(s)..."
    )

    derived = derive_full_history(
        ship_fleet_snapshots
    )
    leader_derived = derive_full_leader_history(
        leader_snapshots
    )
    notification_death_summary = apply_notification_deaths(
        snapshots,
        leader_derived,
    )
    character_summary = character_evidence_summary(
        leader_snapshots,
        leader_derived,
    )
    world_derived = derive_full_world_history(
        world_snapshots
    )
    science_summary = science_evidence_summary(
        science_snapshots
    )
    combat_summary = combat_evidence_summary(
        combat_snapshots
    )
    technology_summary = technology_evidence_summary(
        technology_snapshots
    )
    correlated_engagements = derive_correlated_engagements(
        ship_fleet_snapshots,
        combat_snapshots,
    )
    correlation = correlation_summary(
        correlated_engagements
    )
    direct_combat_episodes = derive_direct_combat_episodes(
        combat_snapshots
    )
    combat_episodes = derive_combat_episodes(
        combat_snapshots,
        correlated_engagements,
        direct_combat_episodes,
    )
    episode_summary = combat_episode_summary(
        combat_episodes
    )
    historical_events = synthesize_historical_events(
        history_entries=entries,
        ship_history=derived,
        leader_history=leader_derived,
        world_history=world_derived,
        science_snapshots=science_snapshots,
        combat_engagements=correlated_engagements,
        direct_combat_episodes=direct_combat_episodes,
        combat_episodes=combat_episodes,
        technology_snapshots=technology_snapshots,
    )

    activity(
        "Derived history - "
        f"Ships {len(derived['ships'])} | "
        f"Fleets {len(derived['fleets'])} | "
        f"Leaders {len(leader_derived['leaders'])} | "
        f"Worlds {len(world_derived['worlds'])} | "
        f"World events {len(world_derived['events'])} "
        f"({sum(int(event.get('visible', 0)) for event in world_derived['events'])} published) | "
        f"Ship/Fleet events {len(derived['events'])} | "
        f"Refit evidence {sum(1 for event in derived['events'] if event.get('event_type') == 'ship_design_changed')} raw / {sum(1 for event in derived['events'] if event.get('event_type') in {'fleet_refit_observed', 'ship_refit_observed', 'naval_modernisation_wave', 'support_refit_wave_observed'} and int(event.get('visible', 0)))} published | "
        f"Career events {len(leader_derived['events'])} "
        f"({sum(int(event.get('visible', 0)) for event in leader_derived['events'])} published) | "
        f"Character evidence {character_summary['confirmed_death_events']} confirmed death(s) / "
        f"{character_summary['dead_records']} dead-record observation(s) | "
        f"Build-site records {len(derived.get('build_provenance', []))} | "
        f"Science evidence {science_summary['archaeology_sites']} digs / "
        f"{science_summary['special_projects']} project instances "
        f"({science_summary['project_families']} families) / "
        f"{science_summary['situations']} situations | "
        f"Combat evidence {combat_summary['wars']} formal wars / "
        f"{combat_summary['battles']} formal battles / "
        f"{combat_summary['ship_activity_markers']} ship activity markers / "
        f"{combat_summary['starbase_activity_markers']} starbase activity markers "
        f"({combat_summary['victories']} formal victories / {combat_summary['defeats']} formal defeats) | "
        f"Technology evidence {technology_summary['opening_technologies']} opening / "
        f"{technology_summary['technology_events']} gained / "
        f"{technology_summary['latest_technologies']} latest | "
        f"Combat correlations {correlation['candidate_engagements']} candidate / "
        f"{correlation['publishable_engagements']} publishable / "
        f"{correlation['high_confidence']} high-confidence / "
        f"{len(direct_combat_episodes)} direct combat anchor(s) / "
        f"{episode_summary['episodes']} synthesized combat episode(s) / "
        f"{episode_summary['telemetry_evolved']} evolving telemetry episode(s) | "
        f"Historical events {len(historical_events)}"
    )

    activity("Rebuilding Historian database records...")

    db.replace_review_data(
        campaign_id,
        history_entries=entries,
        ship_rows=derived["ships"],
        fleet_rows=derived["fleets"],
        ship_fleet_events=derived["events"],
        ship_build_provenance=derived.get("build_provenance", []),
        leader_rows=leader_derived["leaders"],
        leader_career_events=leader_derived["events"],
        world_rows=world_derived["worlds"],
        world_events=world_derived["events"],
    )

    diagnostic_dir = _diagnostics_dir(Path(campaign["archive_dir"]))
    activity(f"Campaign diagnostics directory - {diagnostic_dir}")

    science_debug = write_science_diagnostic(
        diagnostic_dir,
        science_snapshots,
    )
    activity(f"Science evidence diagnostic updated - diagnostics\\{science_debug.name}")
    science_interpretation_debug = write_science_interpretation_diagnostic(
        diagnostic_dir,
        science_snapshots,
    )
    activity(
        "Science interpretation diagnostic updated - "
        f"diagnostics\\{science_interpretation_debug.name}"
    )
    combat_debug = write_combat_diagnostic(
        diagnostic_dir,
        combat_snapshots,
    )
    activity(f"Combat evidence diagnostic updated - diagnostics\\{combat_debug.name}")
    combat_correlation_debug = write_combat_correlation_diagnostic(
        diagnostic_dir,
        correlated_engagements,
        direct_episodes=direct_combat_episodes,
    )
    activity(
        "Combat correlation diagnostic updated - "
        f"diagnostics\\{combat_correlation_debug.name}"
    )
    combat_episode_debug = write_combat_episode_diagnostic(
        diagnostic_dir,
        combat_episodes,
    )
    activity(
        "Combat episode diagnostic updated - "
        f"diagnostics\\{combat_episode_debug.name}"
    )
    notification_death_debug = write_notification_death_diagnostic(
        diagnostic_dir,
        notification_death_summary,
    )
    activity(
        "Notification-derived leader death diagnostic updated - "
        f"diagnostics\\{notification_death_debug.name}"
    )
    leader_exit_debug = write_leader_exit_diagnostic(
        diagnostic_dir,
        leader_derived,
    )
    activity(
        "Leader exit evidence diagnostic updated - "
        f"diagnostics\\{leader_exit_debug.name}"
    )
    character_debug = write_character_evidence_diagnostic(
        diagnostic_dir,
        leader_snapshots,
        leader_derived,
    )
    activity(
        "Character evidence diagnostic updated - "
        f"diagnostics\\{character_debug.name}"
    )
    raw_people_probe = write_raw_evidence_probe(
        diagnostic_dir,
        leader_snapshots,
    )
    activity(
        "Raw evidence probe updated - "
        f"diagnostics\\{raw_people_probe.name}"
    )
    historical_event_debug = write_historical_event_diagnostic(
        diagnostic_dir,
        historical_events,
    )
    activity(
        "Historical event layer diagnostic updated - "
        f"diagnostics\\{historical_event_debug.name}"
    )
    technology_debug = write_technology_diagnostic(
        diagnostic_dir,
        technology_snapshots,
    )
    activity(f"Technology evidence diagnostic updated - diagnostics\\{technology_debug.name}")

    activity(
        f"REVIEW DATA REBUILD COMPLETE - {_cache_summary(cache)} - "
        f"{format_duration(time.perf_counter() - started)}"
    )

    return {
        "reviewed": len(entries),
        "total": len(snapshots),
        "errors": [],
        "rebuilt": True,
        "ship_count": len(derived["ships"]),
        "fleet_count": len(derived["fleets"]),
        "leader_count": len(leader_derived["leaders"]),
        "world_count": len(world_derived["worlds"]),
        "world_event_count": len(world_derived["events"]),
        "ship_fleet_event_count": len(derived["events"]),
        "leader_career_event_count": len(leader_derived["events"]),
        "leader_confirmed_death_count": character_summary["confirmed_death_events"],
        "leader_dead_record_observation_count": character_summary["dead_records"],
        "science_archaeology_count": science_summary["archaeology_sites"],
        "science_project_count": science_summary["special_projects"],
        "science_project_family_count": science_summary["project_families"],
        "science_situation_count": science_summary["situations"],
        "combat_war_count": combat_summary["wars"],
        "combat_battle_count": combat_summary["battles"],
        "combat_victory_count": combat_summary["victories"],
        "combat_defeat_count": combat_summary["defeats"],
        "combat_ship_activity_marker_count": combat_summary["ship_activity_markers"],
        "combat_starbase_activity_marker_count": combat_summary["starbase_activity_markers"],
        "combat_relation_counterpart_count": combat_summary["relation_counterparts"],
        "combat_direct_fleet_record_count": combat_summary["direct_fleet_combat_records"],
        "combat_direct_episode_count": len(direct_combat_episodes),
        "combat_episode_count": episode_summary["episodes"],
        "combat_episode_evolving_telemetry_count": episode_summary["telemetry_evolved"],
        "combat_candidate_engagement_count": correlation["candidate_engagements"],
        "combat_publishable_engagement_count": correlation["publishable_engagements"],
        "combat_high_confidence_engagement_count": correlation["high_confidence"],
        "historical_event_count": len(historical_events),
        "technology_opening_count": technology_summary["opening_technologies"],
        "technology_event_count": technology_summary["technology_events"],
        "technology_latest_count": technology_summary["latest_technologies"],
        "duration_seconds": time.perf_counter() - started,
        "cache_hits": cache["hit"],
        "cache_extends": cache["extend"],
        "cache_misses": cache["miss"],
    }

def construct_campaign(
    db: Database,
    campaign_id: int,
) -> dict:
    """
    Reconstruct a campaign from archived Stellaris saves without reusing parsed
    snapshot cache data.

    Existing derived history remains available until every archived save has
    parsed successfully. On success all current derived tables are atomically
    replaced and every archived snapshot is marked Processed.
    """
    started = time.perf_counter()
    snapshots = db.all_snapshots(
        campaign_id
    )
    campaign, source_save, cache_dir = _campaign_context(
        db,
        campaign_id,
    )
    campaign_name = campaign["empire_name"]
    total = len(snapshots)

    warning(
        f"CONSTRUCT CAMPAIGN START - {campaign_name} - "
        f"{total} archived save(s)"
    )
    warning(
        "Discarding parsed snapshot cache and rebuilding from raw archived saves."
    )

    removed_cache_files = clear_campaign_cache(
        Path(campaign["archive_dir"])
    )

    activity(
        f"Cleared {removed_cache_files} cached snapshot file(s)."
    )

    entries: list[dict] = []
    ship_fleet_snapshots = []
    leader_snapshots = []
    world_snapshots = []
    science_snapshots = []
    combat_snapshots = []
    technology_snapshots = []
    errors: list[str] = []
    cache = _cache_counter()

    for index, snapshot in enumerate(
        snapshots,
        start=1,
    ):
        activity(
            f"CONSTRUCT [{index:02d}/{total:02d}] "
            f"{snapshot['game_date']} - {snapshot['archive_filename']}"
        )

        try:
            (
                profile,
                parsed_snapshot,
                leader_snapshot,
                world_snapshot,
                science_snapshot,
                combat_snapshot,
                technology_snapshot,
                cache_status,
            ) = load_or_parse_snapshot(
                archive_path=Path(snapshot["archive_path"]),
                source_save=source_save,
                source_sha256=snapshot["sha256"],
                snapshot_id=int(snapshot["id"]),
                cache_dir=cache_dir,
            )

            _record_cache_status(
                cache,
                cache_status,
            )

            entries.append(
                _build_entry(
                    snapshot,
                    profile=profile,
                )
            )

            ship_fleet_snapshots.append(
                parsed_snapshot
            )
            leader_snapshots.append(
                leader_snapshot
            )
            world_snapshots.append(
                world_snapshot
            )
            science_snapshots.append(
                science_snapshot
            )
            combat_snapshots.append(
                combat_snapshot
            )
            technology_snapshots.append(
                technology_snapshot
            )

            activity(
                "                  "
                f"CACHE {cache_status.upper()} | "
                f"Ships {len(parsed_snapshot.ships)} | "
                f"Fleets {len(parsed_snapshot.fleets)} | "
                f"Shipyards {len(parsed_snapshot.shipyards)} | "
                f"Leaders {len(leader_snapshot.leaders)} | "
                f"Worlds {len(world_snapshot.worlds)} | "
                f"Dig sites {len(science_snapshot.archaeology_sites)} | "
                f"Projects {len(science_snapshot.special_projects)} | "
                f"Situations {len(science_snapshot.situations)} | "
                f"Wars {len(combat_snapshot.wars)} | "
                f"Formal battles {len(combat_snapshot.battles)} | "
                f"Ship combat {len(combat_snapshot.ship_activity)} | "
                f"Starbase combat {len(combat_snapshot.starbase_activity)} | "
                f"Techs {len(technology_snapshot.technologies)} | "
                f"Queued builds {len(parsed_snapshot.build_orders)}"
            )

        except Exception as exc:
            message = f"{snapshot['archive_filename']}: {exc}"
            errors.append(message)
            error(f"CONSTRUCT CAMPAIGN - {message}")

    if errors:
        warning(
            f"CONSTRUCT CAMPAIGN ABORTED - {len(errors)} error(s). "
            "Existing derived history and processed flags were not replaced."
        )
        warning(
            f"Elapsed {format_duration(time.perf_counter() - started)}"
        )

        return {
            "constructed": len(entries),
            "total": total,
            "errors": errors,
            "rebuilt": False,
            "cache_hits": cache["hit"],
            "cache_extends": cache["extend"],
            "cache_misses": cache["miss"],
            "removed_cache_files": removed_cache_files,
            "duration_seconds": time.perf_counter() - started,
        }

    activity(
        f"CONSTRUCT parsed {len(ship_fleet_snapshots)} snapshot(s) - "
        f"{_cache_summary(cache)}"
    )
    activity(
        "Constructing complete historical data set..."
    )

    derived = derive_full_history(
        ship_fleet_snapshots
    )
    leader_derived = derive_full_leader_history(
        leader_snapshots
    )
    notification_death_summary = apply_notification_deaths(
        snapshots,
        leader_derived,
    )
    character_summary = character_evidence_summary(
        leader_snapshots,
        leader_derived,
    )
    world_derived = derive_full_world_history(
        world_snapshots
    )
    science_summary = science_evidence_summary(
        science_snapshots
    )
    combat_summary = combat_evidence_summary(
        combat_snapshots
    )
    technology_summary = technology_evidence_summary(
        technology_snapshots
    )
    correlated_engagements = derive_correlated_engagements(
        ship_fleet_snapshots,
        combat_snapshots,
    )
    correlation = correlation_summary(
        correlated_engagements
    )
    direct_combat_episodes = derive_direct_combat_episodes(
        combat_snapshots
    )
    combat_episodes = derive_combat_episodes(
        combat_snapshots,
        correlated_engagements,
        direct_combat_episodes,
    )
    episode_summary = combat_episode_summary(
        combat_episodes
    )
    historical_events = synthesize_historical_events(
        history_entries=entries,
        ship_history=derived,
        leader_history=leader_derived,
        world_history=world_derived,
        science_snapshots=science_snapshots,
        combat_engagements=correlated_engagements,
        direct_combat_episodes=direct_combat_episodes,
        combat_episodes=combat_episodes,
        technology_snapshots=technology_snapshots,
    )

    activity(
        "Constructed history - "
        f"Ships {len(derived['ships'])} | "
        f"Fleets {len(derived['fleets'])} | "
        f"Leaders {len(leader_derived['leaders'])} | "
        f"Worlds {len(world_derived['worlds'])} | "
        f"World events {len(world_derived['events'])} "
        f"({sum(int(event.get('visible', 0)) for event in world_derived['events'])} published) | "
        f"Ship/Fleet events {len(derived['events'])} | "
        f"Refit evidence {sum(1 for event in derived['events'] if event.get('event_type') == 'ship_design_changed')} raw / {sum(1 for event in derived['events'] if event.get('event_type') in {'fleet_refit_observed', 'ship_refit_observed', 'naval_modernisation_wave', 'support_refit_wave_observed'} and int(event.get('visible', 0)))} published | "
        f"Career events {len(leader_derived['events'])} "
        f"({sum(int(event.get('visible', 0)) for event in leader_derived['events'])} published) | "
        f"Character evidence {character_summary['confirmed_death_events']} confirmed death(s) / "
        f"{character_summary['dead_records']} dead-record observation(s) | "
        f"Build-site records {len(derived.get('build_provenance', []))} | "
        f"Science evidence {science_summary['archaeology_sites']} digs / "
        f"{science_summary['special_projects']} project instances "
        f"({science_summary['project_families']} families) / "
        f"{science_summary['situations']} situations | "
        f"Combat evidence {combat_summary['wars']} formal wars / "
        f"{combat_summary['battles']} formal battles / "
        f"{combat_summary['ship_activity_markers']} ship activity markers / "
        f"{combat_summary['starbase_activity_markers']} starbase activity markers "
        f"({combat_summary['victories']} formal victories / {combat_summary['defeats']} formal defeats) | "
        f"Technology evidence {technology_summary['opening_technologies']} opening / "
        f"{technology_summary['technology_events']} gained / "
        f"{technology_summary['latest_technologies']} latest | "
        f"Combat correlations {correlation['candidate_engagements']} candidate / "
        f"{correlation['publishable_engagements']} publishable / "
        f"{correlation['high_confidence']} high-confidence / "
        f"{len(direct_combat_episodes)} direct combat anchor(s) / "
        f"{episode_summary['episodes']} synthesized combat episode(s) / "
        f"{episode_summary['telemetry_evolved']} evolving telemetry episode(s) | "
        f"Historical events {len(historical_events)}"
    )
    activity(
        "Replacing generated Historian database records..."
    )

    db.replace_review_data(
        campaign_id,
        history_entries=entries,
        ship_rows=derived["ships"],
        fleet_rows=derived["fleets"],
        ship_fleet_events=derived["events"],
        ship_build_provenance=derived.get("build_provenance", []),
        leader_rows=leader_derived["leaders"],
        leader_career_events=leader_derived["events"],
        world_rows=world_derived["worlds"],
        world_events=world_derived["events"],
    )

    diagnostic_dir = _diagnostics_dir(Path(campaign["archive_dir"]))
    activity(f"Campaign diagnostics directory - {diagnostic_dir}")

    science_debug = write_science_diagnostic(
        diagnostic_dir,
        science_snapshots,
    )
    activity(f"Science evidence diagnostic updated - diagnostics\\{science_debug.name}")
    science_interpretation_debug = write_science_interpretation_diagnostic(
        diagnostic_dir,
        science_snapshots,
    )
    activity(
        "Science interpretation diagnostic updated - "
        f"diagnostics\\{science_interpretation_debug.name}"
    )
    combat_debug = write_combat_diagnostic(
        diagnostic_dir,
        combat_snapshots,
    )
    activity(f"Combat evidence diagnostic updated - diagnostics\\{combat_debug.name}")
    combat_correlation_debug = write_combat_correlation_diagnostic(
        diagnostic_dir,
        correlated_engagements,
        direct_episodes=direct_combat_episodes,
    )
    activity(
        "Combat correlation diagnostic updated - "
        f"diagnostics\\{combat_correlation_debug.name}"
    )
    combat_episode_debug = write_combat_episode_diagnostic(
        diagnostic_dir,
        combat_episodes,
    )
    activity(
        "Combat episode diagnostic updated - "
        f"diagnostics\\{combat_episode_debug.name}"
    )
    notification_death_debug = write_notification_death_diagnostic(
        diagnostic_dir,
        notification_death_summary,
    )
    activity(
        "Notification-derived leader death diagnostic updated - "
        f"diagnostics\\{notification_death_debug.name}"
    )
    leader_exit_debug = write_leader_exit_diagnostic(
        diagnostic_dir,
        leader_derived,
    )
    activity(
        "Leader exit evidence diagnostic updated - "
        f"diagnostics\\{leader_exit_debug.name}"
    )
    character_debug = write_character_evidence_diagnostic(
        diagnostic_dir,
        leader_snapshots,
        leader_derived,
    )
    activity(
        "Character evidence diagnostic updated - "
        f"diagnostics\\{character_debug.name}"
    )
    raw_people_probe = write_raw_evidence_probe(
        diagnostic_dir,
        leader_snapshots,
    )
    activity(
        "Raw evidence probe updated - "
        f"diagnostics\\{raw_people_probe.name}"
    )
    historical_event_debug = write_historical_event_diagnostic(
        diagnostic_dir,
        historical_events,
    )
    activity(
        "Historical event layer diagnostic updated - "
        f"diagnostics\\{historical_event_debug.name}"
    )
    technology_debug = write_technology_diagnostic(
        diagnostic_dir,
        technology_snapshots,
    )
    activity(f"Technology evidence diagnostic updated - diagnostics\\{technology_debug.name}")

    newly_marked_processed = db.mark_all_processed(
        campaign_id
    )

    duration = time.perf_counter() - started

    warning(
        f"CONSTRUCT CAMPAIGN COMPLETE - {total} save(s) - "
        f"{_cache_summary(cache)} - {format_duration(duration)}"
    )

    return {
        "constructed": total,
        "total": total,
        "errors": [],
        "rebuilt": True,
        "ship_count": len(derived["ships"]),
        "fleet_count": len(derived["fleets"]),
        "leader_count": len(leader_derived["leaders"]),
        "world_count": len(world_derived["worlds"]),
        "world_event_count": len(world_derived["events"]),
        "ship_fleet_event_count": len(derived["events"]),
        "leader_career_event_count": len(leader_derived["events"]),
        "leader_confirmed_death_count": character_summary["confirmed_death_events"],
        "leader_dead_record_observation_count": character_summary["dead_records"],
        "science_archaeology_count": science_summary["archaeology_sites"],
        "science_project_count": science_summary["special_projects"],
        "science_project_family_count": science_summary["project_families"],
        "science_situation_count": science_summary["situations"],
        "combat_war_count": combat_summary["wars"],
        "combat_battle_count": combat_summary["battles"],
        "combat_victory_count": combat_summary["victories"],
        "combat_defeat_count": combat_summary["defeats"],
        "combat_ship_activity_marker_count": combat_summary["ship_activity_markers"],
        "combat_starbase_activity_marker_count": combat_summary["starbase_activity_markers"],
        "combat_relation_counterpart_count": combat_summary["relation_counterparts"],
        "combat_direct_fleet_record_count": combat_summary["direct_fleet_combat_records"],
        "combat_direct_episode_count": len(direct_combat_episodes),
        "combat_episode_count": episode_summary["episodes"],
        "combat_episode_evolving_telemetry_count": episode_summary["telemetry_evolved"],
        "combat_candidate_engagement_count": correlation["candidate_engagements"],
        "combat_publishable_engagement_count": correlation["publishable_engagements"],
        "combat_high_confidence_engagement_count": correlation["high_confidence"],
        "historical_event_count": len(historical_events),
        "technology_opening_count": technology_summary["opening_technologies"],
        "technology_event_count": technology_summary["technology_events"],
        "technology_latest_count": technology_summary["latest_technologies"],
        "cache_hits": cache["hit"],
        "cache_extends": cache["extend"],
        "cache_misses": cache["miss"],
        "removed_cache_files": removed_cache_files,
        "newly_marked_processed": newly_marked_processed,
        "duration_seconds": duration,
    }

