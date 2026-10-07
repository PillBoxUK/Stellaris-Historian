from __future__ import annotations

from dataclasses import dataclass

from ..ships.models import ShipFleetSnapshot, ShipState
from .models import (
    BattleState,
    CombatSnapshot,
    RelationKillCounterState,
    ShipCombatActivityState,
    StarbaseCombatActivityState,
)


@dataclass(frozen=True)
class RelationCounterDelta:
    other_country_id: int
    other_country_name: str
    player_counter_before: int
    player_counter_after: int
    player_counter_delta: int
    reciprocal_counter_before: int
    reciprocal_counter_after: int
    reciprocal_counter_delta: int
    hostile: bool
    first_contact_hostility: bool


@dataclass(frozen=True)
class PossibleLoss:
    ship_id: int
    ship_name: str
    ship_type: str
    fleet_id: int | None
    fleet_name: str | None
    commander_id: int | None
    commander_name: str | None
    linked_to_participant_fleet: bool


@dataclass(frozen=True)
class CorrelatedEngagement:
    combat_date: str
    first_observed_date: str
    ship_participants: tuple[ShipCombatActivityState, ...]
    starbase_participants: tuple[StarbaseCombatActivityState, ...]
    formal_battles: tuple[BattleState, ...]
    relation_counter_deltas: tuple[RelationCounterDelta, ...]
    possible_losses: tuple[PossibleLoss, ...]
    window_start_date: str | None
    window_end_date: str | None
    mobile_ships_before: int | None
    mobile_ships_after: int | None
    queued_builds_after: int | None
    fleet_names: tuple[str, ...]
    commander_names: tuple[str, ...]
    context_system_names: tuple[str, ...]
    correlation_confidence: str
    publishable: bool

    @property
    def marker_count(self) -> int:
        return len(self.ship_participants) + len(self.starbase_participants)



def _unique_activity(
    combat_snapshots: list[CombatSnapshot],
) -> dict[str, dict[str, list[tuple[str, object]]]]:
    groups: dict[str, dict[str, list[tuple[str, object]]]] = {}
    seen_ship: set[tuple[int, str]] = set()
    seen_base: set[tuple[int, str]] = set()

    for snapshot in sorted(combat_snapshots, key=lambda row: row.game_date):
        for state in snapshot.ship_activity.values():
            key = (state.ship_id, state.last_combat_activity)
            if key in seen_ship:
                continue
            seen_ship.add(key)
            group = groups.setdefault(
                state.last_combat_activity,
                {"ships": [], "bases": []},
            )
            group["ships"].append((snapshot.game_date, state))

        for state in snapshot.starbase_activity.values():
            key = (state.starbase_id, state.last_combat_activity)
            if key in seen_base:
                continue
            seen_base.add(key)
            group = groups.setdefault(
                state.last_combat_activity,
                {"ships": [], "bases": []},
            )
            group["bases"].append((snapshot.game_date, state))

    return groups


def _window_for_date(
    date: str,
    ship_snapshots: list[ShipFleetSnapshot],
    combat_snapshots: list[CombatSnapshot],
) -> tuple[
    ShipFleetSnapshot | None,
    ShipFleetSnapshot | None,
    CombatSnapshot | None,
    CombatSnapshot | None,
]:
    if not ship_snapshots or not combat_snapshots:
        return None, None, None, None

    ordered_ship = sorted(ship_snapshots, key=lambda row: row.game_date)
    ordered_combat = sorted(combat_snapshots, key=lambda row: row.game_date)

    after_index = None
    for index, snapshot in enumerate(ordered_ship):
        if snapshot.game_date >= date:
            after_index = index
            break
    if after_index is None:
        after_index = len(ordered_ship) - 1

    before_ship = ordered_ship[after_index - 1] if after_index > 0 else None
    after_ship = ordered_ship[after_index]

    combat_by_id = {row.snapshot_id: row for row in ordered_combat}
    before_combat = (
        combat_by_id.get(before_ship.snapshot_id)
        if before_ship is not None
        else None
    )
    after_combat = combat_by_id.get(after_ship.snapshot_id)
    return before_ship, after_ship, before_combat, after_combat


def _relation_deltas(
    before: CombatSnapshot | None,
    after: CombatSnapshot | None,
) -> tuple[RelationCounterDelta, ...]:
    if after is None:
        return ()

    before_rows = before.relation_kill_counters if before else {}
    after_rows = after.relation_kill_counters
    other_ids = set(before_rows) | set(after_rows)
    result: list[RelationCounterDelta] = []

    for other_id in sorted(other_ids):
        old = before_rows.get(other_id)
        new = after_rows.get(other_id)
        old_player = old.player_relation_counter if old else 0
        old_recip = old.reciprocal_relation_counter if old else 0
        new_player = new.player_relation_counter if new else old_player
        new_recip = new.reciprocal_relation_counter if new else old_recip
        delta_player = new_player - old_player
        delta_recip = new_recip - old_recip
        if delta_player <= 0 and delta_recip <= 0:
            continue

        context: RelationKillCounterState | None = new or old
        if context is None:
            continue
        result.append(
            RelationCounterDelta(
                other_country_id=other_id,
                other_country_name=context.other_country_name,
                player_counter_before=old_player,
                player_counter_after=new_player,
                player_counter_delta=delta_player,
                reciprocal_counter_before=old_recip,
                reciprocal_counter_after=new_recip,
                reciprocal_counter_delta=delta_recip,
                hostile=context.hostile,
                first_contact_hostility=context.first_contact_hostility,
            )
        )
    return tuple(result)


def _possible_losses(
    before: ShipFleetSnapshot | None,
    after: ShipFleetSnapshot | None,
    *,
    participant_fleet_ids: set[int],
    participant_fleet_names: set[str],
) -> tuple[PossibleLoss, ...]:
    if before is None or after is None:
        return ()

    missing_ids = set(before.ships) - set(after.ships)
    result: list[PossibleLoss] = []
    for ship_id in sorted(missing_ids):
        ship: ShipState = before.ships[ship_id]
        linked = (
            (ship.fleet_id is not None and ship.fleet_id in participant_fleet_ids)
            or (ship.fleet_name is not None and ship.fleet_name in participant_fleet_names)
        )
        result.append(
            PossibleLoss(
                ship_id=ship.ship_id,
                ship_name=ship.name,
                ship_type=ship.ship_type,
                fleet_id=ship.fleet_id,
                fleet_name=ship.fleet_name,
                commander_id=ship.commander_id,
                commander_name=ship.commander_name,
                linked_to_participant_fleet=linked,
            )
        )
    return tuple(result)


def _confidence(
    *,
    ship_participants: tuple[ShipCombatActivityState, ...],
    starbase_participants: tuple[StarbaseCombatActivityState, ...],
    formal_battles: tuple[BattleState, ...],
    relation_deltas: tuple[RelationCounterDelta, ...],
) -> tuple[str, bool]:
    if formal_battles:
        return "high", True

    marker_count = len(ship_participants) + len(starbase_participants)
    fleets = {row.fleet_id for row in ship_participants if row.fleet_id is not None}
    systems = {
        row.system_id
        for row in (*ship_participants, *starbase_participants)
        if row.system_id is not None
    }

    if marker_count >= 3:
        return "high", True
    if marker_count >= 2 and (len(fleets) <= 1 or len(systems) <= 1):
        return "high", True
    if marker_count >= 2 or relation_deltas or starbase_participants:
        return "medium", True
    return "low", False


def derive_correlated_engagements(
    ship_snapshots: list[ShipFleetSnapshot],
    combat_snapshots: list[CombatSnapshot],
) -> list[CorrelatedEngagement]:
    """Correlate exact combat markers with adjacent snapshot evidence.

    The output is deliberately conservative. A disappearance inside the same
    archive window is only a *possible* loss, and relation kill counters retain
    their directional save-record labels rather than being translated into
    player kills/losses before their engine semantics are proven.
    """
    groups = _unique_activity(combat_snapshots)

    formal_by_date: dict[str, dict[str, BattleState]] = {}
    for snapshot in combat_snapshots:
        for key, battle in snapshot.battles.items():
            formal_by_date.setdefault(battle.date, {}).setdefault(key, battle)

    result: list[CorrelatedEngagement] = []
    for combat_date in sorted(groups):
        group = groups[combat_date]
        ship_items = sorted(
            group["ships"],
            key=lambda item: (item[1].fleet_name or "", item[1].ship_name, item[1].ship_id),
        )
        base_items = sorted(
            group["bases"],
            key=lambda item: (item[1].starbase_name, item[1].starbase_id),
        )
        ships = tuple(item[1] for item in ship_items)
        bases = tuple(item[1] for item in base_items)
        first_observed = min(
            [item[0] for item in ship_items] + [item[0] for item in base_items]
        )

        before_ship, after_ship, before_combat, after_combat = _window_for_date(
            combat_date,
            ship_snapshots,
            combat_snapshots,
        )

        fleet_names = tuple(sorted({row.fleet_name for row in ships if row.fleet_name}))
        fleet_ids = {row.fleet_id for row in ships if row.fleet_id is not None}
        commanders = tuple(sorted({row.commander_name for row in ships if row.commander_name}))
        systems = tuple(sorted({
            row.system_name
            for row in (*ships, *bases)
            if row.system_name
        }))
        relation_deltas = _relation_deltas(before_combat, after_combat)
        possible_losses = _possible_losses(
            before_ship,
            after_ship,
            participant_fleet_ids=fleet_ids,
            participant_fleet_names=set(fleet_names),
        )
        formal = tuple(
            formal_by_date.get(combat_date, {}).values()
        )
        confidence, publishable = _confidence(
            ship_participants=ships,
            starbase_participants=bases,
            formal_battles=formal,
            relation_deltas=relation_deltas,
        )

        result.append(
            CorrelatedEngagement(
                combat_date=combat_date,
                first_observed_date=first_observed,
                ship_participants=ships,
                starbase_participants=bases,
                formal_battles=formal,
                relation_counter_deltas=relation_deltas,
                possible_losses=possible_losses,
                window_start_date=before_ship.game_date if before_ship else None,
                window_end_date=after_ship.game_date if after_ship else None,
                mobile_ships_before=len(before_ship.ships) if before_ship else None,
                mobile_ships_after=len(after_ship.ships) if after_ship else None,
                queued_builds_after=len(after_ship.build_orders) if after_ship else None,
                fleet_names=fleet_names,
                commander_names=commanders,
                context_system_names=systems,
                correlation_confidence=confidence,
                publishable=publishable,
            )
        )

    return result


def correlation_summary(events: list[CorrelatedEngagement]) -> dict[str, int]:
    return {
        "candidate_engagements": len(events),
        "publishable_engagements": sum(1 for row in events if row.publishable),
        "high_confidence": sum(1 for row in events if row.correlation_confidence == "high"),
        "medium_confidence": sum(1 for row in events if row.correlation_confidence == "medium"),
        "low_confidence": sum(1 for row in events if row.correlation_confidence == "low"),
        "with_relation_deltas": sum(1 for row in events if row.relation_counter_deltas),
        "with_possible_losses": sum(1 for row in events if row.possible_losses),
        "with_fleet_linked_possible_losses": sum(
            1 for row in events if any(loss.linked_to_participant_fleet for loss in row.possible_losses)
        ),
    }


@dataclass(frozen=True)
class DirectCombatEpisode:
    episode_key: str
    start_date: str
    latest_observed_date: str
    player_fleets: tuple[object, ...]
    system_id: int | None
    system_name: str | None
    enemy_country_ids: tuple[int, ...]
    enemy_country_names: tuple[str, ...]
    enemy_fleet_ids: tuple[int, ...]
    enemy_fleet_names: tuple[str, ...]
    commander_names: tuple[str, ...]
    player_ships_lost: int
    enemy_ships_lost: int
    direct_evidence: bool = True


def _stellar_ordinal(value: str) -> int:
    try:
        year, month, day = (int(part) for part in value.split(".")[:3])
        return year * 360 + (month - 1) * 30 + day
    except (ValueError, AttributeError):
        return 0


def derive_direct_combat_episodes(
    combat_snapshots: list[CombatSnapshot],
) -> list[DirectCombatEpisode]:
    """Reconstruct direct fleet combat episodes from retained combat_stats.

    Multiple player fleets can join the same enemy fleet a few days apart. If
    the enemy fleet/country and system are identical and their combat starts are
    within 15 in-game days, Historian treats those records as one episode. This
    is stronger than marker correlation because the save itself names both
    sides and keeps aggregate fleet loss counters.
    """
    observations: list[tuple[str, object]] = []
    for snapshot in sorted(combat_snapshots, key=lambda row: row.game_date):
        for state in snapshot.fleet_combat_stats.values():
            observations.append((snapshot.game_date, state))

    # First collapse repeated observations of the same player-fleet combat key,
    # keeping the latest/highest-loss state from the surviving telemetry.
    by_key: dict[str, tuple[str, object]] = {}
    for observed_date, state in observations:
        previous = by_key.get(state.combat_key)
        if previous is None or observed_date >= previous[0]:
            by_key[state.combat_key] = (observed_date, state)

    rows = sorted(
        by_key.values(),
        key=lambda item: (
            _stellar_ordinal(item[1].start_date),
            item[1].system_id if item[1].system_id is not None else -1,
            item[1].player_fleet_id,
        ),
    )

    clusters: list[list[tuple[str, object]]] = []
    for item in rows:
        observed_date, state = item
        enemy_country_ids = tuple(sorted({
            enemy.country_id for enemy in state.enemy_fleets
            if enemy.country_id is not None
        }))
        enemy_fleet_ids = tuple(sorted({
            enemy.fleet_id for enemy in state.enemy_fleets
            if enemy.fleet_id is not None
        }))
        placed = False
        for cluster in reversed(clusters):
            anchor = cluster[0][1]
            anchor_countries = tuple(sorted({
                enemy.country_id for enemy in anchor.enemy_fleets
                if enemy.country_id is not None
            }))
            anchor_fleets = tuple(sorted({
                enemy.fleet_id for enemy in anchor.enemy_fleets
                if enemy.fleet_id is not None
            }))
            if (
                anchor.system_id == state.system_id
                and anchor_countries == enemy_country_ids
                and anchor_fleets == enemy_fleet_ids
                and abs(_stellar_ordinal(anchor.start_date) - _stellar_ordinal(state.start_date)) <= 15
            ):
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    result: list[DirectCombatEpisode] = []
    for index, cluster in enumerate(clusters, start=1):
        states = [item[1] for item in cluster]
        dates = [state.start_date for state in states]
        latest_observed = max(item[0] for item in cluster)
        system_id = next((state.system_id for state in states if state.system_id is not None), None)
        system_name = next((state.system_name for state in states if state.system_name), None)
        enemy_country_ids = tuple(sorted({
            enemy.country_id for state in states for enemy in state.enemy_fleets
            if enemy.country_id is not None
        }))
        enemy_country_names = tuple(sorted({
            enemy.country_name for state in states for enemy in state.enemy_fleets
            if enemy.country_name
        }))
        enemy_fleet_ids = tuple(sorted({
            enemy.fleet_id for state in states for enemy in state.enemy_fleets
            if enemy.fleet_id is not None
        }))
        enemy_fleet_names = tuple(sorted({
            enemy.fleet_name for state in states for enemy in state.enemy_fleets
            if enemy.fleet_name
        }))
        commanders = tuple(sorted({
            state.commander_name for state in states if state.commander_name
        }))

        # Player loss counts are per distinct player fleet, so summing the latest
        # record for each fleet is safe. Enemy loss counters may be duplicated in
        # several participating fleet records; take the maximum per enemy fleet.
        latest_by_player_fleet: dict[int, object] = {}
        for state in states:
            latest_by_player_fleet[state.player_fleet_id] = state
        player_losses = sum(
            int(state.player_ships_lost or 0)
            for state in latest_by_player_fleet.values()
        )

        enemy_losses_by_fleet: dict[int | None, int] = {}
        for state in states:
            for enemy in state.enemy_fleets:
                key = enemy.fleet_id
                enemy_losses_by_fleet[key] = max(
                    enemy_losses_by_fleet.get(key, 0),
                    int(enemy.ships_lost or 0),
                )
        enemy_losses = sum(enemy_losses_by_fleet.values())

        start = min(dates, key=_stellar_ordinal)
        episode_key = (
            f"direct:{start}:{system_id if system_id is not None else '-'}:"
            + ",".join(map(str, enemy_country_ids or enemy_fleet_ids or (index,)))
        )
        result.append(DirectCombatEpisode(
            episode_key=episode_key,
            start_date=start,
            latest_observed_date=latest_observed,
            player_fleets=tuple(sorted(states, key=lambda row: (row.start_date, row.player_fleet_name))),
            system_id=system_id,
            system_name=system_name,
            enemy_country_ids=enemy_country_ids,
            enemy_country_names=enemy_country_names,
            enemy_fleet_ids=enemy_fleet_ids,
            enemy_fleet_names=enemy_fleet_names,
            commander_names=commanders,
            player_ships_lost=player_losses,
            enemy_ships_lost=enemy_losses,
        ))

    return sorted(result, key=lambda row: (_stellar_ordinal(row.start_date), row.episode_key))
