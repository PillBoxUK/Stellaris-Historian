from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import re
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_51_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.51.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.51"

REQUIRED_FILES = [
    "start.bat",
    "README.md",
    "docs/CHANGELOG.md",
    "historian/__init__.py",
    "historian/console.py",
    "historian_manifest.json",
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
    log.append(f"Backed up {relative} -> backups/v0.0.51/{relative}")


def write_if_changed(path: Path, original: str, updated: str, log: list[str]) -> None:
    if updated == original:
        log.append(f"No change needed: {path.relative_to(ROOT)}")
        return
    backup(path, log)
    path.write_text(updated, encoding="utf-8", newline="\n")
    log.append(f"Updated: {path.relative_to(ROOT)}")


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('__version__ = "0.0.50.4"', '__version__ = "0.0.51"', 1)
    if updated == original and '__version__ = "0.0.51"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.50.4 to 0.0.51.")
    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")

    current_section = """## Current version

### v0.0.51 — Console Completion Banner & Workflow Clarity

v0.0.51 is a small workflow-quality release built on the tested v0.0.50.4 First Contact line. It makes long manual Historian operations unmistakably finish in the command window, so a completed Review, Update or Construct run no longer looks as though it may still be working.

### What changed in v0.0.51

- Adds a large final `ALL UPDATES ARE COMPLETED` console banner after a successful manual **Update History**, **Review Campaign** or **Construct Campaign** operation has genuinely finished.
- Keeps the banner until the next console activity naturally scrolls it away; the command window itself remains open as before.
- Prints `PROCESS COMPLETED WITH ERRORS` instead when the active manual workflow logged one or more errors.
- Tracks Review/Construct aborts and journal-refresh failures so failed operations do not receive a success banner.
- Deliberately suppresses completion banners for automatic **Live History** cycles, preventing repetitive banner spam while playing.
- Leaves campaign data, SQLite schema, processed flags, archived saves and parsed-cache component versions unchanged.

### Code areas changed in v0.0.51

- `historian/console.py` — manual-operation state tracking, Live History suppression and atomic success/error completion banners.
- `migrate_v0_0_51.py` — one-time version/metadata migration and source validation.
- `start.bat` — v0.0.51 startup banner and migration hook.
- `README.md`, `docs/CHANGELOG.md` and `historian_manifest.json` — updated by the migration with v0.0.51 release metadata.
"""

    pattern = re.compile(r"## Current version\n\n.*?(?=\n## Recent development progress)", re.S)
    if not pattern.search(original):
        raise RuntimeError("Could not locate README Current version section.")
    updated = pattern.sub(current_section.rstrip() + "\n", original, count=1)

    current_row = "| **v0.0.51** | Unmistakable manual workflow completion/error banner in the CMD window | Current development version |\n"
    progress_heading = "## Recent development progress\n\n| Version | Main change | Status |\n| --- | --- | --- |\n"
    if progress_heading not in updated:
        raise RuntimeError("Could not locate README Recent development progress table.")
    if current_row not in updated:
        updated = updated.replace(progress_heading, progress_heading + current_row, 1)

    updated = updated.replace(
        "| **v0.0.50.4** | Stellaris adjective inflection for generated First Contact names; owner diagnostic polish | Current development version |",
        "| **v0.0.50.4** | Stellaris adjective inflection for generated First Contact names; owner diagnostic polish | Tested and retained |",
        1,
    )
    updated = updated.replace(
        "The v0.0.50.x First Contact work does **not** change the SQLite schema or parsed-cache component version, so no full cache rebuild is required for v0.0.50.4.",
        "v0.0.51 changes console workflow presentation only. It does **not** change the SQLite schema or parsed-cache component versions, so no full cache rebuild is required.",
        1,
    )
    updated = updated.replace(
        "Current development priorities include final validation of generated First Contact identity resolution, richer combat/war presentation, and continuing to turn retained Stellaris save evidence into a reliable long-form campaign history.",
        "Current development priorities include clearer workflow/status feedback, richer combat/war presentation, and continuing to turn retained Stellaris save evidence into a reliable long-form campaign history.",
        1,
    )
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = """## v0.0.51
- Adds an unmistakable final `ALL UPDATES ARE COMPLETED` banner after successful manual Update History, Review Campaign and Construct Campaign workflows.
- Prints `PROCESS COMPLETED WITH ERRORS` when the active manual workflow logged errors, including Review/Construct refresh failures.
- Tracks manual workflow boundaries inside the console logger so the banner appears only after the operation's final journal/refresh step.
- Suppresses completion banners for automatic Live History cycles to avoid repetitive console spam during normal play.
- No SQLite schema, parsed-cache, archived-save or processed-flag changes.

"""
    if section not in original:
        anchor = "# Changelog\n\n"
        if anchor not in original:
            anchor = "# Stellaris Historian Changelog\n\n"
        if anchor not in original:
            raise RuntimeError("Could not locate CHANGELOG heading.")
        updated = original.replace(anchor, anchor + section, 1)
    else:
        updated = original
    write_if_changed(path, original, updated, log)


def patch_manifest(log: list[str]) -> None:
    path = ROOT / "historian_manifest.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["version"] = "0.0.51"
    data["architecture"] = "modular-foundation-30-console-completion-banner"
    workflow = data.setdefault("console_workflow", {})
    workflow.update({
        "status": "manual-operation-completion-banner",
        "success_banner": "ALL UPDATES ARE COMPLETED",
        "error_banner": "PROCESS COMPLETED WITH ERRORS",
        "manual_operations": ["Update History", "Review Campaign", "Construct Campaign"],
        "live_history_banner_suppressed": True,
        "cache_version_change": False,
        "database_schema_change": False,
    })
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def validate_console(log: list[str]) -> None:
    path = ROOT / "historian" / "console.py"
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename="console.py")
    required = [
        "ALL UPDATES ARE COMPLETED",
        "PROCESS COMPLETED WITH ERRORS",
        "UPDATE HISTORY START - ",
        "REVIEW START - ",
        "CONSTRUCT CAMPAIGN START - ",
        "LIVE HISTORY - Historical_Journal.html refresh complete -",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("historian/console.py is not the v0.0.51 completion-banner build: " + ", ".join(missing))
    log.append("Validated v0.0.51 console completion-banner source.")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.51 console completion-banner migration started.",
        "No archived Stellaris saves, campaign history rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.51 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.51 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        validate_console(log)
        patch_version(log)
        patch_readme(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.51 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.51 migration failed.")
        print("Original metadata/source backups are retained under backups\\v0.0.51 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.51 console completion-banner migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Manual Update History, Review Campaign and Construct Campaign now receive a final completion banner.",
        "Manual workflows with logged errors receive an explicit error completion banner instead of a success banner.",
        "Automatic Live History cycles are excluded from completion banners.",
        "README, changelog and manifest release metadata updated to v0.0.51.",
        "Existing parsed cache component versions remain unchanged.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.51 console completion-banner migration complete.")
    print("Manual Update History, Review Campaign and Construct Campaign runs now finish with an unmistakable CMD completion banner.")
    print("Live History cycles remain quiet and do not print the manual completion banner.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
