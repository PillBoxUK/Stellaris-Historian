from __future__ import annotations

from .models import LeaderSnapshot, LeaderState

def _event(
    *,
    snapshot_id: int,
    game_date: str,
    leader_id: int,
    event_type: str,
    title: str,
    body: str,
    date_kind: str,
    confidence: str,
    visible: bool = False,
) -> dict:
    return {
        "event_key": (
            f"leader:{leader_id}:{event_type}:{game_date}:{snapshot_id}"
        ),
        "snapshot_id": snapshot_id,
        "game_date": game_date,
        "event_type": event_type,
        "leader_id": leader_id,
        "title": title,
        "body": body,
        # The raw career chronicle keeps every structured change, while the
        # journal publishes only events that are historically meaningful.
        "visible": int(visible),
        "confidence": confidence,
        "date_kind": date_kind,
    }


def _leader_class_label(raw: str | None) -> str:
    mapping = {
        "official": "Official",
        "scientist": "Scientist",
        "commander": "Commander",
        "envoy": "Envoy",
        "governor": "Governor",
        "admiral": "Admiral",
        "general": "General",
    }

    if raw in mapping:
        return mapping[raw]

    return (
        raw
        or "Leader"
    ).replace(
        "_",
        " ",
    ).title()


def _assignment_description(
    assignment: str | None,
) -> tuple[str | None, str | None]:
    if not assignment:
        return None, None

    prefixes = (
        ("Fleet: ", "fleet"),
        ("Science Ship: ", "science_ship"),
        ("Construction Ship: ", "construction_ship"),
        ("Colony Ship: ", "colony_ship"),
        ("Planet: ", "planet"),
    )

    for prefix, kind in prefixes:
        if assignment.startswith(prefix):
            return kind, assignment[len(prefix):]

    if assignment == "First Contact Assignment":
        return "first_contact", "First Contact duty"

    return "other", assignment


def _assignment_sentence(
    leader: LeaderState,
    *,
    date: str,
) -> str | None:
    kind, subject = _assignment_description(
        leader.assignment_name
    )

    if not kind or not subject:
        return None

    if kind == "fleet":
        if leader.leader_class in {
            "commander",
            "admiral",
            "general",
        }:
            return (
                f"By {date}, {leader.name} was recorded in command of "
                f"{subject}."
            )

        return (
            f"By {date}, {leader.name} was assigned to the fleet {subject}."
        )

    if kind == "science_ship":
        return (
            f"By {date}, {leader.name} was assigned to the science ship "
            f"{subject}."
        )

    if kind == "construction_ship":
        return (
            f"By {date}, {leader.name} was assigned to the construction ship "
            f"{subject}."
        )

    if kind == "colony_ship":
        return (
            f"By {date}, {leader.name} was assigned to the colony ship "
            f"{subject}."
        )

    if kind == "planet":
        return (
            f"By {date}, {leader.name} was assigned to {subject}."
        )

    if kind == "first_contact":
        return (
            f"By {date}, {leader.name} was assigned to First Contact duty."
        )

    return (
        f"By {date}, {leader.name}'s recorded assignment was {subject}."
    )


def _assignment_is_unresolved(
    leader: LeaderState,
) -> bool:
    return (
        leader.leader_class in {
            "commander",
            "admiral",
            "general",
        }
        and leader.location_type in {
            "fleet",
            "ship",
        }
        and leader.location_id is not None
        and leader.assignment_name is None
    )


def _unresolved_assignment_event(
    before: LeaderState,
    after: LeaderState,
    *,
    current: LeaderSnapshot,
) -> dict:
    """
    Preserve an ambiguous commander-assignment transition internally without
    turning it into narrative prose. The raw location type/ID remains present
    in the snapshot cache and leader registry evidence.
    """
    parts: list[str] = []

    if before.location_type and before.location_id is not None:
        parts.append(
            f"previous raw location {before.location_type}:{before.location_id}"
        )

    if after.location_type and after.location_id is not None:
        parts.append(
            f"current raw location {after.location_type}:{after.location_id}"
        )

    detail = (
        "; ".join(parts)
        if parts
        else "raw assignment evidence changed"
    )

    return _event(
        snapshot_id=current.snapshot_id,
        game_date=current.game_date,
        leader_id=after.leader_id,
        event_type="leader_assignment_unresolved",
        title=f"{after.name} Had an Unresolved Assignment Change",
        body=(
            f"By {current.game_date}, Historian detected a commander assignment "
            f"transition for {after.name}, but the available display name was "
            f"ambiguous and was not published as a fleet command ({detail})."
        ),
        date_kind="first_observed",
        confidence="low",
        visible=False,
    )


def _assignment_event(
    before: LeaderState,
    after: LeaderState,
    *,
    current: LeaderSnapshot,
) -> dict:
    after_kind, after_subject = _assignment_description(
        after.assignment_name
    )
    before_kind, before_subject = _assignment_description(
        before.assignment_name
    )

    if after_kind and after_subject:
        if (
            after_kind == "fleet"
            and after.leader_class in {
                "commander",
                "admiral",
                "general",
            }
        ):
            title = f"{after.name} Took Command of {after_subject}"
            body = (
                f"By {current.game_date}, {after.name} was recorded in command "
                f"of {after_subject}."
            )
        elif after_kind == "science_ship":
            title = f"{after.name} Assigned to {after_subject}"
            body = (
                f"By {current.game_date}, {after.name} was assigned to the "
                f"science ship {after_subject}."
            )
        elif after_kind == "planet":
            title = f"{after.name} Assigned to {after_subject}"
            body = (
                f"By {current.game_date}, {after.name} was recorded serving at "
                f"{after_subject}."
            )
        elif after_kind == "first_contact":
            title = f"{after.name} Assigned to First Contact Duty"
            body = (
                f"By {current.game_date}, {after.name} was recorded on a First "
                "Contact assignment."
            )
        else:
            title = f"{after.name} Received a New Assignment"
            body = (
                f"By {current.game_date}, {after.name}'s recorded assignment "
                f"was {after.assignment_name}."
            )
    else:
        title = f"{after.name}'s Assignment Ended"

        if before_subject:
            body = (
                f"By {current.game_date}, no active assignment was recorded for "
                f"{after.name}. The previous archived assignment was "
                f"{before.assignment_name}. The archive does not establish why "
                "the assignment ended."
            )
        else:
            body = (
                f"By {current.game_date}, no active assignment was recorded for "
                f"{after.name}."
            )

    return _event(
        snapshot_id=current.snapshot_id,
        game_date=current.game_date,
        leader_id=after.leader_id,
        event_type="leader_assignment_changed",
        title=title,
        body=body,
        date_kind="first_observed",
        confidence="high",
        visible=True,
    )


def _first_observed_event(
    leader: LeaderState,
    *,
    current: LeaderSnapshot,
    previous: LeaderSnapshot | None,
) -> dict:
    exact_recruitment = (
        leader.recruitment_date
        if leader.recruitment_date
        and leader.recruitment_date <= current.game_date
        and (
            previous is None
            or leader.recruitment_date > previous.game_date
        )
        else None
    )

    leader_role = _leader_class_label(
        leader.leader_class
    )

    assignment_sentence = _assignment_sentence(
        leader,
        date=current.game_date,
    )

    context: list[str] = []

    if leader.is_ruler:
        context.append(
            f"By {current.game_date}, {leader.name} was also recorded as the "
            "ruler of the state."
        )

    if leader.is_heir:
        context.append(
            f"By {current.game_date}, {leader.name} was also recorded as the "
            "designated heir."
        )

    if leader.council_role_name:
        context.append(
            f"By {current.game_date}, {leader.name} held the council role "
            f"{leader.council_role_name}."
        )

    if assignment_sentence:
        context.append(
            assignment_sentence
        )

    suffix = (
        " " + " ".join(context)
        if context
        else ""
    )

    if exact_recruitment:
        return _event(
            snapshot_id=current.snapshot_id,
            game_date=exact_recruitment,
            leader_id=leader.leader_id,
            event_type="leader_entered_service",
            title=f"{leader.name} Entered Service",
            body=(
                f"Stellaris records {leader.name} as entering service as a "
                f"{leader_role.lower()} on {exact_recruitment}. The first "
                f"surviving archived state containing this leader is dated "
                f"{current.game_date}.{suffix}"
            ),
            date_kind="exact_save_field",
            confidence="high",
            visible=True,
        )

    return _event(
        snapshot_id=current.snapshot_id,
        game_date=current.game_date,
        leader_id=leader.leader_id,
        event_type="leader_first_observed",
        title=f"{leader.name} Entered the Record",
        body=(
            f"{leader.name} first appears in the surviving archive by "
            f"{current.game_date} as a {leader_role.lower()}.{suffix}"
        ),
        date_kind="first_observed",
        confidence="medium",
        visible=True,
    )

def _change_events(
    before: LeaderState,
    after: LeaderState,
    *,
    current: LeaderSnapshot,
) -> list[dict]:
    events: list[dict] = []

    if (
        not before.is_ruler
        and after.is_ruler
    ):
        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_became_ruler",
                title=f"{after.name} Became Ruler",
                body=(
                    f"By {current.game_date}, {after.name} was recorded as "
                    "the ruler of the state."
                ),
                date_kind="first_observed",
                confidence="high",
                visible=True,
            )
        )

    if (
        before.is_ruler
        and not after.is_ruler
    ):
        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_left_rulership",
                title=f"{after.name}'s Rule Ended",
                body=(
                    f"By {current.game_date}, {after.name} was no longer "
                    "recorded as ruler. The archive alone does not establish "
                    "why the rulership ended."
                ),
                date_kind="first_observed",
                confidence="high",
                visible=True,
            )
        )

    if (
        not before.is_heir
        and after.is_heir
    ):
        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_became_heir",
                title=f"{after.name} Became Heir",
                body=(
                    f"By {current.game_date}, {after.name} was recorded as "
                    "the designated heir."
                ),
                date_kind="first_observed",
                confidence="high",
                visible=True,
            )
        )

    if (
        before.is_heir
        and not after.is_heir
    ):
        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_left_heirship",
                title=f"{after.name} Was No Longer Heir",
                body=(
                    f"By {current.game_date}, {after.name} was no longer "
                    "recorded as the designated heir. The archive does not "
                    "establish why."
                ),
                date_kind="first_observed",
                confidence="high",
                visible=True,
            )
        )

    assignment_changed = (
        before.assignment_name
        != after.assignment_name
        or before.location_type
        != after.location_type
        or before.location_id
        != after.location_id
    )

    if assignment_changed:
        unresolved = (
            _assignment_is_unresolved(
                before
            )
            or _assignment_is_unresolved(
                after
            )
        )

        if unresolved:
            events.append(
                _unresolved_assignment_event(
                    before,
                    after,
                    current=current,
                )
            )
        elif (
            before.assignment_name
            != after.assignment_name
            and (
                before.assignment_name
                or after.assignment_name
            )
        ):
            events.append(
                _assignment_event(
                    before,
                    after,
                    current=current,
                )
            )

    if (
        before.council_role_key
        != after.council_role_key
    ):
        if after.council_role_name:
            title = f"{after.name} Assumed the {after.council_role_name} Role"
            body = (
                f"By {current.game_date}, {after.name} was recorded in the "
                f"council role {after.council_role_name}."
            )
        else:
            title = f"{after.name}'s Council Service Changed"
            body = (
                f"By {current.game_date}, {after.name} was no longer recorded "
                f"in the previous council role {before.council_role_name or 'unknown'}. "
                "The archive does not establish why."
            )

        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_council_changed",
                title=title,
                body=body,
                date_kind="first_observed",
                confidence="high",
                visible=True,
            )
        )

    if (
        before.level is not None
        and after.level is not None
        and after.level != before.level
    ):
        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_level_changed",
                title=f"{after.name} Reached Level {after.level}",
                body=(
                    f"Between archived states, {after.name}'s recorded leader "
                    f"level changed from {before.level} to {after.level}."
                ),
                date_kind="between_snapshots",
                confidence="high",
                visible=False,
            )
        )

    before_traits = set(
        before.traits
    )

    gained_traits = [
        name
        for key, name in zip(
            after.traits,
            after.trait_names,
        )
        if key not in before_traits
    ]

    if gained_traits:
        label = (
            "New Trait"
            if len(gained_traits) == 1
            else "New Traits"
        )

        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_traits_gained",
                title=f"{after.name} Gained {label}",
                body=(
                    f"By {current.game_date}, the archive records "
                    f"{after.name} with newly observed trait"
                    f"{'s' if len(gained_traits) != 1 else ''}: "
                    f"{', '.join(gained_traits)}."
                ),
                date_kind="first_observed",
                confidence="high",
                visible=True,
            )
        )

    removed_traits = [
        name
        for key, name in zip(before.traits, before.trait_names)
        if key not in set(after.traits)
    ]
    if removed_traits:
        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type="leader_traits_removed",
                title=f"{after.name} Lost Recorded Trait Evidence",
                body=(
                    f"By {current.game_date}, the following previously recorded "
                    f"trait evidence was no longer attached to {after.name}: "
                    f"{', '.join(removed_traits)}."
                ),
                date_kind="first_observed",
                confidence="high",
                visible=False,
            )
        )

    deep_fields = (
        ("leader_class", "class", before.leader_class, after.leader_class),
        ("tier_key", "tier", before.tier_key, after.tier_key),
        ("species_id", "species", before.species_name or before.species_id, after.species_name or after.species_id),
        ("ethic_key", "ethic", before.ethic_name or before.ethic_key, after.ethic_name or after.ethic_key),
        ("job_key", "job", before.job_name or before.job_key, after.job_name or after.job_key),
        ("background_planet_id", "background world", before.background_planet_name or before.background_planet_id, after.background_planet_name or after.background_planet_id),
        ("portrait", "portrait", before.portrait, after.portrait),
    )
    for event_suffix, label, before_value, after_value in deep_fields:
        if before_value == after_value:
            continue
        if before_value is None and after_value is None:
            continue
        events.append(
            _event(
                snapshot_id=current.snapshot_id,
                game_date=current.game_date,
                leader_id=after.leader_id,
                event_type=f"leader_{event_suffix}_changed",
                title=f"{after.name} {label.title()} Evidence Changed",
                body=(
                    f"Between archived states, {after.name}'s recorded {label} "
                    f"changed from {before_value or 'not recorded'} to "
                    f"{after_value or 'not recorded'}."
                ),
                date_kind="between_snapshots",
                confidence="high",
                visible=False,
            )
        )

    return events

def leader_transition_data(
    previous: LeaderSnapshot | None,
    current: LeaderSnapshot,
    *,
    baseline: bool = False,
) -> dict:
    rows: list[dict] = []
    events: list[dict] = []

    previous_leaders = (
        previous.leaders
        if previous is not None
        else {}
    )

    for leader in current.leaders.values():
        rows.append(
            {
                "leader_id": leader.leader_id,
                "first_seen_date": current.game_date,
                "last_seen_date": current.game_date,
                "name": leader.name,
                "leader_class": leader.leader_class,
                "latest_level": leader.level,
                "latest_experience": leader.experience,
                "recruitment_date": leader.recruitment_date,
                "gender": leader.gender,
                "traits": leader.traits,
                "trait_names": leader.trait_names,
                "species_id": leader.species_id,
                "species_name": leader.species_name,
                "portrait": leader.portrait,
                "creator_country_id": leader.creator_country_id,
                "tier_key": leader.tier_key,
                "tier_name": leader.tier_name,
                "recorded_date": leader.recorded_date,
                "date_added": leader.date_added,
                "raw_age": leader.raw_age,
                "ethic_key": leader.ethic_key,
                "ethic_name": leader.ethic_name,
                "job_key": leader.job_key,
                "job_name": leader.job_name,
                "background_planet_id": leader.background_planet_id,
                "background_planet_name": leader.background_planet_name,
                "custom_description_key": leader.custom_description_key,
                "custom_description_name": leader.custom_description_name,
                "bonus_skill_level": leader.bonus_skill_level,
                "raw_record_keys": leader.raw_keys,
                "raw_flag_values": leader.flag_values,
                "raw_variable_values": leader.variable_values,
                "event_target_aliases": current.saved_event_target_names.get(leader.leader_id, ()),
                "death_date": None,
                "death_reason_key": None,
                "death_reason_value": None,
                "death_evidence_kind": None,
                "death_first_observed_date": None,
                "latest_assignment_type": leader.location_type,
                "latest_assignment_id": leader.location_id,
                "latest_assignment": leader.assignment_name,
                "latest_council_role": leader.council_role_name,
                "latest_is_ruler": int(
                    leader.is_ruler
                ),
                "ever_ruler": int(
                    leader.is_ruler
                ),
                "latest_is_heir": int(
                    leader.is_heir
                ),
                "ever_heir": int(
                    leader.is_heir
                ),
                "status": "present",
                "baseline_present": int(
                    baseline
                ),
                "first_snapshot_id": current.snapshot_id,
                "last_snapshot_id": current.snapshot_id,
            }
        )

        before = previous_leaders.get(
            leader.leader_id
        )

        if before is None:
            if not baseline:
                events.append(
                    _first_observed_event(
                        leader,
                        current=current,
                        previous=previous,
                    )
                )
        else:
            events.extend(
                _change_events(
                    before,
                    leader,
                    current=current,
                )
            )

    missing_ids = sorted(
        set(
            previous_leaders
        )
        - set(
            current.leaders
        )
    )

    dead_leader_updates: list[dict] = []

    for leader_id in missing_ids:
        before = previous_leaders[leader_id]
        dead = current.dead_leaders.get(leader_id)

        if dead is not None:
            exact_date = dead.death_date
            event_date = exact_date or current.game_date
            reason_text = None
            if dead.death_reason_key and dead.death_reason_value:
                reason_text = (
                    f" The retained dead-leader record also stores "
                    f"{dead.death_reason_key}={dead.death_reason_value}."
                )

            events.append(
                _event(
                    snapshot_id=current.snapshot_id,
                    game_date=event_date,
                    leader_id=leader_id,
                    event_type="leader_death_recorded",
                    title=f"{before.name} Recorded Dead",
                    body=(
                        f"A dead-leader record for {before.name} is present by "
                        f"{current.game_date}."
                        + (f" It explicitly records the death date as {exact_date}." if exact_date else " The exact death date is not retained in a dedicated death-date field.")
                        + (reason_text or " No explicit cause of death is retained in the parsed dead-leader fields.")
                    ),
                    date_kind=("exact_save_field" if exact_date else "first_observed"),
                    confidence=("high" if exact_date else "medium"),
                    visible=True,
                )
            )
            dead_leader_updates.append({
                "leader_id": leader_id,
                "status": "dead_confirmed",
                "death_date": exact_date,
                "death_reason_key": dead.death_reason_key,
                "death_reason_value": dead.death_reason_value,
                "death_evidence_kind": (
                    "explicit_dead_leader_with_death_date"
                    if exact_date else "dead_leader_record"
                ),
                "death_first_observed_date": current.game_date,
            })
        elif leader_id in current.tombstoned_leader_ids:
            events.append(
                _event(
                    snapshot_id=current.snapshot_id,
                    game_date=current.game_date,
                    leader_id=leader_id,
                    event_type="leader_tombstone_unconfirmed",
                    title=f"{before.name} Left the Active Leader Record",
                    body=(
                        f"By {current.game_date}, {before.name}'s active leader object was "
                        "replaced by a retained 'none' tombstone in the save. This proves "
                        "removal from the active leader database, but does not by itself "
                        "establish death, retirement, dismissal or execution."
                    ),
                    date_kind="first_observed",
                    confidence="high",
                    visible=True,
                )
            )
        else:
            events.append(
                _event(
                    snapshot_id=current.snapshot_id,
                    game_date=current.game_date,
                    leader_id=leader_id,
                    event_type="leader_missing_unconfirmed",
                    title=f"{before.name} Left the Surviving Record",
                    body=(
                        f"{before.name} is no longer present in the archived leader "
                        f"record by {current.game_date}. The archive does not establish why."
                    ),
                    date_kind="first_observed",
                    confidence="medium",
                    visible=True,
                )
            )

    missing_leader_statuses = []
    dead_ids = {int(row["leader_id"]) for row in dead_leader_updates}
    for leader_id in missing_ids:
        if leader_id in dead_ids:
            status = "dead_confirmed"
        elif leader_id in current.tombstoned_leader_ids:
            status = "tombstoned_unconfirmed"
        else:
            status = "missing_unconfirmed"
        missing_leader_statuses.append({
            "leader_id": leader_id,
            "status": status,
            "event_target_aliases": tuple(
                current.saved_event_target_names.get(leader_id, ())
            ),
        })

    return {
        "leaders": rows,
        "events": events,
        "missing_leader_ids": missing_ids,
        "missing_leader_statuses": missing_leader_statuses,
        "dead_leader_updates": dead_leader_updates,
    }


def derive_full_leader_history(
    snapshots: list[LeaderSnapshot],
) -> dict:
    if not snapshots:
        return {
            "leaders": [],
            "events": [],
        }

    registry: dict[
        int,
        dict,
    ] = {}

    events_by_key: dict[
        str,
        dict,
    ] = {}

    previous: LeaderSnapshot | None = None

    for index, snapshot in enumerate(
        snapshots
    ):
        delta = leader_transition_data(
            previous,
            snapshot,
            baseline=(index == 0),
        )

        for row in delta[
            "leaders"
        ]:
            leader_id = row[
                "leader_id"
            ]

            existing = registry.get(
                leader_id
            )

            if existing is None:
                registry[
                    leader_id
                ] = dict(
                    row
                )
            else:
                existing[
                    "last_seen_date"
                ] = row[
                    "last_seen_date"
                ]

                existing[
                    "name"
                ] = row[
                    "name"
                ]

                existing[
                    "leader_class"
                ] = row[
                    "leader_class"
                ]

                existing[
                    "latest_level"
                ] = row[
                    "latest_level"
                ]

                existing[
                    "latest_experience"
                ] = row[
                    "latest_experience"
                ]

                if (
                    not existing.get(
                        "recruitment_date"
                    )
                    and row.get(
                        "recruitment_date"
                    )
                ):
                    existing[
                        "recruitment_date"
                    ] = row[
                        "recruitment_date"
                    ]

                existing[
                    "gender"
                ] = row[
                    "gender"
                ]

                existing[
                    "traits"
                ] = row[
                    "traits"
                ]

                existing[
                    "trait_names"
                ] = row[
                    "trait_names"
                ]

                for field in (
                    "species_id", "species_name", "portrait", "creator_country_id",
                    "tier_key", "tier_name", "recorded_date", "date_added", "raw_age",
                    "ethic_key", "ethic_name", "job_key", "job_name",
                    "background_planet_id", "background_planet_name",
                    "custom_description_key", "custom_description_name",
                    "bonus_skill_level", "raw_record_keys", "raw_flag_values",
                    "raw_variable_values", "event_target_aliases",
                ):
                    if row.get(field) is not None:
                        existing[field] = row.get(field)

                existing[
                    "latest_assignment_type"
                ] = row[
                    "latest_assignment_type"
                ]

                existing[
                    "latest_assignment_id"
                ] = row[
                    "latest_assignment_id"
                ]

                existing[
                    "latest_assignment"
                ] = row[
                    "latest_assignment"
                ]

                existing[
                    "latest_council_role"
                ] = row[
                    "latest_council_role"
                ]

                existing[
                    "latest_is_ruler"
                ] = row[
                    "latest_is_ruler"
                ]

                existing[
                    "ever_ruler"
                ] = max(
                    existing.get(
                        "ever_ruler",
                        0,
                    ),
                    row[
                        "ever_ruler"
                    ],
                )

                existing[
                    "latest_is_heir"
                ] = row[
                    "latest_is_heir"
                ]

                existing[
                    "ever_heir"
                ] = max(
                    existing.get(
                        "ever_heir",
                        0,
                    ),
                    row[
                        "ever_heir"
                    ],
                )

                existing[
                    "status"
                ] = "present"

                existing[
                    "baseline_present"
                ] = max(
                    existing.get(
                        "baseline_present",
                        0,
                    ),
                    row[
                        "baseline_present"
                    ],
                )

                existing[
                    "last_snapshot_id"
                ] = row[
                    "last_snapshot_id"
                ]

        dead_ids = {int(row["leader_id"]) for row in delta.get("dead_leader_updates", [])}
        tombstone_ids = set(snapshot.tombstoned_leader_ids)

        for missing_id in delta[
            "missing_leader_ids"
        ]:
            if missing_id in registry:
                if missing_id in dead_ids:
                    status = "dead_confirmed"
                elif missing_id in tombstone_ids:
                    status = "tombstoned_unconfirmed"
                else:
                    status = "missing_unconfirmed"
                registry[missing_id]["status"] = status
                aliases = snapshot.saved_event_target_names.get(missing_id)
                if aliases:
                    existing_aliases = set(registry[missing_id].get("event_target_aliases") or ())
                    registry[missing_id]["event_target_aliases"] = tuple(sorted(existing_aliases | set(aliases)))
                registry[missing_id]["latest_is_ruler"] = 0
                registry[missing_id]["latest_is_heir"] = 0

        for update in delta.get("dead_leader_updates", []):
            leader_id = int(update["leader_id"])
            if leader_id not in registry:
                continue
            registry[leader_id].update({
                "status": update.get("status", "dead_confirmed"),
                "death_date": update.get("death_date"),
                "death_reason_key": update.get("death_reason_key"),
                "death_reason_value": update.get("death_reason_value"),
                "death_evidence_kind": update.get("death_evidence_kind"),
                "death_first_observed_date": update.get("death_first_observed_date"),
            })

        for event in delta[
            "events"
        ]:
            events_by_key[
                event[
                    "event_key"
                ]
            ] = event

        previous = snapshot

    return {
        "leaders": sorted(
            registry.values(),
            key=lambda row: (
                -int(
                    row.get(
                        "baseline_present",
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
                    "leader_id"
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
