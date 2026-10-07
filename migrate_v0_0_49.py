from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_49_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.49.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.49"

REQUIRED_FILES = [
    "app.py", "start.bat", "README.md", "docs/CHANGELOG.md",
    "historian/__init__.py", "historian/watcher.py", "historian_manifest.json",
    "static/campaign.html", "static/campaign.js", "static/style.css",
    "historian/domains/politics/first_contact_probe.py",
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
    log.append(f"Backed up {relative} -> backups/v0.0.49/{relative}")


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
        raise RuntimeError(f"Could not locate v0.0.48.1 anchor for {label}.")
    log.append(f"Installed: {label}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, count: int, label: str, log: list[str]) -> str:
    if text.count(new) >= count:
        log.append(f"Already installed: {label}")
        return text
    found = text.count(old)
    if found < count:
        raise RuntimeError(f"Expected at least {count} v0.0.48.1 anchor(s) for {label}, found {found}.")
    log.append(f"Installed: {label} ({count} occurrence(s))")
    return text.replace(old, new, count)


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('__version__ = "0.0.48.1"', '__version__ = "0.0.49"', 1)
    if updated == original and '__version__ = "0.0.49"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.48.1 to 0.0.49.")
    write_if_changed(path, original, updated, log)


def patch_watcher(log: list[str]) -> None:
    path = ROOT / "historian" / "watcher.py"
    original = path.read_text(encoding="utf-8")
    anchor = """    def selected(self) -> tuple[Path | None, int | None]:
        with self._lock:
            return self._selected_path, self._campaign_id
"""
    replacement = """    def clear_campaign(self) -> None:
        with self._lock:
            self._selected_path = None
            self._campaign_id = None
            self._candidate_signature = None
            self._candidate_since = None
            self._processed_signature = None
            self.status = "Waiting for campaign"

        info("Campaign monitoring cleared - waiting for campaign selection.")

    def selected(self) -> tuple[Path | None, int | None]:
        with self._lock:
            return self._selected_path, self._campaign_id
"""
    updated = replace_once(original, anchor, replacement, "watcher campaign-clear method", log)
    ast.parse(updated, filename=str(path))
    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_anchor = "from historian.domains.politics.probe import write_politics_diplomacy_probe\n"
    import_replacement = import_anchor + "from historian.domains.politics.first_contact_probe import write_first_contact_probe\n"
    updated = replace_once(updated, import_anchor, import_replacement, "First Contact probe import", log)

    helper_anchor = "def safe_name(value: str, max_len: int = 60) -> str:\n"
    helper_replacement = """def _first_contact_probe_refresh(
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
                "First_Contact_Probe_Debug.txt - "
                f"scanning {done}/{total} - {snapshot.get('game_date', 'unknown date')}"
            )

    return write_first_contact_probe(DB, campaign_id, progress=progress)


def safe_name(value: str, max_len: int = 60) -> str:
"""
    updated = replace_once(updated, helper_anchor, helper_replacement, "First Contact refresh helper", log)

    route_anchor = """@app.get("/api/active-campaign")
def api_active_campaign():
"""
    route_replacement = """@app.post("/api/select-new-campaign")
def api_select_new_campaign():
    global ACTIVE_CAMPAIGN_ID, LIVE_HISTORY_ENABLED, LIVE_HISTORY_STATUS

    if LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Live History is finishing an automatic update. Wait for it to finish before selecting another campaign.",
        )

    previous_campaign = DB.campaign(ACTIVE_CAMPAIGN_ID) if ACTIVE_CAMPAIGN_ID is not None else None
    LIVE_HISTORY_ENABLED = False
    LIVE_HISTORY_STATUS = "OFF"
    WATCHER.clear_campaign()
    ACTIVE_CAMPAIGN_ID = None

    label = previous_campaign["empire_name"] if previous_campaign is not None else "no active campaign"
    activity(f"SELECT NEW CAMPAIGN - stopped monitoring {label}")

    return {"ok": True, "redirect": "/"}


@app.get("/api/active-campaign")
def api_active_campaign():
"""
    updated = replace_once(updated, route_anchor, route_replacement, "Select New Campaign API route", log)

    updated = replace_count(updated, "    refresh_total = 5\n", "    refresh_total = 6\n", 2, "six-step refresh total", log)

    politics_block = """    politics_probe_path, politics_probe_error = _run_refresh_step(
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
"""
    politics_replacement = """    politics_probe_path, politics_probe_error = _run_refresh_step(
        4,
        refresh_total,
        "Politics_Diplomacy_Probe_Debug.txt",
        lambda: _politics_probe_refresh(ACTIVE_CAMPAIGN_ID, 4, refresh_total),
    )

    first_contact_probe_path, first_contact_probe_error = _run_refresh_step(
        5,
        refresh_total,
        "First_Contact_Probe_Debug.txt",
        lambda: _first_contact_probe_refresh(ACTIVE_CAMPAIGN_ID, 5, refresh_total),
    )

    diagnostic_path, diagnostic_error = _run_refresh_step(
        6,
        refresh_total,
        "Origin_Localisation_Debug.txt",
        lambda: _origin_localisation_refresh(ACTIVE_CAMPAIGN_ID),
    )
"""
    updated = replace_count(updated, politics_block, politics_replacement, 2, "First Contact refresh step", log)

    errors_anchor = """            notification_decoder_error,
            politics_probe_error,
            diagnostic_error,
"""
    errors_replacement = """            notification_decoder_error,
            politics_probe_error,
            first_contact_probe_error,
            diagnostic_error,
"""
    updated = replace_count(updated, errors_anchor, errors_replacement, 2, "First Contact refresh error accounting", log)

    ast.parse(updated, filename=str(path))
    write_if_changed(path, original, updated, log)


def patch_campaign_html(log: list[str]) -> None:
    path = ROOT / "static" / "campaign.html"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('/static/style.css?v=006', '/static/style.css?v=007', 1)
    anchor = """  </div>

  <button id="update-history" type="button">
"""
    replacement = """  </div>

  <button id="select-new-campaign" class="campaign-nav-button" type="button">
    Select New Campaign
  </button>

  <div class="campaign-action-spacer" aria-hidden="true"></div>

  <button id="update-history" type="button">
"""
    updated = replace_once(updated, anchor, replacement, "Select New Campaign button", log)
    updated = updated.replace('/static/campaign.js?v=010', '/static/campaign.js?v=011', 1)
    write_if_changed(path, original, updated, log)


def patch_campaign_js(log: list[str]) -> None:
    path = ROOT / "static" / "campaign.js"
    original = path.read_text(encoding="utf-8")
    updated = original
    updated = replace_once(updated,
        'const status = document.getElementById("status");\nconst updateButton = document.getElementById("update-history");\n',
        'const status = document.getElementById("status");\nconst selectCampaignButton = document.getElementById("select-new-campaign");\nconst updateButton = document.getElementById("update-history");\n',
        "Select New Campaign JS handle", log)

    updated = replace_once(updated,
        '  const liveBlocking = liveEnabled || liveBusy;\n\n  updateButton.disabled =\n',
        '  const liveBlocking = liveEnabled || liveBusy;\n\n  selectCampaignButton.disabled = actionInProgress || liveBusy;\n  selectCampaignButton.title = liveBusy\n    ? "Wait for the current Live History update to finish before selecting another campaign."\n    : "Stop monitoring this campaign and return to campaign selection.";\n\n  updateButton.disabled =\n',
        "Select New Campaign availability", log)

    listener_anchor = 'liveHistoryButton.addEventListener("click", async () => {\n'
    listener_replacement = """selectCampaignButton.addEventListener("click", async () => {
  actionInProgress = true;
  applyActionAvailability();
  status.textContent = "Stopping campaign monitoring and returning to campaign selection...";

  try{
    const response = await fetch("/api/select-new-campaign", {method:"POST"});
    const data = await response.json();
    if(!response.ok){
      throw new Error(data.detail || "Could not return to campaign selection.");
    }
    window.location.href = data.redirect || "/";
  }catch(error){
    status.textContent = `Could not select a new campaign: ${error.message}`;
    actionInProgress = false;
    applyActionAvailability();
  }
});

liveHistoryButton.addEventListener("click", async () => {
"""
    updated = replace_once(updated, listener_anchor, listener_replacement, "Select New Campaign click handler", log)
    write_if_changed(path, original, updated, log)


def patch_style(log: list[str]) -> None:
    path = ROOT / "static" / "style.css"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('  margin-right:auto;\n  min-width:0;\n', '  margin-right:0;\n  min-width:0;\n', 1)
    anchor = """.close-button{
  border-color:#743e3e;
  background:#3b2020;
  color:#ffe0e0;
}
"""
    replacement = """.campaign-nav-button{
  border-color:#4f8fba;
  background:#215b82;
  color:#eef8ff;
  white-space:nowrap;
}

.campaign-nav-button:hover{
  background:#2a739f;
}

.campaign-action-spacer{
  flex:1 1 70px;
  min-width:28px;
}

.close-button{
  border-color:#743e3e;
  background:#3b2020;
  color:#ffe0e0;
}
"""
    updated = replace_once(updated, anchor, replacement, "campaign navigation styling", log)
    media_anchor = """@media(max-width:980px){
  header{flex-wrap:wrap}
  .brand{width:100%}
  .header-control{min-width:0;max-width:none;flex:1}
}
"""
    media_replacement = """@media(max-width:980px){
  header{flex-wrap:wrap}
  .brand{width:100%}
  .campaign-action-spacer{display:none}
  .header-control{min-width:0;max-width:none;flex:1}
}
"""
    updated = replace_once(updated, media_anchor, media_replacement, "responsive campaign navigation spacer", log)
    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original.replace("## Current version\n\nv0.0.48.1", "## Current version\n\nv0.0.49", 1)
    feature_anchor = "- Live History ON/OFF can automatically process newly archived saves\n"
    feature_text = feature_anchor + "- Select New Campaign returns safely to campaign selection without refreshing the browser\n- First Contact evidence probe correlates assignment windows, diplomacy state and targeted raw-save structures\n"
    if "First Contact evidence probe" not in updated:
        if feature_anchor not in updated:
            raise RuntimeError("Could not locate README v0.0.49 feature anchor.")
        updated = updated.replace(feature_anchor, feature_text, 1)
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = """## v0.0.49
- Added a blue **Select New Campaign** control to the campaign header with a visual spacer separating navigation from current-campaign actions.
- Added `/api/select-new-campaign` and watcher deselection support. Returning to campaign selection turns Live History OFF, stops monitoring the current save, and leaves all archives/history data untouched.
- Added `diagnostics/First_Contact_Probe_Debug.txt`, a dedicated evidence-first First Contact foundation.
- The First Contact probe correlates cached leader `first_contact_system` assignment transitions with adjacent Politics/Diplomacy relation/communications changes.
- Review Campaign and Construct Campaign now run First Contact as refresh step 5/6 with targeted raw-save progress; Origin Localisation becomes step 6/6.
- Raw First Contact structures are sampled around assignment transitions and the recent campaign edge, capped at 48 raw archive reads.
- v0.0.49 does not claim an exact First Contact date, counterpart or response choice unless a later decoder establishes those fields directly.
- No SQLite schema change, no parsed-cache version bump, and no archived `.sav` changes.

"""
    if section not in original:
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
    data["version"] = "0.0.49"
    data["architecture"] = "modular-foundation-24-campaign-navigation-first-contact-probe"
    diagnostics = data.setdefault("diagnostics", {})
    files = diagnostics.setdefault("files", [])
    if "First_Contact_Probe_Debug.txt" not in files:
        files.append("First_Contact_Probe_Debug.txt")
    data["first_contact_probe"] = {
        "status": "diagnostic-correlation-foundation",
        "cache_version_change": False,
        "raw_sample_maximum": 48,
        "evidence": [
            "leader first_contact_system assignment transitions",
            "adjacent structured relation-record appearances",
            "adjacent communications-field changes",
            "targeted raw first_contact/contact/communications keys and contexts",
        ],
        "rule": "Correlation is diagnostic-only; exact First Contact completion, counterpart and response choice are not published without direct retained evidence.",
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.49 campaign navigation and First Contact foundation migration started.",
        "No archived Stellaris saves, campaign identity, SQLite rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.49 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.49 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        ast.parse((ROOT / "historian/domains/politics/first_contact_probe.py").read_text(encoding="utf-8"), filename="first_contact_probe.py")
        patch_version(log)
        patch_watcher(log)
        patch_app(log)
        patch_campaign_html(log)
        patch_campaign_js(log)
        patch_style(log)
        patch_readme(log)
        patch_changelog(log)
        patch_manifest(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.49 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.49 migration failed.")
        print("Original source backups are retained under backups\\v0.0.49 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("Stellaris Historian v0.0.49 campaign navigation and First Contact foundation migration completed.\n", encoding="utf-8")

    log.extend([
        "Select New Campaign navigation installed.",
        "First_Contact_Probe_Debug.txt refresh integration installed.",
        "First Contact remains evidence-first and diagnostic-only in v0.0.49.",
        "Existing parsed cache component versions remain unchanged.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.49 campaign navigation and First Contact foundation migration complete.")
    print("Select New Campaign is now available on the campaign page.")
    print("Review/Construct now refresh First_Contact_Probe_Debug.txt as step 5/6.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
