from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import re
import shutil


ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_52_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.52.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.52"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "docs/CHANGELOG.md",
    "historian/__init__.py",
    "historian/war_journal.py",
    "historian_manifest.json",
    "static/campaign.html",
    "static/campaign.js",
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
    log.append(f"Backed up {relative} -> backups/v0.0.52/{relative}")


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
    updated = original.replace('__version__ = "0.0.51"', '__version__ = "0.0.52"', 1)
    if updated == original and '__version__ = "0.0.52"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.51 to 0.0.52.")
    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_line = "from historian.war_journal import render_war_journal\n"
    if import_line not in updated:
        anchor = "from historian.timeline import render_timeline\n"
        if anchor not in updated:
            raise RuntimeError("Could not locate app.py timeline import anchor.")
        updated = updated.replace(anchor, anchor + import_line, 1)

    route = '''@app.get("/war-journal")\ndef open_war_journal():\n    if ACTIVE_CAMPAIGN_ID is None:\n        raise HTTPException(400, "No campaign is active.")\n\n    try:\n        path = render_war_journal(DB, ACTIVE_CAMPAIGN_ID)\n    except Exception as exc:\n        error(f"WAR JOURNAL - {exc}")\n        raise HTTPException(500, f"War Journal could not be rendered: {exc}") from exc\n\n    return FileResponse(\n        path,\n        media_type="text/html",\n        headers={"Cache-Control": "no-store, max-age=0"},\n    )\n\n\n'''
    if '@app.get("/war-journal")' not in updated:
        anchor = '@app.get("/scribes")\n'
        if anchor not in updated:
            raise RuntimeError("Could not locate app.py Scribes route anchor.")
        updated = updated.replace(anchor, route + anchor, 1)

    ast.parse(updated, filename="app.py")
    write_if_changed(path, original, updated, log)


def patch_campaign_html(log: list[str]) -> None:
    path = ROOT / "static" / "campaign.html"
    original = path.read_text(encoding="utf-8")
    updated = original

    if 'id="view-war-journal"' not in updated:
        pattern = re.compile(
            r'(?P<indent>^[ \t]*)<button id="view-journal" type="button" disabled>\s*'
            r'View Journal\s*</button>',
            re.M,
        )
        match = pattern.search(updated)
        if not match:
            raise RuntimeError("Could not locate campaign View Journal button anchor.")
        indent = match.group("indent")
        addition = (
            match.group(0)
            + "\n\n"
            + indent + '<button id="view-war-journal" type="button" disabled>\n'
            + indent + "  War Journal\n"
            + indent + "</button>"
        )
        updated = updated[:match.start()] + addition + updated[match.end():]

    updated = re.sub(r'/static/campaign\.js\?v=\d+', '/static/campaign.js?v=012', updated, count=1)
    write_if_changed(path, original, updated, log)


def patch_campaign_js(log: list[str]) -> None:
    path = ROOT / "static" / "campaign.js"
    original = path.read_text(encoding="utf-8")
    updated = original

    const_line = 'const viewWarJournalButton = document.getElementById("view-war-journal");\n'
    if const_line not in updated:
        anchor = 'const viewJournalButton = document.getElementById("view-journal");\n'
        if anchor not in updated:
            raise RuntimeError("Could not locate campaign.js View Journal constant anchor.")
        updated = updated.replace(anchor, anchor + const_line, 1)

    availability = '''\n  viewWarJournalButton.disabled =\n    actionInProgress || liveBusy || archived === 0 || unprocessed > 0;\n\n  viewWarJournalButton.title = liveBusy\n    ? "Wait for the current Live History update to finish before opening the War Journal."\n    : (unprocessed > 0\n      ? "Run Update History first so the War Journal uses fully processed evidence."\n      : (archived > 0\n        ? "Open the evidence-led War Journal for this campaign."\n        : "No archived saves are available for the War Journal."));\n'''
    if "viewWarJournalButton.disabled" not in updated:
        anchor = '''  constructButton.disabled =\n    actionInProgress || liveBlocking || archived === 0;\n'''
        if anchor not in updated:
            raise RuntimeError("Could not locate campaign.js Construct availability anchor.")
        updated = updated.replace(anchor, anchor + availability, 1)

    listener = '''viewWarJournalButton.addEventListener("click", () => {\n  window.open(\n    "/war-journal",\n    "_blank",\n    "noopener"\n  );\n});\n\n'''
    if 'viewWarJournalButton.addEventListener("click"' not in updated:
        anchor = 'viewJournalButton.addEventListener("click", () => {\n'
        if anchor not in updated:
            raise RuntimeError("Could not locate campaign.js View Journal listener anchor.")
        updated = updated.replace(anchor, listener + anchor, 1)

    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = """## v0.0.52\n- Adds a dedicated evidence-led `War_Journal.html` generated from existing reviewed combat cache data.\n- Adds a War Journal control to the active-campaign dashboard and a local `/war-journal` render route.\n- Keeps retained formal wars separate from reconstructed combat episodes so fauna/guardian fighting is not silently promoted into a diplomatic war.\n- Formal-war cards preserve retained start/observation windows, player side, war goals, latest exhaustion values and direct player battle rows.\n- Combat-episode cards preserve systems, opposing forces, fleets, commanders, direct retained loss telemetry and possible-but-unconfirmed loss identities.\n- Formal victory/defeat is published only where retained formal battle evidence establishes it.\n- The renderer reads the shared presentation layer and snapshot cache; it does not silently reparse Ironman saves.\n- No SQLite schema, parsed-cache component version, archived-save or processed-flag changes.\n\n"""
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
    data["version"] = "0.0.52"
    data["architecture"] = "modular-foundation-31-war-journal-foundation"
    data["war_journal"] = {
        "status": "evidence-led-foundation",
        "path": "<campaign archive>/War_Journal.html",
        "route": "/war-journal",
        "source": "shared presentation history and reviewed combat cache",
        "formal_wars_separate_from_combat_episodes": True,
        "formal_outcome_requires_formal_battle_evidence": True,
        "raw_save_reparse": False,
        "cache_version_change": False,
        "database_schema_change": False,
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def validate_readme(log: list[str]) -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "v0.0.52 — War Journal Foundation",
        "War_Journal.html",
        "Formal Wars",
        "Combat Episodes",
        "No SQLite schema change",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("README.md is not the v0.0.52 War Journal README: " + ", ".join(missing))
    log.append("Validated README.md v0.0.52 War Journal documentation.")


def validate_source(log: list[str]) -> None:
    war_path = ROOT / "historian" / "war_journal.py"
    war_text = war_path.read_text(encoding="utf-8")
    ast.parse(war_text, filename="war_journal.py")
    for token in (
        "def render_war_journal",
        "def war_journal_path",
        "Formal Wars",
        "Combat Episodes",
        "Outcome not established",
    ):
        if token not in war_text:
            raise RuntimeError(f"historian/war_journal.py missing expected v0.0.52 token: {token}")
    log.append("Validated v0.0.52 War Journal renderer source.")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.52 War Journal foundation migration started.",
        "No archived Stellaris saves, campaign history rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.52 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.52 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        validate_source(log)
        validate_readme(log)
        patch_version(log)
        patch_app(log)
        patch_campaign_html(log)
        patch_campaign_js(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError, re.error) as exc:
        log.append(f"ABORTED: v0.0.52 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.52 migration failed.")
        print("Original source/UI backups are retained under backups\\v0.0.52 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.52 War Journal foundation migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Installed dedicated War_Journal.html renderer over existing reviewed combat evidence.",
        "Installed /war-journal route and active-campaign War Journal button.",
        "Formal wars remain separate from reconstructed combat episodes.",
        "Formal victory/defeat remains evidence-gated by retained formal battle state.",
        "No raw-save reparse, SQLite schema change or parsed-cache version bump is required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.52 War Journal foundation migration complete.")
    print("The campaign dashboard now includes a War Journal button.")
    print("Formal wars and reconstructed combat episodes are kept separate and evidence-gated.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
