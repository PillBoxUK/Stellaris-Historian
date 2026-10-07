from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_50_4_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.50.4.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.50.4"

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
    log.append(f"Backed up {relative} -> backups/v0.0.50.4/{relative}")


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
    updated = original.replace('__version__ = "0.0.50.3"', '__version__ = "0.0.50.4"', 1)
    if updated == original and '__version__ = "0.0.50.4"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.50.3 to 0.0.50.4.")
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = """## v0.0.50.4\n- Applies installed Stellaris `adj_NN*` adjective suffix grammar inside generated `%ADJECTIVE%` First Contact country names.\n- Fixes the live contact-91 generated form from `Stellar Hazar Council` to `Stellar Hazaran Council` when the installed `r -> *ran` rule is present.\n- Aligns generated-name substitution with Stellaris one-at-a-time placeholder semantics and cleans leftover numeric continuation placeholders.\n- Restores the First Contact diagnostic owner display from the selected campaign identity when the retained owner ID is the player country.\n- Retains v0.0.50.3 technical-key rejection, `NAME_*` cleanup, nested name grammar, candidate diagnostics and reciprocal completion detection.\n- Updates the expanded README with detailed current-version and code-change notes.\n- No SQLite schema change, parsed-cache version bump, archive rewrite or full cache rebuild.\n\n"""
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
    data["version"] = "0.0.50.4"
    data["architecture"] = "modular-foundation-29-first-contact-adjective-inflection"
    fc = data.setdefault("first_contact_history", {})
    fc.update({
        "status": "structured-decoder-generated-name-adjective-inflection",
        "cache_version_change": False,
        "database_schema_change": False,
        "name_resolution": "Render nested %ADJ%/%ADJECTIVE% grammar with installed adj_NN* adjective suffix rules; reject technical identifiers; retain candidate audit data.",
        "completion_rule": "Unchanged: player or reciprocal counterpart completion marker must appear across the assignment-end interval unless a direct exact field is decoded.",
    })
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def validate_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    required = [
        "v0.0.50.4 — First Contact Adjective Inflection & Diagnostic Polish Hotfix",
        "### What changed in v0.0.50.4",
        "### Code areas changed in v0.0.50.4",
        "## Recent development progress",
        "## Evidence-first design",
        "## Known limitations",
        "## Important — use at your own risk",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("README.md is not the expanded v0.0.50.4 README: " + ", ".join(missing))
    log.append("Validated expanded README.md current-version/progress/code-change documentation.")


def main() -> int:
    if MARKER.exists():
        return 0
    log = [
        f"[{stamp()}] Stellaris Historian v0.0.50.4 First Contact adjective-inflection hotfix migration started.",
        "No archived Stellaris saves, campaign identity, SQLite rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.50.4 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.50.4 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1
    try:
        history = (ROOT / "historian/domains/politics/first_contact_history.py").read_text(encoding="utf-8")
        journal = (ROOT / "historian/domains/politics/first_contact_journal.py").read_text(encoding="utf-8")
        ast.parse(history, filename="first_contact_history.py")
        ast.parse(journal, filename="first_contact_journal.py")
        if '"version": "0.0.50.4"' not in history:
            raise RuntimeError("The v0.0.50.4 First Contact history module was not copied into place.")
        validate_readme(log)
        patch_version(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.50.4 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.50.4 migration failed.")
        print("Original source backups are retained under backups\\v0.0.50.4 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("Stellaris Historian v0.0.50.4 First Contact adjective-inflection hotfix completed.\n", encoding="utf-8")
    log.extend([
        "Installed Stellaris adj_NN* adjective suffix rendering for generated First Contact country names.",
        "Generated-name placeholder substitution now mirrors one-at-a-time Stellaris semantics and cleans unresolved numeric continuations.",
        "Player-country owner label restored in First Contact diagnostics from selected campaign identity.",
        "Technical-name filtering, NAME_* cleanup and two-sided completion-marker detection remain unchanged.",
        "Expanded README.md updated for v0.0.50.4.",
        "Existing parsed cache component versions remain unchanged.",
        "Migration completed successfully.",
    ])
    write_log(log)
    print("v0.0.50.4 First Contact adjective-inflection hotfix complete.")
    print("Generated %ADJECTIVE% names now apply installed Stellaris adj_NN* suffix grammar (for example Hazar -> Hazaran).")
    print("First Contact diagnostic owner labels now reuse the selected player-empire identity when appropriate.")
    print("README.md current-version and code-change details were updated.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
