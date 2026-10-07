from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import py_compile
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_48_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.48.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.48"
PAYLOAD_ROOT = ROOT / "payload"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian/localisation.py",
    "historian/domains/people/event_probe.py",
    "historian/domains/politics/history.py",
    "historian/domains/politics/journal.py",
    "historian/domains/politics/probe.py",
    "historian_manifest.json",
    "docs/CHANGELOG.md",
    "README_v0.0.48.md",
    "docs/MIGRATION_v0.0.48.md",
    "payload/historian/domains/politics/history.py",
    "payload/historian/domains/politics/journal.py",
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
    log.append(f"Backed up {relative} -> backups/v0.0.48/{relative}")


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
        raise RuntimeError(f"Could not locate v0.0.47.1 anchor for {label}.")
    log.append(f"Installed: {label}")
    return text.replace(old, new, 1)


def replace_between(
    text: str,
    start: str,
    end: str,
    replacement: str,
    label: str,
    log: list[str],
) -> str:
    start_index = text.find(start)
    if start_index < 0:
        if replacement in text:
            log.append(f"Already installed: {label}")
            return text
        raise RuntimeError(f"Could not locate start anchor for {label}.")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"Could not locate end anchor for {label}.")
    log.append(f"Installed: {label}")
    return text[:start_index] + replacement + text[end_index:]


def install_payload(relative: str, log: list[str]) -> None:
    source = PAYLOAD_ROOT / relative
    destination = ROOT / relative
    if not source.is_file():
        raise RuntimeError(f"Missing v0.0.48 payload file: payload/{relative}")
    backup(destination, log)
    shutil.copy2(source, destination)
    log.append(f"Installed payload: {relative}")


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    if '__version__ = "0.0.48"' in original:
        return
    if '__version__ = "0.0.47.1"' not in original:
        raise RuntimeError("v0.0.48 requires Stellaris Historian v0.0.47.1.")
    updated = original.replace('__version__ = "0.0.47.1"', '__version__ = "0.0.48"', 1)
    write_if_changed(path, original, updated, log)


def patch_localisation(log: list[str]) -> None:
    path = ROOT / "historian" / "localisation.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    anchor = '''def _significant_origin_tokens(\n    origin_key: str,\n) -> list[str]:\n'''
    helper = '''def resolve_localisation_key(\n    source_save: Path,\n    key: str | None,\n) -> str | None:\n    """Resolve one Stellaris/mod localisation key to cleaned display text.\n\n    This lightweight public helper reuses Historian's existing localisation\n    index and cache.  It is intentionally conservative: unresolved keys return\n    ``None`` so callers can apply their own readable fallback.\n    """\n    if not key:\n        return None\n\n    try:\n        index = _load_index_data(source_save)\n        raw = index.values.get(str(key))\n        if not raw:\n            return None\n        cleaned = _clean_markup(\n            _resolve_references(raw, index.values)\n        )\n        return cleaned or None\n    except Exception:\n        return None\n\n\n'''
    updated = replace_once(updated, anchor, helper + anchor, "generic localisation-key resolver", log)
    write_if_changed(path, original, updated, log)


def patch_event_probe(log: list[str]) -> None:
    path = ROOT / "historian" / "domains" / "people" / "event_probe.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    old = '''            _combat_snapshot,\n            _technology_snapshot,\n            _cache_status,\n        ) = load_or_parse_snapshot(\n'''
    new = '''            _combat_snapshot,\n            _technology_snapshot,\n            _politics_snapshot,\n            _cache_status,\n        ) = load_or_parse_snapshot(\n'''
    updated = replace_once(updated, old, new, "Event/Character probe v0.0.47 cache tuple compatibility", log)
    write_if_changed(path, original, updated, log)


def patch_politics_probe(log: list[str]) -> None:
    path = ROOT / "historian" / "domains" / "politics" / "probe.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        "from typing import Iterable\n",
        "from typing import Callable, Iterable\n",
        "Politics probe progress callback import",
        log,
    )
    updated = replace_once(
        updated,
        '''def write_politics_diplomacy_probe(db: Database, campaign_id: int) -> Path:\n''',
        '''def write_politics_diplomacy_probe(\n    db: Database,\n    campaign_id: int,\n    progress: Callable[[int, int, dict], None] | None = None,\n) -> Path:\n''',
        "Politics probe progress callback argument",
        log,
    )
    updated = replace_once(
        updated,
        '''    for snapshot in selected:\n        try:\n''',
        '''    selected_total = len(selected)\n    for selected_index, snapshot in enumerate(selected, start=1):\n        if progress is not None:\n            progress(selected_index, selected_total, snapshot)\n        try:\n''',
        "Politics probe per-sample progress callback",
        log,
    )
    write_if_changed(path, original, updated, log)


def patch_history_processor(log: list[str]) -> None:
    path = ROOT / "historian" / "history_processor.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    bad = 'f"diagnostics\\{politics_live_debug.name}"'
    good = 'f"diagnostics\\\\{politics_live_debug.name}"'
    if bad in updated:
        updated = updated.replace(bad, good, 1)
        log.append("Installed: Politics diagnostic path escape fix")
    elif good in updated:
        log.append("Already installed: Politics diagnostic path escape fix")
    else:
        raise RuntimeError("Could not locate Politics live diagnostic path string.")

    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    helper_anchor = '''def safe_name(value: str, max_len: int = 60) -> str:\n'''
    helper = '''def _run_refresh_step(index: int, total: int, label: str, action):\n    started = time.perf_counter()\n    activity(f"REFRESH [{index:02d}/{total:02d}] {label}...")\n    try:\n        result = action()\n    except Exception as exc:\n        message = str(exc)\n        error(f"REFRESH [{index:02d}/{total:02d}] {label} FAILED - {message}")\n        return None, message\n\n    activity(\n        f"REFRESH [{index:02d}/{total:02d}] {label} complete - "\n        f"{format_duration(time.perf_counter() - started)}"\n    )\n    return result, None\n\n\ndef _origin_localisation_refresh(campaign_id: int):\n    campaign = DB.campaign(campaign_id)\n    if campaign is None:\n        raise ValueError("Campaign does not exist.")\n\n    snapshots = DB.all_snapshots(campaign_id)\n    start_snapshot = None\n    for snapshot in snapshots:\n        if snapshot["kind"] == "start":\n            start_snapshot = snapshot\n            break\n    if start_snapshot is None and snapshots:\n        start_snapshot = snapshots[0]\n    if start_snapshot is None:\n        raise ValueError("No archived snapshot is available for origin localisation.")\n\n    founding_profile = read_empire_profile(Path(start_snapshot["archive_path"]))\n    return write_origin_localisation_debug(\n        Path(campaign["source_save"]),\n        founding_profile.origin,\n        Path(campaign["archive_dir"]) / "Origin_Localisation_Debug.txt",\n    )\n\n\ndef _politics_probe_refresh(\n    campaign_id: int,\n    step_index: int,\n    total_steps: int,\n):\n    last_reported = 0\n\n    def progress(done: int, total: int, snapshot: dict) -> None:\n        nonlocal last_reported\n        if (\n            done == 1\n            or done == total\n            or done - last_reported >= 10\n        ):\n            last_reported = done\n            activity(\n                f"REFRESH [{step_index:02d}/{total_steps:02d}] "\n                "Politics_Diplomacy_Probe_Debug.txt - "\n                f"scanning {done}/{total} - {snapshot.get('game_date', 'unknown date')}"\n            )\n\n    return write_politics_diplomacy_probe(\n        DB,\n        campaign_id,\n        progress=progress,\n    )\n\n\n'''
    updated = replace_once(updated, helper_anchor, helper + helper_anchor, "refresh progress helpers", log)

    live_old = '''                if result["processed"]:\n                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")\n                    render_journal(DB, campaign_id)\n'''
    live_new = '''                if result["processed"]:\n                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")\n                    journal_started = time.perf_counter()\n                    render_journal(DB, campaign_id)\n                    activity(\n                        "LIVE HISTORY - Historical_Journal.html refresh complete - "\n                        f"{format_duration(time.perf_counter() - journal_started)}"\n                    )\n'''
    updated = replace_once(updated, live_old, live_new, "Live History journal refresh completion", log)

    review_start = '''    activity(\n        "Rendering Historical_Journal.html..."\n    )\n'''
    review_end = '''    message = (\n        f"Reviewed all {result['reviewed']} archived save(s). "\n'''
    review_replacement = '''    refresh_started = time.perf_counter()\n    refresh_total = 5\n    activity(f"REFRESH START - {refresh_total} output(s)")\n\n    journal, journal_error = _run_refresh_step(\n        1,\n        refresh_total,\n        "Historical_Journal.html",\n        lambda: render_journal(DB, ACTIVE_CAMPAIGN_ID),\n    )\n    if journal_error:\n        raise HTTPException(500, f"Historical journal refresh failed: {journal_error}")\n\n    event_probe_path, event_probe_error = _run_refresh_step(\n        2,\n        refresh_total,\n        "Event_Character_Probe_Debug.txt",\n        lambda: write_event_character_probe(DB, ACTIVE_CAMPAIGN_ID),\n    )\n\n    notification_decoder_path, notification_decoder_error = _run_refresh_step(\n        3,\n        refresh_total,\n        "Notification_Event_Decoder_Debug.txt",\n        lambda: write_notification_event_decoder(DB, ACTIVE_CAMPAIGN_ID),\n    )\n\n    politics_probe_path, politics_probe_error = _run_refresh_step(\n        4,\n        refresh_total,\n        "Politics_Diplomacy_Probe_Debug.txt",\n        lambda: _politics_probe_refresh(ACTIVE_CAMPAIGN_ID, 4, refresh_total),\n    )\n\n    diagnostic_path, diagnostic_error = _run_refresh_step(\n        5,\n        refresh_total,\n        "Origin_Localisation_Debug.txt",\n        lambda: _origin_localisation_refresh(ACTIVE_CAMPAIGN_ID),\n    )\n\n    refresh_errors = [\n        value\n        for value in (\n            event_probe_error,\n            notification_decoder_error,\n            politics_probe_error,\n            diagnostic_error,\n        )\n        if value\n    ]\n    activity(\n        f"REFRESH COMPLETE - {refresh_total - len(refresh_errors)}/{refresh_total} succeeded - "\n        f"{len(refresh_errors)} failed - "\n        f"{format_duration(time.perf_counter() - refresh_started)}"\n    )\n\n'''
    updated = replace_between(
        updated,
        review_start,
        review_end,
        review_replacement,
        "Review refresh progress pipeline",
        log,
    )

    construct_start = '''    activity(\n        "Rendering Historical_Journal.html from reconstructed history..."\n    )\n'''
    construct_end = '''    message = (\n        f"Constructed {result['constructed']} archived save(s) from scratch. "\n'''
    construct_replacement = '''    refresh_started = time.perf_counter()\n    refresh_total = 5\n    activity(f"REFRESH START - {refresh_total} output(s)")\n\n    journal, journal_error = _run_refresh_step(\n        1,\n        refresh_total,\n        "Historical_Journal.html",\n        lambda: render_journal(DB, ACTIVE_CAMPAIGN_ID),\n    )\n    if journal_error:\n        raise HTTPException(500, f"Constructed journal refresh failed: {journal_error}")\n\n    event_probe_path, event_probe_error = _run_refresh_step(\n        2,\n        refresh_total,\n        "Event_Character_Probe_Debug.txt",\n        lambda: write_event_character_probe(DB, ACTIVE_CAMPAIGN_ID),\n    )\n\n    notification_decoder_path, notification_decoder_error = _run_refresh_step(\n        3,\n        refresh_total,\n        "Notification_Event_Decoder_Debug.txt",\n        lambda: write_notification_event_decoder(DB, ACTIVE_CAMPAIGN_ID),\n    )\n\n    politics_probe_path, politics_probe_error = _run_refresh_step(\n        4,\n        refresh_total,\n        "Politics_Diplomacy_Probe_Debug.txt",\n        lambda: _politics_probe_refresh(ACTIVE_CAMPAIGN_ID, 4, refresh_total),\n    )\n\n    diagnostic_path, diagnostic_error = _run_refresh_step(\n        5,\n        refresh_total,\n        "Origin_Localisation_Debug.txt",\n        lambda: _origin_localisation_refresh(ACTIVE_CAMPAIGN_ID),\n    )\n\n    refresh_errors = [\n        value\n        for value in (\n            event_probe_error,\n            notification_decoder_error,\n            politics_probe_error,\n            diagnostic_error,\n        )\n        if value\n    ]\n    activity(\n        f"REFRESH COMPLETE - {refresh_total - len(refresh_errors)}/{refresh_total} succeeded - "\n        f"{len(refresh_errors)} failed - "\n        f"{format_duration(time.perf_counter() - refresh_started)}"\n    )\n\n'''
    updated = replace_between(
        updated,
        construct_start,
        construct_end,
        construct_replacement,
        "Construct refresh progress pipeline",
        log,
    )

    # Surface refresh warnings in API messages without changing successful core rebuild semantics.
    review_msg_anchor = '''    if diagnostic_path is not None:\n        message += (\n            " Origin_Localisation_Debug.txt was also written to the "\n            "campaign archive folder."\n        )\n    elif diagnostic_error:\n        message += (\n            f" Origin localisation diagnostic could not be written: "\n            f"{diagnostic_error}"\n        )\n\n    return {\n'''
    review_msg_new = '''    if diagnostic_path is not None:\n        message += (\n            " Origin_Localisation_Debug.txt was also written to the "\n            "campaign archive folder."\n        )\n    elif diagnostic_error:\n        message += (\n            f" Origin localisation diagnostic could not be written: "\n            f"{diagnostic_error}"\n        )\n\n    if refresh_errors:\n        message += (\n            f" {len(refresh_errors)} refresh output(s) reported errors; "\n            "see the console/log for the failed step."\n        )\n\n    return {\n'''
    updated = replace_once(updated, review_msg_anchor, review_msg_new, "Review refresh warning summary", log)

    construct_msg_anchor = '''    if diagnostic_error:\n        message += (\n            f" Origin localisation diagnostic could not be refreshed: "\n            f"{diagnostic_error}"\n        )\n\n    return {\n'''
    construct_msg_new = '''    if diagnostic_error:\n        message += (\n            f" Origin localisation diagnostic could not be refreshed: "\n            f"{diagnostic_error}"\n        )\n\n    if refresh_errors:\n        message += (\n            f" {len(refresh_errors)} refresh output(s) reported errors; "\n            "see the console/log for the failed step."\n        )\n\n    return {\n'''
    updated = replace_once(updated, construct_msg_anchor, construct_msg_new, "Construct refresh warning summary", log)

    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original.replace("## Current version\n\nv0.0.47.1", "## Current version\n\nv0.0.48", 1)
    updated = updated.replace(
        "The current codebase includes migration and historical tracking work through version 0.0.47.1.",
        "The current codebase includes migration and historical tracking work through version 0.0.48.",
        1,
    )
    if updated == original and "v0.0.48" not in original:
        log.append("README version sentence did not use the expected v0.0.47.1 wording; current-version heading may be maintained separately.")
    write_if_changed(path, original, updated, log)


def patch_manifest(log: list[str]) -> None:
    path = ROOT / "historian_manifest.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["version"] = "0.0.48"
    data["architecture"] = "modular-foundation-23-politics-publication-filter-refresh-progress"
    data["politics_diplomacy_v2"] = {
        "agenda_progress_publication": "diagnostic-only",
        "agenda_identity_changes_public": True,
        "non_diplomatic_relation_entities": "retained-but-filtered-from-public-history",
        "summary_localisation": "installed Stellaris/mod localisation with readable fallback",
    }
    data["refresh_progress"] = {
        "review_and_construct_steps": True,
        "politics_probe_inner_progress": True,
        "live_journal_completion_log": True,
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.48\n- Politics/Diplomacy publication filtering now keeps routine `council_agenda_progress` telemetry in SQL/diagnostics but removes it from public historical narrative.\n- Actual council-agenda identity transitions remain publishable and receive readable titles.\n- Raw `relations_manager` evidence is still retained, while strong pseudo-country/event-entity indicators are filtered from public diplomatic contact/state history.\n- Politics/Diplomacy journal summary values now resolve through installed Stellaris/mod localisation with a readable fallback.\n- Fixed Event_Character_Probe_Debug.txt cache tuple compatibility after the v0.0.47 Politics cache component was added.\n- Fixed the invalid Python escape warning in the incremental Politics diagnostic path.\n- Review Campaign and Construct Campaign now show numbered REFRESH progress, per-step timing, failures, and an overall refresh summary.\n- Politics_Diplomacy_Probe_Debug.txt reports inner raw-sample scan progress during Review/Construct.\n- Live History now explicitly logs Historical_Journal.html refresh completion and duration.\n- Existing archived `.sav` files are not changed or deleted.\n\n'''
    if section in original:
        updated = original
    else:
        anchor = "# Stellaris Historian Changelog\n\n" if "# Stellaris Historian Changelog\n\n" in original else "# Changelog\n\n"
        if anchor not in original:
            raise RuntimeError("Could not locate CHANGELOG heading.")
        updated = original.replace(anchor, anchor + section, 1)
    write_if_changed(path, original, updated, log)


def cleanup_existing_politics_rows(log: list[str]) -> None:
    db_path = ROOT / "data" / "historian.db"
    if not db_path.is_file():
        log.append("No historian.db present yet; skipped existing Politics/Diplomacy row cleanup.")
        return

    con = sqlite3.connect(db_path)
    try:
        table = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='politics_history_events'"
        ).fetchone()
        if table is None:
            log.append("Politics/Diplomacy table not present; skipped existing row cleanup.")
            return

        progress_cur = con.execute(
            """
            UPDATE politics_history_events
            SET visible=0,
                event_type='council_agenda_progress_changed',
                title='Council Agenda Progress Changed'
            WHERE event_type='council_agenda_state_changed'
              AND attributes_json LIKE '%\"raw_field\":\"council_agenda_progress\"%'
            """
        )

        pseudo_cur = con.execute(
            """
            UPDATE politics_history_events
            SET visible=0
            WHERE category='diplomacy'
              AND (
                    COALESCE(subject_id, 0) >= 10000000
                 OR lower(COALESCE(subject_name, '')) = 'gateway_system'
                 OR lower(COALESCE(subject_name, '')) GLOB 'country [0-9]*'
                 OR lower(COALESCE(subject_name, '')) LIKE '%incoming asteroid%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%mining drone%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%mineral extraction operation%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%cracked crystalline shard%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%space amoeba%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%spaceborne organics%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%voidwyrm%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%leviathan%'
                 OR lower(COALESCE(subject_name, '')) LIKE '%locust swarm%'
              )
            """
        )
        con.commit()
        try:
            con.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        except sqlite3.DatabaseError:
            pass
        log.append(
            "Existing Politics/Diplomacy rows cleaned: "
            f"agenda progress hidden={progress_cur.rowcount}; "
            f"pseudo/special diplomacy rows hidden={pseudo_cur.rowcount}."
        )
    finally:
        con.close()


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.48 Politics publication/refesh-progress migration started.",
        "Archived Stellaris saves are not modified or deleted by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.48 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.48 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        patch_version(log)
        install_payload("historian/domains/politics/history.py", log)
        install_payload("historian/domains/politics/journal.py", log)
        patch_localisation(log)
        patch_event_probe(log)
        patch_politics_probe(log)
        patch_history_processor(log)
        patch_app(log)
        patch_readme(log)
        patch_manifest(log)
        patch_changelog(log)
        cleanup_existing_politics_rows(log)

        for relative in (
            "app.py",
            "historian/history_processor.py",
            "historian/localisation.py",
            "historian/domains/people/event_probe.py",
            "historian/domains/politics/history.py",
            "historian/domains/politics/journal.py",
            "historian/domains/politics/probe.py",
        ):
            py_compile.compile(str(ROOT / relative), doraise=True)

    except (py_compile.PyCompileError, RuntimeError, OSError, json.JSONDecodeError, sqlite3.DatabaseError) as exc:
        log.append(f"ABORTED: v0.0.48 migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.48 validation failed.")
        print("Original source backups are retained under backups\\v0.0.48 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.48 Politics publication/refesh-progress migration completed.\n",
        encoding="utf-8",
    )
    log.append("Migration completed successfully.")
    write_log(log)

    print("v0.0.48 Politics/Diplomacy publication filtering and refresh progress migration complete.")
    print("Agenda progress remains diagnostic-only; meaningful agenda/tradition/diplomacy events remain publishable.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
