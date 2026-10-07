from __future__ import annotations

import re

from .models import WorldSnapshot, WorldState


def _location_phrase(
    world: WorldState,
) -> str:
    if world.system_name:
        return f" in the {world.system_name} system"

    return ""


def format_population_units(
    raw_value: int | None,
) -> str | None:
    """Render Stellaris' hundredth-pop save units as player-facing pops."""
    if raw_value is None:
        return None

    value = raw_value / 100

    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _population_phrase(
    world: WorldState,
) -> str:
    value = format_population_units(
        world.population
    )

    if value is None:
        return ""

    return (
        f" Its first confirmed population in the archive was "
        f"{value} pops."
    )


def _event(
    *,
    snapshot_id: int,
    game_date: str,
    planet_id: int,
    event_type: str,
    title: str,
    body: str,
    date_kind: str,
    confidence: str,
    visible: bool = True,
    discriminator: str = "",
) -> dict:
    safe_discriminator = re.sub(
        r"\s+",
        " ",
        discriminator,
    ).strip().casefold()

    return {
        "event_key": (
            f"{event_type}:{planet_id}:{game_date}:{safe_discriminator}"
        ),
        "snapshot_id": snapshot_id,
        "game_date": game_date,
        "event_type": event_type,
        "planet_id": planet_id,
        "title": title,
        "body": body,
        "visible": int(
            visible
        ),
        "confidence": confidence,
        "date_kind": date_kind,
    }


def _first_world_event(
    world: WorldState,
    *,
    current: WorldSnapshot,
    previous: WorldSnapshot | None,
) -> dict:
    previous_date = (
        previous.game_date
        if previous is not None
        else None
    )

    exact_foundation = (
        world.colonize_date is not None
        and previous_date is not None
        and previous_date < world.colonize_date <= current.game_date
        and world.original_owner_id in {
            None,
            current.player_country_id,
        }
    )

    if exact_foundation:
        return _event(
            snapshot_id=current.snapshot_id,
            game_date=world.colonize_date,
            planet_id=world.planet_id,
            event_type="colony_founded",
            title=f"{world.name} Founded",
            body=(
                f"Stellaris records the colony of {world.name}"
                f"{_location_phrase(world)} as founded on {world.colonize_date}. "
                f"The first surviving archived state containing the colony is "
                f"dated {current.game_date}."
                f"{_population_phrase(world)}"
            ),
            date_kind="exact_save_field",
            confidence="high",
            visible=True,
        )

    return _event(
        snapshot_id=current.snapshot_id,
        game_date=current.game_date,
        planet_id=world.planet_id,
        event_type="world_entered_control",
        title=f"{world.name} Entered Imperial Control",
        body=(
            f"{world.name}{_location_phrase(world)} first appears among the "
            f"empire's owned colonies by {current.game_date}. The archive does "
            f"not establish the exact date or cause of acquisition."
            f"{_population_phrase(world)}"
        ),
        date_kind="first_observed",
        confidence="medium",
        visible=True,
    )


def world_transition_data(
    previous: WorldSnapshot | None,
    current: WorldSnapshot,
    *,
    baseline: bool = False,
) -> dict:
    rows: list[dict] = []
    events: list[dict] = []

    previous_worlds = (
        previous.worlds
        if previous is not None
        else {}
    )

    for world in current.worlds.values():
        rows.append(
            {
                "planet_id": world.planet_id,
                "latest_colony_id": world.colony_id,
                "first_seen_date": current.game_date,
                "last_seen_date": current.game_date,
                "colonize_date": world.colonize_date,
                "name": world.name,
                "system_id": world.system_id,
                "system_name": world.system_name,
                "planet_class_key": world.planet_class_key,
                "planet_class_name": world.planet_class_name,
                "planet_size": world.planet_size,
                "original_owner_id": world.original_owner_id,
                "latest_owner_id": world.owner_id,
                "latest_controller_id": world.controller_id,
                "latest_governor_id": world.governor_id,
                "latest_governor_name": world.governor_name,
                "latest_population": world.population,
                "latest_employable_pops": world.employable_pops,
                "latest_designation_key": world.designation_key,
                "latest_designation_name": world.designation_name,
                "latest_ascension_tier": world.ascension_tier,
                "latest_district_count": world.district_count,
                "latest_building_count": world.building_count,
                "latest_is_capital": int(
                    world.is_capital
                ),
                "ever_capital": int(
                    world.is_capital
                ),
                "status": "present",
                "baseline_present": int(
                    baseline
                ),
                "first_snapshot_id": current.snapshot_id,
                "last_snapshot_id": current.snapshot_id,
            }
        )

        before = previous_worlds.get(
            world.planet_id
        )

        if before is None:
            if not baseline:
                events.append(
                    _first_world_event(
                        world,
                        current=current,
                        previous=previous,
                    )
                )
            continue

        if (
            before.name != world.name
            and before.name != "Unnamed World"
            and world.name != "Unnamed World"
        ):
            events.append(
                _event(
                    snapshot_id=current.snapshot_id,
                    game_date=current.game_date,
                    planet_id=world.planet_id,
                    event_type="world_renamed",
                    title=f"{before.name} Renamed {world.name}",
                    body=(
                        f"Between the {previous.game_date} and {current.game_date} "
                        f"archived states, the world previously recorded as "
                        f"{before.name} was renamed {world.name}."
                    ),
                    date_kind="between_snapshots",
                    confidence="high",
                    visible=True,
                    discriminator=f"{before.name}->{world.name}",
                )
            )

        if (
            not before.is_capital
            and world.is_capital
        ):
            events.append(
                _event(
                    snapshot_id=current.snapshot_id,
                    game_date=current.game_date,
                    planet_id=world.planet_id,
                    event_type="world_became_capital",
                    title=f"{world.name} Became the Capital",
                    body=(
                        f"By {current.game_date}, {world.name} was recorded as the "
                        f"capital world of the empire. The exact date of the transfer "
                        f"is not established by the surviving quarterly archive."
                    ),
                    date_kind="first_observed",
                    confidence="medium",
                    visible=True,
                )
            )

        if before.governor_id != world.governor_id:
            events.append(
                _event(
                    snapshot_id=current.snapshot_id,
                    game_date=current.game_date,
                    planet_id=world.planet_id,
                    event_type="governor_changed",
                    title=f"Government of {world.name} Changed",
                    body=(
                        f"By {current.game_date}, the recorded governor assignment for "
                        f"{world.name} had changed."
                    ),
                    date_kind="first_observed",
                    confidence="high",
                    visible=False,
                    discriminator=str(world.governor_id),
                )
            )

        if before.designation_key != world.designation_key:
            events.append(
                _event(
                    snapshot_id=current.snapshot_id,
                    game_date=current.game_date,
                    planet_id=world.planet_id,
                    event_type="designation_changed",
                    title=f"{world.name} Changed Designation",
                    body=(
                        f"By {current.game_date}, {world.name} was recorded with the "
                        f"designation {world.designation_name or 'not resolved'}."
                    ),
                    date_kind="first_observed",
                    confidence="high",
                    visible=False,
                    discriminator=str(world.designation_key),
                )
            )

    missing_ids = sorted(
        set(
            previous_worlds
        )
        - set(
            current.worlds
        )
    )

    for planet_id in missing_ids:
        before = previous_worlds[
            planet_id
        ]

        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                planet_id=planet_id,
                event_type="world_left_control",
                title=f"{before.name} Left Imperial Control",
                body=(
                    f"{before.name} is no longer recorded among the empire's owned "
                    f"colonies by {current.game_date}. The surviving archive does not "
                    f"establish whether the cause was conquest, transfer, abandonment "
                    f"or another change of status."
                ),
                date_kind="first_observed",
                confidence="medium",
                visible=True,
            )
        )

    return {
        "worlds": rows,
        "events": events,
        "missing_planet_ids": missing_ids,
    }


def derive_full_world_history(
    snapshots: list[WorldSnapshot],
) -> dict:
    if not snapshots:
        return {
            "worlds": [],
            "events": [],
        }

    registry: dict[int, dict] = {}
    events_by_key: dict[str, dict] = {}
    seen_before: set[int] = set()
    previous: WorldSnapshot | None = None

    for index, snapshot in enumerate(
        snapshots
    ):
        delta = world_transition_data(
            previous,
            snapshot,
            baseline=(index == 0),
        )

        for row in delta[
            "worlds"
        ]:
            planet_id = row[
                "planet_id"
            ]

            existing = registry.get(
                planet_id
            )

            if existing is None:
                registry[
                    planet_id
                ] = dict(
                    row
                )
            else:
                first_seen = existing[
                    "first_seen_date"
                ]
                first_snapshot_id = existing[
                    "first_snapshot_id"
                ]
                baseline_present = existing.get(
                    "baseline_present",
                    0,
                )
                ever_capital = max(
                    existing.get(
                        "ever_capital",
                        0,
                    ),
                    row.get(
                        "ever_capital",
                        0,
                    ),
                )
                # colonize_date can be repurposed/reset by later planetary
                # transformations. Preserve the earliest usable value seen in
                # the surviving record so the register agrees with the exact
                # colony-founding event derived at first appearance.
                recorded_colonize_date = existing.get(
                    "colonize_date"
                ) or row.get(
                    "colonize_date"
                )

                existing.update(
                    row
                )

                existing[
                    "first_seen_date"
                ] = first_seen
                existing[
                    "colonize_date"
                ] = recorded_colonize_date
                existing[
                    "first_snapshot_id"
                ] = first_snapshot_id
                existing[
                    "baseline_present"
                ] = baseline_present
                existing[
                    "ever_capital"
                ] = ever_capital
                existing[
                    "status"
                ] = "present"

            seen_before.add(
                planet_id
            )

        for missing_id in delta[
            "missing_planet_ids"
        ]:
            if missing_id in registry:
                registry[
                    missing_id
                ][
                    "status"
                ] = "no_longer_owned"

                registry[
                    missing_id
                ][
                    "latest_is_capital"
                ] = 0

        for event in delta[
            "events"
        ]:
            # If an already known world reappears after an absence, make the
            # published wording explicitly about a return to control.
            if (
                event["event_type"] == "world_entered_control"
                and event["planet_id"] in registry
                and registry[event["planet_id"]].get("first_seen_date") != snapshot.game_date
            ):
                world = snapshot.worlds.get(
                    event["planet_id"]
                )

                if world is not None:
                    event = _event(
                        snapshot_id=snapshot.snapshot_id,
                        game_date=snapshot.game_date,
                        planet_id=world.planet_id,
                        event_type="world_returned_control",
                        title=f"{world.name} Returned to Imperial Control",
                        body=(
                            f"{world.name}{_location_phrase(world)} is again recorded "
                            f"among the empire's owned colonies by {snapshot.game_date}. "
                            f"The exact date and circumstances of its return are not "
                            f"established by the surviving archive."
                        ),
                        date_kind="first_observed",
                        confidence="medium",
                        visible=True,
                    )

            events_by_key[
                event[
                    "event_key"
                ]
            ] = event

        previous = snapshot

    return {
        "worlds": sorted(
            registry.values(),
            key=lambda row: (
                -int(
                    row.get(
                        "baseline_present",
                        0,
                    )
                ),
                -int(
                    row.get(
                        "ever_capital",
                        0,
                    )
                ),
                row[
                    "first_seen_date"
                ],
                row[
                    "name"
                ],
                row[
                    "planet_id"
                ],
            ),
        ),
        "events": sorted(
            events_by_key.values(),
            key=lambda event: (
                event[
                    "game_date"
                ],
                event[
                    "event_key"
                ],
            ),
        ),
    }
