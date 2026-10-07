from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_46_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.46.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.46"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "README_v0.0.46.md",
    "historian/__init__.py",
    "historian/domains/politics/__init__.py",
    "historian/domains/politics/probe.py",
    "historian_manifest.json",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.46.md",
]


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def backup(path: Path, log: list[str]) -> None:
    relative = path.relative_to(ROOT)
    target = BACKUP_ROOT / relative
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    log.append(f"Backed up {relative} -> backups/v0.0.46/{relative}")


def write_if_changed(path: Path, original: str, updated: str, log: list[str]) -> None:
    if updated == original:
        log.append(f"No change needed: {path.relative_to(ROOT)}")
        return
    backup(path, log)
    path.write_text(updated, encoding="utf-8", newline="\n")
    log.append(f"Updated: {path.relative_to(ROOT)}")


def replace_once(text: str, old: str, new: str, label: str, log: list[str]) -> str:
    if new in text:
        log.append(f"Already installed: {label}")
        return text
    if old not in text:
        raise RuntimeError(f"Could not locate v0.0.45 anchor for {label}.")
    log.append(f"Installed: {label}")
    return text.replace(old, new, 1)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_anchor = (
        "from historian.domains.people.notification_decoder import write_notification_event_decoder\n"
    )
    import_replacement = (
        import_anchor
        + "from historian.domains.politics.probe import write_politics_diplomacy_probe\n"
    )
    updated = replace_once(
        updated,
        import_anchor,
        import_replacement,
        "Politics/diplomacy probe import",
        log,
    )

    helper_anchor = '''def _refresh_notification_event_decoder(campaign_id: int):
    try:
        activity("Refreshing Notification_Event_Decoder_Debug.txt...")
        path = write_notification_event_decoder(DB, campaign_id)
        activity(
            "Notification / event object decoder updated - "
            f"{path.name}"
        )
        return path, None
    except Exception as exc:
        message = str(exc)
        error(f"NOTIFICATION / EVENT DECODER - {message}")
        return None, message

def safe_name'''
    helper_replacement = '''def _refresh_notification_event_decoder(campaign_id: int):
    try:
        activity("Refreshing Notification_Event_Decoder_Debug.txt...")
        path = write_notification_event_decoder(DB, campaign_id)
        activity(
            "Notification / event object decoder updated - "
            f"{path.name}"
        )
        return path, None
    except Exception as exc:
        message = str(exc)
        error(f"NOTIFICATION / EVENT DECODER - {message}")
        return None, message


def _refresh_politics_diplomacy_probe(campaign_id: int):
    try:
        activity("Refreshing Politics_Diplomacy_Probe_Debug.txt...")
        path = write_politics_diplomacy_probe(DB, campaign_id)
        activity(
            "Politics / diplomacy deep probe updated - "
            f"{path.name}"
        )
        return path, None
    except Exception as exc:
        message = str(exc)
        error(f"POLITICS / DIPLOMACY PROBE - {message}")
        return None, message


def safe_name'''
    updated = replace_once(
        updated,
        helper_anchor,
        helper_replacement,
        "Politics/diplomacy refresh helper",
        log,
    )

    review_anchor = '''    notification_decoder_path, notification_decoder_error = _refresh_notification_event_decoder(
        ACTIVE_CAMPAIGN_ID
    )

    diagnostic_path = None
'''
    review_replacement = '''    notification_decoder_path, notification_decoder_error = _refresh_notification_event_decoder(
        ACTIVE_CAMPAIGN_ID
    )

    politics_probe_path, politics_probe_error = _refresh_politics_diplomacy_probe(
        ACTIVE_CAMPAIGN_ID
    )

    diagnostic_path = None
'''
    updated = replace_once(
        updated,
        review_anchor,
        review_replacement,
        "Review Campaign politics/diplomacy probe hook",
        log,
    )

    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original
    if "## Current version\n\nv0.0.46" not in updated:
        updated = updated.replace("## Current version\n\nv0.0.45", "## Current version\n\nv0.0.46", 1)
    if "Tracks politics and diplomatic raw evidence" not in updated:
        anchor = "- Tracks combat evidence and battle events\n"
        if anchor not in updated:
            raise RuntimeError("Could not locate README feature-list anchor.")
        updated = updated.replace(
            anchor,
            anchor + "- Tracks politics and diplomatic raw evidence through an evidence-only deep probe\n",
            1,
        )
    updated = updated.replace(
        "The current codebase includes migration and historical tracking work through version 0.0.43.",
        "The current codebase includes migration and historical tracking work through version 0.0.46.",
        1,
    )
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.46\n- Added an evidence-only Politics & Diplomacy Deep Probe.\n- Added `diagnostics/Politics_Diplomacy_Probe_Debug.txt`.\n- Review Campaign now inventories retained player-government fields, candidate political keys, raw relation records and changes between selected raw-save samples.\n- The probe uses all reviewed profile/government states plus adaptive raw-save sampling (maximum 64 raw archives) so mature comparison campaigns are not fully reparsed.\n- Existing People ruler/heir/death milestones are included as cross-domain anchors without inventing election or succession causes.\n- Raw relation keys/blocks are preserved literally; v0.0.46 does not yet infer alliances, treaties, factions, elections, rivalries or diplomatic outcomes from unfamiliar fields.\n- No database schema changes and no parsed-cache component version changes.\n- Review Campaign is required once after installation to generate the new diagnostic.\n\n'''
    if section not in original:
        anchor = "# Stellaris Historian Changelog\n\n"
        if anchor not in original:
            raise RuntimeError("Could not locate CHANGELOG heading.")
        updated = original.replace(anchor, anchor + section, 1)
    else:
        updated = original
    write_if_changed(path, original, updated, log)


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.46 politics/diplomacy deep-probe migration started.",
        "No archived Stellaris saves, campaign identity, database schema or parsed-cache versions are modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.46 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.46 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        py_compile.compile(str(ROOT / "historian/domains/politics/probe.py"), doraise=True)
        patch_app(log)
        patch_readme(log)
        patch_changelog(log)
        py_compile.compile(str(ROOT / "app.py"), doraise=True)
    except (py_compile.PyCompileError, RuntimeError, OSError) as exc:
        log.append(f"ABORTED: v0.0.46 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.46 validation failed.")
        print("Original source backups are retained under backups\\v0.0.46 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.46 politics/diplomacy deep-probe migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Existing parsed cache component versions remain unchanged.",
        "Review Campaign now generates diagnostics/Politics_Diplomacy_Probe_Debug.txt.",
        "The probe reads all already-reviewed profile/government states and adaptively selects at most 64 raw archived saves for political/diplomatic structure inspection.",
        "No politics/diplomacy interpretation is promoted to the Historical Event Layer in v0.0.46.",
        "Run Review Campaign once after installation.",
        "Construct Campaign is not required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.46 politics / diplomacy deep-probe migration complete.")
    print("Parsed cache versions are unchanged; no full cache refresh is required.")
    print("Run Review Campaign once to generate Politics_Diplomacy_Probe_Debug.txt.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
