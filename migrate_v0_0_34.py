from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_34_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.34.log"

REQUIRED_FILES = [
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/domains/combat/__init__.py",
    "historian/domains/combat/models.py",
    "historian/domains/combat/parser.py",
    "historian/domains/combat/cache.py",
    "historian/domains/combat/diagnostic.py",
    "historian_manifest.json",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.34.md",
]

DISPOSABLE_DIRS = [
    "__pycache__",
    "historian/__pycache__",
    "historian/domains/combat/__pycache__",
]

COMPILE_CHECKS = [
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/domains/combat/models.py",
    "historian/domains/combat/parser.py",
    "historian/domains/combat/cache.py",
    "historian/domains/combat/diagnostic.py",
]


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            try:
                child.rmdir()
            except OSError:
                pass
    try:
        path.rmdir()
    except OSError:
        pass


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.34 combat activity evidence migration started.",
        "Protected campaign archives, historian.db and processed flags are not modified by this migration.",
        "Combat cache component advances from v1 to v2; other valid cache components remain reusable.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.34 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.34 migration files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.34 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    for name in DISPOSABLE_DIRS:
        path = ROOT / name
        if path.exists():
            remove_tree(path)
            log.append(f"Cleaned disposable bytecode: {name}")

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.34 combat activity evidence migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Existing cache containers remain valid. The first Review/Construct will extend combat component v2 where needed.",
        "Combat v2 records exact ship and starbase last_combat_activity dates in addition to formal war/battle evidence.",
        "Fleet, commander and system values attached to activity markers remain snapshot context, not inferred battle facts.",
        "Combat evidence remains diagnostic-only and is not published into the Historical Journal in v0.0.34.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.34 combat activity evidence migration complete.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
