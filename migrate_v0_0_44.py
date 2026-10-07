from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_44_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.44.log"
APP_PATH = ROOT / "app.py"
BACKUP_PATH = ROOT / "backups" / "v0.0.44" / "app.py.before_v0.0.44"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "README_v0.0.44.md",
    "historian/__init__.py",
    "historian/domains/people/event_probe.py",
    "historian/domains/people/notification_decoder.py",
    "historian_manifest.json",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.44.md",
]

COMPILE_CHECKS = [
    "historian/domains/people/notification_decoder.py",
]

IMPORT_LINE = (
    "from historian.domains.people.notification_decoder "
    "import write_notification_event_decoder\n"
)
IMPORT_ANCHORS = [
    "from historian.domains.people.event_probe import write_event_character_probe\n",
    "from historian.watcher import CampaignWatcher\n",
]

HELPER_MARKER = "def _refresh_notification_event_decoder(campaign_id: int):"
HELPER_ANCHOR = "\ndef safe_name(value: str, max_len: int = 60) -> str:\n"
HELPER = '''\n\ndef _refresh_notification_event_decoder(campaign_id: int):
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
'''

EVENT_PROBE_CALL = '''    event_probe_path, event_probe_error = _refresh_event_character_probe(
        ACTIVE_CAMPAIGN_ID
    )
'''

DECODER_CALL = '''
    notification_decoder_path, notification_decoder_error = _refresh_notification_event_decoder(
        ACTIVE_CAMPAIGN_ID
    )
'''


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_app(log: list[str]) -> None:
    original = APP_PATH.read_text(encoding="utf-8")
    updated = original

    if IMPORT_LINE not in updated:
        for anchor in IMPORT_ANCHORS:
            if anchor in updated:
                updated = updated.replace(anchor, anchor + IMPORT_LINE, 1)
                log.append("app.py notification-decoder import installed.")
                break
        else:
            raise RuntimeError("Could not locate app.py import anchor.")
    else:
        log.append("app.py notification-decoder import already present.")

    if HELPER_MARKER not in updated:
        if HELPER_ANCHOR not in updated:
            raise RuntimeError("Could not locate app.py helper insertion anchor.")
        updated = updated.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
        log.append("app.py notification-decoder helper installed.")
    else:
        log.append("app.py notification-decoder helper already present.")

    call_marker = "notification_decoder_path, notification_decoder_error = _refresh_notification_event_decoder("
    existing_calls = updated.count(call_marker)

    if existing_calls < 2:
        event_probe_calls = updated.count(EVENT_PROBE_CALL)
        if event_probe_calls < 2:
            raise RuntimeError(
                "Expected v0.0.43 Review/Construct event-probe hooks were not found. "
                "Run/start v0.0.43 successfully before applying v0.0.44."
            )

        needed = 2 - existing_calls
        search_from = 0
        for _ in range(needed):
            index = updated.find(EVENT_PROBE_CALL, search_from)
            if index < 0:
                raise RuntimeError("Could not locate next Review/Construct event-probe hook.")
            insert_at = index + len(EVENT_PROBE_CALL)
            updated = updated[:insert_at] + DECODER_CALL + updated[insert_at:]
            search_from = insert_at + len(DECODER_CALL)
        log.append("Review/Construct notification-decoder hooks installed.")
    else:
        log.append("Review/Construct notification-decoder hooks already present.")

    if updated != original:
        BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not BACKUP_PATH.exists():
            shutil.copy2(APP_PATH, BACKUP_PATH)
        APP_PATH.write_text(updated, encoding="utf-8", newline="\n")
        log.append(f"Original app.py backup preserved at {BACKUP_PATH}.")
    else:
        log.append("app.py required no source changes.")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.44 notification/event object decoder migration started.",
        "No archived save, campaign identity, database schema, processed flag or parsed-cache version is modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.44 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.44 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
        patch_app(log)
        py_compile.compile(str(APP_PATH), doraise=True)
    except (py_compile.PyCompileError, RuntimeError, OSError) as exc:
        log.append(f"ABORTED: validation/source-hook installation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.44 validation failed.")
        print("The original app.py backup is retained if a source change was attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.44 notification/event object decoder migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "People cache remains v5; no full 299-save raw cache refresh is required.",
        "Review/Construct now generate diagnostics/Notification_Event_Decoder_Debug.txt.",
        "The decoder opens only raw saves in leader-exit windows already identified from cached history.",
        "Retained message objects are decoded into notification ID, type, localization, date/end, variables, targets and custom_message_text.",
        "Allocated notification IDs whose message payload has already expired are reported explicitly instead of reconstructed.",
        "player_event selection records remain separate from scripted event_id values unless a future parser proves a mapping.",
        "save_on_death is explicitly treated as a generic object-lifetime field and not as leader-death evidence.",
        "Run Review Campaign once after installation to generate the decoder diagnostic.",
        "Construct Campaign is not required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.44 notification / event object decoder migration complete.")
    print("People cache remains v5; no full raw cache refresh is required.")
    print("Run Review Campaign once to generate Notification_Event_Decoder_Debug.txt.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
