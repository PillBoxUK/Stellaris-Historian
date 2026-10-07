from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import hashlib
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from historian import __version__
from historian.config import load_config
from historian.console import activity, error, format_duration, info, warning
from historian.db import Database
from historian.history_processor import construct_campaign, process_unprocessed, review_campaign
from historian.journal import journal_path, render_journal
from historian.scribes import render_scribes_journal, render_scribes_pdf
from historian.timeline import render_timeline
from historian.localisation import write_origin_localisation_debug
from historian.save_reader import read_campaign_summary, read_empire_profile, valid_stellaris_save
from historian.watcher import CampaignWatcher
from historian.domains.people.event_probe import write_event_character_probe
from historian.domains.people.notification_decoder import write_notification_event_decoder
from historian.domains.politics.probe import write_politics_diplomacy_probe


APP_VERSION = __version__
BASE = Path(__file__).resolve().parent
CONFIG = load_config(BASE)

DATA_DIR = BASE / "data"
ARCHIVE_ROOT = DATA_DIR / "campaigns"

DB = Database(DATA_DIR / "historian.db")

WATCHER = CampaignWatcher(
    DB,
    archive_root=ARCHIVE_ROOT,
    poll_seconds=CONFIG.poll_seconds,
    stable_seconds=CONFIG.stable_seconds,
)

ACTIVE_CAMPAIGN_ID: int | None = None
server: uvicorn.Server | None = None
LIVE_HISTORY_ENABLED = False
LIVE_HISTORY_BUSY = False
LIVE_HISTORY_STATUS = "OFF"
LIVE_HISTORY_STOP = threading.Event()
LIVE_HISTORY_THREAD: threading.Thread | None = None


def _refresh_event_character_probe(campaign_id: int):
    try:
        activity("Refreshing Event_Character_Probe_Debug.txt...")
        path = write_event_character_probe(DB, campaign_id)
        activity(
            "Event / character deep probe updated - "
            f"{path.name}"
        )
        return path, None
    except Exception as exc:
        message = str(exc)
        error(f"EVENT / CHARACTER PROBE - {message}")
        return None, message



def _refresh_notification_event_decoder(campaign_id: int):
    try:
        activity("Refreshing Notification_Event_Decoder_Debug.txt...")
        path = write_notification_event_decoder(DB, campaign_id)
        activity(
            "Notification / event object decoder updated - "
            f"{path.name}"
        )
        return path, None
    except Exception as exc:
        message = str(exc)
        error(f"NOTIFICATION / EVENT DECODER - {message}")
        return None, message


def _refresh_politics_diplomacy_probe(campaign_id: int):
    try:
        activity("Refreshing Politics_Diplomacy_Probe_Debug.txt...")
        path = write_politics_diplomacy_probe(DB, campaign_id)
        activity(
            "Politics / diplomacy deep probe updated - "
            f"{path.name}"
        )
        return path, None
    except Exception as exc:
        message = str(exc)
        error(f"POLITICS / DIPLOMACY PROBE - {message}")
        return None, message


def _live_history_loop() -> None:
    global LIVE_HISTORY_ENABLED, LIVE_HISTORY_BUSY, LIVE_HISTORY_STATUS

    while not LIVE_HISTORY_STOP.is_set():
        campaign_id = ACTIVE_CAMPAIGN_ID

        if not LIVE_HISTORY_ENABLED or campaign_id is None:
            LIVE_HISTORY_STOP.wait(1.0)
            continue

        try:
            waiting = DB.unprocessed_count(campaign_id)
            if waiting <= 0:
                LIVE_HISTORY_STATUS = "ON - waiting for the next archived save"
                LIVE_HISTORY_STOP.wait(1.0)
                continue

            LIVE_HISTORY_BUSY = True
            LIVE_HISTORY_STATUS = f"ON - processing {waiting} archived save(s)"
            activity(f"LIVE HISTORY - {waiting} archived save(s) waiting")
            try:
                result = process_unprocessed(DB, campaign_id)

                if result["processed"]:
                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")
                    journal_started = time.perf_counter()
                    render_journal(DB, campaign_id)
                    activity(
                        "LIVE HISTORY - Historical_Journal.html refresh complete - "
                        f"{format_duration(time.perf_counter() - journal_started)}"
                    )

                if result["errors"]:
                    LIVE_HISTORY_ENABLED = False
                    LIVE_HISTORY_STATUS = (
                        "OFF - processing error: " + result["errors"][0]
                    )
                    error("LIVE HISTORY STOPPED - " + result["errors"][0])
                else:
                    LIVE_HISTORY_STATUS = (
                        "ON - waiting for the next archived save"
                        if LIVE_HISTORY_ENABLED
                        else "OFF"
                    )
            finally:
                LIVE_HISTORY_BUSY = False

        except Exception as exc:
            LIVE_HISTORY_ENABLED = False
            LIVE_HISTORY_BUSY = False
            LIVE_HISTORY_STATUS = f"OFF - processing error: {exc}"
            error(f"LIVE HISTORY - {exc}")

        LIVE_HISTORY_STOP.wait(1.0)


def _start_live_history_worker() -> None:
    global LIVE_HISTORY_THREAD
    if LIVE_HISTORY_THREAD and LIVE_HISTORY_THREAD.is_alive():
        return
    LIVE_HISTORY_STOP.clear()
    LIVE_HISTORY_THREAD = threading.Thread(
        target=_live_history_loop,
        name="stellaris-historian-live-history",
        daemon=True,
    )
    LIVE_HISTORY_THREAD.start()
    info("Live History worker started (OFF by default).")


def _stop_live_history_worker() -> None:
    LIVE_HISTORY_STOP.set()
    if LIVE_HISTORY_THREAD and LIVE_HISTORY_THREAD.is_alive():
        LIVE_HISTORY_THREAD.join(timeout=5)
    info("Live History worker stopped.")


def _run_refresh_step(index: int, total: int, label: str, action):
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


def safe_name(value: str, max_len: int = 60) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip().strip(".")
    return (value or "campaign")[:max_len]


def source_key(path: Path) -> str:
    relative = path.parent.resolve().relative_to(CONFIG.save_root.resolve())
    return str(relative).replace("\\", "/").lower()


def archive_dir_for(summary, key: str) -> Path:
    short_hash = hashlib.sha1(
        key.encode("utf-8", errors="replace")
    ).hexdigest()[:8]

    folder = (
        f"{safe_name(summary.empire_name)}__"
        f"{safe_name(summary.folder_name)}__"
        f"{short_hash}"
    )

    return ARCHIVE_ROOT / folder


def get_or_create_campaign(save_path: Path):
    key = source_key(save_path)
    existing = DB.get_campaign_by_source(key)
    summary = read_campaign_summary(save_path)

    if existing is not None:
        DB.update_campaign(
            int(existing["id"]),
            empire_name=summary.empire_name,
            game_version=summary.version,
            game_date=summary.game_date,
        )

        return DB.campaign(int(existing["id"]))

    campaign_id = DB.create_campaign(
        source_key=key,
        source_folder=str(save_path.parent),
        source_save=str(save_path),
        empire_name=summary.empire_name,
        game_version=summary.version,
        archive_dir=str(archive_dir_for(summary, key)),
        game_date=summary.game_date,
    )

    return DB.campaign(campaign_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    info(
        f"Stellaris Historian v{APP_VERSION} is ready."
    )

    WATCHER.start()
    _start_live_history_worker()

    try:
        yield
    finally:
        _stop_live_history_worker()
        WATCHER.stop()

        info(
            "Historian shutdown complete."
        )


app = FastAPI(
    title="Stellaris Historian",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=BASE / "static"),
    name="static",
)


def recent_campaigns(limit: int) -> list[dict]:
    if not CONFIG.save_root.exists():
        return []

    candidates: list[tuple[float, Path]] = []

    for path in CONFIG.save_root.rglob("ironman.sav"):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue

    candidates.sort(key=lambda item: item[0], reverse=True)

    results: list[dict] = []

    for _, path in candidates:
        if len(results) >= limit:
            break

        if not valid_stellaris_save(path):
            continue

        try:
            summary = read_campaign_summary(path)
        except Exception:
            continue

        results.append(
            {
                "save_path": summary.save_path,
                "folder_name": summary.folder_name,
                "empire_name": summary.empire_name,
                "game_date": summary.game_date,
                "version": summary.version,
                "modified": summary.modified,
            }
        )

    return results


@app.get("/")
def splash():
    return FileResponse(
        BASE / "static" / "splash.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/campaign")
def campaign_page():
    if ACTIVE_CAMPAIGN_ID is None:
        return FileResponse(
            BASE / "static" / "splash.html",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    return FileResponse(
        BASE / "static" / "campaign.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/api/recent-campaigns")
def api_recent_campaigns(limit: int = Query(default=5)):
    if limit not in {5, 10, 20, 25}:
        raise HTTPException(
            400,
            "Campaign limit must be 5, 10, 20 or 25.",
        )

    return {
        "version": APP_VERSION,
        "save_root": str(CONFIG.save_root),
        "limit": limit,
        "campaigns": recent_campaigns(limit),
    }


@app.post("/api/start-campaign")
async def api_start_campaign(request: Request):
    global ACTIVE_CAMPAIGN_ID, LIVE_HISTORY_ENABLED, LIVE_HISTORY_STATUS

    if LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Live History is finishing an automatic update. Wait for it to finish before selecting another campaign.",
        )

    payload = await request.json()
    raw_path = payload.get("save_path")

    if not raw_path:
        raise HTTPException(400, "No campaign was selected.")

    selected = Path(raw_path).resolve()

    try:
        selected.relative_to(CONFIG.save_root.resolve())
    except ValueError as exc:
        raise HTTPException(
            400,
            "Selected campaign is outside the configured Stellaris save folder.",
        ) from exc

    if selected.name.lower() != "ironman.sav" or not selected.is_file():
        raise HTTPException(
            400,
            "Selected ironman.sav no longer exists.",
        )

    if not valid_stellaris_save(selected):
        raise HTTPException(
            400,
            "Selected file is not a valid Stellaris save.",
        )

    campaign = get_or_create_campaign(selected)
    ACTIVE_CAMPAIGN_ID = int(campaign["id"])
    LIVE_HISTORY_ENABLED = False
    LIVE_HISTORY_STATUS = "OFF"

    WATCHER.select_campaign(
        selected,
        ACTIVE_CAMPAIGN_ID,
    )

    return {
        "ok": True,
        "campaign_id": ACTIVE_CAMPAIGN_ID,
        "redirect": "/campaign",
    }


@app.get("/api/active-campaign")
def api_active_campaign():
    if ACTIVE_CAMPAIGN_ID is None:
        return {
            "version": APP_VERSION,
            "campaign": None,
            "monitoring": False,
            "live_history_enabled": False,
            "live_history_busy": False,
            "live_history_status": "OFF",
        }

    campaign = DB.campaign(ACTIVE_CAMPAIGN_ID)

    if campaign is None:
        return {
            "version": APP_VERSION,
            "campaign": None,
            "monitoring": False,
            "live_history_enabled": False,
            "live_history_busy": False,
            "live_history_status": "OFF",
        }

    snapshots = [
        dict(row)
        for row in DB.latest_snapshots(
            ACTIVE_CAMPAIGN_ID,
            limit=10,
        )
    ]

    current_journal = journal_path(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    return {
        "version": APP_VERSION,
        "campaign": dict(campaign),
        "monitoring": True,
        "watcher_status": WATCHER.status,
        "live_history_enabled": LIVE_HISTORY_ENABLED,
        "live_history_busy": LIVE_HISTORY_BUSY,
        "live_history_status": LIVE_HISTORY_STATUS,
        "archive_count": DB.snapshot_count(ACTIVE_CAMPAIGN_ID),
        "unprocessed_count": DB.unprocessed_count(ACTIVE_CAMPAIGN_ID),
        "processed_count": DB.processed_count(ACTIVE_CAMPAIGN_ID),
        "journal_exists": current_journal.exists(),
        "journal_url": "/journal",
        "snapshots": snapshots,
    }


@app.post("/api/update-history")
def api_update_history():
    if LIVE_HISTORY_ENABLED or LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Live History is ON or finishing an automatic update. Wait for it to become fully OFF before running Update History manually.",
        )

    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(
            400,
            "No campaign is active.",
        )

    result = process_unprocessed(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    activity(
        "Rendering Historical_Journal.html..."
    )

    journal_started = time.perf_counter()

    journal = render_journal(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    activity(
        f"Journal updated - {format_duration(time.perf_counter() - journal_started)}"
    )

    errors = result["errors"]
    politics_warnings = result.get("politics_warnings", [])
    recovered = int(result.get("recovered", 0) or 0)

    if errors:
        message = (
            f"Processed {result['processed']} save(s). "
            f"{len(errors)} save(s) could not be processed. "
            f"{result['remaining']} remain unprocessed."
        )
    else:
        message = (
            f"Processed {result['processed']} new save(s). "
            f"{recovered} already-written save(s) were recovered from SQL. "
            f"Historical_Journal.html updated successfully. "
            f"{result['remaining']} save(s) remain unprocessed."
        )
        if politics_warnings:
            message += (
                f" Politics/Diplomacy produced {len(politics_warnings)} warning(s); "
                "core history progress was still saved and will not be replayed."
            )

    return {
        "ok": len(errors) == 0,
        "processed": result["processed"],
        "remaining": result["remaining"],
        "errors": errors,
        "politics_warnings": politics_warnings,
        "recovered": recovered,
        "journal_path": str(journal),
        "journal_url": "/journal",
        "message": message,
    }


@app.post("/api/live-history")
async def api_live_history(request: Request):
    global LIVE_HISTORY_ENABLED, LIVE_HISTORY_STATUS

    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(400, "No campaign is active.")

    payload = await request.json()
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(400, "enabled must be true or false.")

    LIVE_HISTORY_ENABLED = enabled
    LIVE_HISTORY_STATUS = (
        "ON - checking archived saves"
        if enabled
        else (
            "OFF requested - finishing current history update"
            if LIVE_HISTORY_BUSY
            else "OFF"
        )
    )

    activity(f"LIVE HISTORY {'ON' if enabled else 'OFF'}")

    return {
        "ok": True,
        "enabled": LIVE_HISTORY_ENABLED,
        "busy": LIVE_HISTORY_BUSY,
        "status": LIVE_HISTORY_STATUS,
    }


@app.post("/api/review-campaign")
def api_review_campaign():
    if LIVE_HISTORY_ENABLED or LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Wait for Live History to be fully OFF before running Review Campaign.",
        )

    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(
            400,
            "No campaign is active.",
        )

    waiting = DB.unprocessed_count(
        ACTIVE_CAMPAIGN_ID
    )

    if waiting > 0:
        raise HTTPException(
            409,
            (
                "Review Campaign is unavailable while archived saves are waiting "
                f"for history. Run Update History first ({waiting} waiting)."
            ),
        )

    result = review_campaign(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    if result["errors"]:
        return {
            "ok": False,
            "reviewed": result["reviewed"],
            "total": result["total"],
            "errors": result["errors"],
            "message": (
                f"Review stopped. {result['reviewed']} of "
                f"{result['total']} archived save(s) were readable, but "
                f"{len(result['errors'])} error(s) were found. "
                "Existing historical data and processed flags were left unchanged."
            ),
        }

    refresh_started = time.perf_counter()
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

    message = (
        f"Reviewed all {result['reviewed']} archived save(s). "
        "Historical data and Historical_Journal.html were rebuilt using "
        "the current Historian logic. Processed save flags were not changed."
    )

    if diagnostic_path is not None:
        message += (
            " Origin_Localisation_Debug.txt was also written to the "
            "campaign archive folder."
        )
    elif diagnostic_error:
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
        "ok": True,
        "reviewed": result["reviewed"],
        "total": result["total"],
        "errors": [],
        "journal_path": str(journal),
        "journal_url": "/journal",
        "origin_debug_path": (
            str(diagnostic_path)
            if diagnostic_path is not None
            else None
        ),
        "origin_debug_error": diagnostic_error,
        "message": message,
    }



@app.post("/api/construct-campaign")
def api_construct_campaign():
    if LIVE_HISTORY_ENABLED or LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Wait for Live History to be fully OFF before running Construct Campaign.",
        )

    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(
            400,
            "No campaign is active.",
        )

    campaign = DB.campaign(
        ACTIVE_CAMPAIGN_ID
    )

    if campaign is None:
        raise HTTPException(
            404,
            "Active campaign no longer exists.",
        )

    warning(
        f"CONSTRUCT requested for {campaign['empire_name']}."
    )

    result = construct_campaign(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    if result["errors"]:
        return {
            "ok": False,
            "constructed": result["constructed"],
            "total": result["total"],
            "errors": result["errors"],
            "message": (
                f"Construction stopped after reading {result['constructed']} of "
                f"{result['total']} archived save(s). "
                f"{len(result['errors'])} error(s) were found. "
                "Existing derived history and processed flags were not replaced."
            ),
        }

    refresh_started = time.perf_counter()
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

    message = (
        f"Constructed {result['constructed']} archived save(s) from scratch. "
        "Historical data, cache and Historical_Journal.html were rebuilt. "
        "All archived saves are now marked Processed."
    )

    if diagnostic_error:
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
        "ok": True,
        "constructed": result["constructed"],
        "total": result["total"],
        "errors": [],
        "cache_hits": result["cache_hits"],
        "cache_extends": result.get("cache_extends", 0),
        "cache_misses": result["cache_misses"],
        "removed_cache_files": result["removed_cache_files"],
        "newly_marked_processed": result["newly_marked_processed"],
        "journal_path": str(
            journal
        ),
        "journal_url": "/journal",
        "origin_debug_path": (
            str(
                diagnostic_path
            )
            if diagnostic_path is not None
            else None
        ),
        "origin_debug_error": diagnostic_error,
        "message": message,
    }


@app.get("/journal")
def open_journal():
    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(
            400,
            "No campaign is active.",
        )

    path = journal_path(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    if not path.exists():
        raise HTTPException(
            404,
            "Historical journal has not been created yet.",
        )

    return FileResponse(
        path,
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/scribes")
def open_scribes():
    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(
            400,
            "No campaign is active.",
        )

    try:
        path = render_scribes_journal(
            DB,
            ACTIVE_CAMPAIGN_ID,
        )
    except Exception as exc:
        error(
            f"SCRIBES JOURNAL - {exc}"
        )
        raise HTTPException(
            500,
            f"Scribes chronicle could not be rendered: {exc}",
        ) from exc

    return FileResponse(
        path,
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/scribes/pdf")
def export_scribes_pdf():
    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(400, "No campaign is active.")

    campaign = DB.campaign(ACTIVE_CAMPAIGN_ID)
    if campaign is None:
        raise HTTPException(404, "Campaign does not exist.")

    try:
        path = render_scribes_pdf(DB, ACTIVE_CAMPAIGN_ID)
    except Exception as exc:
        error(f"SCRIBES PDF - {exc}")
        raise HTTPException(500, f"Scribes PDF could not be generated: {exc}") from exc

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{safe_name(campaign['empire_name'])} - Scribes Chronicle.pdf",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/timeline")
def open_timeline():
    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(400, "No campaign is active.")

    try:
        path = render_timeline(DB, ACTIVE_CAMPAIGN_ID)
    except Exception as exc:
        error(f"EMPIRE TIMELINE - {exc}")
        raise HTTPException(500, f"Empire Timeline could not be rendered: {exc}") from exc

    return FileResponse(
        path,
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


def _require_local_request(request: Request) -> None:
    if request.client is None or request.client.host not in {
        "127.0.0.1",
        "::1",
        "localhost",
    }:
        raise HTTPException(403, "Local access only.")


def _open_local_folder(path: Path) -> None:
    target = Path(path).resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, f"Folder does not exist: {target}")

    try:
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except OSError as exc:
        raise HTTPException(500, f"Could not open folder: {exc}") from exc


@app.post("/api/open-campaign-folder")
def api_open_campaign_folder(request: Request):
    _require_local_request(request)
    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(400, "No campaign is active.")

    campaign = DB.campaign(ACTIVE_CAMPAIGN_ID)
    if campaign is None:
        raise HTTPException(404, "Active campaign no longer exists.")

    path = Path(campaign["archive_dir"])
    _open_local_folder(path)
    return {"ok": True, "path": str(path)}


@app.post("/api/open-diagnostics-folder")
def api_open_diagnostics_folder(request: Request):
    _require_local_request(request)
    if ACTIVE_CAMPAIGN_ID is None:
        raise HTTPException(400, "No campaign is active.")

    campaign = DB.campaign(ACTIVE_CAMPAIGN_ID)
    if campaign is None:
        raise HTTPException(404, "Active campaign no longer exists.")

    path = Path(campaign["archive_dir"]) / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    _open_local_folder(path)
    return {"ok": True, "path": str(path)}


@app.post("/app/close")
def close_app(request: Request):
    _require_local_request(request)

    def stop():
        global server

        WATCHER.stop()

        if server is not None:
            server.should_exit = True

    threading.Timer(
        0.2,
        stop,
    ).start()

    return JSONResponse({"ok": True})


if __name__ == "__main__":
    info(
        f"Starting local server at http://{CONFIG.host}:{CONFIG.port}"
    )

    config = uvicorn.Config(
        app,
        host=CONFIG.host,
        port=CONFIG.port,
        log_level="warning",
        access_log=False,
    )

    server = uvicorn.Server(config)

    if CONFIG.open_browser:
        threading.Timer(
            1.0,
            lambda: webbrowser.open(
                f"http://{CONFIG.host}:{CONFIG.port}/?v={APP_VERSION}",
                new=2,
            ),
        ).start()

    server.run()
