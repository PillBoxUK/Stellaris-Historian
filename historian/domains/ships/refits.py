from __future__ import annotations

from collections import defaultdict

from .identity import _meaningful_fleet_name
from .models import ShipFleetSnapshot, ShipState
from .provenance import _is_living_or_biological_vessel


_MAJOR_MILITARY_TYPES = {
    "Destroyer",
    "Cruiser",
    "Battleship",
    "Titan",
    "Juggernaut",
}

_SUPPORT_TYPES = {
    "Science Ship",
    "Construction Ship",
    "Colony Ship",
    "Transport Ship",
}


def _design_changed(
    before: ShipState,
    after: ShipState,
) -> bool:
    return (
        before.design_id is not None
        and after.design_id is not None
        and before.design_id != after.design_id
    )


def _safe_refit_interpretation(
    before: ShipState,
    after: ShipState,
) -> bool:
    """
    A design-ID transition is hard evidence that Stellaris now records a
    different design for the same ship. Publicly calling that a refit is kept
    deliberately conservative: living vessels and class/size transformations
    are retained as raw design-change evidence only.
    """
    if not _design_changed(before, after):
        return False

    if (
        _is_living_or_biological_vessel(before)
        or _is_living_or_biological_vessel(after)
    ):
        return False

    if before.ship_type != after.ship_type:
        return False

    if (
        before.ship_size is not None
        and after.ship_size is not None
        and before.ship_size != after.ship_size
    ):
        return False

    return True


def _event(
    *,
    key: str,
    snapshot_id: int,
    game_date: str,
    event_type: str,
    title: str,
    body: str,
    ship_id: int | None = None,
    fleet_id: int | None = None,
    visible: bool,
    confidence: str,
) -> dict:
    return {
        "event_key": key,
        "snapshot_id": snapshot_id,
        "game_date": game_date,
        "event_type": event_type,
        "ship_id": ship_id,
        "fleet_id": fleet_id,
        "title": title,
        "body": body,
        "visible": 1 if visible else 0,
        "confidence": confidence,
        "date_kind": "between_snapshots",
    }


def _ship_name_summary(
    ships: list[ShipState],
    *,
    limit: int = 6,
) -> str:
    names = [ship.name for ship in ships]

    if len(names) <= limit:
        return ", ".join(names)

    shown = ", ".join(names[:limit])
    remaining = len(names) - limit
    return f"{shown}, and {remaining} other vessel(s)"


def _fleet_name_summary(
    names: list[str],
    *,
    limit: int = 4,
) -> str:
    if len(names) <= limit:
        return ", ".join(names)

    shown = ", ".join(names[:limit])
    remaining = len(names) - limit
    return f"{shown}, and {remaining} other fleet(s)"


def _fleet_is_military(
    snapshot: ShipFleetSnapshot,
    fleet_id: int | None,
) -> bool:
    if fleet_id is None:
        return False

    fleet = snapshot.fleets.get(fleet_id)
    return bool(fleet and fleet.ship_class == "shipclass_military")


def _is_support_ship(ship: ShipState) -> bool:
    return ship.ship_type in _SUPPORT_TYPES


def _is_major_military_ship(
    snapshot: ShipFleetSnapshot,
    ship: ShipState,
) -> bool:
    return (
        _fleet_is_military(snapshot, ship.fleet_id)
        and ship.ship_type in _MAJOR_MILITARY_TYPES
    )


def derive_refit_events(
    previous: ShipFleetSnapshot,
    current: ShipFleetSnapshot,
) -> list[dict]:
    """
    Derive conservative ship-design transition evidence between two adjacent
    archived states.

    The collector remains greedy: every stable-vessel design change is kept as
    a hidden raw event with the old/new design IDs. Public publication is more
    selective:

    * broad naval modernisation affecting multiple named military fleets is one
      journal event;
    * otherwise two or more changed ships in the same named military fleet are
      one fleet-refit event;
    * three or more support ships changing together are one support-fleet event;
    * an isolated refit is published only for a major military hull.

    Routine single-corvette and utility-ship design churn remains available in
    the structured evidence but no longer floods the published journal.
    """
    raw_changes: list[tuple[ShipState, ShipState]] = []
    public_changes: list[tuple[ShipState, ShipState]] = []

    for ship_id in sorted(set(previous.ships) & set(current.ships)):
        before = previous.ships[ship_id]
        after = current.ships[ship_id]

        if not _design_changed(before, after):
            continue

        raw_changes.append((before, after))

        if _safe_refit_interpretation(before, after):
            public_changes.append((before, after))

    events: list[dict] = []

    # Greedy evidence layer: preserve every stable-vessel design transition.
    for before, after in raw_changes:
        events.append(
            _event(
                key=(
                    f"ship_design_changed:{after.ship_id}:"
                    f"{current.snapshot_id}:{before.design_id}:{after.design_id}"
                ),
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                event_type="ship_design_changed",
                ship_id=after.ship_id,
                fleet_id=after.fleet_id,
                title=f"{after.name} Recorded Design Changed",
                body=(
                    f"Between {previous.game_date} and {current.game_date}, "
                    f"{after.name}'s recorded ship design changed from internal "
                    f"design {before.design_id} to {after.design_id}. Historian "
                    "preserves this as refit evidence without inferring exact "
                    "component changes."
                ),
                visible=False,
                confidence="high",
            )
        )

    if not public_changes:
        return events

    # Group public-safe changes by their current named fleet.
    grouped: dict[int, list[tuple[ShipState, ShipState]]] = defaultdict(list)
    ungrouped: list[tuple[ShipState, ShipState]] = []

    for before, after in public_changes:
        if (
            after.fleet_id is not None
            and after.fleet_name
            and _meaningful_fleet_name(after.fleet_name)
        ):
            grouped[after.fleet_id].append((before, after))
        else:
            ungrouped.append((before, after))

    military_groups: dict[int, list[tuple[ShipState, ShipState]]] = {
        fleet_id: changes
        for fleet_id, changes in grouped.items()
        if _fleet_is_military(current, fleet_id)
    }

    military_change_count = sum(len(changes) for changes in military_groups.values())
    affected_named_military_fleets = [
        fleet_id
        for fleet_id, changes in military_groups.items()
        if changes
    ]

    published_ship_ids: set[int] = set()

    # When several military fleets modernise in the same archived interval, one
    # campaign-level event is far more useful than a stack of near-identical
    # fleet/ship cards.
    if (
        len(affected_named_military_fleets) >= 2
        and military_change_count >= 4
    ):
        fleet_names: list[str] = []
        ships: list[ShipState] = []

        for fleet_id in sorted(affected_named_military_fleets):
            changes = military_groups[fleet_id]
            if not changes:
                continue

            fleet_name = changes[0][1].fleet_name or "Unnamed Military Fleet"
            fleet_names.append(fleet_name)
            ships.extend(after for _, after in changes)

        published_ship_ids.update(ship.ship_id for ship in ships)

        events.append(
            _event(
                key=(
                    f"naval_modernisation_wave:{current.snapshot_id}:"
                    f"{','.join(str(ship.ship_id) for ship in ships)}"
                ),
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                event_type="naval_modernisation_wave",
                title="Naval Modernisation Wave Observed",
                body=(
                    f"Between the {previous.game_date} and {current.game_date} "
                    f"archived states, {len(ships)} surviving military vessels "
                    f"across {len(fleet_names)} named fleets changed their "
                    f"recorded ship design. Affected fleets included "
                    f"{_fleet_name_summary(fleet_names)}. Historian treats this "
                    "as strong evidence of a coordinated naval refit or upgrade "
                    "wave, but does not yet infer the exact components changed."
                ),
                visible=True,
                confidence="high",
            )
        )

    else:
        # Otherwise, publish only substantial same-fleet refits. A single
        # corvette changing design is useful evidence but not usually a useful
        # journal entry by itself.
        for fleet_id, changes in sorted(military_groups.items()):
            if len(changes) < 2:
                continue

            after_ships = [after for _, after in changes]
            fleet_name = after_ships[0].fleet_name or "Fleet"
            names = _ship_name_summary(after_ships)
            vessel_word = "vessel" if len(after_ships) == 1 else "vessels"

            published_ship_ids.update(ship.ship_id for ship in after_ships)

            events.append(
                _event(
                    key=(
                        f"fleet_refit_observed:{fleet_id}:"
                        f"{current.snapshot_id}:"
                        f"{','.join(str(ship.ship_id) for ship in after_ships)}"
                    ),
                    snapshot_id=current.snapshot_id,
                    game_date=current.game_date,
                    event_type="fleet_refit_observed",
                    fleet_id=fleet_id,
                    title=f"{fleet_name} Refit Observed",
                    body=(
                        f"Between the {previous.game_date} and {current.game_date} "
                        f"archived states, {len(after_ships)} surviving {vessel_word} "
                        f"in {fleet_name} changed their recorded ship design: "
                        f"{names}. Historian treats this as strong evidence of a "
                        "fleet refit or upgrade, but does not yet infer the exact "
                        "components changed."
                    ),
                    visible=True,
                    confidence="high",
                )
            )

    # Civilian/support designs often update together when empire technology
    # changes. Keep isolated changes quiet, but preserve a broad support-fleet
    # modernisation as one compact historical event.
    support_changes = [
        (before, after)
        for before, after in public_changes
        if after.ship_id not in published_ship_ids and _is_support_ship(after)
    ]

    if len(support_changes) >= 3:
        support_ships = [after for _, after in support_changes]
        published_ship_ids.update(ship.ship_id for ship in support_ships)

        events.append(
            _event(
                key=(
                    f"support_refit_wave:{current.snapshot_id}:"
                    f"{','.join(str(ship.ship_id) for ship in support_ships)}"
                ),
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                event_type="support_refit_wave_observed",
                title="Support Fleet Refit Wave Observed",
                body=(
                    f"Between the {previous.game_date} and {current.game_date} "
                    f"archived states, {len(support_ships)} surviving support "
                    f"vessels changed their recorded ship design: "
                    f"{_ship_name_summary(support_ships)}. Historian treats this "
                    "as strong evidence of a broad support-fleet refit or upgrade "
                    "wave, without inferring the exact components changed."
                ),
                visible=True,
                confidence="high",
            )
        )

    # Large military hulls are historically notable enough to publish even when
    # their refit is isolated. Routine single-corvette changes remain internal.
    for before, after in public_changes:
        if after.ship_id in published_ship_ids:
            continue

        if not _is_major_military_ship(current, after):
            continue

        events.append(
            _event(
                key=(
                    f"ship_refit_observed:{after.ship_id}:"
                    f"{current.snapshot_id}:{before.design_id}:{after.design_id}"
                ),
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                event_type="ship_refit_observed",
                ship_id=after.ship_id,
                fleet_id=after.fleet_id,
                title=f"{after.name} Refit Observed",
                body=(
                    f"Between the {previous.game_date} and {current.game_date} "
                    f"archived states, {after.name}'s recorded ship design "
                    "changed while it remained the same recorded vessel. "
                    "Historian treats this as strong evidence of a refit or "
                    "upgrade, but does not yet infer the exact components "
                    "changed."
                ),
                visible=True,
                confidence="high",
            )
        )

    return events
