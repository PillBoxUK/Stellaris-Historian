from __future__ import annotations

from pathlib import Path

from .history import derive_science_interpretation
from .models import ScienceSnapshot


def _observe(snapshots: list[ScienceSnapshot], attr: str, identity_attr: str | None = None):
    seen: dict[object, dict] = {}
    for snapshot in snapshots:
        records = getattr(snapshot, attr)
        for record_id, record in records.items():
            identity = (record_id, getattr(record, identity_attr)) if identity_attr else record_id
            row = seen.setdefault(
                identity,
                {
                    "first": snapshot.game_date,
                    "last": snapshot.game_date,
                    "record": record,
                    "max_chapter": None,
                    "scientists": [],
                    "completion_dates": [],
                },
            )
            row["last"] = snapshot.game_date
            row["record"] = record
            chapter = getattr(record, "chapter_index", None)
            if chapter is not None:
                row["max_chapter"] = max(row["max_chapter"] or chapter, chapter)
            scientist = getattr(record, "scientist_name", None)
            if scientist and scientist not in row["scientists"]:
                row["scientists"].append(scientist)
            for date in getattr(record, "player_completion_dates", ()):
                if date not in row["completion_dates"]:
                    row["completion_dates"].append(date)
    return seen


def science_evidence_summary(snapshots: list[ScienceSnapshot]) -> dict[str, int]:
    archaeology = _observe(snapshots, "archaeology_sites")
    projects = _observe(snapshots, "special_projects", "project_key")
    situations = _observe(snapshots, "situations", "type_key")
    interpretation = derive_science_interpretation(snapshots)
    anomaly_ids = set()
    for snapshot in snapshots:
        anomaly_ids.update(snapshot.anomaly_ids)
    return {
        "archaeology_sites": len(archaeology),
        "special_projects": len(projects),
        "project_families": len(interpretation.project_families),
        "situations": len(situations),
        "anomaly_ids": len(anomaly_ids),
    }


def write_science_diagnostic(archive_dir: Path, snapshots: list[ScienceSnapshot]) -> Path:
    target = Path(archive_dir) / "Science_Evidence_Debug.txt"
    archaeology = _observe(snapshots, "archaeology_sites")
    projects = _observe(snapshots, "special_projects", "project_key")
    situations = _observe(snapshots, "situations", "type_key")
    interpretation = derive_science_interpretation(snapshots)
    anomaly_ids = set()
    for snapshot in snapshots:
        anomaly_ids.update(snapshot.anomaly_ids)

    lines = [
        "STELLARIS HISTORIAN - SCIENCE EVIDENCE DEBUG",
        "",
        "This file is raw/near-raw diagnostic evidence. v0.0.30 publishes only a",
        "selective subset into the Historical Journal. The separate",
        "Science_Interpretation_Debug.txt groups evidence conservatively without",
        "inventing outcomes.",
        "",
        f"Snapshots analysed: {len(snapshots)}",
        f"Unique player-related archaeological sites: {len(archaeology)}",
        f"Raw player special-project instances: {len(projects)}",
        f"Semantic special-project families: {len(interpretation.project_families)}",
        f"Unique player situation instances: {len(situations)}",
        f"Unique active anomaly IDs observed: {len(anomaly_ids)}",
        "",
        "ARCHAEOLOGICAL SITES",
        "--------------------",
    ]

    if not archaeology:
        lines.append("None observed in the surviving archive.")
    for site_id, row in sorted(archaeology.items()):
        record = row["record"]
        lines.extend([
            f"[{site_id}] {record.title}",
            f"  Type key: {record.type_key}",
            f"  First observed: {row['first']}",
            f"  Last observed: {row['last']}",
            f"  Location: {record.location_name or ('Planet ' + str(record.planet_id) if record.planet_id is not None else 'Not resolved')}",
            f"  Highest observed chapter index: {row['max_chapter'] if row['max_chapter'] is not None else 'Not recorded'}",
            f"  Scientists observed: {', '.join(row['scientists']) if row['scientists'] else 'None resolved'}",
            "  Player archaeology progress-marker dates retained by save: "
            f"{', '.join(row['completion_dates']) if row['completion_dates'] else 'None recorded'}",
            "  Interpretation note: these dates come from Stellaris site records and are",
            "  treated as chapter/progress evidence, NOT proof that the whole site completed.",
            "",
        ])

    lines.extend(["SPECIAL PROJECT INSTANCES", "-------------------------"])
    if not projects:
        lines.append("None observed in the surviving archive.")
    for project_identity, row in sorted(projects.items(), key=lambda item: (item[0][0], item[0][1])):
        project_id = project_identity[0]
        record = row["record"]
        lines.extend([
            f"[{project_id}] {record.title}",
            f"  Project key: {record.project_key}",
            f"  First observed active: {row['first']}",
            f"  Last observed active: {row['last']}",
            f"  Location: {record.location_name or ('Planet ' + str(record.planet_id) if record.planet_id is not None else 'Not resolved')}",
            f"  Linked ship: {record.linked_ship_name or 'None resolved'}",
            f"  Linked scientist: {record.scientist_name or 'None resolved'}",
            "",
        ])

    lines.extend(["SITUATION INSTANCES", "-------------------"])
    if not situations:
        lines.append("None observed in the surviving archive.")
    for situation_identity, row in sorted(situations.items(), key=lambda item: (item[0][0], item[0][1])):
        situation_id = situation_identity[0]
        record = row["record"]
        lines.extend([
            f"[{situation_id}] {record.title}",
            f"  Situation key: {record.type_key}",
            f"  First observed active: {row['first']}",
            f"  Last observed active: {row['last']}",
            f"  Latest observed progress: {record.progress if record.progress is not None else 'Not recorded'}",
            f"  Latest observed approach: {record.approach_key or 'Not recorded'}",
            "",
        ])

    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return target


def _status_text(*, present_in_latest: bool, last: str, absent_after: str | None) -> str:
    if present_in_latest:
        return "Present in the latest archived state; no outcome is inferred."
    if absent_after:
        return (
            f"No longer observed by {absent_after} after last being observed on {last}; "
            "completion, failure, cancellation or expiry is not established."
        )
    return "No longer observed in the available archive; outcome is not established."


def write_science_interpretation_diagnostic(
    archive_dir: Path,
    snapshots: list[ScienceSnapshot],
) -> Path:
    target = Path(archive_dir) / "Science_Interpretation_Debug.txt"
    interpretation = derive_science_interpretation(snapshots)

    situation_type_counts: dict[tuple[str, str], int] = {}
    for row in interpretation.situations:
        key = (row.type_key, row.title)
        situation_type_counts[key] = situation_type_counts.get(key, 0) + 1

    lines = [
        "STELLARIS HISTORIAN - SCIENCE INTERPRETATION DEBUG",
        "",
        "This file is the conservative semantic view used by the v0.0.30 Science journal.",
        "Only selected, well-contextualised records are published; disappearance from",
        "the save is never treated as proof of completion or success.",
        "",
        f"Snapshots analysed: {len(snapshots)}",
        f"Archaeological site records: {len(interpretation.archaeology_sites)}",
        f"Raw special-project instances: {interpretation.raw_project_instances}",
        f"Semantic special-project families: {len(interpretation.project_families)}",
        f"Situation instances retained separately: {len(interpretation.situations)}",
        f"Unique active anomaly IDs observed: {len(interpretation.anomaly_ids)}",
        "",
        "INTERPRETATION RULES",
        "--------------------",
        "1. Archaeology 'completed' dates are treated only as chapter/progress markers.",
        "2. Special projects sharing a project key are grouped into one semantic family,",
        "   while every raw project ID and the peak number active together are retained.",
        "3. Situation IDs remain separate episodes even when several share the same title/type.",
        "4. A record disappearing between snapshots is NOT called completed, failed or cancelled.",
        "5. Scientist/ship/location links are published here only when the cached save evidence",
        "   actually preserved that relationship.",
        "",
        "ARCHAEOLOGY INTERPRETATION",
        "--------------------------",
    ]

    if not interpretation.archaeology_sites:
        lines.append("None observed in the surviving archive.")
    for site in interpretation.archaeology_sites:
        lines.extend([
            f"[{site.site_id}] {site.title}",
            f"  Type key: {site.type_key}",
            f"  Observation window: {site.first_observed} -> {site.last_observed}",
            f"  Record status: {_status_text(present_in_latest=site.record_persists_in_latest, last=site.last_observed, absent_after=site.first_absent_after_last)}",
            f"  Location(s): {', '.join(site.location_names) if site.location_names else 'Not resolved'}",
            f"  Highest observed chapter index: {site.highest_chapter_index if site.highest_chapter_index is not None else 'Not recorded'}",
            f"  Scientist(s) linked by save evidence: {', '.join(site.scientist_names) if site.scientist_names else 'None resolved'}",
            f"  Chapter/progress marker dates: {', '.join(site.progress_marker_dates) if site.progress_marker_dates else 'None recorded'}",
            f"  Observation runs: {site.observation_runs}",
            "",
        ])

    lines.extend(["SPECIAL-PROJECT FAMILIES", "------------------------"])
    if not interpretation.project_families:
        lines.append("None observed in the surviving archive.")
    for family in interpretation.project_families:
        lines.extend([
            f"{family.title}",
            f"  Project key: {family.project_key}",
            f"  Raw project IDs: {', '.join(str(value) for value in family.project_ids)}",
            f"  Raw instance count: {family.instance_count}",
            f"  Peak concurrent instances: {family.peak_concurrent_instances}",
            f"  Observation window: {family.first_observed} -> {family.last_observed}",
            f"  Family status: {_status_text(present_in_latest=family.present_in_latest, last=family.last_observed, absent_after=family.first_absent_after_last)}",
            f"  Location(s): {', '.join(family.location_names) if family.location_names else 'Not resolved'}",
            f"  Linked ship(s): {', '.join(family.ship_names) if family.ship_names else 'None resolved'}",
            f"  Linked scientist(s): {', '.join(family.scientist_names) if family.scientist_names else 'None resolved'}",
            "",
        ])

    lines.extend(["SITUATION TYPE SUMMARY", "----------------------"])
    if not situation_type_counts:
        lines.append("None observed in the surviving archive.")
    for (type_key, title), count in sorted(situation_type_counts.items(), key=lambda item: (item[0][1], item[0][0])):
        lines.append(f"{title} | {type_key} | {count} separate situation instance(s)")

    lines.extend(["", "SITUATION EPISODES", "------------------"])
    if not interpretation.situations:
        lines.append("None observed in the surviving archive.")
    for situation in interpretation.situations:
        target_text = "Not recorded"
        if situation.target_type:
            target_text = situation.target_type
            if situation.target_id is not None:
                target_text += f" #{situation.target_id}"
        lines.extend([
            f"[{situation.situation_id}] {situation.title}",
            f"  Situation key: {situation.type_key}",
            f"  Observation window: {situation.first_observed} -> {situation.last_observed}",
            f"  Episode status: {_status_text(present_in_latest=situation.present_in_latest, last=situation.last_observed, absent_after=situation.first_absent_after_last)}",
            f"  Latest observed progress: {situation.latest_progress if situation.latest_progress is not None else 'Not recorded'}",
            f"  Latest observed approach: {situation.latest_approach_key or 'Not recorded'}",
            f"  Target: {target_text}",
            f"  Observation runs: {situation.observation_runs}",
            "",
        ])

    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return target
