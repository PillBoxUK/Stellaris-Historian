from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_45_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.45.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.45"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "README_v0.0.45.md",
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian/historical_events.py",
    "historian/timeline.py",
    "historian/scribes.py",
    "historian/domains/people/journal.py",
    "historian/domains/people/evidence_diagnostic.py",
    "historian/domains/people/exit_diagnostic.py",
    "historian/domains/people/notification_decoder.py",
    "historian/domains/people/notification_deaths.py",
    "historian_manifest.json",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.45.md",
]

COMPILE_CHECKS = [
    "historian/domains/people/notification_deaths.py",
]


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _backup(path: Path) -> None:
    relative = path.relative_to(ROOT)
    target = BACKUP_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)


def _replace_once(text: str, old: str, new: str, label: str, log: list[str]) -> str:
    if new in text:
        log.append(f"{label}: already present.")
        return text
    if old not in text:
        raise RuntimeError(f"Could not locate expected anchor for {label}.")
    log.append(f"{label}: installed.")
    return text.replace(old, new, 1)


def _replace_all_expected(
    text: str,
    old: str,
    new: str,
    expected: int,
    label: str,
    log: list[str],
) -> str:
    if new in text and old not in text:
        log.append(f"{label}: already present.")
        return text
    count = text.count(old)
    if count != expected:
        raise RuntimeError(
            f"Expected {expected} anchor(s) for {label}, found {count}."
        )
    log.append(f"{label}: installed in {expected} location(s).")
    return text.replace(old, new)


def _write_if_changed(path: Path, original: str, updated: str, log: list[str]) -> None:
    if updated == original:
        log.append(f"{path.relative_to(ROOT)} required no source changes.")
        return
    _backup(path)
    path.write_text(updated, encoding="utf-8", newline="\n")
    log.append(
        f"Updated {path.relative_to(ROOT)}; backup preserved under backups/v0.0.45/."
    )


def patch_notification_decoder(log: list[str]) -> None:
    path = ROOT / "historian" / "domains" / "people" / "notification_decoder.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    helper_anchor = '''def _leader_exit_rows(db: Database, campaign_id: int) -> tuple[list[dict], dict[int, dict]]:
'''
    helper_replacement = '''def _normalise_leader_name(value: object | None) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\\x11[A-Za-z](.*?)\\x11!", r"\\1", text)
    text = "".join(ch if ord(ch) >= 32 else " " for ch in text)
    return re.sub(r"\\s+", " ", text).strip().casefold()


def _unique_named_leader_match(
    message: dict,
    *,
    leader_id: int,
    leader_rows: dict[int, dict],
) -> bool:
    variables = {str(key): str(value) for key, value in message.get("variables", ())}
    retained_name = variables.get("LEADER")
    if not retained_name:
        return False
    wanted = _normalise_leader_name(retained_name)
    matching = [
        candidate_id
        for candidate_id, row in leader_rows.items()
        if _normalise_leader_name(row.get("name")) == wanted
    ]
    return matching == [leader_id]


def _leader_exit_rows(db: Database, campaign_id: int) -> tuple[list[dict], dict[int, dict]]:
'''
    updated = _replace_once(
        updated,
        helper_anchor,
        helper_replacement,
        "Notification decoder unique leader-name helper",
        log,
    )

    intro_old = "A message is linked to a leader only when an explicit typed leader reference survives inside that message object. Timing alone is correlation, not causation."
    intro_new = "A message can support a leader identity through either an explicit typed leader reference or, for LEADER_DEATH messages, a LEADER variable that uniquely matches one known player leader. Timing alone is correlation, not causation."
    if intro_new not in updated:
        if intro_old not in updated:
            raise RuntimeError("Could not locate notification decoder introduction wording.")
        updated = updated.replace(intro_old, intro_new, 1)
        log.append("Notification decoder introduction wording updated.")
    else:
        log.append("Notification decoder introduction wording already updated.")

    doc_old = (
        "    rebuilt database, then only the narrow raw-save windows around those exits\n"
        "    are opened. A message is linked to a leader only when a typed leader\n"
        "    reference is retained in the message itself. Timing alone is never\n"
        "    promoted to causation.\n"
    )
    doc_new = (
        "    rebuilt database, then only the narrow raw-save windows around those exits\n"
        "    are opened. Explicit typed leader references remain direct identity evidence.\n"
        "    v0.0.45 additionally recognizes a LEADER variable inside a retained\n"
        "    LEADER_DEATH message when that name uniquely matches one known player leader;\n"
        "    the promotion layer still requires a matching exit interval and exact date.\n"
        "    Timing alone is never promoted to causation.\n"
    )
    if doc_new not in updated:
        if doc_old not in updated:
            raise RuntimeError("Could not locate notification decoder docstring wording.")
        updated = updated.replace(doc_old, doc_new, 1)
        log.append("Notification decoder docstring wording updated.")
    else:
        log.append("Notification decoder docstring wording already updated.")

    typed_anchor = '''                if message["typed_leader_refs"]:
                    lines.append(
                        "      EXACT TYPED LEADER LINK: "
                        + ", ".join(message["typed_leader_refs"])
                    )
                else:
                    lines.append("      Exact typed leader link: None")
                lines.append(f"      raw: {message['raw']}")
'''
    typed_replacement = '''                if message["typed_leader_refs"]:
                    lines.append(
                        "      EXACT TYPED LEADER LINK: "
                        + ", ".join(message["typed_leader_refs"])
                    )
                else:
                    lines.append("      Exact typed leader link: None")
                if _unique_named_leader_match(
                    message,
                    leader_id=leader_id,
                    leader_rows=leader_rows,
                ):
                    lines.append(
                        "      UNIQUE LEADER-NAME MATCH: "
                        + str(leader_row.get("name") or leader_id)
                    )
                else:
                    lines.append("      Unique leader-name match: None")
                lines.append(f"      raw: {message['raw']}")
'''
    updated = _replace_once(
        updated,
        typed_anchor,
        typed_replacement,
        "Notification decoder unique leader-name output",
        log,
    )

    old_interpret = (
        "Only an explicit typed leader reference inside a retained message object can directly connect that message to this leader. "
        "Counter movement, an allocated-but-expired notification ID, or a new player_event ID remains correlation evidence only."
    )
    new_interpret = (
        "An explicit typed leader reference is direct identity evidence. For a retained LEADER_DEATH message, a LEADER variable can also identify the subject when it uniquely matches one known player leader and the death date fits that leader's exit interval. "
        "Counter movement, an allocated-but-expired notification ID, or a new player_event ID remains correlation evidence only."
    )
    if new_interpret not in updated:
        if old_interpret not in updated:
            raise RuntimeError("Could not locate notification decoder interpretation wording.")
        updated = updated.replace(old_interpret, new_interpret, 1)
        log.append("Notification decoder interpretation wording updated.")
    else:
        log.append("Notification decoder interpretation wording already updated.")

    rule_anchor = '        "- Retained message fields such as type/localization/date/variables/targets are raw save evidence.",\n'
    rule_replacement = (
        rule_anchor
        + '        "- v0.0.45 may promote a retained LEADER_DEATH message when its LEADER variable uniquely identifies the exiting player leader and the date falls inside that exit interval.",\n'
    )
    updated = _replace_once(
        updated,
        rule_anchor,
        rule_replacement,
        "Notification decoder v0.0.45 rule",
        log,
    )

    _write_if_changed(path, original, updated, log)


def patch_history_processor(log: list[str]) -> None:
    path = ROOT / "historian" / "history_processor.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_anchor = (
        "from .domains.people.history import derive_full_leader_history, leader_transition_data\n"
    )
    import_line = (
        "from .domains.people.notification_deaths import (\n"
        "    apply_notification_deaths,\n"
        "    promote_notification_deaths_in_database,\n"
        "    write_notification_death_diagnostic,\n"
        ")\n"
    )
    if import_line not in updated:
        if import_anchor not in updated:
            raise RuntimeError("Could not locate People history import anchor.")
        updated = updated.replace(import_anchor, import_anchor + import_line, 1)
        log.append("history_processor notification-death import installed.")
    else:
        log.append("history_processor notification-death import already present.")

    derive_anchor = '''    leader_derived = derive_full_leader_history(
        leader_snapshots
    )
    character_summary = character_evidence_summary(
'''
    derive_replacement = '''    leader_derived = derive_full_leader_history(
        leader_snapshots
    )
    notification_death_summary = apply_notification_deaths(
        snapshots,
        leader_derived,
    )
    character_summary = character_evidence_summary(
'''
    updated = _replace_all_expected(
        updated,
        derive_anchor,
        derive_replacement,
        2,
        "Review/Construct in-memory notification-death promotion",
        log,
    )

    diagnostic_anchor = '''    leader_exit_debug = write_leader_exit_diagnostic(
        diagnostic_dir,
        leader_derived,
    )
'''
    diagnostic_replacement = '''    notification_death_debug = write_notification_death_diagnostic(
        diagnostic_dir,
        notification_death_summary,
    )
    activity(
        "Notification-derived leader death diagnostic updated - "
        f"diagnostics\\\\{notification_death_debug.name}"
    )
    leader_exit_debug = write_leader_exit_diagnostic(
        diagnostic_dir,
        leader_derived,
    )
'''
    updated = _replace_all_expected(
        updated,
        diagnostic_anchor,
        diagnostic_replacement,
        2,
        "Review/Construct notification-death diagnostic",
        log,
    )

    incremental_anchor = '''    remaining = db.unprocessed_count(
        campaign_id
    )
'''
    incremental_replacement = '''    try:
        notification_death_incremental = promote_notification_deaths_in_database(
            db,
            campaign_id,
        )
        write_notification_death_diagnostic(
            _diagnostics_dir(Path(campaign["archive_dir"])),
            notification_death_incremental,
        )
        if notification_death_incremental.get("confirmed", 0):
            activity(
                "Notification-derived leader deaths promoted - "
                f"{notification_death_incremental['confirmed']} confirmed"
            )
    except Exception as exc:
        error(f"NOTIFICATION-DERIVED LEADER DEATHS - {exc}")

    remaining = db.unprocessed_count(
        campaign_id
    )
'''
    updated = _replace_once(
        updated,
        incremental_anchor,
        incremental_replacement,
        "Update History notification-death promotion",
        log,
    )

    _write_if_changed(path, original, updated, log)


def patch_historical_events(log: list[str]) -> None:
    path = ROOT / "historian" / "historical_events.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    map_anchor = '''        "leader_traits_gained": 52,
        "leader_missing_unconfirmed": 88,
'''
    map_replacement = '''        "leader_traits_gained": 52,
        "leader_death_recorded": 98,
        "leader_tombstone_unconfirmed": 88,
        "leader_missing_unconfirmed": 88,
'''
    updated = _replace_once(
        updated,
        map_anchor,
        map_replacement,
        "Historical Event leader death importance",
        log,
    )

    attr_anchor = '''        if event_type == "leader_missing_unconfirmed":
            attributes = _pairs(
                leader_id=row.get("leader_id"),
                death_established="false",
                exit_reason_established="false",
            )
'''
    attr_replacement = '''        if event_type == "leader_death_recorded":
            attributes = _pairs(
                leader_id=row.get("leader_id"),
                death_established="true",
                evidence_kind=row.get("death_evidence_kind") or "retained_death_evidence",
                notification_id=row.get("notification_id"),
                recorded_age=row.get("recorded_age"),
                recorded_service=row.get("time_served"),
                death_reason=row.get("death_reason"),
            )
        elif event_type in {"leader_missing_unconfirmed", "leader_tombstone_unconfirmed"}:
            attributes = _pairs(
                leader_id=row.get("leader_id"),
                death_established="false",
                exit_reason_established="false",
            )
'''
    updated = _replace_once(
        updated,
        attr_anchor,
        attr_replacement,
        "Historical Event leader death attributes",
        log,
    )

    _write_if_changed(path, original, updated, log)


def patch_people_journal(log: list[str]) -> None:
    path = ROOT / "historian" / "domains" / "people" / "journal.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    label_anchor = '''        "exact_save_field": "Recorded recruitment date",
        "first_observed": "First observed in archive",
'''
    label_replacement = '''        "exact_save_field": "Recorded recruitment date",
        "exact_notification_date": "Exact retained death-notification date",
        "first_observed": "First observed in archive",
'''
    updated = _replace_once(
        updated,
        label_anchor,
        label_replacement,
        "People Journal exact notification date label",
        log,
    )

    status_anchor = '''def _leader_status(row) -> str:
    if row["status"] == "present":
        return "Present in latest archive"
    return "No longer present - cause unconfirmed"
'''
    status_replacement = '''def _leader_status(row) -> str:
    if row["status"] == "present":
        return "Present in latest archive"
    if row["status"] == "dead_confirmed":
        return "Dead - retained death evidence confirmed"
    if row["status"] == "tombstoned_unconfirmed":
        return "Removed from active leader record - cause unconfirmed"
    return "No longer present - cause unconfirmed"
'''
    updated = _replace_once(
        updated,
        status_anchor,
        status_replacement,
        "People Journal confirmed-death status",
        log,
    )

    _write_if_changed(path, original, updated, log)


def patch_timeline(log: list[str]) -> None:
    path = ROOT / "historian" / "timeline.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    anchor = '''    if event_type in {"leader_became_ruler", "leader_left_rulership", "leader_missing_unconfirmed"}:
        return True
'''
    replacement = '''    if event_type in {
        "leader_became_ruler",
        "leader_left_rulership",
        "leader_death_recorded",
        "leader_missing_unconfirmed",
    }:
        return True
'''
    updated = _replace_once(
        updated,
        anchor,
        replacement,
        "Timeline confirmed leader deaths",
        log,
    )

    _write_if_changed(path, original, updated, log)


def patch_scribes(log: list[str]) -> None:
    path = ROOT / "historian" / "scribes.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    scientist_anchor = '''            if row["status"] != "present":
                text += (
                    f" The name is last confirmed in {_year(row['last_seen_date'])}; after that the record falls silent, "
                    "without establishing death, retirement or reassignment."
                )
'''
    scientist_replacement = '''            if row["status"] == "dead_confirmed":
                death_events = [
                    event for event in events_by_leader.get(int(row["leader_id"]), [])
                    if event["event_type"] == "leader_death_recorded"
                ]
                if death_events:
                    death = death_events[-1]
                    text += f" The surviving rolls record the death on {_natural_date(death['game_date'])}."
                else:
                    text += " The surviving rolls record the leader as dead, though the death notice is not reproduced here."
            elif row["status"] != "present":
                text += (
                    f" The name is last confirmed in {_year(row['last_seen_date'])}; after that the record falls silent, "
                    "without establishing death, retirement or reassignment."
                )
'''
    updated = _replace_once(
        updated,
        scientist_anchor,
        scientist_replacement,
        "Scribes scientist death handling",
        log,
    )

    missing_anchor = '''    # Preserve unexplained departures once, even if they were already mentioned above.
    non_scientist_missing = [row for row in missing if row["leader_class"] != "scientist"]
    for row in non_scientist_missing:
        paragraphs.append(
            f"{row['name']} is last confirmed in {_year(row['last_seen_date'])}; thereafter the name disappears from the surviving rolls. "
            "The reason is not recorded, and no later scribe can honestly supply it."
        )
'''
    missing_replacement = '''    # Preserve confirmed deaths and unexplained departures once, even if mentioned above.
    non_scientist_missing = [row for row in missing if row["leader_class"] != "scientist"]
    for row in non_scientist_missing:
        if row["status"] == "dead_confirmed":
            death_events = [
                event for event in events_by_leader.get(int(row["leader_id"]), [])
                if event["event_type"] == "leader_death_recorded"
            ]
            if death_events:
                death = death_events[-1]
                paragraphs.append(
                    f"The surviving rolls record the death of {row['name']} on {_natural_date(death['game_date'])}."
                )
            else:
                paragraphs.append(
                    f"The surviving rolls record {row['name']} as dead, though the surviving chronicle does not reproduce the notice here."
                )
        else:
            paragraphs.append(
                f"{row['name']} is last confirmed in {_year(row['last_seen_date'])}; thereafter the name disappears from the surviving rolls. "
                "The reason is not recorded, and no later scribe can honestly supply it."
            )
'''
    updated = _replace_once(
        updated,
        missing_anchor,
        missing_replacement,
        "Scribes confirmed-death departure handling",
        log,
    )

    _write_if_changed(path, original, updated, log)


def patch_people_diagnostics(log: list[str]) -> None:
    evidence_path = ROOT / "historian" / "domains" / "people" / "evidence_diagnostic.py"
    original = evidence_path.read_text(encoding="utf-8")
    updated = original
    old = '        "A disappearance remains an unconfirmed exit unless a retained dead_leader record explicitly supports death.",\n'
    new = '        "A disappearance remains unconfirmed unless retained death evidence supports it. Valid sources include an explicit dead_leader record or a validated retained LEADER_DEATH notification uniquely naming the exiting leader.",\n'
    updated = _replace_once(updated, old, new, "Character diagnostic death-evidence rule", log)
    updated = updated.replace(
        'f"Confirmed death transitions from dead_leader evidence: {summary[\'confirmed_death_events\']}",',
        'f"Confirmed death transitions from retained death evidence: {summary[\'confirmed_death_events\']}",',
    )
    _write_if_changed(evidence_path, original, updated, log)

    exit_path = ROOT / "historian" / "domains" / "people" / "exit_diagnostic.py"
    original = exit_path.read_text(encoding="utf-8")
    updated = original
    updated = _replace_once(
        updated,
        '        "Purpose: distinguish disappearance from explicit retained death evidence.",\n        "v0.0.42 probes the raw dead_leader block. A leader is only called dead when a retained dead_leader record supports that interpretation.",\n        "If no dead_leader record exists, disappearance remains an unconfirmed exit; screenshots or human memory are not silently converted into save evidence.",\n',
        '        "Purpose: distinguish disappearance from explicit retained death evidence.",\n        "Historian accepts explicit dead_leader records and validated retained LEADER_DEATH notifications that uniquely name the exiting leader.",\n        "A tombstone or disappearance without qualifying death evidence remains an unconfirmed exit; screenshots or human memory are not silently converted into save evidence.",\n',
        "Leader exit diagnostic evidence-source wording",
        log,
    )
    old_interpret = '            f"  Interpretation: {(\'death supported by raw dead_leader evidence\' if confirmed_death else (\'active leader object tombstoned; cause still unconfirmed\' if tombstoned_exit else \'disappearance/exit only\'))}",\n'
    new_interpret = '            f"  Interpretation: {(\'death supported by retained \' + str(leader.get(\'death_evidence_kind\') or \'death evidence\') if confirmed_death else (\'active leader object tombstoned; cause still unconfirmed\' if tombstoned_exit else \'disappearance/exit only\'))}",\n'
    updated = _replace_once(
        updated,
        old_interpret,
        new_interpret,
        "Leader exit diagnostic confirmed-death interpretation",
        log,
    )
    _write_if_changed(exit_path, original, updated, log)


def patch_sources(log: list[str]) -> None:
    patch_notification_decoder(log)
    patch_history_processor(log)
    patch_historical_events(log)
    patch_people_journal(log)
    patch_timeline(log)
    patch_scribes(log)
    patch_people_diagnostics(log)


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.45 notification-derived leader death migration started.",
        "Archived Stellaris saves, campaign identity and parsed-cache versions are not modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.45 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.45 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
        patch_sources(log)
        for name in (
            "historian/history_processor.py",
            "historian/historical_events.py",
            "historian/timeline.py",
            "historian/scribes.py",
            "historian/domains/people/journal.py",
            "historian/domains/people/notification_decoder.py",
            "historian/domains/people/evidence_diagnostic.py",
            "historian/domains/people/exit_diagnostic.py",
        ):
            py_compile.compile(str(ROOT / name), doraise=True)
    except (py_compile.PyCompileError, RuntimeError, OSError) as exc:
        log.append(f"ABORTED: v0.0.45 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.45 validation failed.")
        print("Original source backups are retained under backups\\v0.0.45 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.45 notification-derived leader death migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "People cache remains v5; no full raw cache refresh is required.",
        "Validated retained LEADER_DEATH notifications can now promote unresolved leader exits to dead_confirmed.",
        "Promotion requires LEADER_DEATH + MESSAGE_LEADER_LOST_DESC + a unique exact player-leader name match + an unresolved exit in the same archive interval + a notification date inside that interval.",
        "Death date, notification service duration, recorded age and custom death text are preserved in the career event; death date/reason/evidence kind are persisted in leader_deep_evidence.",
        "Review/Construct generate diagnostics/Notification_Death_Evidence_Debug.txt.",
        "Historical Event Layer, Timeline, Journal and Scribes now recognize confirmed leader-death events without treating unresolved exits as deaths.",
        "Run Review Campaign once after installation to rebuild existing leader history under v0.0.45 rules.",
        "Construct Campaign is not required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.45 notification-derived leader death migration complete.")
    print("People cache remains v5; no full raw cache refresh is required.")
    print("Run Review Campaign once to promote validated retained LEADER_DEATH evidence.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
