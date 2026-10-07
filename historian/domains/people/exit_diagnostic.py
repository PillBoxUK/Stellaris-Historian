from __future__ import annotations

from pathlib import Path


def write_leader_exit_diagnostic(archive_dir: Path, leader_history: dict) -> Path:
    """Write a conservative leader exit/death evidence audit."""
    base = Path(archive_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / "Leader_Exit_Evidence_Debug.txt"
    leaders = {int(row["leader_id"]): row for row in leader_history.get("leaders", [])}
    exits = [
        row for row in leader_history.get("events", [])
        if row.get("event_type") in {"leader_missing_unconfirmed", "leader_tombstone_unconfirmed", "leader_death_recorded"}
    ]
    confirmed = [row for row in exits if row.get("event_type") == "leader_death_recorded"]
    tombstoned = [row for row in exits if row.get("event_type") == "leader_tombstone_unconfirmed"]
    unconfirmed = [row for row in exits if row.get("event_type") == "leader_missing_unconfirmed"]

    lines = [
        "STELLARIS HISTORIAN - LEADER EXIT EVIDENCE DEBUG",
        "",
        "Purpose: distinguish disappearance from explicit retained death evidence.",
        "Historian accepts explicit dead_leader records and validated retained LEADER_DEATH notifications that uniquely name the exiting leader.",
        "A tombstone or disappearance without qualifying death evidence remains an unconfirmed exit; screenshots or human memory are not silently converted into save evidence.",
        "",
        f"Confirmed death transitions: {len(confirmed)}",
        f"Tombstoned-but-cause-unconfirmed transitions: {len(tombstoned)}",
        f"Unconfirmed disappearance transitions: {len(unconfirmed)}",
        f"Total exit transitions: {len(exits)}",
        "",
    ]

    for event in exits:
        leader_id = int(event.get("leader_id", -1))
        leader = leaders.get(leader_id, {})
        confirmed_death = event.get("event_type") == "leader_death_recorded"
        tombstoned_exit = event.get("event_type") == "leader_tombstone_unconfirmed"
        lines.extend([
            f"{event.get('game_date', 'Unknown date')} | {event.get('title', 'Leader exit')}",
            f"  Leader ID: {leader_id}",
            f"  Name: {leader.get('name') or 'Unknown'}",
            f"  Class: {leader.get('leader_class') or 'Unknown'}",
            f"  Species: {leader.get('species_name') or leader.get('species_id') or 'Not recorded'}",
            f"  Recruitment date: {leader.get('recruitment_date') or 'Not recorded'}",
            f"  Last confirmed present: {leader.get('last_seen_date') or 'Not resolved'}",
            f"  First archived state absent/dead: {leader.get('death_first_observed_date') or event.get('game_date') or 'Not resolved'}",
            f"  Last assignment: {leader.get('latest_assignment') or 'Not recorded'}",
            f"  Last council role: {leader.get('latest_council_role') or 'Not recorded'}",
            f"  Ever ruler: {'yes' if int(leader.get('ever_ruler', 0) or 0) else 'no'}",
            f"  Exact death date established: {'yes - ' + str(leader.get('death_date')) if leader.get('death_date') else 'no'}",
            f"  Death/cause field: {leader.get('death_reason_key') or 'Not established'}",
            f"  Death/cause value: {leader.get('death_reason_value') or 'Not established'}",
            f"  Death evidence kind: {leader.get('death_evidence_kind') or 'None'}",
            f"  Interpretation: {('death supported by retained ' + str(leader.get('death_evidence_kind') or 'death evidence') if confirmed_death else ('active leader object tombstoned; cause still unconfirmed' if tombstoned_exit else 'disappearance/exit only'))}",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path
