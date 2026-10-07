from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_50_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.50.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.50"

REQUIRED_FILES = [
    "app.py", "start.bat", "README.md", "docs/CHANGELOG.md",
    "historian/__init__.py", "historian/journal.py", "historian_manifest.json",
    "historian/domains/politics/first_contact_probe.py",
    "historian/domains/politics/first_contact_history.py",
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
    log.append(f"Backed up {relative} -> backups/v0.0.50/{relative}")


def write_if_changed(path: Path, original: str, updated: str, log: list[str]) -> None:
    if updated == original:
        log.append(f"No change needed: {path.relative_to(ROOT)}")
        return
    backup(path, log)
    path.write_text(updated, encoding="utf-8", newline="\n")
    log.append(f"Updated: {path.relative_to(ROOT)}")


def replace_once(text: str, old: str, new: str, label: str, log: list[str]) -> str:
    if new in text:
        log.append(f"Already installed: {label}")
        return text
    if old not in text:
        raise RuntimeError(f"Could not locate v0.0.49 anchor for {label}.")
    log.append(f"Installed: {label}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, count: int, label: str, log: list[str]) -> str:
    if text.count(new) >= count:
        log.append(f"Already installed: {label}")
        return text
    found = text.count(old)
    if found < count:
        raise RuntimeError(f"Expected at least {count} v0.0.49 anchor(s) for {label}, found {found}.")
    log.append(f"Installed: {label} ({count} occurrence(s))")
    return text.replace(old, new, count)


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('__version__ = "0.0.49"', '__version__ = "0.0.50"', 1)
    if updated == original and '__version__ = "0.0.50"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.49 to 0.0.50.")
    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_anchor = "from historian.domains.politics.first_contact_probe import write_first_contact_probe\n"
    import_replacement = import_anchor + "from historian.domains.politics.first_contact_history import write_first_contact_history\n"
    updated = replace_once(updated, import_anchor, import_replacement, "structured First Contact import", log)

    helper_anchor = "def safe_name(value: str, max_len: int = 60) -> str:\n"
    helper_replacement = '''def _first_contact_history_refresh(\n    campaign_id: int,\n    step_index: int,\n    total_steps: int,\n):\n    last_reported = 0\n\n    def progress(done: int, total: int, snapshot: dict) -> None:\n        nonlocal last_reported\n        if done == 1 or done == total or done - last_reported >= 10:\n            last_reported = done\n            activity(\n                f"REFRESH [{step_index:02d}/{total_steps:02d}] "\n                "First_Contact_History_Debug.txt - "\n                f"scanning {done}/{total} - {snapshot.get('game_date', 'unknown date')}"\n            )\n\n    return write_first_contact_history(DB, campaign_id, progress=progress)\n\n\ndef _refresh_first_contact_history_for_journal(campaign_id: int, label: str) -> None:\n    try:\n        started = time.perf_counter()\n        write_first_contact_history(DB, campaign_id)\n        activity(\n            f"{label} - structured First Contact history refreshed - "\n            f"{format_duration(time.perf_counter() - started)}"\n        )\n    except Exception as exc:\n        warning(\n            f"{label} - First Contact history refresh failed; "\n            f"journal will continue without new First Contact data: {exc}"\n        )\n\n\ndef safe_name(value: str, max_len: int = 60) -> str:\n'''
    updated = replace_once(updated, helper_anchor, helper_replacement, "structured First Contact refresh helpers", log)

    live_anchor = '''                if result["processed"]:\n                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")\n'''
    live_replacement = '''                if result["processed"]:\n                    _refresh_first_contact_history_for_journal(\n                        campaign_id,\n                        "LIVE HISTORY",\n                    )\n                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")\n'''
    updated = replace_once(updated, live_anchor, live_replacement, "Live History First Contact refresh", log)

    update_anchor = '''    activity(\n        "Rendering Historical_Journal.html..."\n    )\n'''
    update_replacement = '''    _refresh_first_contact_history_for_journal(\n        ACTIVE_CAMPAIGN_ID,\n        "UPDATE HISTORY",\n    )\n\n    activity(\n        "Rendering Historical_Journal.html..."\n    )\n'''
    updated = replace_once(updated, update_anchor, update_replacement, "manual Update History First Contact refresh", log)

    updated = replace_count(
        updated,
        "    refresh_total = 6\n",
        "    refresh_total = 7\n",
        2,
        "seven-step refresh totals",
        log,
    )

    journal_anchor = '''    journal, journal_error = _run_refresh_step(\n        1,\n        refresh_total,\n        "Historical_Journal.html",\n        lambda: render_journal(DB, ACTIVE_CAMPAIGN_ID),\n    )\n'''
    journal_replacement = '''    first_contact_history_path, first_contact_history_error = _run_refresh_step(\n        1,\n        refresh_total,\n        "First_Contact_History_Debug.txt",\n        lambda: _first_contact_history_refresh(ACTIVE_CAMPAIGN_ID, 1, refresh_total),\n    )\n\n    journal, journal_error = _run_refresh_step(\n        2,\n        refresh_total,\n        "Historical_Journal.html",\n        lambda: render_journal(DB, ACTIVE_CAMPAIGN_ID),\n    )\n'''
    updated = replace_count(updated, journal_anchor, journal_replacement, 2, "structured First Contact before journal", log)

    event_anchor = '''    event_probe_path, event_probe_error = _run_refresh_step(\n        2,\n        refresh_total,\n        "Event_Character_Probe_Debug.txt",\n'''
    event_replacement = '''    event_probe_path, event_probe_error = _run_refresh_step(\n        3,\n        refresh_total,\n        "Event_Character_Probe_Debug.txt",\n'''
    updated = replace_count(updated, event_anchor, event_replacement, 2, "Event/Character refresh renumber", log)

    notification_anchor = '''    notification_decoder_path, notification_decoder_error = _run_refresh_step(\n        3,\n        refresh_total,\n        "Notification_Event_Decoder_Debug.txt",\n'''
    notification_replacement = '''    notification_decoder_path, notification_decoder_error = _run_refresh_step(\n        4,\n        refresh_total,\n        "Notification_Event_Decoder_Debug.txt",\n'''
    updated = replace_count(updated, notification_anchor, notification_replacement, 2, "notification refresh renumber", log)

    politics_anchor = '''    politics_probe_path, politics_probe_error = _run_refresh_step(\n        4,\n        refresh_total,\n        "Politics_Diplomacy_Probe_Debug.txt",\n        lambda: _politics_probe_refresh(ACTIVE_CAMPAIGN_ID, 4, refresh_total),\n'''
    politics_replacement = '''    politics_probe_path, politics_probe_error = _run_refresh_step(\n        5,\n        refresh_total,\n        "Politics_Diplomacy_Probe_Debug.txt",\n        lambda: _politics_probe_refresh(ACTIVE_CAMPAIGN_ID, 5, refresh_total),\n'''
    updated = replace_count(updated, politics_anchor, politics_replacement, 2, "Politics refresh renumber", log)

    probe_anchor = '''    first_contact_probe_path, first_contact_probe_error = _run_refresh_step(\n        5,\n        refresh_total,\n        "First_Contact_Probe_Debug.txt",\n        lambda: _first_contact_probe_refresh(ACTIVE_CAMPAIGN_ID, 5, refresh_total),\n'''
    probe_replacement = '''    first_contact_probe_path, first_contact_probe_error = _run_refresh_step(\n        6,\n        refresh_total,\n        "First_Contact_Probe_Debug.txt",\n        lambda: _first_contact_probe_refresh(ACTIVE_CAMPAIGN_ID, 6, refresh_total),\n'''
    updated = replace_count(updated, probe_anchor, probe_replacement, 2, "First Contact probe refresh renumber", log)

    origin_anchor = '''    diagnostic_path, diagnostic_error = _run_refresh_step(\n        6,\n        refresh_total,\n        "Origin_Localisation_Debug.txt",\n'''
    origin_replacement = '''    diagnostic_path, diagnostic_error = _run_refresh_step(\n        7,\n        refresh_total,\n        "Origin_Localisation_Debug.txt",\n'''
    updated = replace_count(updated, origin_anchor, origin_replacement, 2, "Origin refresh renumber", log)

    errors_anchor = '''            event_probe_error,\n            notification_decoder_error,\n            politics_probe_error,\n            first_contact_probe_error,\n            diagnostic_error,\n'''
    errors_replacement = '''            first_contact_history_error,\n            event_probe_error,\n            notification_decoder_error,\n            politics_probe_error,\n            first_contact_probe_error,\n            diagnostic_error,\n'''
    updated = replace_count(updated, errors_anchor, errors_replacement, 2, "structured First Contact refresh error accounting", log)

    ast.parse(updated, filename=str(path))
    write_if_changed(path, original, updated, log)


def patch_journal(log: list[str]) -> None:
    path = ROOT / "historian" / "journal.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_anchor = "from .domains.politics.journal import render_politics_section\n"
    import_replacement = import_anchor + "from .domains.politics.first_contact_journal import render_first_contact_section\n"
    updated = replace_once(updated, import_anchor, import_replacement, "First Contact journal import", log)

    section_anchor = '''    politics_html = render_politics_section(\n        db,\n        campaign_id,\n    )\n\n    science_html = render_science_section(\n'''
    section_replacement = '''    first_contact_html = render_first_contact_section(\n        db,\n        campaign_id,\n    )\n\n    politics_html = render_politics_section(\n        db,\n        campaign_id,\n    )\n\n    science_html = render_science_section(\n'''
    updated = replace_once(updated, section_anchor, section_replacement, "First Contact journal section render", log)

    nav_anchor = '''    if politics_html.strip():\n        nav_links.append(\n            '<a href="#politics-diplomacy">Politics &amp; Diplomacy</a>'\n        )\n'''
    nav_replacement = '''    if first_contact_html.strip():\n        nav_links.append(\n            '<a href="#first-contact-history">First Contact</a>'\n        )\n\n    if politics_html.strip():\n        nav_links.append(\n            '<a href="#politics-diplomacy">Politics &amp; Diplomacy</a>'\n        )\n'''
    updated = replace_once(updated, nav_anchor, nav_replacement, "First Contact journal navigation", log)

    body_anchor = '''  {\n    f'<div id="politics-diplomacy" class="journal-anchor">{politics_html}</div>'\n    if politics_html.strip()\n    else ''\n  }\n'''
    body_replacement = '''  {\n    f'<div id="first-contact-history" class="journal-anchor">{first_contact_html}</div>'\n    if first_contact_html.strip()\n    else ''\n  }\n\n  {\n    f'<div id="politics-diplomacy" class="journal-anchor">{politics_html}</div>'\n    if politics_html.strip()\n    else ''\n  }\n'''
    updated = replace_once(updated, body_anchor, body_replacement, "First Contact journal body", log)

    ast.parse(updated, filename=str(path))
    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original.replace("## Current version\n\nv0.0.49", "## Current version\n\nv0.0.50", 1)
    anchor = "- First Contact evidence probe correlates assignment windows, diplomacy state and targeted raw-save structures\n"
    addition = anchor + "- Structured First Contact decoder extracts individual contact records, counterpart identity and conservative completion evidence into the Historical Journal\n"
    if "Structured First Contact decoder" not in updated:
        if anchor not in updated:
            raise RuntimeError("Could not locate README First Contact feature anchor.")
        updated = updated.replace(anchor, addition, 1)
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.50\n- Added a structured First Contact decoder that matches leader `first_contact_system` location ids to individual `first_contacts.contacts.<id>` records in retained Stellaris saves.\n- Extracts contact owner, counterpart country, pre-contact designation, location, assigned leader, retained record date, stage/status, event id and saved `contact_country` target evidence.\n- Resolves counterpart country ids to country names from the same retained save state and filters non-diplomatic pseudo actors from public narrative.\n- Promotes a conservative First Contact completion only when the counterpart-specific `first_contact_completed<country_id>` marker first appears across the same archived interval in which the First Contact assignment ends, unless a future direct exact completion field is decoded.\n- Adds `diagnostics/First_Contact_History_Debug.txt` and `diagnostics/First_Contact_History.json`.\n- Adds an evidence-first **First Contact** section to `Historical_Journal.html`.\n- Manual Update History and Live History refresh structured First Contact history before rendering the journal.\n- Review Campaign and Construct Campaign now use 7 refresh steps, with structured First Contact history first so the journal can include it immediately.\n- Response-choice keyword candidates are retained diagnostically but are not published without a proven direct retained selection field.\n- No SQLite schema change, no parsed-cache version bump, and no archived `.sav` changes.\n\n'''
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
    data["version"] = "0.0.50"
    data["architecture"] = "modular-foundation-25-structured-first-contact-decoder"
    diagnostics = data.setdefault("diagnostics", {})
    files = diagnostics.setdefault("files", [])
    for name in ("First_Contact_History_Debug.txt", "First_Contact_History.json"):
        if name not in files:
            files.append(name)
    data["first_contact_history"] = {
        "status": "structured-decoder-and-journal-publication",
        "cache_version_change": False,
        "database_schema_change": False,
        "record_key": "leader.location(type=first_contact_system).id -> first_contacts.contacts.<id>",
        "counterpart_identity": "contact.country resolved through retained country record and cross-checked with saved_event_target name=contact_country when present",
        "completion_rule": "Publish only when first_contact_completed<country_id> first appears across the assignment-end interval, unless a direct exact completion field is decoded.",
        "response_choice_rule": "Diagnostic-only until a direct retained response selection field is proven.",
        "journal_section": "First Contact",
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.50 structured First Contact decoder migration started.",
        "No archived Stellaris saves, campaign identity, SQLite rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.50 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.50 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        ast.parse((ROOT / "historian/domains/politics/first_contact_history.py").read_text(encoding="utf-8"), filename="first_contact_history.py")
        ast.parse((ROOT / "historian/domains/politics/first_contact_journal.py").read_text(encoding="utf-8"), filename="first_contact_journal.py")
        patch_version(log)
        patch_app(log)
        patch_journal(log)
        patch_readme(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.50 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.50 migration failed.")
        print("Original source backups are retained under backups\\v0.0.50 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("Stellaris Historian v0.0.50 structured First Contact decoder migration completed.\n", encoding="utf-8")

    log.extend([
        "Structured First Contact decoder installed.",
        "Historical Journal First Contact section installed.",
        "Review/Construct refresh now uses seven outputs with First Contact history generated before the journal.",
        "Existing parsed cache component versions remain unchanged.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.50 structured First Contact decoder migration complete.")
    print("First_Contact_History_Debug.txt and First_Contact_History.json are now generated.")
    print("Historical_Journal.html can now publish evidence-backed First Contact events.")
    print("Review/Construct now refresh 7 outputs, with structured First Contact history first.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
