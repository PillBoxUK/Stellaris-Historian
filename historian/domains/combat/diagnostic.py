from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .models import (
    BattleState,
    CombatSnapshot,
    ShipCombatActivityState,
    StarbaseCombatActivityState,
    WarState,
)


def _date_key(value: str) -> tuple[int, int, int]:
    try:
        year, month, day = value.split(".")[:3]
        return int(year), int(month), int(day)
    except (ValueError, AttributeError):
        return (999999, 99, 99)


def _fmt_losses(value: int | None) -> str:
    return "Unknown" if value is None else str(value)


def _ship_activity_evidence(
    snapshots: list[CombatSnapshot],
) -> list[tuple[str, ShipCombatActivityState]]:
    seen: set[tuple[int, str]] = set()
    result: list[tuple[str, ShipCombatActivityState]] = []

    for snapshot in snapshots:
        for ship_id, state in snapshot.ship_activity.items():
            key = (ship_id, state.last_combat_activity)
            if key in seen:
                continue
            seen.add(key)
            result.append((snapshot.game_date, state))

    return result


def _starbase_activity_evidence(
    snapshots: list[CombatSnapshot],
) -> list[tuple[str, StarbaseCombatActivityState]]:
    seen: set[tuple[int, str]] = set()
    result: list[tuple[str, StarbaseCombatActivityState]] = []

    for snapshot in snapshots:
        for starbase_id, state in snapshot.starbase_activity.items():
            key = (starbase_id, state.last_combat_activity)
            if key in seen:
                continue
            seen.add(key)
            result.append((snapshot.game_date, state))

    return result


def combat_evidence_summary(snapshots: list[CombatSnapshot]) -> dict[str, int]:
    war_ids: set[int] = set()
    battle_keys: set[str] = set()
    victories = 0
    defeats = 0

    seen_result: set[str] = set()
    for snapshot in snapshots:
        war_ids.update(snapshot.wars)
        for key, battle in snapshot.battles.items():
            battle_keys.add(key)
            if key in seen_result:
                continue
            seen_result.add(key)
            if battle.player_victory is True:
                victories += 1
            elif battle.player_victory is False:
                defeats += 1

    ship_evidence = _ship_activity_evidence(snapshots)
    starbase_evidence = _starbase_activity_evidence(snapshots)

    relation_counterparts = {
        other_id
        for snapshot in snapshots
        for other_id in snapshot.relation_kill_counters
    }
    relation_counter_snapshots = sum(
        1 for snapshot in snapshots if snapshot.relation_kill_counters
    )
    direct_fleet_combat_keys = {
        key
        for snapshot in snapshots
        for key in snapshot.fleet_combat_stats
    }
    direct_fleet_combat_snapshots = sum(
        1 for snapshot in snapshots if snapshot.fleet_combat_stats
    )
    direct_opponent_country_ids = {
        enemy.country_id
        for snapshot in snapshots
        for state in snapshot.fleet_combat_stats.values()
        for enemy in state.enemy_fleets
        if enemy.country_id is not None
    }

    return {
        "wars": len(war_ids),
        "battles": len(battle_keys),
        "victories": victories,
        "defeats": defeats,
        "ship_activity_markers": len(ship_evidence),
        "starbase_activity_markers": len(starbase_evidence),
        "ships_with_activity": len({state.ship_id for _, state in ship_evidence}),
        "starbases_with_activity": len(
            {state.starbase_id for _, state in starbase_evidence}
        ),
        "relation_counterparts": len(relation_counterparts),
        "relation_counter_snapshots": relation_counter_snapshots,
        "direct_fleet_combat_records": len(direct_fleet_combat_keys),
        "direct_fleet_combat_snapshots": direct_fleet_combat_snapshots,
        "direct_opponent_countries": len(direct_opponent_country_ids),
    }


def write_combat_diagnostic(
    archive_dir: Path,
    snapshots: list[CombatSnapshot],
) -> Path:
    archive_dir = Path(archive_dir)
    path = archive_dir / "Combat_Evidence_Debug.txt"

    summary = combat_evidence_summary(snapshots)
    latest_game_date = snapshots[-1].game_date if snapshots else "Unknown"

    war_observations: dict[int, list[tuple[str, WarState]]] = defaultdict(list)
    battle_by_key: dict[str, BattleState] = {}

    for snapshot in snapshots:
        for war_id, war in snapshot.wars.items():
            war_observations[war_id].append((snapshot.game_date, war))
        for key, battle in snapshot.battles.items():
            battle_by_key.setdefault(key, battle)

    ship_evidence = _ship_activity_evidence(snapshots)
    starbase_evidence = _starbase_activity_evidence(snapshots)

    lines = [
        "STELLARIS HISTORIAN - COMBAT EVIDENCE DEBUG",
        "",
        "This diagnostic is evidence-first. It does not infer that a disappeared ship was destroyed.",
        "Formal war/battle records and exact last_combat_activity markers are separate evidence sources.",
        "A last_combat_activity value proves that Stellaris retained an exact combat-activity date for that entity; by itself it does not identify the opponent, outcome or losses.",
        "Fleet, commander and system shown for an activity marker are the values in the first archived snapshot where Historian observed that marker. They are context, not proof that those values were unchanged at the exact combat moment.",
        "",
        f"Snapshots analysed: {len(snapshots)}",
        f"Latest snapshot: {latest_game_date}",
        f"Player-related formal war episodes observed: {summary['wars']}",
        f"Unique direct player formal battle records: {summary['battles']}",
        f"Recorded formal-battle victories: {summary['victories']}",
        f"Recorded formal-battle defeats: {summary['defeats']}",
        f"Unique ship combat-activity markers: {summary['ship_activity_markers']} across {summary['ships_with_activity']} ship(s)",
        f"Unique starbase combat-activity markers: {summary['starbase_activity_markers']} across {summary['starbases_with_activity']} starbase(s)",
        f"Relation kill-counter counterparts observed: {summary['relation_counterparts']} across {summary['relation_counter_snapshots']} snapshot(s)",
        f"Direct player fleet-combat telemetry records: {summary['direct_fleet_combat_records']} across {summary['direct_fleet_combat_snapshots']} snapshot(s)",
        f"Distinct opposing country IDs named by direct fleet-combat telemetry: {summary['direct_opponent_countries']}",
        "",
        "DIRECT FLEET-COMBAT TELEMETRY",
        "=============================",
    ]

    direct_seen: set[str] = set()
    for snapshot in snapshots:
        for key, state in sorted(snapshot.fleet_combat_stats.items()):
            if key in direct_seen:
                continue
            direct_seen.add(key)
            enemies = []
            for enemy in state.enemy_fleets:
                country = enemy.country_name or (f"Country {enemy.country_id}" if enemy.country_id is not None else "Unknown country")
                fleet = enemy.fleet_name or (f"Fleet {enemy.fleet_id}" if enemy.fleet_id is not None else "Unknown fleet")
                enemy_loss = enemy.ships_lost if enemy.ships_lost is not None else 0
                enemies.append(f"{country} / {fleet} (ships {enemy.ship_count if enemy.ship_count is not None else 'unknown'}; losses {enemy_loss})")
            lines.extend([
                "",
                f"{state.start_date} - {state.player_fleet_name}",
                "  Evidence: direct fleet combat_stats retained in player fleet record",
                f"  First archive observation in this diagnostic: {snapshot.game_date}",
                f"  Player fleet ID: {state.player_fleet_id}",
                f"  Commander: {state.commander_name or 'None recorded'}",
                f"  System: {state.system_name or 'Not resolved'}" + (f" (ID {state.system_id})" if state.system_id is not None else ""),
                f"  Player fleet ship count: {state.player_ship_count if state.player_ship_count is not None else 'Not recorded'}",
                f"  Player fleet ships lost in retained stats: {state.player_ships_lost if state.player_ships_lost is not None else 'Not recorded'}",
                "  Opposing force(s): " + ("; ".join(enemies) if enemies else "Not resolved"),
                "  Confidence: HIGH for the direct telemetry fields above; no victory/defeat is inferred from loss counts alone",
            ])

    if not direct_seen:
        lines.append("No direct player fleet combat_stats records were preserved in the analysed snapshots.")

    lines.extend([
        "",
        "SHIP COMBAT-ACTIVITY MARKERS",
        "============================",
    ])

    if not ship_evidence:
        lines.append("No player mobile-ship last_combat_activity markers were preserved in the analysed snapshots.")
    else:
        for first_observed, state in sorted(
            ship_evidence,
            key=lambda item: (
                _date_key(item[1].last_combat_activity),
                item[1].ship_id,
                _date_key(item[0]),
            ),
        ):
            lines.extend([
                "",
                f"{state.last_combat_activity} - {state.ship_name}",
                f"  Evidence: ship last_combat_activity exact save field",
                f"  Ship ID: {state.ship_id}",
                f"  Type: {state.ship_type}",
                f"  First archive observation of this marker: {first_observed}",
                f"  Fleet at first observation: {state.fleet_name or 'Not recorded'}"
                + (f" (ID {state.fleet_id})" if state.fleet_id is not None else ""),
                f"  Commander at first observation: {state.commander_name or 'None recorded'}"
                + (f" (ID {state.commander_id})" if state.commander_id is not None else ""),
                f"  System at first observation: {state.system_name or 'Not resolved'}"
                + (f" (ID {state.system_id})" if state.system_id is not None else ""),
                "  Confidence: HIGH for exact combat date; contextual fields are snapshot observations",
            ])

    lines.extend(["", "STARBASE COMBAT-ACTIVITY MARKERS", "================================"])

    if not starbase_evidence:
        lines.append("No player starbase last_combat_activity markers were preserved in the analysed snapshots.")
    else:
        for first_observed, state in sorted(
            starbase_evidence,
            key=lambda item: (
                _date_key(item[1].last_combat_activity),
                item[1].starbase_id,
                _date_key(item[0]),
            ),
        ):
            lines.extend([
                "",
                f"{state.last_combat_activity} - {state.starbase_name}",
                f"  Evidence: starbase station last_combat_activity exact save field",
                f"  Starbase ID: {state.starbase_id}",
                f"  Station ship ID at first observation: {state.station_ship_id}",
                f"  First archive observation of this marker: {first_observed}",
                f"  System at first observation: {state.system_name or 'Not resolved'}"
                + (f" (ID {state.system_id})" if state.system_id is not None else ""),
                "  Confidence: HIGH for exact combat date; system is first-observed snapshot context",
            ])

    lines.extend(["", "RELATION KILL-COUNTER EVIDENCE", "=============================="])

    relation_seen: dict[int, list[tuple[str, object]]] = defaultdict(list)
    for snapshot in snapshots:
        for other_id, state in snapshot.relation_kill_counters.items():
            relation_seen[other_id].append((snapshot.game_date, state))

    if not relation_seen:
        lines.append("No player-related killed_ships relation counters were preserved in the analysed snapshots.")
    else:
        for other_id, observations in sorted(relation_seen.items(), key=lambda item: item[0]):
            first_date, first = observations[0]
            last_date, last = observations[-1]
            lines.extend([
                "",
                f"{last.other_country_name} (country ID {other_id})",
                f"  First observed relation-counter state: {first_date}",
                f"  Latest observed relation-counter state: {last_date}",
                f"  Player-side relation record: {first.player_relation_counter} -> {last.player_relation_counter}",
                f"  Reciprocal relation record: {first.reciprocal_relation_counter} -> {last.reciprocal_relation_counter}",
                f"  Hostile in latest observed state: {'YES' if last.hostile else 'NO'}",
                f"  First-contact hostility marker seen: {'YES' if any(state.first_contact_hostility for _, state in observations) else 'NO'}",
                "  Semantics: directional counters are preserved verbatim; v0.0.38 does not label either direction as kills inflicted or ships lost.",
            ])

    lines.extend(["", "FORMAL WAR EPISODES", "==================="])

    if not war_observations:
        lines.append("No player-related formal war episode was preserved in the analysed snapshots.")
    else:
        for war_id, observations in sorted(
            war_observations.items(), key=lambda item: _date_key(item[1][0][0])
        ):
            first_date, first = observations[0]
            last_date, last = observations[-1]
            active_latest = last_date == latest_game_date
            battle_keys = {
                battle.battle_key
                for _, war in observations
                for battle in war.battles
            }
            lines.extend([
                "",
                f"War {war_id}: {last.name}",
                f"  Player side: {last.player_side}",
                f"  Recorded war start: {first.start_date or 'Not recorded'}",
                f"  First archive observation: {first_date}",
                f"  Last archive observation: {last_date}",
                f"  Status: {'Active in latest snapshot' if active_latest else 'No longer observed'}",
                f"  Attacker war goal: {last.attacker_war_goal or 'Not recorded'}",
                f"  Defender war goal: {last.defender_war_goal or 'Not recorded'}",
                f"  Direct player battles retained: {len(battle_keys)}",
            ])

    lines.extend(["", "DIRECT PLAYER FORMAL BATTLES", "============================"])

    if not battle_by_key:
        lines.append("No direct player formal battle records were preserved in the analysed snapshots.")
    else:
        for battle in sorted(
            battle_by_key.values(),
            key=lambda item: (_date_key(item.date), item.war_id, item.battle_index),
        ):
            result = (
                "Victory" if battle.player_victory is True
                else "Defeat" if battle.player_victory is False
                else "Result not recorded"
            )
            location = battle.system_name or battle.planet_name or "Location not resolved"
            if battle.planet_name and battle.system_name:
                location = f"{battle.planet_name} / {battle.system_name}"
            lines.extend([
                "",
                f"{battle.date} - {result}",
                f"  War ID: {battle.war_id}",
                f"  Type: {battle.battle_type}",
                f"  Player side: {battle.player_side}",
                f"  Location: {location}",
                f"  Player losses: {_fmt_losses(battle.player_losses)}",
                f"  Opposing losses: {_fmt_losses(battle.enemy_losses)}",
                f"  Attacker countries: {', '.join(map(str, battle.attacker_country_ids)) or 'None recorded'}",
                f"  Defender countries: {', '.join(map(str, battle.defender_country_ids)) or 'None recorded'}",
            ])

    lines.extend([
        "",
        "INTERPRETATION RULES",
        "====================",
        "- Ship disappearance alone is NOT destruction evidence.",
        "- Fleet disappearance alone is NOT destruction evidence.",
        "- last_combat_activity is exact date evidence for combat activity, but does NOT by itself establish opponent, result, losses or battle location.",
        "- Fleet/commander/system attached to a combat marker are first-observed snapshot context unless stronger evidence later proves they apply to the combat moment.",
        "- A formal war battle loss count is aggregate evidence; it does not identify which named ships were lost.",
        "- Exact named ship losses will only be published later when loss windows can be safely correlated with direct combat evidence.",
        "- Combat against non-war entities can be represented by activity markers even when no formal war or war-battle object survives.",
        "- Relation killed_ships counters are directional evidence. v0.0.38 intentionally leaves their kill/loss semantics unresolved until independently proven.",
        "- Combat correlation may group same-date evidence, but it must preserve uncertainty about opponent, location, outcome and losses unless direct evidence exists.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
