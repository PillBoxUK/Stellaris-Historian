from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .domains.combat.correlation import CorrelatedEngagement
from .domains.combat.episodes import CombatEpisode
from .domains.science.history import derive_science_interpretation
from .domains.technology import derive_technology_history


_RED_GIANT_PROJECT_KEYS = {
    "INF_ORIGIN_RED_GIANT_TRIANGULATION",
    "INF_ORIGIN_RED_GIANT_PROTECT_HOMEWORLD",
    "INF_ORIGIN_RED_GIANT_PARLAY",
    "INF_ORIGIN_RED_GIANT_BOARD_STATION",
}
_RED_GIANT_SITUATION_KEY = "situation_red_giant_expansion"


@dataclass(frozen=True)
class HistoricalEvent:
    game_date: str
    category: str
    event_type: str
    title: str
    summary: str
    confidence: str
    date_kind: str
    source: str
    importance: int
    attributes: tuple[tuple[str, str], ...] = ()


def _clean_system_name(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split()).strip()
    low = text.casefold()
    if "_" in text or low.endswith(" name") or low.startswith("unknown"):
        return None
    return text


def _neutralize_evidence_text(value: object) -> str:
    """Remove renderer/audience voice from source-domain prose.

    The historical event layer may describe evidence provenance, but it should
    not speak as the game or as Historian itself. Journal/Timeline/Scribes are
    responsible for their own voice in later presentation stages.
    """
    text = " ".join(str(value or "").split())
    if not text:
        return text
    text = re.sub(r"^Stellaris records\s+", "The record identifies ", text, flags=re.I)
    text = re.sub(r"\bHistorian treats this as\b", "This is treated as", text, flags=re.I)
    text = re.sub(r"\bStellaris records\b", "The record identifies", text, flags=re.I)
    return text


def _pairs(**values: object) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, (tuple, list, set)):
            text = ", ".join(str(item) for item in value if item not in (None, ""))
            if not text:
                continue
        else:
            text = str(value)
        result.append((key, text))
    return tuple(result)


def _combat_episode_event(episode: CombatEpisode) -> HistoricalEvent | None:
    location = ", ".join(episode.system_names) if episode.system_names else None
    enemies = ", ".join(episode.enemy_country_names) if episode.enemy_country_names else None
    fleets = ", ".join(episode.fleet_names) if episode.fleet_names else None

    # Suppress low-information marker-only noise from the common historical
    # stream. It remains preserved in combat diagnostics and episode diagnostics.
    if not episode.has_direct_evidence and not location and not fleets and not episode.formal_outcome:
        return None

    if enemies and location:
        title = f"Combat with {enemies} in {location}"
    elif enemies:
        title = f"Combat with {enemies}"
    elif location:
        title = f"Combat activity in {location}"
    else:
        title = "Combat activity recorded"

    period = episode.start_date
    if episode.end_date != episode.start_date:
        period = f"{episode.start_date} to {episode.end_date}"

    details: list[str] = [f"Combat evidence spans {period}."]
    if location:
        details.append(f"Recorded location: {location}.")
    if enemies:
        details.append(f"Recorded opposing force: {enemies}.")
    if fleets:
        details.append(f"Recorded fleets: {fleets}.")
    if episode.commander_names:
        details.append("Commanders recorded: " + ", ".join(episode.commander_names) + ".")

    initial = episode.initial_loss_observation
    latest = episode.latest_loss_observation
    if initial is not None and latest is not None:
        if episode.telemetry_evolved:
            details.append(
                f"The first complete retained telemetry state reconstructable by {initial.observed_date} records "
                f"{initial.player_ships_lost} tracked-force loss(es) and {initial.enemy_ships_lost} opposing loss(es); "
                f"the latest complete per-fleet telemetry state reconstructable by {latest.observed_date} records "
                f"{latest.player_ships_lost} and {latest.enemy_ships_lost} respectively. "
                "These are evolving observations of retained combat state, not separately added loss events; "
                "a participant absent from a later snapshot can retain its last known state in the composite."
            )
        elif initial.player_ships_lost or initial.enemy_ships_lost:
            details.append(
                f"Retained direct telemetry records {initial.player_ships_lost} tracked-force loss(es) "
                f"and {initial.enemy_ships_lost} opposing loss(es)."
            )

    if episode.formal_outcome == "victory":
        details.append("A formal battle record establishes victory for the tracked force.")
    elif episode.formal_outcome == "defeat":
        details.append("A formal battle record establishes defeat for the tracked force.")
    else:
        details.append("No victory or defeat is established by the retained episode evidence.")

    if episode.possible_loss_names:
        details.append(
            "Nearby ship disappearances remain possible losses only and are not counted as confirmed combat losses."
        )

    return HistoricalEvent(
        game_date=episode.start_date,
        category="combat",
        event_type="combat_episode",
        title=title,
        summary=" ".join(details),
        confidence=episode.confidence,
        date_kind="combat_episode",
        source="combat_episode_synthesis",
        importance=98 if episode.has_direct_evidence else (88 if episode.confidence == "high" else 76),
        attributes=_pairs(
            end_date=episode.end_date,
            evidence_kind=episode.evidence_kind,
            systems=episode.system_names,
            opposing_countries=episode.enemy_country_names,
            opposing_fleets=episode.enemy_fleet_names,
            player_fleets=episode.fleet_names,
            commanders=episode.commander_names,
            starbases=episode.starbase_names,
            activity_dates=episode.activity_dates,
            direct_record_count=episode.direct_record_count,
            correlated_engagement_count=episode.correlated_engagement_count,
            formal_outcome=episode.formal_outcome or "not_established",
            telemetry_evolved=str(episode.telemetry_evolved).lower(),
            initial_observed_date=(initial.observed_date if initial is not None else None),
            initial_player_losses=(initial.player_ships_lost if initial is not None else None),
            initial_opposing_losses=(initial.enemy_ships_lost if initial is not None else None),
            latest_observed_date=(latest.observed_date if latest is not None else None),
            latest_player_losses=(latest.player_ships_lost if latest is not None else None),
            latest_opposing_losses=(latest.enemy_ships_lost if latest is not None else None),
        ),
    )


def synthesize_historical_events(
    *,
    history_entries: list[dict],
    ship_history: dict,
    leader_history: dict,
    world_history: dict,
    science_snapshots: list,
    combat_engagements: list[CorrelatedEngagement],
    direct_combat_episodes: list | None = None,
    combat_episodes: list[CombatEpisode] | None = None,
    technology_snapshots: list,
) -> list[HistoricalEvent]:
    """Create the normalized, presentation-neutral historical event stream.

    v0.0.41 keeps combat-episode synthesis and expands structured presentation attributes while
    retaining source/confidence/date-kind provenance. Presentation layers should
    render these facts in their own voice rather than embedding game/UI voice in
    the event model itself.
    """
    events: list[HistoricalEvent] = []

    for row in history_entries:
        if row.get("entry_type") != "founding":
            continue
        events.append(HistoricalEvent(
            game_date=str(row["game_date"]),
            category="empire",
            event_type="record_opening",
            title=str(row["title"]),
            summary=_neutralize_evidence_text(row["body"]),
            confidence="high",
            date_kind="archive_opening",
            source="history_entry",
            importance=100,
        ))

    for row in world_history.get("events", []):
        if not int(row.get("visible", 0)):
            continue
        events.append(HistoricalEvent(
            game_date=str(row["game_date"]),
            category="expansion",
            event_type=str(row["event_type"]),
            title=str(row["title"]),
            summary=_neutralize_evidence_text(row["body"]),
            confidence=str(row.get("confidence", "high")),
            date_kind=str(row.get("date_kind", "between_snapshots")),
            source="world_history",
            importance=90,
        ))

    # The source domain uses these actual event names. v0.0.38 still contained
    # obsolete aliases, which unintentionally demoted ruler/service events.
    leader_importance = {
        "leader_entered_service": 74,
        "leader_first_observed": 66,
        "leader_became_ruler": 96,
        "leader_left_rulership": 95,
        "leader_became_heir": 78,
        "leader_left_heirship": 74,
        "leader_assignment_changed": 64,
        "leader_council_changed": 68,
        "leader_level_changed": 42,
        "leader_traits_gained": 52,
        "leader_death_recorded": 98,
        "leader_tombstone_unconfirmed": 88,
        "leader_missing_unconfirmed": 88,
    }
    for row in leader_history.get("events", []):
        if not int(row.get("visible", 0)):
            continue
        event_type = str(row["event_type"])
        attributes = _pairs(leader_id=row.get("leader_id"))
        if event_type == "leader_death_recorded":
            attributes = _pairs(
                leader_id=row.get("leader_id"),
                death_established="true",
                evidence_kind=row.get("death_evidence_kind") or "retained_death_evidence",
                notification_id=row.get("notification_id"),
                recorded_age=row.get("recorded_age"),
                recorded_service=row.get("time_served"),
                death_reason=row.get("death_reason"),
            )
        elif event_type in {"leader_missing_unconfirmed", "leader_tombstone_unconfirmed"}:
            attributes = _pairs(
                leader_id=row.get("leader_id"),
                death_established="false",
                exit_reason_established="false",
            )
        events.append(HistoricalEvent(
            game_date=str(row["game_date"]),
            category="people",
            event_type=event_type,
            title=str(row["title"]),
            summary=_neutralize_evidence_text(row["body"]),
            confidence=str(row.get("confidence", "high")),
            date_kind=str(row.get("date_kind", "between_snapshots")),
            source="leader_history",
            importance=leader_importance.get(event_type, 45),
            attributes=attributes,
        ))

    naval_types = {
        "ship_commissioned": 45,
        "fleet_first_observed": 70,
        "fleet_commander_changed": 65,
        "naval_modernisation_wave": 60,
        "fleet_refit_observed": 55,
    }
    for row in ship_history.get("events", []):
        if not int(row.get("visible", 0)):
            continue
        event_type = str(row["event_type"])
        if event_type not in naval_types:
            continue
        events.append(HistoricalEvent(
            game_date=str(row["game_date"]),
            category="military",
            event_type=event_type,
            title=str(row["title"]),
            summary=_neutralize_evidence_text(row["body"]),
            confidence=str(row.get("confidence", "high")),
            date_kind=str(row.get("date_kind", "between_snapshots")),
            source="ship_history",
            importance=naval_types[event_type],
        ))

    if science_snapshots:
        interpretation = derive_science_interpretation(science_snapshots)
        for site in interpretation.archaeology_sites:
            location = ", ".join(site.location_names) if site.location_names else "an unresolved location"
            events.append(HistoricalEvent(
                game_date=str(site.first_observed),
                category="science",
                event_type="archaeology_site_observed",
                title=str(site.title),
                summary=f"First archived observation of {site.title}: {location}.",
                confidence="high",
                date_kind="first_observed",
                source="science_interpretation",
                importance=72,
                attributes=_pairs(
                    site_type=site.type_key,
                    location=location,
                    last_observed=site.last_observed,
                    scientists=site.scientist_names,
                    progress_marker_dates=site.progress_marker_dates,
                ),
            ))
        for project in interpretation.project_families:
            importance = 76 if project.project_key in _RED_GIANT_PROJECT_KEYS else 50
            events.append(HistoricalEvent(
                game_date=str(project.first_observed),
                category="science",
                event_type="special_project_observed",
                title=str(project.title),
                summary=f"First archived observation of the research project {project.title}.",
                confidence="high",
                date_kind="first_observed",
                source="science_interpretation",
                importance=importance,
                attributes=_pairs(
                    project_key=project.project_key,
                    last_observed=project.last_observed,
                    locations=project.location_names,
                    ships=project.ship_names,
                    scientists=project.scientist_names,
                ),
            ))
        for situation in interpretation.situations:
            if situation.type_key == _RED_GIANT_SITUATION_KEY:
                importance = 82
            elif situation.type_key in {"situation_pre_ftl_nwo", "situation_pre_ftl_singularity"}:
                importance = 72
            elif situation.type_key == "situation_observation_insight":
                importance = 35
            elif situation.type_key.endswith("_deficit"):
                importance = 32
            else:
                importance = 48
            events.append(HistoricalEvent(
                game_date=str(situation.first_observed),
                category="science",
                event_type="situation_observed",
                title=str(situation.title),
                summary=f"The situation {situation.title} first enters the surviving record on this date.",
                confidence="high",
                date_kind="first_observed",
                source="science_interpretation",
                importance=importance,
                attributes=_pairs(
                    situation_key=situation.type_key,
                    last_observed=situation.last_observed,
                    latest_progress=situation.latest_progress,
                    latest_approach=situation.latest_approach_key,
                    target_type=situation.target_type,
                    target_id=situation.target_id,
                ),
            ))

    if technology_snapshots:
        technology = derive_technology_history(technology_snapshots)
        for row in technology["events"]:
            events.append(HistoricalEvent(
                game_date=str(row.game_date),
                category="technology",
                event_type=str(row.event_type),
                title=str(row.name),
                summary=(
                    f"First archived observation of {row.name} by {row.game_date}."
                    if row.event_type != "technology_level_increased"
                    else f"First archived observation of {row.name} at recorded level {row.level} by {row.game_date}."
                ),
                confidence="high",
                date_kind="first_observed",
                source="technology_history",
                importance=55,
                attributes=_pairs(level=getattr(row, "level", None)),
            ))

    if combat_episodes is not None:
        for episode in combat_episodes:
            event = _combat_episode_event(episode)
            if event is not None:
                events.append(event)
    else:
        # Compatibility fallback for callers not yet supplying v0.0.40 episodes.
        for episode in (direct_combat_episodes or []):
            enemy = ", ".join(episode.enemy_country_names) or "an opposing force"
            fleets = ", ".join(row.player_fleet_name for row in episode.player_fleets)
            location = _clean_system_name(episode.system_name) or "an unresolved system"
            summary = (
                f"Direct fleet combat telemetry records {fleets or 'tracked fleets'} entering combat with {enemy} "
                f"from {episode.start_date} in {location}."
            )
            if episode.commander_names:
                summary += " Commanders recorded: " + ", ".join(episode.commander_names) + "."
            if episode.player_ships_lost or episode.enemy_ships_lost:
                summary += (
                    f" Retained fleet statistics record {episode.player_ships_lost} tracked-force ship loss(es) "
                    f"and {episode.enemy_ships_lost} opposing ship loss(es); those counts do not establish an outcome."
                )
            events.append(HistoricalEvent(
                game_date=episode.start_date,
                category="combat",
                event_type="direct_fleet_combat",
                title=f"Combat with {enemy}",
                summary=summary,
                confidence="high",
                date_kind="exact_combat_stats",
                source="fleet_combat_stats",
                importance=98,
            ))

        for engagement in combat_engagements:
            if not engagement.publishable:
                continue
            participants = [row.ship_name for row in engagement.ship_participants]
            participants += [
                row.starbase_name for row in engagement.starbase_participants
                if str(row.starbase_name).strip().casefold() not in {"planet station", "station"}
            ]
            subject = ", ".join(participants[:6])
            if len(participants) > 6:
                subject += f" and {len(participants) - 6} other recorded participant(s)"
            if not subject and not engagement.context_system_names:
                continue
            summary = f"Exact combat activity is recorded on this date for {subject or 'tracked forces'}."
            if engagement.formal_battles:
                formal = engagement.formal_battles[0]
                if formal.player_victory is True:
                    summary += " A formal battle record establishes a victory."
                elif formal.player_victory is False:
                    summary += " A formal battle record establishes a defeat."
            elif engagement.possible_losses:
                summary += " Nearby ship disappearances remain possible losses only."
            events.append(HistoricalEvent(
                game_date=engagement.combat_date,
                category="combat",
                event_type="correlated_engagement",
                title="Engagement recorded",
                summary=summary,
                confidence=engagement.correlation_confidence,
                date_kind="exact_combat_activity",
                source="combat_correlation",
                importance=85 if engagement.correlation_confidence == "high" else 75,
            ))

    events.sort(key=lambda row: (row.game_date, -row.importance, row.category, row.title))
    return events


def write_historical_event_diagnostic(
    archive_dir: Path,
    events: list[HistoricalEvent],
) -> Path:
    path = Path(archive_dir) / "Historical_Event_Debug.txt"
    lines = [
        "STELLARIS HISTORIAN - HISTORICAL EVENT LAYER DEBUG",
        "",
        "v0.0.41 presentation-neutral historical event stream.",
        "Evidence facts remain tagged with source, confidence, date-kind and optional structured attributes.",
        "Presentation voice belongs to the Evidence Journal, Empire Timeline and Scribes Chronicle, not to this layer.",
        "",
        f"Historical events synthesized: {len(events)}",
        "",
    ]
    for row in events:
        lines.extend([
            f"{row.game_date} | {row.category.upper()} | {row.title}",
            f"  Type: {row.event_type}",
            f"  Importance: {row.importance}",
            f"  Confidence: {row.confidence}",
            f"  Date kind: {row.date_kind}",
            f"  Source: {row.source}",
            f"  Summary: {row.summary}",
        ])
        if row.attributes:
            lines.append("  Attributes:")
            lines.extend(f"    {key}: {value}" for key, value in row.attributes)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
