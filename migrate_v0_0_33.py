from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import zipfile


ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_33_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.33.log"
BACKUP_PATH = ROOT / "backups" / "pre_v0.0.33_code.zip"

REQUIRED_NEW_FILES = [
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
    "docs/MIGRATION_v0.0.33.md",
]

OBSOLETE_FILES = [
    "migrate_v0_0_32.py",
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
        f"[{stamp()}] Stellaris Historian v0.0.33 combat evidence foundation migration started.",
        "Protected campaign archives, historian.db, processed flags and existing parsed snapshot data are not deleted by this migration.",
        "A new combat cache component v1 is added alongside the existing modular cache components.",
    ]

    missing = [name for name in REQUIRED_NEW_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.33 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.33 migration files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.33 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    existing_obsolete = [name for name in OBSOLETE_FILES if (ROOT / name).is_file()]
    if existing_obsolete and not BACKUP_PATH.exists():
        BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(BACKUP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in existing_obsolete:
                archive.write(ROOT / name, arcname=name)
        log.append(f"Created pre-migration code backup: {BACKUP_PATH}")

    for name in existing_obsolete:
        try:
            (ROOT / name).unlink()
            log.append(f"Removed obsolete migration helper: {name}")
        except OSError as exc:
            log.append(f"WARNING: could not remove {name}: {exc}")

    for name in DISPOSABLE_DIRS:
        path = ROOT / name
        if path.exists():
            remove_tree(path)
            log.append(f"Cleaned disposable bytecode: {name}")

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.33 combat evidence foundation migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Existing cache containers remain valid. The first Review Campaign will extend cached snapshots with combat component v1 where needed.",
        "Combat evidence currently records player-related wars and direct player battle records retained by Stellaris.",
        "Ship/fleet disappearance is not treated as proof of destruction.",
        "Combat evidence is diagnostic-only in v0.0.33; it is not yet published into the Historical Journal.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.33 combat evidence foundation migration complete.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
