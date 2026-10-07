from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_50_3_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.50.3.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.50.3"

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
    log.append(f"Backed up {relative} -> backups/v0.0.50.3/{relative}")


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
    updated = original.replace('__version__ = "0.0.50.2"', '__version__ = "0.0.50.3"', 1)
    if updated == original and '__version__ = "0.0.50.3"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.50.2 to 0.0.50.3.")
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = """## v0.0.50.3\n- Adds nested Stellaris `%ADJ%` / `%ADJECTIVE%` country-name grammar needed by generated empire identities.\n- Rejects technical raw keys such as `build_waystation_poi_name`, `gateway_system`, `observing_country`, `this_country` and similar script identifiers before localisation can turn them into misleading public names.\n- Cleans unresolved `NAME_*` country-name tokens with a conservative human-readable fallback when installed localisation does not resolve the key.\n- Continues scanning later cached `relations_manager` names after rejected technical candidates rather than stopping at the first readable localisation.\n- Adds accepted/rejected candidate state, rejection reason, source date and country-name attempts to `First_Contact_History_Debug.txt` / JSON.\n- Keeps reciprocal First Contact completion detection and generic Politics/Diplomacy high-ID filtering unchanged.\n- Replaces the root `README.md` with expanded current-version details, recent development progress, evidence-first rules, generated outputs and known limitations.\n- No SQLite schema change, parsed-cache version bump, archive rewrite or full cache rebuild.\n\n"""
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
    data["version"] = "0.0.50.3"
    data["architecture"] = "modular-foundation-28-first-contact-name-grammar-quality"
    fc = data.setdefault("first_contact_history", {})
    fc.update({
        "status": "structured-decoder-generated-name-grammar-and-candidate-quality",
        "cache_version_change": False,
        "database_schema_change": False,
        "name_resolution": "Render nested %ADJ%/%ADJECTIVE% generated-name grammar, reject technical raw identifiers before localisation, prefer clean NAME_* fallback, and continue later country/relation candidate search.",
        "completion_rule": "Unchanged from v0.0.50.1: player or reciprocal counterpart completion marker must appear across the assignment-end interval unless a direct exact field is decoded.",
    })
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def validate_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    required = [
        "v0.0.50.3 — First Contact Name Grammar & Candidate Quality Hotfix",
        "## Recent development progress",
        "## Evidence-first design",
        "## Known limitations",
        "## Important — use at your own risk",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("README.md is not the expanded v0.0.50.3 README: " + ", ".join(missing))
    log.append("Validated expanded README.md current-version/progress documentation.")


def main() -> int:
    if MARKER.exists():
        return 0
    log = [
        f"[{stamp()}] Stellaris Historian v0.0.50.3 First Contact name-grammar hotfix migration started.",
        "No archived Stellaris saves, campaign identity, SQLite rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.50.3 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.50.3 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1
    try:
        history = (ROOT / "historian/domains/politics/first_contact_history.py").read_text(encoding="utf-8")
        journal = (ROOT / "historian/domains/politics/first_contact_journal.py").read_text(encoding="utf-8")
        ast.parse(history, filename="first_contact_history.py")
        ast.parse(journal, filename="first_contact_journal.py")
        if '"version": "0.0.50.3"' not in history:
            raise RuntimeError("The v0.0.50.3 First Contact history module was not copied into place.")
        validate_readme(log)
        patch_version(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.50.3 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.50.3 migration failed.")
        print("Original source backups are retained under backups\\v0.0.50.3 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("Stellaris Historian v0.0.50.3 First Contact name-grammar hotfix completed.\n", encoding="utf-8")
    log.extend([
        "Nested %ADJ% / %ADJECTIVE% generated-country-name grammar installed.",
        "Technical name-key rejection and NAME_* cleanup installed.",
        "Later relations_manager candidate scanning now preserves rejection reasons and continues after technical labels.",
        "Expanded README.md installed.",
        "Two-sided First Contact completion-marker detection remains unchanged.",
        "Existing parsed cache component versions remain unchanged.",
        "Migration completed successfully.",
    ])
    write_log(log)
    print("v0.0.50.3 First Contact name-grammar hotfix complete.")
    print("Generated %ADJ% / %ADJECTIVE% empire names are now rendered recursively before publication.")
    print("Technical relation/localisation labels are rejected; NAME_* fallbacks and candidate diagnostics were improved.")
    print("README.md now includes detailed current-version, progress and code-change information.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
