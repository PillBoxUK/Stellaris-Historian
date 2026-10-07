from __future__ import annotations

from collections import Counter
from pathlib import Path

from .models import LeaderSnapshot


_MAPPED_ACTIVE_KEYS = {
    "name",
    "species",
    "portrait",
    "gender",
    "country",
    "creator",
    "class",
    "tier",
    "experience",
    "location",
    "council_location",
    "leader_flags",
    "date",
    "date_added",
    "recruitment_date",
    "age",
    "flags",
    "variables",
    "ethic",
    "background_planet",
    "custom_description",
    "design",
    "traits",
    "level",
    "bonus_skill_level",
    "job",
}


def _stellaris_ordinal(value: str | None) -> int | None:
    if not value:
        return None
    try:
        year, month, day = (int(part) for part in value.split("."))
    except (TypeError, ValueError):
        return None
    if month < 1 or day < 1:
        return None
    return year * 360 + (month - 1) * 30 + (day - 1)


def _service_span(recruitment: str | None, last_seen: str | None) -> str:
    start = _stellaris_ordinal(recruitment)
    end = _stellaris_ordinal(last_seen)
    if start is None or end is None or end < start:
        return "Not calculable"
    days = end - start
    years, rem = divmod(days, 360)
    months, day = divmod(rem, 30)
    return f"{years}y {months}m {day}d confirmed through last presence"


def character_evidence_summary(snapshots: list[LeaderSnapshot], leader_history: dict) -> dict:
    leaders = leader_history.get("leaders", [])
    dead_records = sum(len(snapshot.dead_leaders) for snapshot in snapshots)
    death_events = [
        event for event in leader_history.get("events", [])
        if event.get("event_type") == "leader_death_recorded"
    ]
    return {
        "leaders": len(leaders),
        "snapshots": len(snapshots),
        "dead_records": dead_records,
        "confirmed_death_events": len(death_events),
        "tombstone_observations": sum(len(snapshot.tombstoned_leader_ids) for snapshot in snapshots),
        "leaders_with_species": sum(bool(row.get("species_name") or row.get("species_id")) for row in leaders),
        "leaders_with_portrait": sum(bool(row.get("portrait")) for row in leaders),
        "leaders_with_tier": sum(bool(row.get("tier_key")) for row in leaders),
        "leaders_with_ethic": sum(bool(row.get("ethic_key")) for row in leaders),
        "leaders_with_background": sum(bool(row.get("background_planet_name") or row.get("background_planet_id")) for row in leaders),
        "leaders_with_custom_description": sum(bool(row.get("custom_description_key")) for row in leaders),
    }


def write_character_evidence_diagnostic(
    archive_dir: Path,
    snapshots: list[LeaderSnapshot],
    leader_history: dict,
) -> Path:
    base = Path(archive_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "Character_Evidence_Debug.txt"
    summary = character_evidence_summary(snapshots, leader_history)

    events_by_leader: dict[int, list[dict]] = {}
    for event in leader_history.get("events", []):
        events_by_leader.setdefault(int(event.get("leader_id", -1)), []).append(event)

    lines = [
        "STELLARIS HISTORIAN - CHARACTER EVIDENCE DEBUG",
        "",
        "Purpose: preserve deeper leader/character evidence before presentation cleanup.",
        "Recorded date and raw age fields are stored exactly as save evidence and are NOT interpreted as birth dates/ages unless a future explicit field proves that meaning.",
        "A disappearance remains unconfirmed unless retained death evidence supports it. Valid sources include an explicit dead_leader record or a validated retained LEADER_DEATH notification uniquely naming the exiting leader.",
        "",
        f"Snapshots analysed: {summary['snapshots']}",
        f"Unique player leaders: {summary['leaders']}",
        f"dead_leader records observed across snapshots: {summary['dead_records']}",
        f"Confirmed death transitions from retained death evidence: {summary['confirmed_death_events']}",
        f"Leader tombstone observations (=none): {summary['tombstone_observations']}",
        f"Leaders with species evidence: {summary['leaders_with_species']}",
        f"Leaders with portrait evidence: {summary['leaders_with_portrait']}",
        f"Leaders with tier evidence: {summary['leaders_with_tier']}",
        f"Leaders with ethic evidence: {summary['leaders_with_ethic']}",
        f"Leaders with background-world evidence: {summary['leaders_with_background']}",
        f"Leaders with custom-description evidence: {summary['leaders_with_custom_description']}",
        "",
        "CHARACTER REGISTER",
        "==================",
        "",
    ]

    for row in leader_history.get("leaders", []):
        leader_id = int(row.get("leader_id", -1))
        leader_events = events_by_leader.get(leader_id, [])
        assignment_events = [e for e in leader_events if e.get("event_type") == "leader_assignment_changed"]
        trait_events = [e for e in leader_events if e.get("event_type") in {"leader_traits_gained", "leader_traits_removed"}]
        level_events = [e for e in leader_events if e.get("event_type") == "leader_level_changed"]
        council_events = [e for e in leader_events if e.get("event_type") == "leader_council_changed"]
        ruler_events = [e for e in leader_events if e.get("event_type") in {"leader_became_ruler", "leader_left_rulership", "leader_became_heir", "leader_left_heirship"}]

        lines.extend([
            f"{row.get('name') or 'Unknown'} | Leader ID {leader_id}",
            f"  Class: {row.get('leader_class') or 'Unknown'}",
            f"  First seen: {row.get('first_seen_date') or 'Unknown'}",
            f"  Last confirmed present: {row.get('last_seen_date') or 'Unknown'}",
            f"  Recruitment date: {row.get('recruitment_date') or 'Not recorded'}",
            f"  Confirmed service span: {_service_span(row.get('recruitment_date'), row.get('last_seen_date'))}",
            f"  Status: {row.get('status') or 'Unknown'}",
            f"  Species: {row.get('species_name') or row.get('species_id') or 'Not recorded'}",
            f"  Portrait: {row.get('portrait') or 'Not recorded'}",
            f"  Gender: {row.get('gender') or 'Not recorded'}",
            f"  Tier: {row.get('tier_name') or row.get('tier_key') or 'Not recorded'}",
            f"  Ethic: {row.get('ethic_name') or row.get('ethic_key') or 'Not recorded'}",
            f"  Job: {row.get('job_name') or row.get('job_key') or 'Not recorded'}",
            f"  Background world: {row.get('background_planet_name') or row.get('background_planet_id') or 'Not recorded'}",
            f"  Custom description key: {row.get('custom_description_key') or 'Not recorded'}",
            f"  Recorded raw date: {row.get('recorded_date') or 'Not recorded'}",
            f"  Date added: {row.get('date_added') or 'Not recorded'}",
            f"  Raw age field: {row.get('raw_age') if row.get('raw_age') is not None else 'Not recorded'}",
            f"  Latest level: {row.get('latest_level') if row.get('latest_level') is not None else 'Not recorded'}",
            f"  Bonus skill level: {row.get('bonus_skill_level') if row.get('bonus_skill_level') is not None else 'Not recorded'}",
            f"  Latest assignment: {row.get('latest_assignment') or 'Not recorded'}",
            f"  Latest council role: {row.get('latest_council_role') or 'Not recorded'}",
            f"  Ever ruler: {'yes' if int(row.get('ever_ruler', 0) or 0) else 'no'}",
            f"  Ever heir: {'yes' if int(row.get('ever_heir', 0) or 0) else 'no'}",
            f"  Latest traits: {', '.join(row.get('trait_names') or ()) or 'None recorded'}",
            f"  Assignment changes: {len(assignment_events)}",
            f"  Trait change events: {len(trait_events)}",
            f"  Level change events: {len(level_events)}",
            f"  Council change events: {len(council_events)}",
            f"  Ruler/heir change events: {len(ruler_events)}",
            f"  Death date: {row.get('death_date') or 'Not established'}",
            f"  Death reason field: {row.get('death_reason_key') or 'Not established'}",
            f"  Death reason value: {row.get('death_reason_value') or 'Not established'}",
            f"  Death evidence: {row.get('death_evidence_kind') or 'None'}",
            f"  Retained event-target aliases: {', '.join(row.get('event_target_aliases') or ()) or 'None'}",
            f"  First observed dead: {row.get('death_first_observed_date') or 'Not established'}",
            f"  Raw record keys retained: {', '.join(row.get('raw_record_keys') or ()) or 'None'}",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def write_raw_evidence_probe(
    archive_dir: Path,
    snapshots: list[LeaderSnapshot],
) -> Path:
    base = Path(archive_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "Raw_Evidence_Probe.txt"

    active_keys: set[str] = set()
    flag_keys: set[str] = set()
    variable_keys: set[str] = set()
    dead_keys: set[str] = set()
    dead_dates: list[tuple[str, int, str]] = []
    dead_reasons: list[tuple[str, int, str, str]] = []
    notification_values: list[int] = []
    event_values: list[int] = []
    selection_counts: list[int] = []
    tombstone_observations = 0
    event_target_aliases: dict[int, set[str]] = {}

    for snapshot in snapshots:
        active_keys.update(snapshot.active_record_keys)
        flag_keys.update(snapshot.active_flag_keys)
        variable_keys.update(snapshot.active_variable_keys)
        dead_keys.update(snapshot.dead_record_keys)
        if snapshot.last_notification_id is not None:
            notification_values.append(snapshot.last_notification_id)
        if snapshot.last_event_id is not None:
            event_values.append(snapshot.last_event_id)
        selection_counts.append(snapshot.selected_player_event_count)
        tombstone_observations += len(snapshot.tombstoned_leader_ids)
        for leader_id, names in snapshot.saved_event_target_names.items():
            event_target_aliases.setdefault(leader_id, set()).update(names)
        for dead in snapshot.dead_leaders.values():
            if dead.death_date:
                dead_dates.append((snapshot.game_date, dead.leader_id, dead.death_date))
            if dead.death_reason_key and dead.death_reason_value:
                dead_reasons.append((snapshot.game_date, dead.leader_id, dead.death_reason_key, dead.death_reason_value))

    unmapped = sorted(active_keys - _MAPPED_ACTIVE_KEYS)

    lines = [
        "STELLARIS HISTORIAN - RAW EVIDENCE PROBE",
        "",
        "Purpose: inventory raw character-related save fields so future patches can exploit evidence Historian does not yet interpret.",
        "This file is discovery output. A field appearing here does not by itself establish historical meaning.",
        "",
        f"Snapshots analysed: {len(snapshots)}",
        f"Active leader top-level keys seen: {len(active_keys)}",
        f"Unmapped active leader top-level keys: {len(unmapped)}",
        f"Leader flag keys seen: {len(flag_keys)}",
        f"Leader variable keys seen: {len(variable_keys)}",
        f"dead_leader top-level keys seen: {len(dead_keys)}",
        f"Snapshots containing any dead_leader record: {sum(bool(s.dead_leaders) for s in snapshots)}",
        f"Leader tombstone observations (=none): {tombstone_observations}",
        f"Leader IDs with retained saved_event_target aliases: {len(event_target_aliases)}",
        "",
        "ACTIVE LEADER RECORD KEYS",
        "-------------------------",
        ", ".join(sorted(active_keys)) or "None",
        "",
        "CURRENTLY UNMAPPED ACTIVE LEADER KEYS",
        "-------------------------------------",
        ", ".join(unmapped) or "None - all observed top-level keys are recognized by the v0.0.42 parser.",
        "",
        "LEADER FLAG KEYS",
        "----------------",
        ", ".join(sorted(flag_keys)) or "None",
        "",
        "LEADER VARIABLE KEYS",
        "--------------------",
        ", ".join(sorted(variable_keys)) or "None",
        "",
        "RETAINED LEADER EVENT-TARGET ALIASES",
        "------------------------------------",
        *(
            [f"{leader_id}: {', '.join(sorted(names))}" for leader_id, names in sorted(event_target_aliases.items())]
            if event_target_aliases else ["None"]
        ),
        "",
        "DEAD LEADER RECORD KEYS",
        "-----------------------",
        ", ".join(sorted(dead_keys)) or "No dead_leader record fields observed in this campaign.",
        "",
        "DEATH-SPECIFIC RAW FIELDS",
        "-------------------------",
    ]

    if dead_dates:
        for observed, leader_id, death_date in dead_dates:
            lines.append(f"{observed} | Leader {leader_id} | explicit death date {death_date}")
    else:
        lines.append("No explicit death-date field was observed in dead_leader records.")

    if dead_reasons:
        for observed, leader_id, key, value in dead_reasons:
            lines.append(f"{observed} | Leader {leader_id} | {key}={value}")
    else:
        lines.append("No explicit death/cause/reason field was observed in dead_leader records.")

    lines.extend([
        "",
        "EVENT / NOTIFICATION PERSISTENCE PROBE",
        "--------------------------------------",
        f"last_notification_id range: {min(notification_values) if notification_values else 'Not observed'} -> {max(notification_values) if notification_values else 'Not observed'}",
        f"last_event_id range: {min(event_values) if event_values else 'Not observed'} -> {max(event_values) if event_values else 'Not observed'}",
        f"open_player_event_selection_history selections: min {min(selection_counts) if selection_counts else 0}, max {max(selection_counts) if selection_counts else 0}",
        "These counters prove that event/notification state exists in the save, but v0.0.42 does not claim the visible notification text can yet be reconstructed from them.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
