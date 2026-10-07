from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_41_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.41.log"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "historian/__init__.py",
    "historian/historical_events.py",
    "historian/presentation_history.py",
    "historian/timeline.py",
    "historian/scribes.py",
    "historian/domains/combat/episodes.py",
    "historian_manifest.json",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.41.md",
]

COMPILE_CHECKS = [
    "app.py",
    "historian/historical_events.py",
    "historian/presentation_history.py",
    "historian/timeline.py",
    "historian/scribes.py",
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
        f"[{stamp()}] Stellaris Historian v0.0.41 validation started.",
        "No database schema, archived save, parsed cache or processed flag is modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.41 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.41 files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.41 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.41 timeline/Scribes presentation validation completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Empire Timeline now consumes the shared presentation-neutral Historical Event Layer.",
        "Timeline combat rows are synthesized combat episodes rather than raw ship/starbase activity markers.",
        "Scribes Chapter V now consumes synthesized combat episodes and compresses weaker correlated evidence.",
        "Generic unresolved station labels are not promoted into polished Timeline/Scribes battle prose.",
        "Historical Event Layer now exposes richer combat/science attributes for presentation without changing evidence semantics.",
        "No cache version changes are required.",
        "Run Review Campaign once after installation to refresh Historical_Event_Debug.txt under the v0.0.41 event model.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.41 timeline and Scribes episode-renderer validation complete.")
    print("No database or cache migration was required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
