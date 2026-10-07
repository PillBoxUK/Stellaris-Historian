from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_39_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.39.log"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "assets/stellaris_banner.txt",
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian_manifest.json",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.39.md",
]

COMPILE_CHECKS = [
    "app.py",
    "historian/history_processor.py",
]

DIAGNOSTIC_FILENAMES = (
    "Science_Evidence_Debug.txt",
    "Science_Interpretation_Debug.txt",
    "Combat_Evidence_Debug.txt",
    "Combat_Correlation_Debug.txt",
    "Historical_Event_Debug.txt",
    "Technology_Evidence_Debug.txt",
)

EXCLUDED_ROOT_NAMES = {
    ".venv",
    "backups",
    "Updates and source",
}


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _excluded(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True
    return any(part in EXCLUDED_ROOT_NAMES for part in rel.parts)


def _looks_like_campaign_archive(path: Path) -> bool:
    try:
        return any(path.glob("*.sav"))
    except OSError:
        return False


def move_legacy_diagnostics(log: list[str]) -> tuple[int, int]:
    moved = 0
    retained = 0
    candidate_dirs: set[Path] = set()

    for filename in DIAGNOSTIC_FILENAMES:
        for source in ROOT.rglob(filename):
            if _excluded(source):
                continue
            if source.parent.name.lower() == "diagnostics":
                continue
            if not _looks_like_campaign_archive(source.parent):
                continue
            candidate_dirs.add(source.parent)

    for archive_dir in sorted(candidate_dirs, key=lambda p: str(p).lower()):
        diagnostic_dir = archive_dir / "diagnostics"
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        log.append(f"Campaign diagnostics directory: {diagnostic_dir}")

        for filename in DIAGNOSTIC_FILENAMES:
            source = archive_dir / filename
            if not source.is_file():
                continue
            destination = diagnostic_dir / filename
            if destination.exists():
                retained += 1
                log.append(
                    f"  RETAINED legacy source because destination already exists: {source}"
                )
                continue
            shutil.move(str(source), str(destination))
            moved += 1
            log.append(f"  MOVED {source.name} -> diagnostics/{destination.name}")

    return moved, retained


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.39 diagnostics housekeeping/launcher validation started.",
        "No database schema, archived save, parsed cache or processed flag is modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.39 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.39 files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.39 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        moved, retained = move_legacy_diagnostics(log)
    except Exception as exc:
        log.append(f"ABORTED: legacy diagnostic housekeeping failed: {exc!r}")
        write_log(log)
        print("ERROR: v0.0.39 diagnostic housekeeping failed.")
        print("No archived .sav files were intentionally modified.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.39 diagnostics housekeeping and launcher repair completed.\n",
        encoding="utf-8",
    )

    log.extend([
        f"Legacy diagnostic files moved into campaign diagnostics folders: {moved}",
        f"Legacy diagnostic files retained because a destination already existed: {retained}",
        "Review Campaign and Construct Campaign now write all diagnostic text files into <campaign archive>/diagnostics/.",
        "The console now prints the exact diagnostics directory before diagnostic generation.",
        "Launcher ASCII is displayed from assets/stellaris_banner.txt using TYPE instead of ECHO commands.",
        "No cache version changes are required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.39 diagnostics housekeeping and launcher validation complete.")
    print(f"Legacy diagnostic files moved: {moved}")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
