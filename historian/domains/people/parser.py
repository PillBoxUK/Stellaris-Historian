from __future__ import annotations

from pathlib import Path
import re

from ...localisation import resolve_localisation_key
from ...save_reader import EmpireProfile
from ..worlds.parser import world_location_display_name
from ...core.stellaris_text import (
    _extract_braced_after,
    _find_named_block,
    _id_list_from_block,
    _int_scalar,
    _numeric_record,
    _record_name,
    _scalar,
    _top_numeric_records,
)
from ..ships.models import ShipFleetSnapshot
from .models import DeadLeaderState, LeaderSnapshot, LeaderState

def _float_scalar(
    text: str | None,
    key: str,
) -> float | None:
    value = _scalar(
        text,
        key,
    )

    if value is None:
        return None

    try:
        return float(
            value
        )
    except ValueError:
        return None


def _clean_date(
    value: str | None,
) -> str | None:
    if not value or value == "0.01.01":
        return None

    return value


def _find_top_level_block(text: str | None, key: str) -> str | None:
    if not text:
        return None

    depth = 0
    in_quote = False
    escaped = False
    offset = 0

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.strip()
        if depth == 0 and re.match(rf'{re.escape(key)}\s*=', line):
            return _extract_braced_after(text, offset)

        for char in raw_line:
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
            elif char == '{':
                depth += 1
            elif char == '}':
                depth = max(0, depth - 1)
        offset += len(raw_line)

    return None


def _top_level_pairs(text: str | None) -> tuple[tuple[str, str], ...]:
    """Return scalar key/value pairs that occur at depth zero in a block.

    This is deliberately generic so new Stellaris leader fields can be
    surfaced in diagnostics before Historian knows how to interpret them.
    """
    if not text:
        return ()

    result: list[tuple[str, str]] = []
    depth = 0
    in_quote = False
    escaped = False

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if depth == 0 and line:
            match = re.match(
                r'([A-Za-z0-9_.:-]+)\s*=\s*(?:"([^"]*)"|([^\s{}]+))\s*$',
                line,
            )
            if match:
                result.append((match.group(1), match.group(2) or match.group(3) or ""))

        # Update nesting depth quote-safely after inspecting the current line.
        for char in raw_line:
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
            elif char == '{':
                depth += 1
            elif char == '}':
                depth = max(0, depth - 1)

    return tuple(result)


def _top_level_keys(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()

    keys: list[str] = []
    depth = 0
    in_quote = False
    escaped = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if depth == 0:
            match = re.match(r'([A-Za-z0-9_.:-]+)\s*=', line)
            if match:
                keys.append(match.group(1))

        for char in raw_line:
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
            elif char == '{':
                depth += 1
            elif char == '}':
                depth = max(0, depth - 1)

    return tuple(dict.fromkeys(keys))


def _species_name(
    gamestate: str,
    species_id: int | None,
    source_save: Path,
) -> str | None:
    if species_id is None:
        return None

    species_block = _find_named_block(gamestate, "species_db")
    record = _numeric_record(species_block, species_id)
    if not record:
        return None

    return _record_name(record, source_save, fallback=f"Species {species_id}")


def _background_planet_name(
    gamestate: str,
    planet_id: int | None,
    source_save: Path,
) -> str | None:
    if planet_id is None or planet_id == 4294967295:
        return None
    return _planet_name(gamestate, planet_id, source_save)


def _dead_leader_states(
    gamestate: str,
    country_id: int,
    source_save: Path,
) -> tuple[dict[int, DeadLeaderState], tuple[str, ...]]:
    block = _find_named_block(gamestate, "dead_leader")
    result: dict[int, DeadLeaderState] = {}
    all_keys: set[str] = set()

    # Paradox versions/mods can retain either full leader records or nothing at
    # all in dead_leader. Parse conservatively and only promote player records.
    for leader_id, record in _top_numeric_records(block):
        record_country = _int_scalar(record, "country")
        if record_country is not None and record_country != country_id:
            continue

        raw_keys = _top_level_keys(record)
        all_keys.update(raw_keys)

        death_date = None
        death_date_key = None
        for key in ("death_date", "date_of_death", "killed_date", "died_date"):
            value = _clean_date(_scalar(record, key))
            if value:
                death_date = value
                death_date_key = key
                break

        death_reason_key = None
        death_reason_value = None
        for key in (
            "death_reason", "death_cause", "cause_of_death", "died_reason",
            "dismiss_reason", "retirement_reason", "execution_reason",
            "killed_by", "killer", "reason",
        ):
            value = _scalar(record, key)
            if value:
                death_reason_key = key
                death_reason_value = value
                break

        leader_class = _scalar(record, "class")
        name = _record_name(record, source_save, fallback=f"Leader {leader_id}")

        result[leader_id] = DeadLeaderState(
            leader_id=leader_id,
            name=name,
            leader_class=leader_class,
            country_id=record_country,
            death_date=death_date,
            death_date_key=death_date_key,
            death_reason_key=death_reason_key,
            death_reason_value=death_reason_value,
            raw_keys=raw_keys,
        )

    return result, tuple(sorted(all_keys))


def _humanise_key(
    value: str | None,
) -> str | None:
    if not value:
        return None

    prefixes = (
        "leader_trait_",
        "trait_ruler_",
        "trait_",
        "councilor_",
        "leader_",
        "ethic_",
        "leader_tier_",
        "job_",
    )

    cleaned = value

    for prefix in prefixes:
        if cleaned.startswith(
            prefix
        ):
            cleaned = cleaned[
                len(prefix):
            ]
            break

    cleaned = cleaned.replace(
        "_",
        " ",
    ).strip()

    return (
        cleaned.title()
        if cleaned
        else value
    )


def _localised_or_humanised(
    source_save: Path,
    key: str | None,
) -> str | None:
    if not key:
        return None

    resolved = resolve_localisation_key(
        source_save,
        key,
    )

    return (
        resolved
        or _humanise_key(
            key
        )
    )


def _player_country_record(
    gamestate: str,
    country_id: int,
) -> str | None:
    countries = _find_named_block(
        gamestate,
        "country",
    )

    return _numeric_record(
        countries,
        country_id,
    )


def _council_roles(
    gamestate: str,
    country_id: int,
    source_save: Path,
) -> dict[int, tuple[str, str]]:
    outer = _find_named_block(
        gamestate,
        "council_positions",
    )

    positions = _find_named_block(
        outer or "",
        "council_positions",
    )

    result: dict[
        int,
        tuple[str, str],
    ] = {}

    for _, record in _top_numeric_records(
        positions
    ):
        if _int_scalar(
            record,
            "country",
        ) != country_id:
            continue

        leader_id = _int_scalar(
            record,
            "leader",
        )

        role_key = _scalar(
            record,
            "type",
        )

        if (
            leader_id is None
            or not role_key
        ):
            continue

        role_name = (
            _localised_or_humanised(
                source_save,
                role_key,
            )
            or role_key
        )

        result[
            leader_id
        ] = (
            role_key,
            role_name,
        )

    return result


def _planet_name(
    gamestate: str,
    planet_id: int,
    source_save: Path,
) -> str | None:
    return world_location_display_name(
        gamestate,
        planet_id,
        source_save,
    )


def _same_display_name(
    left: str | None,
    right: str | None,
) -> bool:
    if not left or not right:
        return False

    def normalise(value: str) -> str:
        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip().casefold()

    return normalise(left) == normalise(right)


def _assignment_name(
    *,
    leader_name: str,
    leader_class: str,
    location_type: str | None,
    location_id: int | None,
    assignment_key: str | None,
    gamestate: str,
    source_save: Path,
    ship_snapshot: ShipFleetSnapshot,
) -> str | None:
    if (
        location_type == "ship"
        and location_id is not None
    ):
        ship = ship_snapshot.ships.get(
            location_id
        )

        if ship is not None:
            if (
                leader_class == "commander"
                and ship.fleet_name
            ):
                # Stellaris can temporarily expose a commander assignment
                # through a fleet-like object whose display name is merely the
                # leader's own name. That is not evidence that the commander
                # literally commanded a fleet named after themselves. Keep the
                # raw location ID in the snapshot, but leave the public
                # assignment unresolved until a real fleet name is available.
                if _same_display_name(
                    ship.fleet_name,
                    leader_name,
                ):
                    return None

                return (
                    f"Fleet: {ship.fleet_name}"
                )

            return (
                f"{ship.ship_type}: {ship.name}"
            )

        return f"Ship {location_id}"

    if (
        location_type == "fleet"
        and location_id is not None
    ):
        fleet = ship_snapshot.fleets.get(
            location_id
        )

        if fleet is not None:
            if (
                leader_class in {
                    "commander",
                    "admiral",
                    "general",
                }
                and _same_display_name(
                    fleet.name,
                    leader_name,
                )
            ):
                return None

            return f"Fleet: {fleet.name}"

        return f"Fleet {location_id}"

    if (
        location_type == "planet"
        and location_id is not None
    ):
        name = _planet_name(
            gamestate,
            location_id,
            source_save,
        )

        return f"Planet: {name or location_id}"

    if location_type == "first_contact_system":
        return "First Contact Assignment"

    if assignment_key and assignment_key not in {
        "none",
        "unassigned",
    }:
        return (
            _localised_or_humanised(
                source_save,
                assignment_key,
            )
            or _humanise_key(
                assignment_key
            )
        )

    if location_type and location_type not in {
        "none",
    }:
        label = _humanise_key(
            location_type
        ) or location_type

        if location_id is not None:
            return f"{label} {location_id}"

        return label

    return None


def _saved_leader_event_targets(gamestate: str) -> dict[int, tuple[str, ...]]:
    names: dict[int, set[str]] = {}
    pattern = re.compile(r'(?m)^\s*saved_event_target\s*=\s*\{')
    for match in pattern.finditer(gamestate):
        block = _extract_braced_after(gamestate, match.start())
        if not block or _scalar(block, "type") != "leader":
            continue
        leader_id = _int_scalar(block, "id")
        if leader_id is None or leader_id == 4294967295:
            continue
        name = _scalar(block, "name")
        if name:
            names.setdefault(leader_id, set()).add(name)

    return {
        leader_id: tuple(sorted(values))
        for leader_id, values in names.items()
    }


def extract_leader_snapshot(
    *,
    gamestate: str,
    profile: EmpireProfile,
    source_save: Path,
    snapshot_id: int,
    ship_snapshot: ShipFleetSnapshot,
) -> LeaderSnapshot:
    country_id = profile.player_country_id

    if country_id is None:
        raise ValueError(
            "Could not determine the player country ID for leader parsing."
        )

    country = _player_country_record(
        gamestate,
        country_id,
    )

    if not country:
        return LeaderSnapshot(
            snapshot_id=snapshot_id,
            game_date=profile.game_date,
            leaders={},
        )

    owned_leader_ids = set(
        _id_list_from_block(
            country,
            "owned_leaders",
        )
    )

    ruler_id = _int_scalar(
        country,
        "ruler",
    )

    heir_id = _int_scalar(
        country,
        "heir",
    )

    leaders_block = _find_named_block(
        gamestate,
        "leaders",
    )

    tombstoned_leader_ids = tuple(sorted(
        int(value)
        for value in re.findall(
            r'(?m)^\s*(\d+)\s*=\s*none\s*$',
            leaders_block or "",
        )
    ))
    saved_event_target_names = _saved_leader_event_targets(gamestate)

    council_roles = _council_roles(
        gamestate,
        country_id,
        source_save,
    )

    dead_leaders, dead_record_keys = _dead_leader_states(
        gamestate,
        country_id,
        source_save,
    )

    active_record_keys: set[str] = set()
    active_flag_keys: set[str] = set()
    active_variable_keys: set[str] = set()

    result: dict[
        int,
        LeaderState,
    ] = {}

    for leader_id in sorted(
        owned_leader_ids
    ):
        record = _numeric_record(
            leaders_block,
            leader_id,
        )

        if not record:
            continue

        record_country = _int_scalar(
            record,
            "country",
        )

        if (
            record_country is not None
            and record_country != country_id
        ):
            continue

        name = _record_name(
            record,
            source_save,
            fallback=f"Leader {leader_id}",
        )

        leader_class = (
            _scalar(
                record,
                "class",
            )
            or "unknown"
        )

        traits = tuple(
            re.findall(
                r'(?m)^\s*traits\s*=\s*"([^"]+)"',
                record,
            )
        )

        trait_names = tuple(
            (
                _localised_or_humanised(
                    source_save,
                    trait,
                )
                or trait
            )
            for trait in traits
        )

        location = _find_top_level_block(
            record,
            "location",
        )

        location_type = _scalar(
            location,
            "type",
        )

        location_id = _int_scalar(
            location,
            "id",
        )

        assignment_key = _scalar(
            location,
            "assignment",
        )

        council = council_roles.get(
            leader_id
        )

        council_role_key = (
            council[0]
            if council
            else None
        )

        council_role_name = (
            council[1]
            if council
            else None
        )

        raw_keys = _top_level_keys(record)
        active_record_keys.update(raw_keys)

        flag_values = _top_level_pairs(_find_top_level_block(record, "flags"))
        variable_values = _top_level_pairs(_find_top_level_block(record, "variables"))
        active_flag_keys.update(key for key, _ in flag_values)
        active_variable_keys.update(key for key, _ in variable_values)

        species_id = _int_scalar(record, "species")
        tier_key = _scalar(record, "tier")
        ethic_key = _scalar(record, "ethic")
        job_key = _scalar(record, "job")
        background_planet = _find_top_level_block(record, "background_planet")
        background_planet_id = _int_scalar(background_planet, "reference")
        custom_description_key = _scalar(record, "custom_description")

        result[
            leader_id
        ] = LeaderState(
            leader_id=leader_id,
            name=name,
            leader_class=leader_class,
            level=_int_scalar(
                record,
                "level",
            ),
            experience=_float_scalar(
                record,
                "experience",
            ),
            recruitment_date=_clean_date(
                _scalar(
                    record,
                    "recruitment_date",
                )
            ),
            gender=_scalar(
                record,
                "gender",
            ),
            traits=traits,
            trait_names=trait_names,
            location_type=location_type,
            location_id=location_id,
            assignment_key=assignment_key,
            assignment_name=_assignment_name(
                leader_name=name,
                leader_class=leader_class,
                location_type=location_type,
                location_id=location_id,
                assignment_key=assignment_key,
                gamestate=gamestate,
                source_save=source_save,
                ship_snapshot=ship_snapshot,
            ),
            council_role_key=council_role_key,
            council_role_name=council_role_name,
            is_ruler=(
                ruler_id == leader_id
            ),
            is_heir=(
                heir_id == leader_id
            ),
            species_id=species_id,
            species_name=_species_name(gamestate, species_id, source_save),
            portrait=_scalar(record, "portrait"),
            creator_country_id=_int_scalar(record, "creator"),
            tier_key=tier_key,
            tier_name=_localised_or_humanised(source_save, tier_key),
            recorded_date=_clean_date(_scalar(record, "date")),
            date_added=_clean_date(_scalar(record, "date_added")),
            raw_age=_int_scalar(record, "age"),
            ethic_key=ethic_key,
            ethic_name=_localised_or_humanised(source_save, ethic_key),
            job_key=job_key,
            job_name=_localised_or_humanised(source_save, job_key),
            background_planet_id=(
                None if background_planet_id == 4294967295 else background_planet_id
            ),
            background_planet_name=_background_planet_name(
                gamestate, background_planet_id, source_save
            ),
            custom_description_key=custom_description_key,
            custom_description_name=_localised_or_humanised(
                source_save, custom_description_key
            ),
            bonus_skill_level=_int_scalar(record, "bonus_skill_level"),
            raw_keys=raw_keys,
            flag_values=flag_values,
            variable_values=variable_values,
        )

    event_selection = _find_named_block(gamestate, "open_player_event_selection_history")
    selected_player_event_count = len(
        re.findall(r'(?m)^\s*player_event\s*=\s*\d+', event_selection or "")
    )

    return LeaderSnapshot(
        snapshot_id=snapshot_id,
        game_date=profile.game_date,
        leaders=result,
        dead_leaders=dead_leaders,
        active_record_keys=tuple(sorted(active_record_keys)),
        active_flag_keys=tuple(sorted(active_flag_keys)),
        active_variable_keys=tuple(sorted(active_variable_keys)),
        dead_record_keys=dead_record_keys,
        last_notification_id=_int_scalar(gamestate, "last_notification_id"),
        last_event_id=_int_scalar(gamestate, "last_event_id"),
        selected_player_event_count=selected_player_event_count,
        tombstoned_leader_ids=tombstoned_leader_ids,
        saved_event_target_names=saved_event_target_names,
    )


