from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile


ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_36_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.36.log"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "requirements.txt",
    "historian/__init__.py",
    "historian/journal.py",
    "historian/scribes.py",
    "historian/timeline.py",
    "historian_manifest.json",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.36.md",
]

COMPILE_CHECKS = [
    "app.py",
    "historian/journal.py",
    "historian/scribes.py",
    "historian/timeline.py",
]

DISPOSABLE_DIRS = [
    "__pycache__",
    "historian/__pycache__",
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
        f"[{stamp()}] Stellaris Historian v0.0.36 presentation validation started.",
        "Presentation-only update: no database schema, campaign archive, parsed cache or processed flag is modified.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.36 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.36 files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8", errors="replace")
    if "reportlab" not in requirements.lower():
        log.append("ABORTED: reportlab is missing from requirements.txt.")
        write_log(log)
        print("ERROR: v0.0.36 PDF dependency declaration is missing. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.36 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    for name in DISPOSABLE_DIRS:
        path = ROOT / name
        if path.exists():
            remove_tree(path)
            log.append(f"Cleaned disposable bytecode: {name}")

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.36 timeline and chronicle export validation completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Added the /timeline Empire Timeline presentation and Empire_Timeline.html output.",
        "Added direct /scribes/pdf generation using ReportLab and Scribes_Chronicle.pdf output.",
        "Added evidence-led ruler authorship/sign-off blocks to Scribes chapters using dated cached ruler observations.",
        "The final Scribes note is deliberately left unsigned because the active campaign record remains open.",
        "Historical Journal and Scribes navigation now link to the Empire Timeline.",
        "No combat outcome, casualty, speech, motive, death or succession cause is invented by this patch.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.36 timeline and chronicle export validation complete.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
