from __future__ import annotations

import re

from .models import ShipFleetSnapshot, ShipState
from .parser import _contains_unresolved_token


def _date_key(
    value: str | None,
) -> tuple[int, int, int] | None:
    if not value:
        return None

    match = re.fullmatch(
        r"\s*(-?\d+)\.(\d+)\.(\d+)\s*",
        value,
    )

    if not match:
        return None

    return tuple(
        int(part)
        for part in match.groups()
    )


def _usable_exact_construction_date(
    value: str | None,
    *,
    record_start_date: str,
    observed_date: str,
) -> bool:
    """
    A normal commissioning date must fall inside the surviving campaign
    record and not later than the snapshot where the ship is observed.

    Stellaris can store much older age/origin-like dates on living/event
    vessels. Those raw values are preserved in the ship registry, but are not
    published as ordinary commissioning dates.
    """
    if not value or value == "0.01.01":
        return False

    raw = _date_key(
        value
    )
    start = _date_key(
        record_start_date
    )
    observed = _date_key(
        observed_date
    )

    if raw is None or start is None or observed is None:
        return False

    return (
        start <= raw <= observed
    )


def _is_living_or_biological_vessel(
    ship: ShipState,
) -> bool:
    """
    Best-effort classification for living ships.

    We deliberately use broad raw size tokens instead of hard-coding Bubbles.
    This also covers amoebae, tiyanki/space whales, voidworms, cutholoids and
    similar biological event vessels when Stellaris exposes their size.
    """
    raw = (
        ship.ship_size
        or ""
    ).casefold()

    display = (
        ship.ship_type
        or ""
    ).casefold()

    biological_tokens = (
        "amoeba",
        "space_whale",
        "tiyanki",
        "voidworm",
        "cutholoid",
        "organic",
        "biological",
        "leviathan",
    )

    return any(
        token in raw
        or token in display
        for token in biological_tokens
    )


def _clean_build_location(
    value: str | None,
) -> str | None:
    """
    Reject unresolved or generic display fragments that are not useful
    historical place names.

    Example caught by this rule: "planet Station".
    """
    if not value:
        return None

    cleaned = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    if (
        not cleaned
        or _contains_unresolved_token(
            cleaned
        )
    ):
        return None

    generic = cleaned.casefold()

    if generic in {
        "station",
        "planet station",
        "starbase",
        "shipyard",
        "planet",
        "unnamed station",
        "unnamed starbase",
        "unnamed shipyard",
    }:
        return None

    return cleaned


def _build_location_provenance(
    ship: ShipState,
    *,
    previous: ShipFleetSnapshot | None,
    current: ShipFleetSnapshot,
    fleet_matches: dict[int, int] | None = None,
) -> dict | None:
    """
    Determine the best supported construction location for a newly observed
    ship.

    Priority:
      1. Direct evidence from the preceding shipyard build queue.
      2. First-observed fleet home base (explicitly marked as inference).
      3. A single identifiable player shipyard in the preceding/current state.
      4. Unknown.

    Current home base is never silently rewritten as a historical birthplace.
    """
    fleet_matches = fleet_matches or {}

    if (
        previous is not None
        and ship.design_id is not None
    ):
        design_matches = [
            order
            for order in previous.build_orders
            if order.design_id == ship.design_id
        ]

        if design_matches:
            previous_fleet_id = (
                fleet_matches.get(
                    ship.fleet_id
                )
                if ship.fleet_id is not None
                else None
            )

            target_ids = {
                fleet_id
                for fleet_id in (
                    ship.fleet_id,
                    previous_fleet_id,
                )
                if fleet_id is not None
            }

            targeted = [
                order
                for order in design_matches
                if (
                    order.target_fleet_id is not None
                    and order.target_fleet_id in target_ids
                )
            ]

            considered = (
                targeted
                if targeted
                else design_matches
            )

            starbases = {
                order.starbase_id
                for order in considered
            }

            if len(starbases) == 1:
                starbase_id = next(
                    iter(starbases)
                )

                matching_order = next(
                    order
                    for order in considered
                    if order.starbase_id == starbase_id
                )

                location = _clean_build_location(
                    matching_order.starbase_name
                )

                if location is not None:
                    return {
                        "ship_id": ship.ship_id,
                        "build_location": location,
                        "build_location_starbase_id": starbase_id,
                        "evidence_kind": "direct_shipyard_queue",
                        "confidence": "high",
                        "source_snapshot_id": previous.snapshot_id,
                        "source_game_date": previous.game_date,
                    }

    current_fleet = (
        current.fleets.get(
            ship.fleet_id
        )
        if ship.fleet_id is not None
        else None
    )

    fleet_home_base = (
        _clean_build_location(
            current_fleet.home_base
        )
        if current_fleet is not None
        else None
    )

    if fleet_home_base:
        return {
            "ship_id": ship.ship_id,
            "build_location": fleet_home_base,
            "build_location_starbase_id": None,
            "evidence_kind": "first_observed_fleet_home_base",
            "confidence": "medium",
            "source_snapshot_id": current.snapshot_id,
            "source_game_date": current.game_date,
        }

    candidate_shipyards = (
        previous.shipyards
        if (
            previous is not None
            and previous.shipyards
        )
        else current.shipyards
    )

    if len(candidate_shipyards) == 1:
        starbase_id, shipyard = next(
            iter(
                candidate_shipyards.items()
            )
        )

        location = _clean_build_location(
            shipyard.name
        )

        if location is None:
            return None

        return {
            "ship_id": ship.ship_id,
            "build_location": location,
            "build_location_starbase_id": starbase_id,
            "evidence_kind": "unique_player_shipyard",
            "confidence": "low",
            "source_snapshot_id": (
                previous.snapshot_id
                if previous is not None
                else current.snapshot_id
            ),
            "source_game_date": (
                previous.game_date
                if previous is not None
                else current.game_date
            ),
        }

    return None


def _build_location_sentence(
    provenance: dict | None,
) -> tuple[str | None, str | None]:
    if not provenance:
        return None, None

    location = provenance[
        "build_location"
    ]

    evidence = provenance[
        "evidence_kind"
    ]

    if evidence == "direct_shipyard_queue":
        return (
            f"at {location}",
            None,
        )

    if evidence == "first_observed_fleet_home_base":
        return (
            None,
            (
                f"Its first recorded fleet home base was {location}; "
                "Historian therefore records that as the likely build location."
            ),
        )

    if evidence == "unique_player_shipyard":
        return (
            None,
            (
                f"{location} was the only player shipyard Historian could "
                "identify in the adjacent archived state, making it the "
                "probable build location."
            ),
        )

    return None, None


def _build_provenance_allowed(
    ship: ShipState,
    *,
    record_start_date: str,
    observed_date: str,
) -> bool:
    if _is_living_or_biological_vessel(
        ship
    ):
        return False

    # If Stellaris gives a raw vessel date but it falls outside the surviving
    # campaign chronology, treat the vessel as pre-existing/special rather
    # than pretending it was constructed by one of the player's shipyards.
    if (
        ship.construction_date
        and not _usable_exact_construction_date(
            ship.construction_date,
            record_start_date=record_start_date,
            observed_date=observed_date,
        )
    ):
        return False

    return True
