from __future__ import annotations

import re

from .models import FleetState, ShipFleetSnapshot


_UNRESOLVED_TOKEN = re.compile(r"%(?:[A-Za-z0-9_]+)%|\$(?:[A-Za-z0-9_.-]+)\$")


def _contains_unresolved_token(value: str | None) -> bool:
    if not value:
        return False
    return bool(_UNRESOLVED_TOKEN.search(value))


def _normalised_fleet_name(
    value: str | None,
) -> str | None:
    if not value:
        return None

    cleaned = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    if not cleaned:
        return None

    if _contains_unresolved_token(
        cleaned
    ):
        return None

    if cleaned.lower().startswith(
        "unnamed "
    ):
        return None

    return cleaned.casefold()


def _fleet_signature(
    fleet: "FleetState",
) -> tuple[str, str] | None:
    name = _normalised_fleet_name(
        fleet.name
    )

    if name is None:
        return None

    return (
        fleet.ship_class,
        name,
    )


def _meaningful_fleet_name(
    value: str | None,
) -> bool:
    return (
        _normalised_fleet_name(
            value
        )
        is not None
    )


def _fleet_match_score(
    before: "FleetState",
    after: "FleetState",
) -> int:
    """
    Score whether two adjacent-snapshot fleet records are probably the same
    logical fleet even when Stellaris has replaced the internal fleet ID.
    """
    score = 0

    before_name = _normalised_fleet_name(
        before.name
    )
    after_name = _normalised_fleet_name(
        after.name
    )

    if (
        before_name is not None
        and before_name == after_name
    ):
        score += 100

    overlap = len(
        set(before.ship_ids)
        & set(after.ship_ids)
    )

    if overlap:
        score += 120 + (overlap * 10)

    if before.ship_class == after.ship_class:
        score += 10

    if (
        before.home_base
        and after.home_base
        and before.home_base == after.home_base
    ):
        score += 5

    return score


def _adjacent_fleet_matches(
    previous: "ShipFleetSnapshot",
    current: "ShipFleetSnapshot",
) -> dict[int, int]:
    """
    Return current_fleet_id -> previous_fleet_id for fleets that appear to be
    the same logical fleet across adjacent snapshots.

    Exact IDs win first. Remaining records are matched one-to-one by name,
    overlapping ship membership, class and home base.
    """
    matches: dict[int, int] = {}
    used_previous: set[int] = set()

    for fleet_id in (
        set(previous.fleets)
        & set(current.fleets)
    ):
        matches[fleet_id] = fleet_id
        used_previous.add(
            fleet_id
        )

    candidates: list[tuple[int, int, int]] = []

    for current_id, after in current.fleets.items():
        if current_id in matches:
            continue

        for previous_id, before in previous.fleets.items():
            if previous_id in used_previous:
                continue

            score = _fleet_match_score(
                before,
                after,
            )

            same_name = (
                _normalised_fleet_name(
                    before.name
                )
                is not None
                and _normalised_fleet_name(
                    before.name
                )
                == _normalised_fleet_name(
                    after.name
                )
            )

            overlap = bool(
                set(before.ship_ids)
                & set(after.ship_ids)
            )

            if (
                score >= 100
                and (
                    same_name
                    or overlap
                )
            ):
                candidates.append(
                    (
                        score,
                        current_id,
                        previous_id,
                    )
                )

    candidates.sort(
        reverse=True
    )

    used_current: set[int] = set(
        matches
    )

    for _, current_id, previous_id in candidates:
        if (
            current_id in used_current
            or previous_id in used_previous
        ):
            continue

        matches[
            current_id
        ] = previous_id

        used_current.add(
            current_id
        )
        used_previous.add(
            previous_id
        )

    return matches
