from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .correlation import CorrelatedEngagement, DirectCombatEpisode
from .models import CombatSnapshot


_GENERIC_PARTICIPANT_NAMES = {
    "station",
    "planet station",
    "starbase",
    "unknown",
    "unknown station",
}


@dataclass(frozen=True)
class CombatLossObservation:
    observed_date: str
    record_count: int
    expected_record_count: int
    carried_forward_count: int
    complete: bool
    player_ships_lost: int
    enemy_ships_lost: int


@dataclass(frozen=True)
class CombatEpisode:
    episode_key: str
    start_date: str
    end_date: str
    latest_observed_date: str
    evidence_kind: str
    confidence: str
    system_names: tuple[str, ...]
    enemy_country_names: tuple[str, ...]
    enemy_fleet_names: tuple[str, ...]
    fleet_names: tuple[str, ...]
    commander_names: tuple[str, ...]
    starbase_names: tuple[str, ...]
    activity_dates: tuple[str, ...]
    direct_combat_dates: tuple[str, ...]
    direct_record_count: int
    correlated_engagement_count: int
    loss_observations: tuple[CombatLossObservation, ...]
    formal_outcome: str | None
    possible_loss_names: tuple[str, ...]

    @property
    def has_direct_evidence(self) -> bool:
        return self.direct_record_count > 0

    @property
    def initial_loss_observation(self) -> CombatLossObservation | None:
        if not self.loss_observations:
            return None
        complete = [row for row in self.loss_observations if row.complete]
        return (complete or list(self.loss_observations))[0]

    @property
    def latest_loss_observation(self) -> CombatLossObservation | None:
        if not self.loss_observations:
            return None
        complete = [row for row in self.loss_observations if row.complete]
        return (complete or list(self.loss_observations))[-1]

    @property
    def telemetry_evolved(self) -> bool:
        first = self.initial_loss_observation
        latest = self.latest_loss_observation
        if first is None or latest is None:
            return False
        return (
            first.player_ships_lost != latest.player_ships_lost
            or first.enemy_ships_lost != latest.enemy_ships_lost
        )


def _stellar_ordinal(value: str) -> int:
    try:
        year, month, day = (int(part) for part in str(value).split(".")[:3])
        return year * 360 + (month - 1) * 30 + day
    except (ValueError, TypeError, AttributeError):
        return 0


def _clean_name(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split()).strip()
    if not text or text.casefold() in _GENERIC_PARTICIPANT_NAMES:
        return None
    if "_" in text or text.casefold().startswith("unknown"):
        return None
    return text


def _system_key(names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({name.casefold() for name in names if _clean_name(name)}))


def _engagement_system_names(row: CorrelatedEngagement) -> tuple[str, ...]:
    return tuple(sorted({
        cleaned
        for value in row.context_system_names
        if (cleaned := _clean_name(value))
    }))


def _engagement_starbase_names(row: CorrelatedEngagement) -> tuple[str, ...]:
    return tuple(sorted({
        cleaned
        for state in row.starbase_participants
        if (cleaned := _clean_name(state.starbase_name))
    }))


def _formal_outcome(engagements: list[CorrelatedEngagement]) -> str | None:
    outcomes: set[bool] = set()
    for engagement in engagements:
        for battle in engagement.formal_battles:
            if battle.player_victory is not None:
                outcomes.add(bool(battle.player_victory))
    if outcomes == {True}:
        return "victory"
    if outcomes == {False}:
        return "defeat"
    return None


def _direct_loss_observations(
    combat_snapshots: list[CombatSnapshot],
    direct: DirectCombatEpisode,
) -> tuple[CombatLossObservation, ...]:
    combat_keys = {state.combat_key for state in direct.player_fleets}
    expected = len(combat_keys)
    observations: list[CombatLossObservation] = []
    latest_by_key: dict[str, object] = {}

    for snapshot in sorted(combat_snapshots, key=lambda row: _stellar_ordinal(row.game_date)):
        observed_states = {
            key: state
            for key, state in snapshot.fleet_combat_stats.items()
            if key in combat_keys
        }
        if not observed_states:
            continue

        # combat_stats is retained state rather than an immutable battle result.
        # Stellaris can stop repeating one participant's record while continuing
        # to update another participant from the same combat episode. Preserve
        # the latest observation for each combat key independently so a missing
        # row in a later snapshot does not silently reset that fleet's losses to
        # zero or make an evolved episode look unchanged.
        latest_by_key.update(observed_states)
        states = list(latest_by_key.values())

        # Each player-fleet combat key carries that player's retained loss count.
        # Enemy loss counters can be duplicated across participating player fleets,
        # so preserve the maximum per enemy fleet for the composite latest-known
        # state reconstructed by this archive observation.
        player_by_fleet: dict[int, int] = {}
        enemy_by_fleet: dict[object, int] = {}
        for state in states:
            player_by_fleet[state.player_fleet_id] = int(state.player_ships_lost or 0)
            for enemy in state.enemy_fleets:
                enemy_key: object = enemy.fleet_id
                if enemy_key is None:
                    enemy_key = (enemy.country_id, enemy.country_name, enemy.fleet_name)
                enemy_by_fleet[enemy_key] = max(
                    enemy_by_fleet.get(enemy_key, 0),
                    int(enemy.ships_lost or 0),
                )

        observations.append(CombatLossObservation(
            observed_date=snapshot.game_date,
            record_count=len(observed_states),
            expected_record_count=expected,
            carried_forward_count=max(0, len(states) - len(observed_states)),
            complete=(len(latest_by_key) == expected),
            player_ships_lost=sum(player_by_fleet.values()),
            enemy_ships_lost=sum(enemy_by_fleet.values()),
        ))

    # Collapse identical consecutive observations. The dates remain observation
    # dates, not combat dates; retaining only state changes makes mutable telemetry
    # obvious without flooding diagnostics with repeated snapshots.
    collapsed: list[CombatLossObservation] = []
    for row in observations:
        if collapsed:
            previous = collapsed[-1]
            if (
                previous.record_count == row.record_count
                and previous.expected_record_count == row.expected_record_count
                and previous.carried_forward_count == row.carried_forward_count
                and previous.complete == row.complete
                and previous.player_ships_lost == row.player_ships_lost
                and previous.enemy_ships_lost == row.enemy_ships_lost
            ):
                continue
        collapsed.append(row)
    return tuple(collapsed)


def _direct_matches_engagement(
    direct: DirectCombatEpisode,
    engagement: CorrelatedEngagement,
) -> bool:
    direct_system = _clean_name(direct.system_name)
    engagement_systems = _engagement_system_names(engagement)
    if direct_system and direct_system.casefold() in _system_key(engagement_systems):
        return True

    direct_fleets = {state.player_fleet_name for state in direct.player_fleets if state.player_fleet_name}
    if direct_fleets.intersection(engagement.fleet_names):
        distance = abs(_stellar_ordinal(engagement.combat_date) - _stellar_ordinal(direct.start_date))
        return distance <= 30
    return False


def _attach_correlated_to_direct(
    direct: DirectCombatEpisode,
    engagements: list[CorrelatedEngagement],
    used: set[int],
) -> list[CorrelatedEngagement]:
    direct_dates = [state.start_date for state in direct.player_fleets]
    anchor_start = min((_stellar_ordinal(value) for value in direct_dates), default=_stellar_ordinal(direct.start_date))
    current_end = max((_stellar_ordinal(value) for value in direct_dates), default=anchor_start)

    attached: list[CorrelatedEngagement] = []
    for index, engagement in sorted(
        enumerate(engagements),
        key=lambda item: _stellar_ordinal(item[1].combat_date),
    ):
        if index in used or not engagement.publishable:
            continue
        date_ord = _stellar_ordinal(engagement.combat_date)
        if date_ord < anchor_start - 30:
            continue
        if date_ord > current_end + 120:
            # Once we are beyond the continuity window, a later same-system marker
            # must begin a new episode rather than extending this one forever.
            continue
        if not _direct_matches_engagement(direct, engagement):
            continue
        attached.append(engagement)
        used.add(index)
        current_end = max(current_end, date_ord)
    return attached


def _marker_cluster_key(row: CorrelatedEngagement) -> tuple[str, tuple[str, ...]]:
    systems = _system_key(_engagement_system_names(row))
    if systems:
        return ("system", systems)
    fleets = tuple(sorted(name.casefold() for name in row.fleet_names if name))
    if fleets:
        return ("fleet", fleets)
    bases = tuple(name.casefold() for name in _engagement_starbase_names(row))
    if bases:
        return ("starbase", bases)
    return ("isolated", (row.combat_date,))


def _cluster_remaining_engagements(
    engagements: list[CorrelatedEngagement],
    used: set[int],
) -> list[list[CorrelatedEngagement]]:
    clusters: list[list[CorrelatedEngagement]] = []
    cluster_keys: list[tuple[str, tuple[str, ...]]] = []

    for index, row in sorted(
        enumerate(engagements),
        key=lambda item: _stellar_ordinal(item[1].combat_date),
    ):
        if index in used or not row.publishable:
            continue
        key = _marker_cluster_key(row)
        placed = False
        for cluster_index in range(len(clusters) - 1, -1, -1):
            cluster = clusters[cluster_index]
            if cluster_keys[cluster_index] != key:
                continue
            gap = _stellar_ordinal(row.combat_date) - _stellar_ordinal(cluster[-1].combat_date)
            if 0 <= gap <= 60:
                cluster.append(row)
                placed = True
                break
        if not placed:
            clusters.append([row])
            cluster_keys.append(key)
    return clusters


def derive_combat_episodes(
    combat_snapshots: list[CombatSnapshot],
    correlated_engagements: list[CorrelatedEngagement],
    direct_episodes: list[DirectCombatEpisode],
) -> list[CombatEpisode]:
    """Build a historical combat-episode layer above raw combat evidence.

    Direct combat telemetry remains the strongest anchor. Compatible exact combat
    activity markers can extend a direct episode when they share system/fleet
    context and remain temporally continuous. Remaining markers are grouped only
    when a stable context and a short continuity window support doing so.

    The function never infers victory/defeat from retained loss counters and never
    turns ship disappearance into a confirmed loss.
    """
    episodes: list[CombatEpisode] = []
    used_engagements: set[int] = set()

    for direct in sorted(direct_episodes, key=lambda row: _stellar_ordinal(row.start_date)):
        attached = _attach_correlated_to_direct(direct, correlated_engagements, used_engagements)
        direct_dates = tuple(sorted({state.start_date for state in direct.player_fleets}, key=_stellar_ordinal))
        activity_dates = tuple(sorted({
            *direct_dates,
            *(row.combat_date for row in attached),
        }, key=_stellar_ordinal))
        systems = tuple(sorted({
            value
            for value in (
                [_clean_name(direct.system_name)]
                + [name for row in attached for name in _engagement_system_names(row)]
            )
            if value
        }))
        fleets = tuple(sorted({
            *(state.player_fleet_name for state in direct.player_fleets if state.player_fleet_name),
            *(name for row in attached for name in row.fleet_names if name),
        }))
        commanders = tuple(sorted({
            *direct.commander_names,
            *(name for row in attached for name in row.commander_names if name),
        }))
        starbases = tuple(sorted({
            name for row in attached for name in _engagement_starbase_names(row)
        }))
        possible_losses = tuple(sorted({
            loss.ship_name
            for row in attached
            for loss in row.possible_losses
            if loss.linked_to_participant_fleet
        }))
        loss_observations = _direct_loss_observations(combat_snapshots, direct)
        start = min(activity_dates, key=_stellar_ordinal) if activity_dates else direct.start_date
        end = max(activity_dates, key=_stellar_ordinal) if activity_dates else direct.start_date
        latest_observed_candidates = [direct.latest_observed_date]
        latest_observed_candidates.extend(row.first_observed_date for row in attached)
        latest_observed = max(latest_observed_candidates, key=_stellar_ordinal)

        episodes.append(CombatEpisode(
            episode_key=f"episode:{direct.episode_key}",
            start_date=start,
            end_date=end,
            latest_observed_date=latest_observed,
            evidence_kind="direct_anchored",
            confidence="high",
            system_names=systems,
            enemy_country_names=direct.enemy_country_names,
            enemy_fleet_names=direct.enemy_fleet_names,
            fleet_names=fleets,
            commander_names=commanders,
            starbase_names=starbases,
            activity_dates=activity_dates,
            direct_combat_dates=direct_dates,
            direct_record_count=len(direct.player_fleets),
            correlated_engagement_count=len(attached),
            loss_observations=loss_observations,
            formal_outcome=_formal_outcome(attached),
            possible_loss_names=possible_losses,
        ))

    for cluster_index, cluster in enumerate(
        _cluster_remaining_engagements(correlated_engagements, used_engagements),
        start=1,
    ):
        activity_dates = tuple(sorted({row.combat_date for row in cluster}, key=_stellar_ordinal))
        systems = tuple(sorted({name for row in cluster for name in _engagement_system_names(row)}))
        fleets = tuple(sorted({name for row in cluster for name in row.fleet_names if name}))
        commanders = tuple(sorted({name for row in cluster for name in row.commander_names if name}))
        starbases = tuple(sorted({name for row in cluster for name in _engagement_starbase_names(row)}))
        possible_losses = tuple(sorted({
            loss.ship_name
            for row in cluster
            for loss in row.possible_losses
            if loss.linked_to_participant_fleet
        }))
        confidence = "high" if any(row.correlation_confidence == "high" for row in cluster) else "medium"
        start = activity_dates[0]
        end = activity_dates[-1]
        episodes.append(CombatEpisode(
            episode_key=f"episode:correlated:{start}:{cluster_index}",
            start_date=start,
            end_date=end,
            latest_observed_date=max((row.first_observed_date for row in cluster), key=_stellar_ordinal),
            evidence_kind="correlated_cluster",
            confidence=confidence,
            system_names=systems,
            enemy_country_names=(),
            enemy_fleet_names=(),
            fleet_names=fleets,
            commander_names=commanders,
            starbase_names=starbases,
            activity_dates=activity_dates,
            direct_combat_dates=(),
            direct_record_count=0,
            correlated_engagement_count=len(cluster),
            loss_observations=(),
            formal_outcome=_formal_outcome(cluster),
            possible_loss_names=possible_losses,
        ))

    return sorted(episodes, key=lambda row: (_stellar_ordinal(row.start_date), row.episode_key))


def combat_episode_summary(episodes: list[CombatEpisode]) -> dict[str, int]:
    return {
        "episodes": len(episodes),
        "direct_anchored": sum(1 for row in episodes if row.evidence_kind == "direct_anchored"),
        "correlated_only": sum(1 for row in episodes if row.evidence_kind == "correlated_cluster"),
        "telemetry_evolved": sum(1 for row in episodes if row.telemetry_evolved),
        "formal_outcomes": sum(1 for row in episodes if row.formal_outcome is not None),
    }


def write_combat_episode_diagnostic(
    archive_dir: Path,
    episodes: list[CombatEpisode],
) -> Path:
    base = Path(archive_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "Combat_Episode_Debug.txt"
    summary = combat_episode_summary(episodes)
    lines = [
        "STELLARIS HISTORIAN - COMBAT EPISODE DEBUG",
        "",
        "v0.0.40.1 synthesizes historical combat episodes above raw direct telemetry and exact activity markers.",
        "Direct telemetry is tracked per combat key over time; later snapshots may update only some participating fleets.",
        "A missing participant row in a later snapshot does not erase its previously retained state; Historian carries that latest known fleet state forward in the composite episode view.",
        "Loss counters alone never establish victory or defeat. Ship disappearance remains only a possible loss unless direct evidence proves otherwise.",
        "",
        f"Combat episodes synthesized: {summary['episodes']}",
        f"Direct-anchored episodes: {summary['direct_anchored']}",
        f"Correlated-only episodes: {summary['correlated_only']}",
        f"Episodes with evolving retained telemetry: {summary['telemetry_evolved']}",
        f"Episodes with a formal recorded outcome: {summary['formal_outcomes']}",
        "",
    ]

    for episode in episodes:
        enemy = ", ".join(episode.enemy_country_names) or "Not established"
        systems = ", ".join(episode.system_names) or "Not resolved"
        lines.extend([
            f"{episode.start_date} -> {episode.end_date} | {episode.evidence_kind.upper()}",
            f"  Episode key: {episode.episode_key}",
            f"  Confidence: {episode.confidence}",
            f"  System(s): {systems}",
            f"  Opposing country/countries: {enemy}",
            f"  Opposing fleet(s): {', '.join(episode.enemy_fleet_names) or 'Not established'}",
            f"  Player fleet(s): {', '.join(episode.fleet_names) or 'Not resolved'}",
            f"  Commander(s): {', '.join(episode.commander_names) or 'Not resolved'}",
            f"  Named starbase(s): {', '.join(episode.starbase_names) or 'None resolved'}",
            f"  Direct combat date(s): {', '.join(episode.direct_combat_dates) or 'None'}",
            f"  Exact activity date(s): {', '.join(episode.activity_dates) or 'None'}",
            f"  Direct player-fleet records: {episode.direct_record_count}",
            f"  Correlated engagement markers: {episode.correlated_engagement_count}",
            f"  Formal outcome: {episode.formal_outcome or 'Not established'}",
            f"  Fleet-linked ship disappearances nearby: {', '.join(episode.possible_loss_names) or 'None'}",
        ])

        if episode.loss_observations:
            first = episode.initial_loss_observation
            latest = episode.latest_loss_observation
            lines.append("  Retained direct telemetry observations:")
            for observation in episode.loss_observations:
                completeness = "complete composite" if observation.complete else "partial composite"
                carry_text = (
                    f"; carried forward={observation.carried_forward_count}"
                    if observation.carried_forward_count
                    else ""
                )
                lines.append(
                    f"    {observation.observed_date}: player losses={observation.player_ships_lost}, "
                    f"opposing losses={observation.enemy_ships_lost}, "
                    f"snapshot records={observation.record_count}/{observation.expected_record_count}{carry_text} "
                    f"({completeness})"
                )
            if first is not None and latest is not None:
                lines.append(
                    f"  Initial complete composite state: player={first.player_ships_lost}, opposing={first.enemy_ships_lost} "
                    f"(reconstructable by {first.observed_date})"
                )
                lines.append(
                    f"  Latest complete composite state: player={latest.player_ships_lost}, opposing={latest.enemy_ships_lost} "
                    f"(reconstructable by {latest.observed_date})"
                )
                lines.append(
                    "  Telemetry evolution: "
                    + ("YES - preserve both states" if episode.telemetry_evolved else "No change in retained loss totals")
                )
        else:
            lines.append("  Retained direct telemetry observations: None")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
