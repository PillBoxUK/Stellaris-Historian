from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_50_1_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.50.1.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.50.1"

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
    log.append(f"Backed up {relative} -> backups/v0.0.50.1/{relative}")


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
    updated = original.replace('__version__ = "0.0.50"', '__version__ = "0.0.50.1"', 1)
    if updated == original and '__version__ = "0.0.50.1"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.50 to 0.0.50.1.")
    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original.replace("## Current version\n\nv0.0.50", "## Current version\n\nv0.0.50.1", 1)
    anchor = "- Structured First Contact decoder extracts individual contact records, counterpart identity and conservative completion evidence into the Historical Journal\n"
    addition = anchor + "- First Contact resolution hotfix renders saved Stellaris name templates and checks reciprocal completion markers for normal dynamic empires\n"
    if "First Contact resolution hotfix" not in updated:
        if anchor not in updated:
            raise RuntimeError("Could not locate README structured First Contact feature anchor.")
        updated = updated.replace(anchor, addition, 1)
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.50.1\n- Hotfixes structured First Contact resolution after live Commonwealth testing exposed two retained-save edge cases.\n- Renders modern Stellaris templated country names using the saved `name` key, nested `variables` and local localisation instead of publishing a raw template key such as `build_waystation_poi_name`.\n- Checks both completion directions: player `first_contact_completed<counterpart_id>` and reciprocal counterpart `first_contact_completed<player_id>`.\n- Allows directly evidenced First Contact counterparts with dynamic high country IDs when their resolved name is a real diplomatic actor; the broader Politics/Diplomacy pseudo-country filter remains unchanged.\n- Expands `First_Contact_History_Debug.txt` with name-resolution candidates/method and two-sided completion evidence.\n- Keeps response-choice fields diagnostic-only and keeps exact-date rules conservative.\n- No SQLite schema change, parsed-cache version bump, archive rewrite or full cache rebuild.\n\n'''
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
    data["version"] = "0.0.50.1"
    data["architecture"] = "modular-foundation-26-first-contact-resolution-hotfix"
    fc = data.setdefault("first_contact_history", {})
    fc.update({
        "status": "structured-decoder-two-sided-completion-and-template-name-resolution",
        "cache_version_change": False,
        "database_schema_change": False,
        "name_resolution": "Render saved Stellaris country-name key/variables through local localisation; unresolved templates remain diagnostic-only.",
        "completion_rule": "Publish only when player first_contact_completed<counterpart_id> or reciprocal counterpart first_contact_completed<player_id> first appears across the assignment-end interval, unless a direct exact completion field is decoded.",
        "high_dynamic_country_ids": "Allowed in First Contact only when the contact record directly identifies the country and its resolved name passes pseudo-actor filtering; generic Politics filter is unchanged.",
    })
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def main() -> int:
    if MARKER.exists():
        return 0
    log = [
        f"[{stamp()}] Stellaris Historian v0.0.50.1 First Contact resolution hotfix migration started.",
        "No archived Stellaris saves, campaign identity, SQLite rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.50.1 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.50.1 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1
    try:
        history = (ROOT / "historian/domains/politics/first_contact_history.py").read_text(encoding="utf-8")
        journal = (ROOT / "historian/domains/politics/first_contact_journal.py").read_text(encoding="utf-8")
        ast.parse(history, filename="first_contact_history.py")
        ast.parse(journal, filename="first_contact_journal.py")
        if '"version": "0.0.50.1"' not in history:
            raise RuntimeError("The v0.0.50.1 First Contact history module was not copied into place.")
        patch_version(log)
        patch_readme(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.50.1 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.50.1 migration failed.")
        print("Original source backups are retained under backups\\v0.0.50.1 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("Stellaris Historian v0.0.50.1 First Contact resolution hotfix completed.\n", encoding="utf-8")
    log.extend([
        "Modern templated First Contact country-name resolver installed.",
        "Two-sided First Contact completion-marker detection installed.",
        "First Contact high dynamic country IDs can be published only with direct contact evidence plus a clean resolved name.",
        "Generic Politics/Diplomacy pseudo-country filtering was not changed.",
        "Existing parsed cache component versions remain unchanged.",
        "Migration completed successfully.",
    ])
    write_log(log)
    print("v0.0.50.1 First Contact resolution hotfix complete.")
    print("Dynamic Stellaris country-name templates are now rendered from saved variables and local localisation.")
    print("First Contact completion now checks both player-side and reciprocal counterpart-side completion markers.")
    print("Generic Politics/Diplomacy filtering is unchanged; only directly evidenced First Contact counterparts get the high-ID exception.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
