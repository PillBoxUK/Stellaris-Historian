from __future__ import annotations

from pathlib import Path
import re

from ...core.stellaris_text import (
    _extract_braced_after,
    _find_named_block,
    _humanise_key,
    _id_list_from_block,
    _int_scalar,
    _numeric_record,
    _record_name,
    _scalar,
    _top_numeric_records,
)
from ...save_reader import EmpireProfile
from ..ships.models import ShipFleetSnapshot
from ..ships.parser import extract_ship_fleet_snapshot
from .models import (
    BattleState,
    CombatSnapshot,
    EnemyFleetCombatState,
    FleetCombatStatsState,
    RelationKillCounterState,
    ShipCombatActivityState,
    StarbaseCombatActivityState,
    WarState,
)


INVALID_OBJECT_ID = 4294967295
_TOP_NUMERIC_RECORD_START = re.compile(r'(?m)^\t(\d+)=\s*\n\t\{')


def _find_top_level_block_fast(text: str, key: str) -> str | None:
    """Fast path for a top-level Stellaris `key=\n{...}` block.

    Top-level closing braces are unindented, while nested braces are indented.
    Fall back to the general brace parser when the expected save formatting is
    not present.
    """
    markers = (f"\n{key}=\n{{\n", f"{key}=\n{{\n")
    for marker in markers:
        pos = text.find(marker)
        if pos < 0:
            continue
        start = pos + len(marker)
        if text.startswith("}\n", start) or text.startswith("}\r\n", start):
            return ""
        end = text.find("\n}\n", start)
        if end >= 0:
            return text[start:end]
    return _find_named_block(text, key)


def _float_scalar(text: str | None, key: str) -> float | None:
    value = _scalar(text, key)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _yes_no(text: str | None, key: str) -> bool | None:
    value = _scalar(text, key)
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def _anonymous_blocks(block: str | None) -> tuple[str, ...]:
    """Return top-level anonymous { ... } records from a Stellaris list block."""
    if not block:
        return ()

    result: list[str] = []
    index = 0
    length = len(block)

    while index < length:
        while index < length and block[index].isspace():
            index += 1

        if index >= length:
            break

        if block[index] != "{":
            index += 1
            continue

        inner = _extract_braced_after(block, index)
        if inner is None:
            break

        result.append(inner)

        depth = 0
        in_quote = False
        escaped = False
        end = None
        for pos in range(index, length):
            char = block[pos]
            if in_quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_quote = False
                continue
            if char == '"':
                in_quote = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = pos + 1
                    break

        if end is None:
            break
        index = end

    return tuple(result)


def _country_ids(record: str | None, key: str) -> tuple[int, ...]:
    block = _find_named_block(record or "", key)
    if not block:
        return ()

    values = [
        int(value)
        for value in re.findall(
            r'\bcountry\s*=\s*(\d+)',
            block,
        )
    ]
    return tuple(dict.fromkeys(values))


def _clean_object_id(value: int | None) -> int | None:
    if value is None or value == INVALID_OBJECT_ID:
        return None
    return value


def _display_name_for_numeric_object(
    gamestate: str,
    block_name: str,
    object_id: int | None,
    source_save: Path,
    fallback: str,
) -> str | None:
    object_id = _clean_object_id(object_id)
    if object_id is None:
        return None

    block = _find_named_block(gamestate, block_name)
    record = _numeric_record(block, object_id)
    if not record:
        return fallback

    name = _record_name(record, source_save, fallback=fallback).strip()
    if not name or "%" in name or "$" in name:
        return fallback
    return name


def _goal_name(record: str, key: str) -> str | None:
    block = _find_named_block(record, key)
    raw = _scalar(block, "type")
    if not raw:
        return None
    if raw.startswith("wg_"):
        raw = raw[3:]
    return _humanise_key(raw)


def _war_name(record: str, war_id: int, source_save: Path) -> str:
    value = _record_name(record, source_save, fallback=f"War {war_id}").strip()
    if not value or "%" in value or "$" in value:
        return f"War {war_id}"
    return value


def _battle_key(
    war_id: int,
    index: int,
    date: str,
    system_id: int | None,
    planet_id: int | None,
    battle_type: str,
) -> str:
    return (
        f"{war_id}:{index}:{date}:"
        f"{system_id if system_id is not None else '-'}:"
        f"{planet_id if planet_id is not None else '-'}:{battle_type}"
    )


def _parse_battles(
    *,
    record: str,
    war_id: int,
    player_country_id: int,
    gamestate: str,
    source_save: Path,
) -> tuple[BattleState, ...]:
    battles_block = _find_named_block(record, "battles")
    result: list[BattleState] = []

    for index, battle in enumerate(_anonymous_blocks(battles_block), start=1):
        attackers = _id_list_from_block(battle, "attackers")
        defenders = _id_list_from_block(battle, "defenders")

        if player_country_id in attackers:
            player_side = "attacker"
        elif player_country_id in defenders:
            player_side = "defender"
        else:
            # A war can contain allied battles in which the player did not
            # directly participate. Preserve only direct player battle evidence.
            continue

        date = _scalar(battle, "date")
        if not date or date.startswith("0."):
            continue
        battle_type = _scalar(battle, "type") or "unknown"
        system_id = _clean_object_id(_int_scalar(battle, "system"))
        planet_id = _clean_object_id(_int_scalar(battle, "planet"))
        attacker_victory = _yes_no(battle, "attacker_victory")
        attacker_losses = _int_scalar(battle, "attacker_losses")
        defender_losses = _int_scalar(battle, "defender_losses")

        if player_side == "attacker":
            player_victory = attacker_victory
            player_losses = attacker_losses
            enemy_losses = defender_losses
        else:
            player_victory = (
                None if attacker_victory is None else not attacker_victory
            )
            player_losses = defender_losses
            enemy_losses = attacker_losses

        result.append(
            BattleState(
                battle_key=_battle_key(
                    war_id,
                    index,
                    date,
                    system_id,
                    planet_id,
                    battle_type,
                ),
                war_id=war_id,
                battle_index=index,
                date=date,
                battle_type=battle_type,
                system_id=system_id,
                system_name=_display_name_for_numeric_object(
                    gamestate,
                    "galactic_object",
                    system_id,
                    source_save,
                    fallback=f"System {system_id}" if system_id is not None else "Unknown System",
                ),
                planet_id=planet_id,
                planet_name=_display_name_for_numeric_object(
                    gamestate,
                    "planets",
                    planet_id,
                    source_save,
                    fallback=f"Planet {planet_id}" if planet_id is not None else "Unknown Planet",
                ),
                attacker_country_ids=attackers,
                defender_country_ids=defenders,
                attacker_victory=attacker_victory,
                attacker_losses=attacker_losses,
                defender_losses=defender_losses,
                player_side=player_side,
                player_victory=player_victory,
                player_losses=player_losses,
                enemy_losses=enemy_losses,
            )
        )

    return tuple(result)


def _player_owned_fleet_ids(gamestate: str, country_id: int) -> set[int]:
    countries = _find_top_level_block_fast(gamestate, "country")
    country = _top_numeric_record_map_fast(countries, {country_id}).get(country_id)
    if not country:
        return set()

    manager = (
        _find_named_block(country, "fleets_manager")
        or _find_named_block(country, "fleet_manager")
    )
    owned = _find_named_block(manager or "", "owned_fleets")
    if not owned:
        return set()

    return {
        int(value)
        for value in re.findall(
            r'(?m)^\s*fleet\s*=\s*(\d+)',
            owned,
        )
    }


def _combat_activity_date(record: str | None) -> str | None:
    value = _scalar(record, "last_combat_activity")
    if not value or value.startswith("0."):
        return None
    return value


def _system_id_from_ship_record(record: str | None) -> int | None:
    coordinate = _find_named_block(record or "", "coordinate")
    return _clean_object_id(_int_scalar(coordinate, "origin"))


def _top_numeric_record_map_fast(
    block: str | None,
    wanted_ids: set[int],
) -> dict[int, str]:
    """Return selected top-level numeric records without brace-walking every record.

    Stellaris' numeric manager blocks use one leading tab for their top-level
    records after `_find_named_block` removes the outer braces. Nested numeric
    records are more deeply indented, so this gives us a cheap index into large
    blocks such as `ships` and `galactic_object`.
    """
    if not block or not wanted_ids:
        return {}

    result: dict[int, str] = {}
    pending_id: int | None = None
    pending_start: int | None = None

    for match in _TOP_NUMERIC_RECORD_START.finditer(block):
        if pending_id is not None and pending_start is not None:
            result[pending_id] = block[pending_start:match.start()]
            if len(result) == len(wanted_ids):
                return result
            pending_id = None
            pending_start = None

        object_id = int(match.group(1))
        if object_id in wanted_ids:
            pending_id = object_id
            pending_start = match.end()

    if pending_id is not None and pending_start is not None:
        result[pending_id] = block[pending_start:]

    return result


def _system_names(
    gamestate: str,
    system_ids: set[int],
    source_save: Path,
) -> dict[int, str]:
    if not system_ids:
        return {}

    galactic_objects = _find_top_level_block_fast(gamestate, "galactic_object")
    records = _top_numeric_record_map_fast(galactic_objects, system_ids)
    result: dict[int, str] = {}
    for system_id, record in records.items():
        fallback = f"System {system_id}"
        name = _record_name(record, source_save, fallback=fallback).strip()
        if not name or "%" in name or "$" in name:
            name = fallback
        result[system_id] = name
    return result


def _activity_records(
    *,
    gamestate: str,
    player_country_id: int,
    ship_snapshot: ShipFleetSnapshot,
) -> tuple[dict[int, str], dict[int, tuple[int, str]]]:
    """Return wanted mobile ship records and player-owned starbase station records.

    The large `ships` block is scanned once. Starbase ownership is established by
    checking the station ship's current fleet against the player's owned_fleets
    list, rather than relying on original_owner.
    """
    mobile_ids = set(ship_snapshot.ships)
    owned_fleet_ids = _player_owned_fleet_ids(gamestate, player_country_id)

    manager = _find_top_level_block_fast(gamestate, "starbase_mgr")
    starbases = _find_named_block(manager or "", "starbases")
    station_to_starbase: dict[int, int] = {}
    for starbase_id, starbase_record in _top_numeric_records(starbases):
        station_ship_id = _clean_object_id(_int_scalar(starbase_record, "station"))
        if station_ship_id is not None:
            station_to_starbase[station_ship_id] = starbase_id

    wanted_ids = mobile_ids | set(station_to_starbase)
    mobile_records: dict[int, str] = {}
    player_starbase_records: dict[int, tuple[int, str]] = {}

    ships_block = _find_top_level_block_fast(gamestate, "ships")
    selected_records = _top_numeric_record_map_fast(ships_block, wanted_ids)
    for ship_id, record in selected_records.items():
        if ship_id in mobile_ids:
            mobile_records[ship_id] = record

        starbase_id = station_to_starbase.get(ship_id)
        if starbase_id is not None:
            fleet_id = _clean_object_id(_int_scalar(record, "fleet"))
            if fleet_id is not None and fleet_id in owned_fleet_ids:
                player_starbase_records[starbase_id] = (ship_id, record)

    return mobile_records, player_starbase_records


def _parse_activity_markers(
    *,
    gamestate: str,
    player_country_id: int,
    source_save: Path,
    ship_snapshot: ShipFleetSnapshot,
) -> tuple[
    dict[int, ShipCombatActivityState],
    dict[int, StarbaseCombatActivityState],
]:
    mobile_records, starbase_records = _activity_records(
        gamestate=gamestate,
        player_country_id=player_country_id,
        ship_snapshot=ship_snapshot,
    )

    ship_raw: list[tuple[int, object, str, int | None]] = []
    starbase_raw: list[tuple[int, int, str, str, int | None]] = []
    wanted_system_ids: set[int] = set()

    for ship_id, ship in ship_snapshot.ships.items():
        record = mobile_records.get(ship_id)
        combat_date = _combat_activity_date(record)
        if combat_date is None:
            continue
        system_id = _system_id_from_ship_record(record)
        if system_id is not None:
            wanted_system_ids.add(system_id)
        ship_raw.append((ship_id, ship, combat_date, system_id))

    for starbase_id, (station_ship_id, record) in starbase_records.items():
        combat_date = _combat_activity_date(record)
        if combat_date is None:
            continue
        system_id = _system_id_from_ship_record(record)
        if system_id is not None:
            wanted_system_ids.add(system_id)
        raw_name = _record_name(
            record,
            source_save,
            fallback=f"Starbase {starbase_id}",
        ).strip()
        starbase_raw.append(
            (starbase_id, station_ship_id, raw_name, combat_date, system_id)
        )

    system_names = _system_names(gamestate, wanted_system_ids, source_save)

    ship_activity: dict[int, ShipCombatActivityState] = {}
    for ship_id, ship, combat_date, system_id in ship_raw:
        ship_activity[ship_id] = ShipCombatActivityState(
            ship_id=ship_id,
            ship_name=ship.name,
            ship_type=ship.ship_type,
            last_combat_activity=combat_date,
            fleet_id=ship.fleet_id,
            fleet_name=ship.fleet_name,
            commander_id=ship.commander_id,
            commander_name=ship.commander_name,
            system_id=system_id,
            system_name=(
                system_names.get(system_id)
                if system_id is not None
                else None
            ),
        )

    starbase_activity: dict[int, StarbaseCombatActivityState] = {}
    for starbase_id, station_ship_id, raw_name, combat_date, system_id in starbase_raw:
        system_name = system_names.get(system_id) if system_id is not None else None
        name = raw_name
        if (
            not name
            or "%" in name
            or "$" in name
            or name.upper().startswith("STARBASE STATION NAME FORMAT")
        ):
            name = (
                f"{system_name} Starbase"
                if system_name
                else f"Starbase {starbase_id}"
            )
        starbase_activity[starbase_id] = StarbaseCombatActivityState(
            starbase_id=starbase_id,
            starbase_name=name,
            station_ship_id=station_ship_id,
            last_combat_activity=combat_date,
            system_id=system_id,
            system_name=system_name,
        )

    return ship_activity, starbase_activity


def _named_blocks(text: str | None, key: str) -> tuple[str, ...]:
    """Return every repeated named block at any indentation level in text.

    Stellaris relation managers contain many repeated `relation={...}` blocks,
    so `_find_named_block` is not sufficient there. The brace parser keeps this
    robust around nested modifier and pre-communications structures.
    """
    if not text:
        return ()
    pattern = re.compile(r"(?m)^\s*" + re.escape(key) + r"\s*=\s*\n\s*\{")
    result: list[str] = []
    for match in pattern.finditer(text):
        brace = text.find("{", match.start(), match.end() + 2)
        if brace < 0:
            continue
        inner = _extract_braced_after(text, brace)
        if inner is not None:
            result.append(inner)
    return tuple(result)


def _country_display_name(record: str | None, country_id: int) -> str:
    name_block = _find_named_block(record or "", "name")
    raw = _scalar(name_block, "key") if name_block else None
    if raw:
        for prefix in ("NAME_", "SPEC_"):
            if raw.startswith(prefix):
                raw = raw[len(prefix):]
                break
        raw = raw.replace("_", " ").strip()
        if raw and "%" not in raw and "$" not in raw:
            return raw
    return f"Country {country_id}"



def _sum_int_block(record: str | None, key: str) -> int | None:
    block = _find_named_block(record or "", key)
    if block is None:
        return None
    values = [int(value) for value in re.findall(r"-?\d+", block)]
    return sum(values) if values else 0


def _clean_scalar_name(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip('"')
    if not value or "%" in value or "$" in value:
        return None
    return value


def _parse_fleet_combat_stats(
    *,
    gamestate: str,
    player_country_id: int,
    ship_snapshot: ShipFleetSnapshot,
    source_save: Path,
) -> dict[str, FleetCombatStatsState]:
    """Extract direct player-fleet combat telemetry retained by Stellaris.

    Fleet `combat` / `fleet_stats.combat_stats` blocks are much stronger than
    post-hoc activity markers: they can preserve the exact combat start date,
    player fleet name, commander, enemy fleet/country identity and aggregate
    ship-loss counts while the combat telemetry is still present.
    """
    fleet_ids = set(ship_snapshot.fleets)
    if not fleet_ids:
        return {}

    fleets_block = _find_top_level_block_fast(gamestate, "fleet")
    records = _top_numeric_record_map_fast(fleets_block, fleet_ids)
    raw: list[tuple[int, str, str | None, str, int | None, int | None, tuple[EnemyFleetCombatState, ...], int | None]] = []
    wanted_system_ids: set[int] = set()

    for fleet_id, fleet in ship_snapshot.fleets.items():
        record = records.get(fleet_id)
        if not record:
            continue
        combat = _find_named_block(record, "combat")
        stats = _find_named_block(_find_named_block(record, "fleet_stats") or "", "combat_stats")
        own = _find_named_block(stats or "", "fleet")
        if not stats or not own:
            continue

        stat_fleet_id = _clean_object_id(_int_scalar(own, "fleet"))
        stat_country_id = _clean_object_id(_int_scalar(own, "country"))
        date = _scalar(stats, "date") or _scalar(combat, "start_date")
        if (
            stat_fleet_id is None
            or stat_country_id != player_country_id
            or not date
            or date.startswith("0.")
        ):
            continue

        direct_name = _clean_scalar_name(_scalar(own, "fleet_name"))
        fleet_name = direct_name or fleet.name
        leader = _find_named_block(own, "leader")
        commander_name = _clean_scalar_name(_scalar(leader, "name"))

        coordinate = _find_named_block(combat or "", "coordinate")
        system_id = _clean_object_id(_int_scalar(coordinate, "origin"))
        if system_id is not None:
            wanted_system_ids.add(system_id)

        enemies: list[EnemyFleetCombatState] = []
        enemy_block = _find_named_block(stats, "enemy")
        for enemy in _anonymous_blocks(enemy_block):
            enemy_fleet_id = _clean_object_id(_int_scalar(enemy, "fleet"))
            enemy_country_id = _clean_object_id(_int_scalar(enemy, "country"))
            country_name = _clean_scalar_name(_scalar(enemy, "country_name"))
            enemy_fleet_name = _clean_scalar_name(_scalar(enemy, "fleet_name"))
            enemies.append(
                EnemyFleetCombatState(
                    fleet_id=enemy_fleet_id,
                    country_id=enemy_country_id,
                    country_name=country_name,
                    fleet_name=enemy_fleet_name,
                    ship_count=_sum_int_block(enemy, "ship_size_count"),
                    ships_lost=_sum_int_block(enemy, "ship_size_count_lost"),
                )
            )

        if not enemies:
            # Empty/cleared combat_stats blocks remain in some fleets after the
            # battle. They are not active direct combat evidence on their own.
            continue

        raw.append((
            fleet_id,
            fleet_name,
            commander_name,
            date,
            system_id,
            _sum_int_block(own, "ship_size_count"),
            tuple(enemies),
            _sum_int_block(own, "ship_size_count_lost"),
        ))

    system_names = _system_names(gamestate, wanted_system_ids, source_save) if wanted_system_ids else {}
    result: dict[str, FleetCombatStatsState] = {}
    for (
        fleet_id, fleet_name, commander_name, date, system_id, player_ship_count,
        enemies, player_ships_lost
    ) in raw:
        key = f"{fleet_id}:{date}"
        result[key] = FleetCombatStatsState(
            combat_key=key,
            player_fleet_id=fleet_id,
            player_fleet_name=fleet_name,
            commander_name=commander_name,
            start_date=date,
            system_id=system_id,
            system_name=system_names.get(system_id) if system_id is not None else None,
            player_ship_count=player_ship_count,
            player_ships_lost=player_ships_lost,
            enemy_fleets=enemies,
        )
    return result

def _relation_block_around_counter(gamestate: str, position: int) -> str | None:
    """Return the relation block containing a killed_ships scalar.

    Only a handful of killed_ships fields normally exist in a save. Searching
    backwards from those fields is dramatically cheaper than parsing every
    diplomatic relation in every country record.
    """
    search_start = max(0, position - 12000)
    prefix = gamestate[search_start:position]
    matches = list(re.finditer(r"(?m)^\s*relation\s*=\s*\n\s*\{", prefix))
    if not matches:
        return None
    match = matches[-1]
    absolute_start = search_start + match.start()
    brace = gamestate.find("{", absolute_start, position)
    if brace < 0:
        return None
    return _extract_braced_after(gamestate, brace)


def _relation_kill_counters(
    *,
    gamestate: str,
    player_country_id: int,
) -> dict[int, RelationKillCounterState]:
    counters: dict[int, dict[str, int]] = {}

    for match in re.finditer(r"(?m)^\s*killed_ships\s*=\s*(\d+)", gamestate):
        relation = _relation_block_around_counter(gamestate, match.start())
        if not relation:
            continue
        owner = _int_scalar(relation, "owner")
        country = _int_scalar(relation, "country")
        value = int(match.group(1))
        if owner == player_country_id and country is not None:
            counters.setdefault(country, {"player": 0, "reciprocal": 0})["player"] = value
        elif country == player_country_id and owner is not None:
            counters.setdefault(owner, {"player": 0, "reciprocal": 0})["reciprocal"] = value

    if not counters:
        return {}

    countries = _find_top_level_block_fast(gamestate, "country")
    other_ids = set(counters)
    other_records = _top_numeric_record_map_fast(countries, other_ids)

    player_record = _top_numeric_record_map_fast(
        countries, {player_country_id}
    ).get(player_country_id)
    manager = _find_named_block(player_record or "", "relations_manager")
    context: dict[int, tuple[bool, bool, bool | None]] = {}
    for relation in _named_blocks(manager, "relation"):
        if _int_scalar(relation, "owner") != player_country_id:
            continue
        other = _int_scalar(relation, "country")
        if other not in other_ids:
            continue
        context[other] = (
            _yes_no(relation, "hostile") is True,
            "opinion_first_contact_war" in relation,
            _yes_no(relation, "communications"),
        )

    result: dict[int, RelationKillCounterState] = {}
    for other_id in sorted(other_ids):
        values = counters[other_id]
        hostile, first_contact, communications = context.get(
            other_id, (False, False, None)
        )
        result[other_id] = RelationKillCounterState(
            other_country_id=other_id,
            other_country_name=_country_display_name(
                other_records.get(other_id), other_id
            ),
            player_relation_counter=values["player"],
            reciprocal_relation_counter=values["reciprocal"],
            hostile=hostile,
            first_contact_hostility=first_contact,
            communications=communications,
        )
    return result

def extract_combat_snapshot(
    *,
    gamestate: str,
    profile: EmpireProfile,
    source_save: Path,
    snapshot_id: int,
    ship_snapshot: ShipFleetSnapshot | None = None,
) -> CombatSnapshot:
    if profile.player_country_id is None:
        raise ValueError("Could not determine the player country ID.")

    if ship_snapshot is None:
        ship_snapshot = extract_ship_fleet_snapshot(
            source_save,
            source_save=source_save,
            snapshot_id=snapshot_id,
            profile=profile,
            gamestate=gamestate,
        )

    wars_block = _find_top_level_block_fast(gamestate, "war")
    wars: dict[int, WarState] = {}
    battles: dict[str, BattleState] = {}

    for war_id, record in _top_numeric_records(wars_block):
        attackers = _country_ids(record, "attackers")
        defenders = _country_ids(record, "defenders")

        if profile.player_country_id in attackers:
            player_side = "attacker"
        elif profile.player_country_id in defenders:
            player_side = "defender"
        else:
            continue

        war_battles = _parse_battles(
            record=record,
            war_id=war_id,
            player_country_id=profile.player_country_id,
            gamestate=gamestate,
            source_save=source_save,
        )

        state = WarState(
            war_id=war_id,
            name=_war_name(record, war_id, source_save),
            start_date=_scalar(record, "start_date"),
            player_side=player_side,
            attacker_country_ids=attackers,
            defender_country_ids=defenders,
            attacker_war_goal=_goal_name(record, "attacker_war_goal"),
            defender_war_goal=_goal_name(record, "defender_war_goal"),
            attacker_war_exhaustion=_float_scalar(record, "attacker_war_exhaustion"),
            defender_war_exhaustion=_float_scalar(record, "defender_war_exhaustion"),
            battles=war_battles,
        )
        wars[war_id] = state
        for battle in war_battles:
            battles[battle.battle_key] = battle

    fleet_combat_stats = _parse_fleet_combat_stats(
        gamestate=gamestate,
        player_country_id=profile.player_country_id,
        ship_snapshot=ship_snapshot,
        source_save=source_save,
    )

    relation_kill_counters = _relation_kill_counters(
        gamestate=gamestate,
        player_country_id=profile.player_country_id,
    )

    ship_activity, starbase_activity = _parse_activity_markers(
        gamestate=gamestate,
        player_country_id=profile.player_country_id,
        source_save=source_save,
        ship_snapshot=ship_snapshot,
    )

    return CombatSnapshot(
        snapshot_id=snapshot_id,
        game_date=profile.game_date,
        player_country_id=profile.player_country_id,
        wars=wars,
        battles=battles,
        ship_activity=ship_activity,
        starbase_activity=starbase_activity,
        fleet_combat_stats=fleet_combat_stats,
        relation_kill_counters=relation_kill_counters,
    )
