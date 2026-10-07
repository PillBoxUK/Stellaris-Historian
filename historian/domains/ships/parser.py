from __future__ import annotations

from pathlib import Path
import re

from ...save_reader import EmpireProfile, empire_profile_from_text, read_save_texts
from ...core.stellaris_text import (
    _find_named_block,
    _humanise_key,
    _id_list_from_block,
    _int_scalar,
    _numeric_record,
    _record_name,
    _scalar,
    _top_numeric_records,
)
from .models import BuildOrderState, FleetState, ShipFleetSnapshot, ShipState, ShipyardState


STATIC_FLEET_CLASSES = {
    "shipclass_starbase",
    "shipclass_mining_station",
    "shipclass_research_station",
    "shipclass_observation_station",
    "shipclass_orbital_station",
}

STATIC_SHIP_SIZES = {
    "mining_station",
    "research_station",
    "observation_station",
    "orbital_station",
}


_UNRESOLVED_TOKEN = re.compile(
    r"%(?:[A-Za-z0-9_]+)%|\$(?:[A-Za-z0-9_.-]+)\$"
)


def _contains_unresolved_token(value: str | None) -> bool:
    if not value:
        return False

    return bool(
        _UNRESOLVED_TOKEN.search(
            value
        )
    )


def _clean_display_name(
    value: str | None,
    *,
    fallback: str,
) -> str:
    if not value:
        return fallback

    cleaned = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    if not cleaned:
        return fallback

    if _contains_unresolved_token(
        cleaned
    ):
        return fallback

    return cleaned


def _fallback_fleet_name(
    ship_class: str | None,
) -> str:
    mapping = {
        "shipclass_military": "Unnamed Military Fleet",
        "shipclass_science_ship": "Unnamed Science Vessel",
        "shipclass_constructor": "Unnamed Construction Vessel",
        "shipclass_colonizer": "Unnamed Colony Vessel",
        "shipclass_transport": "Unnamed Transport Fleet",
    }

    return mapping.get(
        ship_class,
        "Unnamed Fleet",
    )


def _ship_type_name(
    ship_size: str | None,
    fleet_class: str | None,
) -> str:
    mapping = {
        "science": "Science Ship",
        "constructor": "Construction Ship",
        "colonizer": "Colony Ship",
        "transport": "Transport Ship",
        "corvette": "Corvette",
        "destroyer": "Destroyer",
        "cruiser": "Cruiser",
        "battleship": "Battleship",
        "titan": "Titan",
        "juggernaut": "Juggernaut",
        "space_amoeba": "Space Amoeba",
    }

    if ship_size in mapping:
        return mapping[
            ship_size
        ]

    fleet_mapping = {
        "shipclass_science_ship": "Science Ship",
        "shipclass_constructor": "Construction Ship",
        "shipclass_colonizer": "Colony Ship",
        "shipclass_transport": "Transport Ship",
        "shipclass_military": "Military Vessel",
    }

    if fleet_class in fleet_mapping:
        return fleet_mapping[
            fleet_class
        ]

    return (
        _humanise_key(
            ship_size
            or fleet_class
            or "ship"
        )
        or "Ship"
    )


def _is_static(
    ship_size: str | None,
    fleet_class: str | None,
) -> bool:
    if fleet_class in STATIC_FLEET_CLASSES:
        return True

    if ship_size in STATIC_SHIP_SIZES:
        return True

    if ship_size and (
        ship_size.startswith("starbase")
        or ship_size.startswith("orbital_ring")
    ):
        return True

    return False


def _player_country_block(
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


def _owned_fleet_ids(
    gamestate: str,
    country_id: int,
) -> set[int]:
    country = _player_country_block(
        gamestate,
        country_id,
    )

    if not country:
        return set()

    manager = (
        _find_named_block(
            country,
            "fleets_manager",
        )
        or _find_named_block(
            country,
            "fleet_manager",
        )
    )

    if not manager:
        return set()

    owned = _find_named_block(
        manager,
        "owned_fleets",
    )

    if not owned:
        return set()

    return {
        int(value)
        for value in re.findall(
            r'(?m)^\s*fleet\s*=\s*(\d+)',
            owned,
        )
    }


def _leader_names(
    gamestate: str,
    leader_ids: set[int],
    source_save: Path,
) -> dict[int, str]:
    result: dict[int, str] = {}

    if not leader_ids:
        return result

    leaders = _find_named_block(
        gamestate,
        "leaders",
    )

    if not leaders:
        return result

    for leader_id in leader_ids:
        record = _numeric_record(
            leaders,
            leader_id,
        )

        if not record:
            continue

        result[leader_id] = _record_name(
            record,
            source_save,
            fallback=f"Leader {leader_id}",
        )

    return result


def _fleet_template_home_bases(
    gamestate: str,
) -> dict[int, int]:
    """
    Return fleet_id -> starbase_id.
    """
    templates = _find_named_block(
        gamestate,
        "fleet_template",
    )

    result: dict[int, int] = {}

    for _, record in _top_numeric_records(
        templates
    ):
        fleet_id = _int_scalar(
            record,
            "fleet",
        )

        home_base = _find_named_block(
            record,
            "home_base",
        )

        orbitable = _find_named_block(
            home_base or "",
            "orbitable",
        )

        starbase_id = _int_scalar(
            orbitable,
            "starbase",
        )

        if (
            fleet_id is not None
            and starbase_id is not None
        ):
            result[
                fleet_id
            ] = starbase_id

    return result


def _fleet_template_fleet_ids(
    gamestate: str,
) -> dict[int, int]:
    """
    Return fleet_template_id -> fleet_id.
    """
    templates = _find_named_block(
        gamestate,
        "fleet_template",
    )

    result: dict[int, int] = {}

    for template_id, record in _top_numeric_records(
        templates
    ):
        fleet_id = _int_scalar(
            record,
            "fleet",
        )

        if fleet_id is not None:
            result[
                template_id
            ] = fleet_id

    return result


def _player_shipyard_records(
    gamestate: str,
    player_owned_ship_ids: set[int],
) -> dict[int, dict]:
    """
    Return player-owned starbases that have shipyard capability.

    Ownership is established from the station ship: the station must be
    present in one of the player's owned fleets. This avoids treating foreign
    shipyards as possible build locations.
    """
    result: dict[int, dict] = {}

    manager = _find_named_block(
        gamestate,
        "starbase_mgr",
    )

    starbases = _find_named_block(
        manager or "",
        "starbases",
    )

    for starbase_id, record in _top_numeric_records(
        starbases
    ):
        station_ship_id = _int_scalar(
            record,
            "station",
        )

        if (
            station_ship_id is None
            or station_ship_id not in player_owned_ship_ids
        ):
            continue

        queue_id = _int_scalar(
            record,
            "shipyard_build_queue",
        )

        modules = _find_named_block(
            record,
            "modules",
        ) or ""

        starbase_type = _scalar(
            record,
            "type",
        )

        has_shipyard = (
            (
                queue_id is not None
                and queue_id != 4294967295
            )
            or "shipyard" in modules
            or (
                starbase_type is not None
                and "shipyard" in starbase_type
            )
        )

        if not has_shipyard:
            continue

        result[
            starbase_id
        ] = {
            "station_ship_id": station_ship_id,
            "queue_id": (
                queue_id
                if queue_id != 4294967295
                else None
            ),
        }

    return result


def _shipyard_build_orders(
    gamestate: str,
    *,
    country_id: int,
    shipyards: dict[int, ShipyardState],
    template_fleet_ids: dict[int, int],
) -> tuple[BuildOrderState, ...]:
    """
    Read active player shipyard queues.

    The construction manager stores queue records separately from item
    records. We only preserve actual new-ship build items; upgrades are
    intentionally excluded.
    """
    construction = _find_named_block(
        gamestate,
        "construction",
    )

    queue_mgr = _find_named_block(
        construction or "",
        "queue_mgr",
    )

    item_mgr = _find_named_block(
        construction or "",
        "item_mgr",
    )

    if not queue_mgr or not item_mgr:
        return ()

    orders: list[BuildOrderState] = []

    for starbase_id, shipyard in shipyards.items():
        queue_id = shipyard.queue_id

        if queue_id is None:
            continue

        queue_record = _numeric_record(
            queue_mgr,
            queue_id,
        )

        if not queue_record:
            continue

        owner = _int_scalar(
            queue_record,
            "owner",
        )

        if (
            owner is not None
            and owner != country_id
        ):
            continue

        item_ids = _id_list_from_block(
            queue_record,
            "items",
        )

        for item_id in item_ids:
            item_record = _numeric_record(
                item_mgr,
                item_id,
            )

            if not item_record:
                continue

            paying_country = _int_scalar(
                item_record,
                "paying_country",
            )

            if (
                paying_country is not None
                and paying_country != country_id
            ):
                continue

            buildable = (
                _find_named_block(
                    item_record,
                    "buildable_ship_reinforcement",
                )
                or _find_named_block(
                    item_record,
                    "buildable_ship",
                )
            )

            if not buildable:
                # Ship upgrades are deliberately excluded: they do not prove
                # where the original vessel was commissioned.
                continue

            implementation = _find_named_block(
                buildable,
                "ship_design_implementation",
            )

            design_id = _int_scalar(
                implementation,
                "design",
            )

            fleet_template_id = _int_scalar(
                buildable,
                "fleet_template",
            )

            target_fleet_id = (
                template_fleet_ids.get(
                    fleet_template_id
                )
                if fleet_template_id is not None
                else None
            )

            orbitable = _find_named_block(
                buildable,
                "orbitable",
            )

            item_starbase_id = _int_scalar(
                orbitable,
                "starbase",
            )

            effective_starbase_id = (
                item_starbase_id
                if item_starbase_id is not None
                else starbase_id
            )

            effective_shipyard = shipyards.get(
                effective_starbase_id
            )

            starbase_name = (
                effective_shipyard.name
                if effective_shipyard is not None
                else shipyard.name
            )

            orders.append(
                BuildOrderState(
                    item_id=item_id,
                    starbase_id=effective_starbase_id,
                    starbase_name=starbase_name,
                    design_id=design_id,
                    target_fleet_id=target_fleet_id,
                    target_fleet_template_id=fleet_template_id,
                )
            )

    return tuple(
        orders
    )


def _starbase_station_ship_ids(
    gamestate: str,
    wanted_starbase_ids: set[int],
) -> dict[int, int]:
    result: dict[int, int] = {}

    if not wanted_starbase_ids:
        return result

    manager = _find_named_block(
        gamestate,
        "starbase_mgr",
    )

    starbases = _find_named_block(
        manager or "",
        "starbases",
    )

    for starbase_id in wanted_starbase_ids:
        record = _numeric_record(
            starbases,
            starbase_id,
        )

        station = _int_scalar(
            record,
            "station",
        )

        if station is not None:
            result[
                starbase_id
            ] = station

    return result


def _design_sizes(
    gamestate: str,
    design_ids: set[int],
) -> dict[int, str]:
    result: dict[int, str] = {}

    if not design_ids:
        return result

    designs = _find_named_block(
        gamestate,
        "ship_design",
    )

    for design_id in design_ids:
        record = _numeric_record(
            designs,
            design_id,
        )

        if not record:
            continue

        match = re.search(
            r'(?m)^\s*ship_size\s*=\s*"([^"]+)"',
            record,
        )

        if match:
            result[
                design_id
            ] = match.group(1)

    return result


def extract_ship_fleet_snapshot(
    save_path: Path,
    *,
    source_save: Path,
    snapshot_id: int,
    profile: EmpireProfile | None = None,
    gamestate: str | None = None,
) -> ShipFleetSnapshot:
    if profile is None or gamestate is None:
        meta, loaded_gamestate = read_save_texts(save_path)

        if gamestate is None:
            gamestate = loaded_gamestate

        if profile is None:
            profile = empire_profile_from_text(meta, gamestate)

    country_id = profile.player_country_id

    if country_id is None:
        raise ValueError(
            "Could not determine the player country ID."
        )

    owned_fleet_ids = _owned_fleet_ids(
        gamestate,
        country_id,
    )

    fleet_block = _find_named_block(
        gamestate,
        "fleet",
    )

    raw_fleets: dict[int, dict] = {}
    wanted_ship_ids: set[int] = set()
    all_owned_ship_ids: set[int] = set()
    leader_ids: set[int] = set()

    for fleet_id in owned_fleet_ids:
        record = _numeric_record(
            fleet_block,
            fleet_id,
        )

        if not record:
            continue

        ship_class = (
            _scalar(
                record,
                "ship_class",
            )
            or "shipclass_unknown"
        )

        ship_ids = _id_list_from_block(
            record,
            "ships",
        )

        fleet_name = _clean_display_name(
            _record_name(
                record,
                source_save,
                fallback="",
            ),
            fallback=_fallback_fleet_name(
                ship_class
            ),
        )

        raw_fleets[
            fleet_id
        ] = {
            "record": record,
            "name": fleet_name,
            "ship_class": ship_class,
            "ship_ids": ship_ids,
        }

        wanted_ship_ids.update(
            ship_ids
        )

        all_owned_ship_ids.update(
            ship_ids
        )

    home_base_ids = _fleet_template_home_bases(
        gamestate
    )

    wanted_starbases = {
        starbase_id
        for fleet_id, starbase_id in home_base_ids.items()
        if fleet_id in raw_fleets
    }

    player_shipyard_records = _player_shipyard_records(
        gamestate,
        all_owned_ship_ids,
    )

    wanted_starbases.update(
        player_shipyard_records
    )

    starbase_station_ids = _starbase_station_ship_ids(
        gamestate,
        wanted_starbases,
    )

    wanted_station_ship_ids = set(
        starbase_station_ids.values()
    )

    ships_block = _find_named_block(
        gamestate,
        "ships",
    )

    raw_ship_records: dict[int, str] = {}

    for ship_id in (
        wanted_ship_ids
        | wanted_station_ship_ids
    ):
        record = _numeric_record(
            ships_block,
            ship_id,
        )

        if record:
            raw_ship_records[
                ship_id
            ] = record

    design_ids: set[int] = set()

    for ship_id in wanted_ship_ids:
        record = raw_ship_records.get(
            ship_id
        )

        implementation = _find_named_block(
            record or "",
            "ship_design_implementation",
        )

        design_id = _int_scalar(
            implementation,
            "design",
        )

        if design_id is not None:
            design_ids.add(
                design_id
            )

    design_sizes = _design_sizes(
        gamestate,
        design_ids,
    )

    # First collect all leader IDs used by the player's mobile ships.
    ship_temp: dict[int, dict] = {}

    for fleet_id, fleet_data in raw_fleets.items():
        fleet_class = fleet_data[
            "ship_class"
        ]

        for ship_id in fleet_data[
            "ship_ids"
        ]:
            record = raw_ship_records.get(
                ship_id
            )

            if not record:
                continue

            implementation = _find_named_block(
                record,
                "ship_design_implementation",
            )

            design_id = _int_scalar(
                implementation,
                "design",
            )

            ship_size = (
                design_sizes.get(
                    design_id
                )
                if design_id is not None
                else None
            )

            # Event/biological vessels do not always use an ordinary ship
            # design record. Preserve a direct ship_size field when Stellaris
            # exposes one so living vessels can be classified correctly.
            if not ship_size:
                ship_size = _scalar(
                    record,
                    "ship_size",
                )

            if _is_static(
                ship_size,
                fleet_class,
            ):
                continue

            leader_id = _int_scalar(
                record,
                "leader",
            )

            if leader_id is not None:
                leader_ids.add(
                    leader_id
                )

            ship_temp[
                ship_id
            ] = {
                "record": record,
                "fleet_id": fleet_id,
                "fleet_name": fleet_data[
                    "name"
                ],
                "fleet_class": fleet_class,
                "ship_size": ship_size,
                "leader_id": leader_id,
                "design_id": design_id,
            }

    leader_names = _leader_names(
        gamestate,
        leader_ids,
        source_save,
    )

    # Resolve home-base display names from the station ships.
    home_base_names: dict[int, str] = {}

    for starbase_id, station_ship_id in starbase_station_ids.items():
        station_record = raw_ship_records.get(
            station_ship_id
        )

        if not station_record:
            continue

        home_base_names[
            starbase_id
        ] = _record_name(
            station_record,
            source_save,
            fallback=f"Starbase {starbase_id}",
        )

    ships: dict[int, ShipState] = {}

    for ship_id, temp in ship_temp.items():
        record = temp["record"]
        leader_id = temp["leader_id"]

        ships[
            ship_id
        ] = ShipState(
            ship_id=ship_id,
            name=_clean_display_name(
                _record_name(
                    record,
                    source_save,
                    fallback="",
                ),
                fallback=f"Unnamed {_ship_type_name(temp['ship_size'], temp['fleet_class'])}",
            ),
            ship_type=_ship_type_name(
                temp["ship_size"],
                temp["fleet_class"],
            ),
            ship_size=temp["ship_size"],
            construction_date=_scalar(
                record,
                "construction_date",
            ),
            fleet_id=temp["fleet_id"],
            fleet_name=temp["fleet_name"],
            commander_id=leader_id,
            commander_name=(
                leader_names.get(
                    leader_id
                )
                if leader_id is not None
                else None
            ),
            design_id=temp[
                "design_id"
            ],
        )

    fleets: dict[int, FleetState] = {}

    for fleet_id, fleet_data in raw_fleets.items():
        mobile_ship_ids = tuple(
            ship_id
            for ship_id in fleet_data[
                "ship_ids"
            ]
            if ship_id in ships
        )

        if not mobile_ship_ids:
            continue

        commander_id = None
        commander_name = None

        for ship_id in mobile_ship_ids:
            ship = ships[
                ship_id
            ]

            if ship.commander_id is not None:
                commander_id = ship.commander_id
                commander_name = ship.commander_name
                break

        starbase_id = home_base_ids.get(
            fleet_id
        )

        home_base = (
            home_base_names.get(
                starbase_id
            )
            if starbase_id is not None
            else None
        )

        if (
            home_base is None
            and starbase_id is not None
        ):
            home_base = f"Starbase {starbase_id}"

        fleets[
            fleet_id
        ] = FleetState(
            fleet_id=fleet_id,
            name=fleet_data[
                "name"
            ],
            ship_class=fleet_data[
                "ship_class"
            ],
            ship_ids=mobile_ship_ids,
            home_base=home_base,
            commander_id=commander_id,
            commander_name=commander_name,
        )

    shipyards: dict[int, ShipyardState] = {}

    for starbase_id, data in player_shipyard_records.items():
        station_ship_id = data[
            "station_ship_id"
        ]

        station_record = raw_ship_records.get(
            station_ship_id
        )

        shipyard_name = (
            _clean_display_name(
                _record_name(
                    station_record,
                    source_save,
                    fallback="",
                ),
                fallback=f"Starbase {starbase_id}",
            )
            if station_record
            else f"Starbase {starbase_id}"
        )

        shipyards[
            starbase_id
        ] = ShipyardState(
            starbase_id=starbase_id,
            name=shipyard_name,
            station_ship_id=station_ship_id,
            queue_id=data.get(
                "queue_id"
            ),
        )

    template_fleet_ids = _fleet_template_fleet_ids(
        gamestate
    )

    build_orders = _shipyard_build_orders(
        gamestate,
        country_id=country_id,
        shipyards=shipyards,
        template_fleet_ids=template_fleet_ids,
    )

    return ShipFleetSnapshot(
        snapshot_id=snapshot_id,
        game_date=profile.game_date,
        ships=ships,
        fleets=fleets,
        shipyards=shipyards,
        build_orders=build_orders,
    )
