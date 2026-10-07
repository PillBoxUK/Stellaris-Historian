from __future__ import annotations

from .identity import (
    _adjacent_fleet_matches,
    _fleet_signature,
    _meaningful_fleet_name,
)
from .models import FleetState, ShipFleetSnapshot, ShipState
from .provenance import (
    _build_location_provenance,
    _build_location_sentence,
    _build_provenance_allowed,
    _is_living_or_biological_vessel,
    _usable_exact_construction_date,
)
from .refits import derive_refit_events


def _military_fleet(
    fleet: FleetState | None,
) -> bool:
    if fleet is None:
        return False

    return (
        fleet.ship_class == "shipclass_military"
        or len(fleet.ship_ids) > 1
    )


def _ship_row(
    ship: ShipState,
    snapshot: ShipFleetSnapshot,
    *,
    baseline_present: bool,
) -> dict:
    return {
        "ship_id": ship.ship_id,
        "first_seen_date": snapshot.game_date,
        "last_seen_date": snapshot.game_date,
        "construction_date": ship.construction_date,
        "name": ship.name,
        "ship_type": ship.ship_type,
        "opening_name": ship.name if baseline_present else None,
        "opening_ship_type": ship.ship_type if baseline_present else None,
        "opening_construction_date": ship.construction_date if baseline_present else None,
        "opening_fleet_id": ship.fleet_id if baseline_present else None,
        "opening_fleet_name": ship.fleet_name if baseline_present else None,
        "opening_commander_id": ship.commander_id if baseline_present else None,
        "opening_commander_name": ship.commander_name if baseline_present else None,
        "latest_fleet_id": ship.fleet_id,
        "latest_fleet_name": ship.fleet_name,
        "latest_commander_id": ship.commander_id,
        "latest_commander_name": ship.commander_name,
        "status": "present",
        "baseline_present": 1 if baseline_present else 0,
        "first_snapshot_id": snapshot.snapshot_id,
        "last_snapshot_id": snapshot.snapshot_id,
    }


def _fleet_row(
    fleet: FleetState,
    snapshot: ShipFleetSnapshot,
    *,
    baseline_present: bool,
) -> dict:
    return {
        "fleet_id": fleet.fleet_id,
        "first_seen_date": snapshot.game_date,
        "last_seen_date": snapshot.game_date,
        "name": fleet.name,
        "ship_class": fleet.ship_class,
        "opening_name": fleet.name if baseline_present else None,
        "opening_ship_class": fleet.ship_class if baseline_present else None,
        "opening_ship_count": len(fleet.ship_ids) if baseline_present else None,
        "opening_home_base": fleet.home_base if baseline_present else None,
        "opening_commander_id": fleet.commander_id if baseline_present else None,
        "opening_commander_name": fleet.commander_name if baseline_present else None,
        "latest_ship_count": len(
            fleet.ship_ids
        ),
        "latest_home_base": fleet.home_base,
        "latest_commander_id": fleet.commander_id,
        "latest_commander_name": fleet.commander_name,
        "status": "present",
        "baseline_present": 1 if baseline_present else 0,
        "first_snapshot_id": snapshot.snapshot_id,
        "last_snapshot_id": snapshot.snapshot_id,
    }


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
    visible: bool = True,
    confidence: str = "high",
    date_kind: str = "between_snapshots",
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
        "date_kind": date_kind,
    }


def _commission_event(
    ship: ShipState,
    current: ShipFleetSnapshot,
    *,
    record_start_date: str,
    build_provenance: dict | None = None,
) -> dict:
    living = _is_living_or_biological_vessel(
        ship
    )

    exact = (
        not living
        and _usable_exact_construction_date(
            ship.construction_date,
            record_start_date=record_start_date,
            observed_date=current.game_date,
        )
    )

    build_phrase, inference_sentence = _build_location_sentence(
        build_provenance
    )

    details = []

    if build_phrase:
        details.append(
            build_phrase
        )

    if (
        ship.fleet_name
        and _meaningful_fleet_name(
            ship.fleet_name
        )
    ):
        details.append(
            f"assigned to {ship.fleet_name}"
        )

    suffix = (
        ", " + ", ".join(details)
        if details
        else ""
    )

    if exact:
        event_date = ship.construction_date
        body = (
            f"The {ship.ship_type.lower()} {ship.name} entered service "
            f"on {event_date}{suffix}."
        )
        title = (
            f"{ship.ship_type} {ship.name} Commissioned"
        )
        event_type = "ship_commissioned"
        event_key_prefix = "ship_commissioned"
        date_kind = "exact_save_field"
        confidence = "high"
    else:
        event_date = current.game_date

        if living:
            subject = (
                ship.ship_type
                if ship.ship_type
                and ship.ship_type != "Military Vessel"
                else "living vessel"
            )

            body = (
                f"The {subject.lower()} {ship.name} first appears among the "
                f"recorded vessels by {event_date}{suffix}."
            )

            if ship.construction_date:
                body += (
                    " Stellaris stores an earlier raw vessel date for this "
                    "entity; Historian preserves that value internally but "
                    "does not interpret it as a commissioning date for a "
                    "living vessel."
                )
        else:
            body = (
                f"{ship.name} first appears in the surviving archive by "
                f"{event_date}{suffix}."
            )

            if ship.construction_date:
                body += (
                    " The save contains a recorded vessel date outside the "
                    "surviving campaign chronology, so Historian preserves it "
                    "without treating it as a commissioning date."
                )
            else:
                body += (
                    " Stellaris did not expose a usable exact construction "
                    "date in this record."
                )

        title = f"{ship.name} Entered the Record"
        event_type = "ship_first_observed"
        event_key_prefix = "ship_first_observed"
        date_kind = "first_observed"
        confidence = "medium"

    if inference_sentence:
        body += (
            " " + inference_sentence
        )

    return _event(
        key=f"{event_key_prefix}:{ship.ship_id}:{event_date}",
        snapshot_id=current.snapshot_id,
        game_date=event_date,
        event_type=event_type,
        ship_id=ship.ship_id,
        fleet_id=ship.fleet_id,
        title=title,
        body=body,
        visible=True,
        confidence=confidence,
        date_kind=date_kind,
    )


def derive_full_history(
    snapshots: list[ShipFleetSnapshot],
) -> dict:
    ships: dict[int, dict] = {}
    fleets: dict[int, dict] = {}
    events: list[dict] = []
    build_provenance: dict[int, dict] = {}

    if not snapshots:
        return {
            "ships": [],
            "fleets": [],
            "events": [],
            "build_provenance": [],
        }

    previous: ShipFleetSnapshot | None = None
    record_start_date = snapshots[0].game_date

    # Narrative identity is not the same as Stellaris' internal fleet ID.
    # Fleet IDs can be destroyed/recreated during merges and reorganisations.
    seen_fleet_signatures: set[
        tuple[str, str]
    ] = set()

    for index, current in enumerate(
        snapshots
    ):
        baseline = index == 0

        for ship in current.ships.values():
            if ship.ship_id not in ships:
                ships[
                    ship.ship_id
                ] = _ship_row(
                    ship,
                    current,
                    baseline_present=baseline,
                )
            else:
                row = ships[
                    ship.ship_id
                ]

                row.update(
                    {
                        "last_seen_date": current.game_date,
                        "name": ship.name,
                        "ship_type": ship.ship_type,
                        "latest_fleet_id": ship.fleet_id,
                        "latest_fleet_name": ship.fleet_name,
                        "latest_commander_id": ship.commander_id,
                        "latest_commander_name": ship.commander_name,
                        "status": "present",
                        "last_snapshot_id": current.snapshot_id,
                    }
                )

                if (
                    not row.get(
                        "construction_date"
                    )
                    and ship.construction_date
                ):
                    row[
                        "construction_date"
                    ] = ship.construction_date

        for fleet in current.fleets.values():
            if fleet.fleet_id not in fleets:
                fleets[
                    fleet.fleet_id
                ] = _fleet_row(
                    fleet,
                    current,
                    baseline_present=baseline,
                )
            else:
                row = fleets[
                    fleet.fleet_id
                ]

                row.update(
                    {
                        "last_seen_date": current.game_date,
                        "name": fleet.name,
                        "ship_class": fleet.ship_class,
                        "latest_ship_count": len(
                            fleet.ship_ids
                        ),
                        "latest_home_base": fleet.home_base,
                        "latest_commander_id": fleet.commander_id,
                        "latest_commander_name": fleet.commander_name,
                        "status": "present",
                        "last_snapshot_id": current.snapshot_id,
                    }
                )

        if baseline:
            for fleet in current.fleets.values():
                signature = _fleet_signature(
                    fleet
                )

                if signature is not None:
                    seen_fleet_signatures.add(
                        signature
                    )

        if previous is not None:
            fleet_matches = _adjacent_fleet_matches(
                previous,
                current,
            )

            new_ship_ids = (
                set(current.ships)
                - set(previous.ships)
            )

            for ship_id in sorted(
                new_ship_ids
            ):
                new_ship = current.ships[
                    ship_id
                ]

                provenance = None

                if _build_provenance_allowed(
                    new_ship,
                    record_start_date=record_start_date,
                    observed_date=current.game_date,
                ):
                    provenance = _build_location_provenance(
                        new_ship,
                        previous=previous,
                        current=current,
                        fleet_matches=fleet_matches,
                    )

                if provenance is not None:
                    build_provenance[
                        ship_id
                    ] = provenance

                events.append(
                    _commission_event(
                        new_ship,
                        current,
                        record_start_date=record_start_date,
                        build_provenance=provenance,
                    )
                )

            missing_ship_ids = (
                set(previous.ships)
                - set(current.ships)
            )

            for ship_id in sorted(
                missing_ship_ids
            ):
                previous_ship = previous.ships[
                    ship_id
                ]

                if ship_id in ships:
                    ships[
                        ship_id
                    ][
                        "status"
                    ] = "missing_unconfirmed"

                events.append(
                    _event(
                        key=(
                            f"ship_missing:{ship_id}:"
                            f"{current.snapshot_id}"
                        ),
                        snapshot_id=current.snapshot_id,
                        game_date=current.game_date,
                        event_type="ship_missing_unconfirmed",
                        ship_id=ship_id,
                        fleet_id=previous_ship.fleet_id,
                        title=f"{previous_ship.name} No Longer Observed",
                        body=(
                            f"{previous_ship.name} is absent from the "
                            f"{current.game_date} snapshot. Historian does not "
                            "treat this alone as proof of destruction."
                        ),
                        visible=False,
                        confidence="low",
                        date_kind="between_snapshots",
                    )
                )

            matched_current_ids = set(
                fleet_matches
            )

            for fleet_id in sorted(
                set(current.fleets)
                - matched_current_ids
            ):
                fleet = current.fleets[
                    fleet_id
                ]

                if not _military_fleet(
                    fleet
                ):
                    continue

                signature = _fleet_signature(
                    fleet
                )

                # Never publish unresolved/generated placeholders. Also do not
                # announce the same named/classed fleet twice simply because
                # Stellaris created a new internal fleet ID later.
                if (
                    signature is None
                    or signature in seen_fleet_signatures
                ):
                    continue

                events.append(
                    _event(
                        key=(
                            "fleet_first_observed:"
                            f"{signature[0]}:{signature[1]}:"
                            f"{current.snapshot_id}"
                        ),
                        snapshot_id=current.snapshot_id,
                        game_date=current.game_date,
                        event_type="fleet_first_observed",
                        fleet_id=fleet_id,
                        title=f"{fleet.name} Entered the Record",
                        body=(
                            f"{fleet.name} first appears as a military fleet "
                            f"in the surviving archive by {current.game_date}, "
                            f"with {len(fleet.ship_ids)} vessel(s)."
                        ),
                        visible=True,
                        confidence="medium",
                        date_kind="first_observed",
                    )
                )

            # Compare logical fleet continuations, including pairs where the
            # internal Stellaris fleet ID changed.
            for current_id, previous_id in sorted(
                fleet_matches.items()
            ):
                before = previous.fleets[
                    previous_id
                ]
                after = current.fleets[
                    current_id
                ]

                meaningful_name = _meaningful_fleet_name(
                    after.name
                )

                if (
                    meaningful_name
                    and _military_fleet(
                        after
                    )
                ):
                    added = (
                        set(after.ship_ids)
                        - set(before.ship_ids)
                    )

                    if added:
                        names = [
                            current.ships[
                                ship_id
                            ].name
                            for ship_id in sorted(
                                added
                            )
                            if ship_id in current.ships
                        ]

                        label = (
                            ", ".join(names)
                            if names
                            else f"{len(added)} vessel(s)"
                        )

                        events.append(
                            _event(
                                key=(
                                    f"fleet_reinforced:{current_id}:"
                                    f"{current.snapshot_id}:"
                                    f"{','.join(str(x) for x in sorted(added))}"
                                ),
                                snapshot_id=current.snapshot_id,
                                game_date=current.game_date,
                                event_type="fleet_reinforced",
                                fleet_id=current_id,
                                title=f"{after.name} Reinforced",
                                body=(
                                    f"Between the {previous.game_date} and "
                                    f"{current.game_date} archived states, "
                                    f"{label} joined {after.name}."
                                ),
                                visible=True,
                                confidence="high",
                                date_kind="between_snapshots",
                            )
                        )

                if (
                    meaningful_name
                    and before.home_base
                    and after.home_base
                    and before.home_base != after.home_base
                ):
                    events.append(
                        _event(
                            key=(
                                f"fleet_home_base:{current_id}:"
                                f"{current.snapshot_id}"
                            ),
                            snapshot_id=current.snapshot_id,
                            game_date=current.game_date,
                            event_type="fleet_home_base_changed",
                            fleet_id=current_id,
                            title=f"{after.name} Rebased",
                            body=(
                                f"By {current.game_date}, {after.name}'s "
                                f"recorded home base had changed from "
                                f"{before.home_base} to {after.home_base}."
                            ),
                            visible=True,
                            confidence="high",
                            date_kind="first_observed",
                        )
                    )

                if (
                    meaningful_name
                    and after.commander_id is not None
                    and after.commander_id
                    != before.commander_id
                ):
                    commander = (
                        after.commander_name
                        or f"Leader {after.commander_id}"
                    )

                    events.append(
                        _event(
                            key=(
                                f"fleet_commander:{current_id}:"
                                f"{after.commander_id}:"
                                f"{current.snapshot_id}"
                            ),
                            snapshot_id=current.snapshot_id,
                            game_date=current.game_date,
                            event_type="fleet_commander_changed",
                            fleet_id=current_id,
                            title=f"{commander} Took Command of {after.name}",
                            body=(
                                f"By {current.game_date}, {commander} was "
                                f"recorded in command of {after.name}."
                            ),
                            visible=True,
                            confidence="high",
                            date_kind="first_observed",
                        )
                    )

            events.extend(
                derive_refit_events(
                    previous,
                    current,
                )
            )

            for ship_id in sorted(
                set(current.ships)
                & set(previous.ships)
            ):
                before = previous.ships[
                    ship_id
                ]
                after = current.ships[
                    ship_id
                ]

                if (
                    before.fleet_id is not None
                    and after.fleet_id is not None
                    and before.fleet_id != after.fleet_id
                ):
                    from_name = (
                        before.fleet_name
                        if _meaningful_fleet_name(
                            before.fleet_name
                        )
                        else "an unnamed fleet"
                    )

                    to_name = (
                        after.fleet_name
                        if _meaningful_fleet_name(
                            after.fleet_name
                        )
                        else "an unnamed fleet"
                    )

                    events.append(
                        _event(
                            key=(
                                f"ship_transfer:{ship_id}:"
                                f"{current.snapshot_id}:"
                                f"{before.fleet_id}:{after.fleet_id}"
                            ),
                            snapshot_id=current.snapshot_id,
                            game_date=current.game_date,
                            event_type="ship_transferred",
                            ship_id=ship_id,
                            fleet_id=after.fleet_id,
                            title=f"{after.name} Transferred",
                            body=(
                                f"{after.name} moved from {from_name} to "
                                f"{to_name} between archived states."
                            ),
                            visible=False,
                            confidence="high",
                            date_kind="between_snapshots",
                        )
                    )

        for fleet in current.fleets.values():
            signature = _fleet_signature(
                fleet
            )

            if signature is not None:
                seen_fleet_signatures.add(
                    signature
                )

        previous = current

    final = snapshots[-1]

    for ship_id in final.ships:
        if ship_id in ships:
            ships[
                ship_id
            ][
                "status"
            ] = "present"

    for fleet_id in final.fleets:
        if fleet_id in fleets:
            fleets[
                fleet_id
            ][
                "status"
            ] = "present"

    return {
        "ships": list(
            ships.values()
        ),
        "fleets": list(
            fleets.values()
        ),
        "events": events,
        "build_provenance": list(
            build_provenance.values()
        ),
    }


def transition_data(
    previous: ShipFleetSnapshot | None,
    current: ShipFleetSnapshot,
    *,
    baseline: bool,
) -> dict:
    """
    Small incremental view used by Update History.
    Registry first-seen values are preserved by DB upserts.
    """
    full = derive_full_history(
        (
            [current]
            if previous is None
            else [previous, current]
        )
    )

    if previous is not None:
        # Rows derived from [previous,current] would otherwise look like they
        # were first seen at the previous snapshot. For incremental upserts
        # only return current rows so the DB preserves the campaign's existing
        # first-seen values.
        ship_rows = [
            _ship_row(
                ship,
                current,
                baseline_present=baseline,
            )
            for ship in current.ships.values()
        ]

        fleet_rows = [
            _fleet_row(
                fleet,
                current,
                baseline_present=baseline,
            )
            for fleet in current.fleets.values()
        ]

        full[
            "ships"
        ] = ship_rows

        full[
            "fleets"
        ] = fleet_rows

        full[
            "missing_ship_ids"
        ] = list(
            set(previous.ships)
            - set(current.ships)
        )

        full[
            "missing_fleet_ids"
        ] = list(
            set(previous.fleets)
            - set(current.fleets)
        )
    else:
        full[
            "missing_ship_ids"
        ] = []

        full[
            "missing_fleet_ids"
        ] = []

    return full
