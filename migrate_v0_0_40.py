from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_40_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.40.log"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian/historical_events.py",
    "historian/domains/combat/episodes.py",
    "historian/domains/people/exit_diagnostic.py",
    "historian_manifest.json",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.40.md",
]

COMPILE_CHECKS = [
    "app.py",
    "historian/history_processor.py",
    "historian/historical_events.py",
    "historian/domains/combat/episodes.py",
    "historian/domains/people/exit_diagnostic.py",
]


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.40 combat episode validation started.",
        "No database schema, archived save, parsed cache or processed flag is modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.40 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.40 files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.40 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.40 combat episode/event-layer validation completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Combat Episode Synthesis is installed.",
        "Historical Event Layer v0.0.40 is installed.",
        "Leader exit evidence diagnostic is installed.",
        "No cache version changes are required.",
        "Run Review Campaign once to regenerate the new Combat_Episode_Debug.txt, Leader_Exit_Evidence_Debug.txt and Historical_Event_Debug.txt outputs.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.40 combat episode and event-layer validation complete.")
    print("No database or cache migration was required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
