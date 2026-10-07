from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_43_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.43.log"
APP_PATH = ROOT / "app.py"
BACKUP_PATH = ROOT / "backups" / "v0.0.43" / "app.py.before_v0.0.43"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "historian/__init__.py",
    "historian/domains/people/event_probe.py",
    "historian_manifest.json",
    "README_v0.0.43.md",
    "docs/MIGRATION_v0.0.43.md",
]

COMPILE_CHECKS = [
    "historian/domains/people/event_probe.py",
]

IMPORT_ANCHOR = "from historian.watcher import CampaignWatcher\n"
IMPORT_LINE = "from historian.domains.people.event_probe import write_event_character_probe\n"

GLOBAL_ANCHOR = "ACTIVE_CAMPAIGN_ID: int | None = None\nserver: uvicorn.Server | None = None\n"
HELPER = '''ACTIVE_CAMPAIGN_ID: int | None = None
server: uvicorn.Server | None = None


def _refresh_event_character_probe(campaign_id: int):
    try:
        activity("Refreshing Event_Character_Probe_Debug.txt...")
        path = write_event_character_probe(DB, campaign_id)
        activity(
            "Event / character deep probe updated - "
            f"{path.name}"
        )
        return path, None
    except Exception as exc:
        message = str(exc)
        error(f"EVENT / CHARACTER PROBE - {message}")
        return None, message
'''

REVIEW_ANCHOR = '''    activity(
        f"Journal rebuilt - {format_duration(time.perf_counter() - journal_started)}"
    )

    diagnostic_path = None
'''
REVIEW_REPLACEMENT = '''    activity(
        f"Journal rebuilt - {format_duration(time.perf_counter() - journal_started)}"
    )

    event_probe_path, event_probe_error = _refresh_event_character_probe(
        ACTIVE_CAMPAIGN_ID
    )

    diagnostic_path = None
'''

CONSTRUCT_ANCHOR = '''    activity(
        f"Constructed journal written - "
        f"{format_duration(time.perf_counter() - journal_started)}"
    )

    diagnostic_path = None
'''
CONSTRUCT_REPLACEMENT = '''    activity(
        f"Constructed journal written - "
        f"{format_duration(time.perf_counter() - journal_started)}"
    )

    event_probe_path, event_probe_error = _refresh_event_character_probe(
        ACTIVE_CAMPAIGN_ID
    )

    diagnostic_path = None
'''


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _insert_once(text: str, anchor: str, replacement: str, label: str, log: list[str]) -> str:
    if replacement in text:
        log.append(f"{label}: already present.")
        return text
    if anchor not in text:
        raise RuntimeError(f"Could not locate expected app.py anchor for {label}.")
    log.append(f"{label}: installed.")
    return text.replace(anchor, replacement, 1)


def patch_app(log: list[str]) -> None:
    original = APP_PATH.read_text(encoding="utf-8")
    updated = original

    if IMPORT_LINE not in updated:
        if IMPORT_ANCHOR not in updated:
            raise RuntimeError("Could not locate app.py import anchor.")
        updated = updated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)
        log.append("app.py event-probe import installed.")
    else:
        log.append("app.py event-probe import already present.")

    if "def _refresh_event_character_probe(campaign_id: int):" not in updated:
        if GLOBAL_ANCHOR not in updated:
            raise RuntimeError("Could not locate app.py global helper anchor.")
        updated = updated.replace(GLOBAL_ANCHOR, HELPER, 1)
        log.append("app.py event-probe helper installed.")
    else:
        log.append("app.py event-probe helper already present.")

    updated = _insert_once(
        updated,
        REVIEW_ANCHOR,
        REVIEW_REPLACEMENT,
        "Review Campaign event-probe hook",
        log,
    )
    updated = _insert_once(
        updated,
        CONSTRUCT_ANCHOR,
        CONSTRUCT_REPLACEMENT,
        "Construct Campaign event-probe hook",
        log,
    )

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
        f"[{stamp()}] Stellaris Historian v0.0.43 event/character deep-probe migration started.",
        "No archived save, campaign identity, database schema, processed flag or parsed-cache version is modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.43 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.43 files are incomplete. Nothing was intentionally changed.")
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
        print("ERROR: v0.0.43 validation failed.")
        print("The original app.py backup is retained if a source change was attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.43 event/character deep-probe migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "People cache remains v5; no 299-save raw cache refresh is required by v0.0.43.",
        "Review Campaign now generates diagnostics/Event_Character_Probe_Debug.txt.",
        "The probe locates leader exits from cached history and opens only previous/current/next raw save windows around those exits.",
        "The probe records event/notification counter deltas, player_event selection IDs, exact-ID saved_event_target blocks, event-adjacent leader-ID contexts, and raw available_trait/cooldown/delayed_event evidence.",
        "All event correlations remain non-causal until stronger evidence establishes meaning.",
        "Run Review Campaign once after installation to generate the new diagnostic.",
        "Construct Campaign is not required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.43 event / character deep-probe migration complete.")
    print("People cache remains v5; no full raw cache refresh is required.")
    print("Run Review Campaign once to generate Event_Character_Probe_Debug.txt.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
