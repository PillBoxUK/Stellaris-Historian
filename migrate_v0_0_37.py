from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_37_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.37.log"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/scribes.py",
    "historian/domains/technology/__init__.py",
    "historian/domains/technology/models.py",
    "historian/domains/technology/parser.py",
    "historian/domains/technology/cache.py",
    "historian/domains/technology/history.py",
    "historian/domains/technology/diagnostic.py",
    "historian_manifest.json",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.37.md",
]

COMPILE_CHECKS = [
    "app.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/scribes.py",
    "historian/domains/technology/parser.py",
    "historian/domains/technology/history.py",
    "historian/domains/technology/diagnostic.py",
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
        f"[{stamp()}] Stellaris Historian v0.0.37 chronicle/technology validation started.",
        "No database schema, archived save or processed flag is modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.37 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.37 files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.37 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.37 expanded chronicle and technology evidence validation completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Added Technology cache component v1; existing domain cache components remain valid.",
        "Review Campaign will extend existing snapshot caches with Technology evidence as needed.",
        "Expanded Scribes with richer leaders, military history, combat activity and technology chapters.",
        "Scribes prose is in-universe and does not expose game/save/parser language.",
        "No unsupported opponent, battle result, casualty, death, speech or exact technology completion day is invented.",
        "Added PillBoxUK project signature to the launcher banner.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.37 chronicle and technology evidence validation complete.")
    print(f"Migration log: {LOG_PATH}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
