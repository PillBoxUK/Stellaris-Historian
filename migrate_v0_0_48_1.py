from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_48_1_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.48.1.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.48.1"
V48_BACKUP_APP = ROOT / "backups" / "v0.0.48" / "app.py"


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
    log.append(f"Backed up {relative} -> backups/v0.0.48.1/{relative}")


def replace_once(text: str, old: str, new: str, label: str, log: list[str]) -> str:
    if new in text:
        log.append(f"Already installed: {label}")
        return text
    if old not in text:
        raise RuntimeError(f"Could not locate anchor for {label}.")
    log.append(f"Installed: {label}")
    return text.replace(old, new, 1)


def replace_within_route(
    text: str,
    route_start: str,
    next_route: str,
    old_start: str,
    old_end: str,
    replacement: str,
    label: str,
    log: list[str],
) -> str:
    start = text.find(route_start)
    if start < 0:
        raise RuntimeError(f"Could not locate route start for {label}.")
    end = text.find(next_route, start + len(route_start))
    if end < 0:
        raise RuntimeError(f"Could not locate next route for {label}.")
    route = text[start:end]
    a = route.find(old_start)
    b = route.find(old_end, a + len(old_start)) if a >= 0 else -1
    if a < 0 or b < 0:
        raise RuntimeError(f"Could not locate route-local refresh anchors for {label}.")
    route = route[:a] + replacement + route[b:]
    log.append(f"Installed: {label}")
    return text[:start] + route + text[end:]


def rebuild_app(log: list[str]) -> None:
    app_path = ROOT / "app.py"
    if not app_path.is_file():
        raise RuntimeError("app.py is missing.")
    if not V48_BACKUP_APP.is_file():
        raise RuntimeError(
            "The v0.0.48 pre-migration app.py backup is missing. "
            "Expected backups\\v0.0.48\\app.py; refusing to guess at route reconstruction."
        )

    pristine = V48_BACKUP_APP.read_text(encoding="utf-8")

    if '@app.post("/api/live-history")' not in pristine:
        raise RuntimeError("v0.0.48 backup app.py does not contain the expected Live History route.")
    if '@app.post("/api/review-campaign")' not in pristine:
        raise RuntimeError("v0.0.48 backup app.py does not contain the expected Review Campaign route.")

    updated = pristine

    helper_anchor = '''def safe_name(value: str, max_len: int = 60) -> str:\n'''
    helper = '''def _run_refresh_step(index: int, total: int, label: str, action):
    started = time.perf_counter()
    activity(f"REFRESH [{index:02d}/{total:02d}] {label}...")
    try:
        result = action()
    except Exception as exc:
        message = str(exc)
        error(f"REFRESH [{index:02d}/{total:02d}] {label} FAILED - {message}")
        return None, message

    activity(
        f"REFRESH [{index:02d}/{total:02d}] {label} complete - "
        f"{format_duration(time.perf_counter() - started)}"
    )
    return result, None


def _origin_localisation_refresh(campaign_id: int):
    campaign = DB.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    snapshots = DB.all_snapshots(campaign_id)
    start_snapshot = None
    for snapshot in snapshots:
        if snapshot["kind"] == "start":
            start_snapshot = snapshot
            break
    if start_snapshot is None and snapshots:
        start_snapshot = snapshots[0]
    if start_snapshot is None:
        raise ValueError("No archived snapshot is available for origin localisation.")

    founding_profile = read_empire_profile(Path(start_snapshot["archive_path"]))
    return write_origin_localisation_debug(
        Path(campaign["source_save"]),
        founding_profile.origin,
        Path(campaign["archive_dir"]) / "Origin_Localisation_Debug.txt",
    )


def _politics_probe_refresh(
    campaign_id: int,
    step_index: int,
    total_steps: int,
):
    last_reported = 0

    def progress(done: int, total: int, snapshot: dict) -> None:
        nonlocal last_reported
        if done == 1 or done == total or done - last_reported >= 10:
            last_reported = done
            activity(
                f"REFRESH [{step_index:02d}/{total_steps:02d}] "
                "Politics_Diplomacy_Probe_Debug.txt - "
                f"scanning {done}/{total} - {snapshot.get('game_date', 'unknown date')}"
            )

    return write_politics_diplomacy_probe(
        DB,
        campaign_id,
        progress=progress,
    )


'''
    updated = replace_once(updated, helper_anchor, helper + helper_anchor, "refresh progress helpers", log)

    live_old = '''                if result["processed"]:
                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")
                    render_journal(DB, campaign_id)
'''
    live_new = '''                if result["processed"]:
                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")
                    journal_started = time.perf_counter()
                    render_journal(DB, campaign_id)
                    activity(
                        "LIVE HISTORY - Historical_Journal.html refresh complete - "
                        f"{format_duration(time.perf_counter() - journal_started)}"
                    )
'''
    updated = replace_once(updated, live_old, live_new, "Live History journal refresh completion", log)

    review_old_start = '''    activity(
        "Rendering Historical_Journal.html..."
    )
'''
    review_old_end = '''    message = (
        f"Reviewed all {result['reviewed']} archived save(s). "
'''
    review_replacement = '''    refresh_started = time.perf_counter()
    refresh_total = 5
    activity(f"REFRESH START - {refresh_total} output(s)")

    journal, journal_error = _run_refresh_step(
        1,
        refresh_total,
        "Historical_Journal.html",
        lambda: render_journal(DB, ACTIVE_CAMPAIGN_ID),
    )
    if journal_error:
        raise HTTPException(500, f"Historical journal refresh failed: {journal_error}")

    event_probe_path, event_probe_error = _run_refresh_step(
        2,
        refresh_total,
        "Event_Character_Probe_Debug.txt",
        lambda: write_event_character_probe(DB, ACTIVE_CAMPAIGN_ID),
    )

    notification_decoder_path, notification_decoder_error = _run_refresh_step(
        3,
        refresh_total,
        "Notification_Event_Decoder_Debug.txt",
        lambda: write_notification_event_decoder(DB, ACTIVE_CAMPAIGN_ID),
    )

    politics_probe_path, politics_probe_error = _run_refresh_step(
        4,
        refresh_total,
        "Politics_Diplomacy_Probe_Debug.txt",
        lambda: _politics_probe_refresh(ACTIVE_CAMPAIGN_ID, 4, refresh_total),
    )

    diagnostic_path, diagnostic_error = _run_refresh_step(
        5,
        refresh_total,
        "Origin_Localisation_Debug.txt",
        lambda: _origin_localisation_refresh(ACTIVE_CAMPAIGN_ID),
    )

    refresh_errors = [
        value
        for value in (
            event_probe_error,
            notification_decoder_error,
            politics_probe_error,
            diagnostic_error,
        )
        if value
    ]
    activity(
        f"REFRESH COMPLETE - {refresh_total - len(refresh_errors)}/{refresh_total} succeeded - "
        f"{len(refresh_errors)} failed - "
        f"{format_duration(time.perf_counter() - refresh_started)}"
    )

'''
    updated = replace_within_route(
        updated,
        '@app.post("/api/review-campaign")',
        '@app.post("/api/construct-campaign")',
        review_old_start,
        review_old_end,
        review_replacement,
        "Review refresh progress pipeline (route-scoped)",
        log,
    )

    construct_old_start = '''    activity(
        "Rendering Historical_Journal.html from reconstructed history..."
    )
'''
    construct_old_end = '''    message = (
        f"Constructed {result['constructed']} archived save(s) from scratch. "
'''
    construct_replacement = '''    refresh_started = time.perf_counter()
    refresh_total = 5
    activity(f"REFRESH START - {refresh_total} output(s)")

    journal, journal_error = _run_refresh_step(
        1,
        refresh_total,
        "Historical_Journal.html",
        lambda: render_journal(DB, ACTIVE_CAMPAIGN_ID),
    )
    if journal_error:
        raise HTTPException(500, f"Constructed journal refresh failed: {journal_error}")

    event_probe_path, event_probe_error = _run_refresh_step(
        2,
        refresh_total,
        "Event_Character_Probe_Debug.txt",
        lambda: write_event_character_probe(DB, ACTIVE_CAMPAIGN_ID),
    )

    notification_decoder_path, notification_decoder_error = _run_refresh_step(
        3,
        refresh_total,
        "Notification_Event_Decoder_Debug.txt",
        lambda: write_notification_event_decoder(DB, ACTIVE_CAMPAIGN_ID),
    )

    politics_probe_path, politics_probe_error = _run_refresh_step(
        4,
        refresh_total,
        "Politics_Diplomacy_Probe_Debug.txt",
        lambda: _politics_probe_refresh(ACTIVE_CAMPAIGN_ID, 4, refresh_total),
    )

    diagnostic_path, diagnostic_error = _run_refresh_step(
        5,
        refresh_total,
        "Origin_Localisation_Debug.txt",
        lambda: _origin_localisation_refresh(ACTIVE_CAMPAIGN_ID),
    )

    refresh_errors = [
        value
        for value in (
            event_probe_error,
            notification_decoder_error,
            politics_probe_error,
            diagnostic_error,
        )
        if value
    ]
    activity(
        f"REFRESH COMPLETE - {refresh_total - len(refresh_errors)}/{refresh_total} succeeded - "
        f"{len(refresh_errors)} failed - "
        f"{format_duration(time.perf_counter() - refresh_started)}"
    )

'''
    updated = replace_within_route(
        updated,
        '@app.post("/api/construct-campaign")',
        '@app.get("/journal")',
        construct_old_start,
        construct_old_end,
        construct_replacement,
        "Construct refresh progress pipeline (route-scoped)",
        log,
    )

    review_warn_old = '''    elif diagnostic_error:
        message += (
            f" Origin localisation diagnostic could not be written: "
            f"{diagnostic_error}"
        )

    return {
'''
    review_warn_new = '''    elif diagnostic_error:
        message += (
            f" Origin localisation diagnostic could not be written: "
            f"{diagnostic_error}"
        )

    if refresh_errors:
        message += (
            f" {len(refresh_errors)} refresh output(s) reported errors; "
            "see the console/log for the failed step."
        )

    return {
'''
    updated = replace_once(updated, review_warn_old, review_warn_new, "Review refresh warning summary", log)

    construct_warn_old = '''    if diagnostic_error:
        message += (
            f" Origin localisation diagnostic could not be refreshed: "
            f"{diagnostic_error}"
        )

    return {
'''
    construct_warn_new = '''    if diagnostic_error:
        message += (
            f" Origin localisation diagnostic could not be refreshed: "
            f"{diagnostic_error}"
        )

    if refresh_errors:
        message += (
            f" {len(refresh_errors)} refresh output(s) reported errors; "
            "see the console/log for the failed step."
        )

    return {
'''
    updated = replace_once(updated, construct_warn_old, construct_warn_new, "Construct refresh warning summary", log)

    for route in (
        '@app.post("/api/update-history")',
        '@app.post("/api/live-history")',
        '@app.post("/api/review-campaign")',
        '@app.post("/api/construct-campaign")',
    ):
        if updated.count(route) != 1:
            raise RuntimeError(f"Route validation failed for {route}: expected exactly one occurrence.")

    backup(app_path, log)
    app_path.write_text(updated, encoding="utf-8", newline="\n")
    log.append("Rebuilt app.py from v0.0.47.1 backup and reapplied v0.0.48 app changes safely.")


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    if '__version__ = "0.0.48.1"' in original:
        return
    if '__version__ = "0.0.48"' not in original:
        raise RuntimeError("v0.0.48.1 requires Stellaris Historian v0.0.48.")
    backup(path, log)
    path.write_text(original.replace('__version__ = "0.0.48"', '__version__ = "0.0.48.1"', 1), encoding="utf-8", newline="\n")
    log.append("Updated historian/__init__.py to v0.0.48.1.")


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    if not path.is_file():
        return
    original = path.read_text(encoding="utf-8")
    updated = original.replace("## Current version\n\nv0.0.48", "## Current version\n\nv0.0.48.1", 1)
    updated = updated.replace(
        "The current codebase includes migration and historical tracking work through version 0.0.48.",
        "The current codebase includes migration and historical tracking work through version 0.0.48.1.",
        1,
    )
    if updated != original:
        backup(path, log)
        path.write_text(updated, encoding="utf-8", newline="\n")
        log.append("Updated README.md version to v0.0.48.1.")


def patch_manifest(log: list[str]) -> None:
    path = ROOT / "historian_manifest.json"
    if not path.is_file():
        return
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["version"] = "0.0.48.1"
    data["architecture"] = "modular-foundation-24-live-history-route-hotfix"
    data["live_history_route_hotfix"] = {
        "restored_routes": ["/api/update-history", "/api/live-history", "/api/review-campaign"],
        "cause": "v0.0.48 refresh migration matched the Update History journal anchor instead of Review Campaign",
        "database_changes": False,
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    backup(path, log)
    path.write_text(updated, encoding="utf-8", newline="\n")
    log.append("Updated historian_manifest.json for v0.0.48.1.")


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    if not path.is_file():
        return
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.48.1
- Hotfix: restores the `/api/live-history` endpoint accidentally removed by the v0.0.48 refresh-progress migration.
- Restores the complete Update History and Review Campaign route block from the automatic v0.0.47.1 backup, then reapplies the intended v0.0.48 refresh changes with route-scoped anchors.
- Keeps v0.0.48 Politics/Diplomacy filtering, refresh progress, localisation and diagnostic fixes intact.
- No SQLite schema/data migration and no archived `.sav` changes.

'''
    if section not in original:
        anchor = "# Stellaris Historian Changelog\n\n" if "# Stellaris Historian Changelog\n\n" in original else "# Changelog\n\n"
        if anchor in original:
            updated = original.replace(anchor, anchor + section, 1)
            backup(path, log)
            path.write_text(updated, encoding="utf-8", newline="\n")
            log.append("Added v0.0.48.1 changelog entry.")


def restore_hotfix_backups(log: list[str]) -> None:
    if not BACKUP_ROOT.exists():
        return
    for source in sorted(BACKUP_ROOT.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(BACKUP_ROOT)
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        log.append(f"Rollback restored: {relative}")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.48.1 Live History route hotfix started.",
        "No SQLite campaign data or archived Stellaris saves are modified by this hotfix.",
    ]

    try:
        rebuild_app(log)
        patch_version(log)
        patch_readme(log)
        patch_manifest(log)
        patch_changelog(log)

        py_compile.compile(str(ROOT / "app.py"), doraise=True)
        py_compile.compile(str(ROOT / "historian" / "__init__.py"), doraise=True)

        app_text = (ROOT / "app.py").read_text(encoding="utf-8")
        for route in (
            '@app.post("/api/update-history")',
            '@app.post("/api/live-history")',
            '@app.post("/api/review-campaign")',
            '@app.post("/api/construct-campaign")',
        ):
            if app_text.count(route) != 1:
                raise RuntimeError(f"Post-write route validation failed: {route}")

    except Exception as exc:
        log.append(f"ABORTED: {exc}")
        try:
            restore_hotfix_backups(log)
        except Exception as rollback_exc:
            log.append(f"ROLLBACK WARNING: {rollback_exc}")
        write_log(log)
        print("ERROR: v0.0.48.1 Live History route hotfix failed.")
        print("No campaign database/save data was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.48.1 Live History route hotfix completed.\n",
        encoding="utf-8",
    )
    log.append("Hotfix completed successfully.")
    write_log(log)

    print("v0.0.48.1 Live History route hotfix complete.")
    print("Restored /api/live-history and repaired the Update History / Review Campaign route block.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
