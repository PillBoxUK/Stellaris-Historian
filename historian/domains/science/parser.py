from __future__ import annotations

from pathlib import Path
import re

from ...localisation import resolve_localisation_key
from ...save_reader import EmpireProfile
from ...core.stellaris_text import (
    _extract_braced_after,
    _find_named_block,
    _id_list_from_block,
    _int_scalar,
    _numeric_record,
    _scalar,
    _top_numeric_records,
)
from ..ships.models import ShipFleetSnapshot
from ..people.models import LeaderSnapshot
from ..worlds.parser import world_location_display_name
from .models import (
    ArchaeologySiteState,
    ScienceSnapshot,
    SituationState,
    SpecialProjectState,
)


_INVALID_ID = 4294967295


def _quoted_scalar(text: str | None, key: str) -> str | None:
    if not text:
        return None
    match = re.search(
        rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]*)"',
        text,
    )
    return match.group(1) if match else None


def _float_scalar(text: str | None, key: str) -> float | None:
    value = _scalar(text, key)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _humanise_key(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = value
    for prefix in (
        "site_",
        "situation_",
        "special_project_",
        "project_",
        "approach_",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break

    cleaned = cleaned.replace("_", " ").strip()
    return cleaned.title() if cleaned else value


def _localised_or_humanised(source_save: Path, key: str | None) -> str | None:
    if not key:
        return None
    return resolve_localisation_key(source_save, key) or _humanise_key(key)


def _player_country_record(gamestate: str, country_id: int) -> str | None:
    countries = _find_named_block(gamestate, "country")
    return _numeric_record(countries, country_id)


def _repeated_named_blocks(text: str | None, key: str):
    if not text:
        return

    pattern = re.compile(rf'(?m)^\s*{re.escape(key)}\s*=\s*\{{')
    position = 0
    while True:
        match = pattern.search(text, position)
        if not match:
            break
        block = _extract_braced_after(text, match.start())
        if block is None:
            break
        yield block

        brace = text.find("{", match.start())
        depth = 0
        in_quote = False
        escaped = False
        end = None
        for index in range(brace, len(text)):
            char = text[index]
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
                    end = index + 1
                    break
        if end is None:
            break
        position = end


def _completion_dates(record: str, player_country_id: int) -> tuple[str, ...]:
    completed = _find_named_block(record, "completed")
    if not completed:
        return ()

    dates: list[str] = []
    entry_pattern = re.compile(r'\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.S)
    # Most completion entries are flat. Fall back to a bounded country/date
    # scan if nested syntax defeats the simple entry expression.
    for match in entry_pattern.finditer(completed):
        entry = match.group(1)
        if _int_scalar(entry, "country") != player_country_id:
            continue
        date = _scalar(entry, "date")
        if date and date not in dates:
            dates.append(date)

    if dates:
        return tuple(dates)

    for match in re.finditer(
        rf'country\s*=\s*{player_country_id}\b(?:(?!country\s*=).)*?date\s*=\s*"([^"]+)"',
        completed,
        re.S,
    ):
        date = match.group(1)
        if date not in dates:
            dates.append(date)

    return tuple(dates)


def _scope_target(record: str, target_type: str) -> int | None:
    scope = _find_named_block(record, "scope")
    if not scope:
        return None
    match = re.search(
        rf'(?s)\btype\s*=\s*{re.escape(target_type)}\s*\n\s*id\s*=\s*(\d+)',
        scope,
    )
    return int(match.group(1)) if match else None


def extract_science_snapshot(
    *,
    gamestate: str,
    profile: EmpireProfile,
    source_save: Path,
    snapshot_id: int,
    ship_snapshot: ShipFleetSnapshot,
    leader_snapshot: LeaderSnapshot,
) -> ScienceSnapshot:
    country_id = profile.player_country_id
    if country_id is None:
        raise ValueError("Could not determine the player country ID for science parsing.")

    leader_names = {
        leader_id: leader.name
        for leader_id, leader in leader_snapshot.leaders.items()
    }

    archaeology_sites: dict[int, ArchaeologySiteState] = {}
    site_block = _find_named_block(gamestate, "archaeological_sites")

    for site_id, record in _top_numeric_records(site_block):
        type_key = _quoted_scalar(record, "type")
        if not type_key:
            continue

        location = _find_named_block(record, "location")
        planet_id = _int_scalar(location, "id") if location else None
        visible_ids = set(_id_list_from_block(record, "visible_to"))
        last_excavator_country = _int_scalar(record, "last_excavator_country")
        excavator_fleet_id = _int_scalar(record, "excavator_fleet")
        completion_dates = _completion_dates(record, country_id)

        fleet = None
        if excavator_fleet_id is not None and excavator_fleet_id != _INVALID_ID:
            fleet = ship_snapshot.fleets.get(excavator_fleet_id)

        player_related = (
            country_id in visible_ids
            or last_excavator_country == country_id
            or bool(completion_dates)
            or fleet is not None
        )
        if not player_related:
            continue

        scientist_id = fleet.commander_id if fleet is not None else None
        scientist_name = (
            fleet.commander_name
            if fleet is not None and fleet.commander_name
            else leader_names.get(scientist_id) if scientist_id is not None else None
        )

        archaeology_sites[site_id] = ArchaeologySiteState(
            site_id=site_id,
            type_key=type_key,
            title=_localised_or_humanised(source_save, type_key) or type_key,
            planet_id=planet_id,
            location_name=(
                world_location_display_name(gamestate, planet_id, source_save)
                if planet_id is not None
                else None
            ),
            visible_to_player=country_id in visible_ids,
            last_excavator_country=(
                None if last_excavator_country == _INVALID_ID else last_excavator_country
            ),
            excavator_fleet_id=(
                None if excavator_fleet_id == _INVALID_ID else excavator_fleet_id
            ),
            excavator_fleet_name=fleet.name if fleet is not None else None,
            scientist_id=scientist_id,
            scientist_name=scientist_name,
            chapter_index=_int_scalar(record, "index"),
            clues=_int_scalar(record, "clues"),
            difficulty=_int_scalar(record, "difficulty"),
            days_left=_int_scalar(record, "days_left"),
            player_completion_dates=completion_dates,
        )

    country = _player_country_record(gamestate, country_id) or ""

    special_projects: dict[int, SpecialProjectState] = {}
    for record in _repeated_named_blocks(country, "special_project"):
        project_id = _int_scalar(record, "id")
        project_key = _scalar(record, "special_project")
        if project_id is None or not project_key:
            continue

        planet_id = _int_scalar(record, "planet")
        linked_ship_id = _scope_target(record, "ship")
        ship = ship_snapshot.ships.get(linked_ship_id) if linked_ship_id is not None else None
        scientist_id = ship.commander_id if ship is not None else None
        scientist_name = (
            ship.commander_name
            if ship is not None and ship.commander_name
            else leader_names.get(scientist_id) if scientist_id is not None else None
        )

        special_projects[project_id] = SpecialProjectState(
            project_id=project_id,
            project_key=project_key,
            title=_localised_or_humanised(source_save, project_key) or project_key,
            planet_id=planet_id,
            location_name=(
                world_location_display_name(gamestate, planet_id, source_save)
                if planet_id is not None
                else None
            ),
            linked_ship_id=linked_ship_id,
            linked_ship_name=ship.name if ship is not None else None,
            scientist_id=scientist_id,
            scientist_name=scientist_name,
            ai_research_date=_scalar(record, "ai_research_date"),
        )

    situations: dict[int, SituationState] = {}
    situation_block = _find_named_block(gamestate, "situations")
    for situation_id, record in _top_numeric_records(situation_block):
        if _int_scalar(record, "country") != country_id:
            continue
        type_key = _quoted_scalar(record, "type")
        if not type_key:
            continue
        target = _find_named_block(record, "target")
        situations[situation_id] = SituationState(
            situation_id=situation_id,
            type_key=type_key,
            title=_localised_or_humanised(source_save, type_key) or type_key,
            progress=_float_scalar(record, "progress"),
            last_month_progress=_float_scalar(record, "last_month_progress"),
            approach_key=_scalar(record, "approach"),
            target_type=_scalar(target, "type") if target else None,
            target_id=_int_scalar(target, "id") if target else None,
        )

    anomaly_ids = _id_list_from_block(country, "anomalies")

    return ScienceSnapshot(
        snapshot_id=snapshot_id,
        game_date=profile.game_date,
        player_country_id=country_id,
        archaeology_sites=archaeology_sites,
        special_projects=special_projects,
        situations=situations,
        anomaly_ids=anomaly_ids,
    )
