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

    try:
        yield
    finally:
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
    global ACTIVE_CAMPAIGN_ID

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
        }

    campaign = DB.campaign(ACTIVE_CAMPAIGN_ID)

    if campaign is None:
        return {
            "version": APP_VERSION,
            "campaign": None,
            "monitoring": False,
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
        "archive_count": DB.snapshot_count(ACTIVE_CAMPAIGN_ID),
        "unprocessed_count": DB.unprocessed_count(ACTIVE_CAMPAIGN_ID),
        "processed_count": DB.processed_count(ACTIVE_CAMPAIGN_ID),
        "journal_exists": current_journal.exists(),
        "journal_url": "/journal",
        "snapshots": snapshots,
    }


@app.post("/api/update-history")
def api_update_history():
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

    if errors:
        message = (
            f"Processed {result['processed']} save(s). "
            f"{len(errors)} save(s) could not be processed. "
            f"{result['remaining']} remain unprocessed."
        )
    else:
        message = (
            f"Processed {result['processed']} save(s). "
            f"Historical_Journal.html updated successfully. "
            f"{result['remaining']} save(s) remain unprocessed."
        )

    return {
        "ok": len(errors) == 0,
        "processed": result["processed"],
        "remaining": result["remaining"],
        "errors": errors,
        "journal_path": str(journal),
        "journal_url": "/journal",
        "message": message,
    }


@app.post("/api/review-campaign")
def api_review_campaign():
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

    activity(
        "Rendering Historical_Journal.html..."
    )

    journal_started = time.perf_counter()

    journal = render_journal(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    activity(
        f"Journal rebuilt - {format_duration(time.perf_counter() - journal_started)}"
    )

    diagnostic_path = None
    diagnostic_error = None

    try:
        campaign = DB.campaign(
            ACTIVE_CAMPAIGN_ID
        )

        snapshots = DB.all_snapshots(
            ACTIVE_CAMPAIGN_ID
        )

        start_snapshot = None

        for snapshot in snapshots:
            if snapshot["kind"] == "start":
                start_snapshot = snapshot
                break

        if start_snapshot is None and snapshots:
            start_snapshot = snapshots[0]

        if campaign is not None and start_snapshot is not None:
            founding_profile = read_empire_profile(
                Path(start_snapshot["archive_path"])
            )

            activity(
                "Refreshing Origin_Localisation_Debug.txt..."
            )

            diagnostic_path = write_origin_localisation_debug(
                Path(campaign["source_save"]),
                founding_profile.origin,
                Path(campaign["archive_dir"])
                / "Origin_Localisation_Debug.txt",
            )

            activity(
                "Origin localisation diagnostic updated."
            )

    except Exception as exc:
        diagnostic_error = str(exc)

        error(
            f"ORIGIN DIAGNOSTIC - {diagnostic_error}"
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

    activity(
        "Rendering Historical_Journal.html from reconstructed history..."
    )

    journal_started = time.perf_counter()

    journal = render_journal(
        DB,
        ACTIVE_CAMPAIGN_ID,
    )

    activity(
        f"Constructed journal written - "
        f"{format_duration(time.perf_counter() - journal_started)}"
    )

    diagnostic_path = None
    diagnostic_error = None

    try:
        snapshots = DB.all_snapshots(
            ACTIVE_CAMPAIGN_ID
        )

        start_snapshot = None

        for snapshot in snapshots:
            if snapshot["kind"] == "start":
                start_snapshot = snapshot
                break

        if start_snapshot is None and snapshots:
            start_snapshot = snapshots[0]

        if start_snapshot is not None:
            founding_profile = read_empire_profile(
                Path(
                    start_snapshot["archive_path"]
                )
            )

            activity(
                "Refreshing Origin_Localisation_Debug.txt..."
            )

            diagnostic_path = write_origin_localisation_debug(
                Path(
                    campaign["source_save"]
                ),
                founding_profile.origin,
                Path(
                    campaign["archive_dir"]
                ) / "Origin_Localisation_Debug.txt",
            )

            activity(
                "Origin localisation diagnostic updated."
            )

    except Exception as exc:
        diagnostic_error = str(
            exc
        )

        error(
            f"ORIGIN DIAGNOSTIC - {diagnostic_error}"
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
