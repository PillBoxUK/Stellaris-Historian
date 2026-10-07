from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_50_2_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.50.2.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.50.2"

REQUIRED_FILES = [
    "start.bat", "README.md", "docs/CHANGELOG.md", "historian/__init__.py",
    "historian_manifest.json", "historian/domains/politics/first_contact_history.py",
    "historian/domains/politics/first_contact_journal.py",
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
    log.append(f"Backed up {relative} -> backups/v0.0.50.2/{relative}")


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
    updated = original.replace('__version__ = "0.0.50.1"', '__version__ = "0.0.50.2"', 1)
    if updated == original and '__version__ = "0.0.50.2"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.50.1 to 0.0.50.2.")
    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original.replace("## Current version\n\nv0.0.50.1", "## Current version\n\nv0.0.50.2", 1)
    anchor = "- First Contact resolution hotfix renders saved Stellaris name templates and checks reciprocal completion markers for normal dynamic empires\n"
    addition = anchor + "- First Contact name-resolution hotfix ignores nested technical name fields, localises NAME_* tokens and follows the same country id into later diplomatic state\n"
    if "First Contact name-resolution hotfix" not in updated:
        if anchor not in updated:
            raise RuntimeError("Could not locate README v0.0.50.1 feature anchor.")
        updated = updated.replace(anchor, addition, 1)
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = """## v0.0.50.2\n- Fixes dynamic First Contact country-name resolution exposed by the Commonwealth contact-91 test.\n- Country identity extraction now reads only top-level country `name`/identity fields, preventing nested government or pre-communications `name` blocks from being mistaken for the empire name.\n- Localises scalar `NAME_*` values before publication, cleaning names such as `NAME_Spaceborne_Organics`.\n- Follows a First Contact counterpart country id into bounded post-contact raw checkpoints and cached `relations_manager` snapshots to find a later revealed diplomatic name without rereading the whole archive.\n- Adds name source/date and top-level identity hints to `First_Contact_History_Debug.txt`.\n- Keeps the v0.0.50.1 two-sided completion evidence rule unchanged.\n- No SQLite schema change, parsed-cache version bump, archive rewrite or full cache rebuild.\n\n"""
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
    data["version"] = "0.0.50.2"
    data["architecture"] = "modular-foundation-27-first-contact-name-resolution-hotfix"
    fc = data.setdefault("first_contact_history", {})
    fc.update({
        "status": "structured-decoder-post-contact-name-followthrough",
        "cache_version_change": False,
        "database_schema_change": False,
        "name_resolution": "Top-level country fields only; localise NAME_* scalars; bounded later raw checkpoints plus cached relations_manager follow-through for the same country id.",
        "completion_rule": "Unchanged from v0.0.50.1: player or reciprocal counterpart completion marker must appear across the assignment-end interval unless a direct exact field is decoded.",
    })
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def main() -> int:
    if MARKER.exists():
        return 0
    log = [
        f"[{stamp()}] Stellaris Historian v0.0.50.2 First Contact name-resolution hotfix migration started.",
        "No archived Stellaris saves, campaign identity, SQLite rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.50.2 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.50.2 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1
    try:
        history = (ROOT / "historian/domains/politics/first_contact_history.py").read_text(encoding="utf-8")
        journal = (ROOT / "historian/domains/politics/first_contact_journal.py").read_text(encoding="utf-8")
        ast.parse(history, filename="first_contact_history.py")
        ast.parse(journal, filename="first_contact_journal.py")
        if '"version": "0.0.50.2"' not in history:
            raise RuntimeError("The v0.0.50.2 First Contact history module was not copied into place.")
        patch_version(log)
        patch_readme(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.50.2 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.50.2 migration failed.")
        print("Original source backups are retained under backups\\v0.0.50.2 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("Stellaris Historian v0.0.50.2 First Contact name-resolution hotfix completed.\n", encoding="utf-8")
    log.extend([
        "Top-level-only First Contact country identity extraction installed.",
        "Scalar localisation-key cleanup and bounded post-contact name follow-through installed.",
        "Cached relations_manager fallback installed; no additional full raw-save scan is required.",
        "Two-sided First Contact completion-marker detection remains unchanged.",
        "Existing parsed cache component versions remain unchanged.",
        "Migration completed successfully.",
    ])
    write_log(log)
    print("v0.0.50.2 First Contact name-resolution hotfix complete.")
    print("First Contact country names now ignore nested technical name fields and follow the same country id after communications.")
    print("NAME_* scalar values are localised before publication; reciprocal completion logic is unchanged.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
