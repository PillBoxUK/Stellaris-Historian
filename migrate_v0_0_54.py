from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import shutil


ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_54_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.54.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.54"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "docs/CHANGELOG.md",
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/presentation_history.py",
    "historian_manifest.json",
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
    log.append(f"Backed up {relative} -> backups/v0.0.54/{relative}")


def write_if_changed(path: Path, original: str, updated: str, log: list[str]) -> None:
    if updated == original:
        log.append(f"No change needed: {path.relative_to(ROOT)}")
        return
    backup(path, log)
    path.write_text(updated, encoding="utf-8", newline="\n")
    log.append(f"Updated: {path.relative_to(ROOT)}")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Could not locate v0.0.53 anchor for {label}.")
    return text.replace(old, new, 1)


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('__version__ = "0.0.53"', '__version__ = "0.0.54"', 1)
    if updated == original and '__version__ = "0.0.54"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.53 to 0.0.54.")
    write_if_changed(path, original, updated, log)


def patch_snapshot_cache(log: list[str]) -> None:
    path = ROOT / "historian" / "snapshot_cache.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        "    cache_dir: Path,\n    timings: dict[str, float] | None = None,\n) -> tuple[\n",
        "    cache_dir: Path,\n    timings: dict[str, float] | None = None,\n    cache_only: bool = False,\n) -> tuple[\n",
        label="snapshot-cache cache_only parameter",
    )

    guard = '''    if cache_only:\n        raise RuntimeError(\n            "Processed snapshot cache is missing, stale or incomplete; "\n            "diagnostic synchronization refused to reparse the raw save."\n        )\n\n'''
    if guard not in updated:
        anchor = '''    # A valid cache container may contain older component versions. Reuse\n'''
        if anchor not in updated:
            raise RuntimeError("Could not locate snapshot-cache raw-fallback anchor.")
        updated = updated.replace(anchor, guard + anchor, 1)

    ast.parse(updated, filename="historian/snapshot_cache.py")
    write_if_changed(path, original, updated, log)


def patch_history_processor(log: list[str]) -> None:
    path = ROOT / "historian" / "history_processor.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    function = '''def refresh_processed_combat_diagnostics(db: Database, campaign_id: int) -> dict:\n    """Synchronize combat diagnostics from processed snapshot cache only.\n\n    This deliberately refuses to reopen raw .sav files.  It exists so Live\n    History / Update History can keep the forensic combat text files current\n    without triggering a full Review Campaign pass or undermining the\n    queue-first performance work added in v0.0.53.\n    """\n    started = time.perf_counter()\n    snapshots = list(db.processed_snapshots(campaign_id))\n    campaign, source_save, cache_dir = _campaign_context(db, campaign_id)\n    ship_fleet_snapshots = []\n    combat_snapshots = []\n    errors: list[str] = []\n\n    for snapshot in snapshots:\n        try:\n            (\n                _profile,\n                ship_snapshot,\n                _leader_snapshot,\n                _world_snapshot,\n                _science_snapshot,\n                combat_snapshot,\n                _technology_snapshot,\n                _politics_snapshot,\n                cache_status,\n            ) = load_or_parse_snapshot(\n                archive_path=Path(snapshot["archive_path"]),\n                source_save=source_save,\n                source_sha256=snapshot["sha256"],\n                snapshot_id=int(snapshot["id"]),\n                cache_dir=cache_dir,\n                cache_only=True,\n            )\n            if cache_status != "hit":\n                raise RuntimeError(\n                    f"expected cache hit, received {cache_status}"\n                )\n            ship_fleet_snapshots.append(ship_snapshot)\n            combat_snapshots.append(combat_snapshot)\n        except Exception as exc:\n            errors.append(f"{snapshot['archive_filename']}: {exc}")\n\n    if errors:\n        warning(\n            "COMBAT DIAGNOSTIC SYNC SKIPPED - "\n            f"{len(errors)} processed snapshot cache error(s). "\n            "Existing diagnostics were left unchanged; run Review Campaign "\n            "if a full cache repair/reparse is required."\n        )\n        for message in errors[:3]:\n            warning(f"COMBAT DIAGNOSTIC SYNC - {message}")\n        if len(errors) > 3:\n            warning(\n                f"COMBAT DIAGNOSTIC SYNC - {len(errors) - 3} additional error(s) omitted."\n            )\n        return {\n            "refreshed": False,\n            "snapshots": len(combat_snapshots),\n            "expected_snapshots": len(snapshots),\n            "errors": errors,\n            "duration_seconds": time.perf_counter() - started,\n        }\n\n    correlated_engagements = derive_correlated_engagements(\n        ship_fleet_snapshots,\n        combat_snapshots,\n    )\n    direct_combat_episodes = derive_direct_combat_episodes(\n        combat_snapshots\n    )\n    combat_episodes = derive_combat_episodes(\n        combat_snapshots,\n        correlated_engagements,\n        direct_combat_episodes,\n    )\n\n    diagnostic_dir = _diagnostics_dir(Path(campaign["archive_dir"]))\n    combat_debug = write_combat_diagnostic(\n        diagnostic_dir,\n        combat_snapshots,\n    )\n    correlation_debug = write_combat_correlation_diagnostic(\n        diagnostic_dir,\n        correlated_engagements,\n        direct_episodes=direct_combat_episodes,\n    )\n    episode_debug = write_combat_episode_diagnostic(\n        diagnostic_dir,\n        combat_episodes,\n    )\n\n    combat_summary = combat_evidence_summary(combat_snapshots)\n    correlation = correlation_summary(correlated_engagements)\n    episode_summary = combat_episode_summary(combat_episodes)\n    latest = combat_snapshots[-1].game_date if combat_snapshots else "none"\n    duration = time.perf_counter() - started\n\n    activity(\n        "COMBAT DIAGNOSTIC SYNC COMPLETE - "\n        f"{len(combat_snapshots)} processed snapshot(s) through {latest} | "\n        f"Wars {combat_summary['wars']} | "\n        f"Formal battles {combat_summary['battles']} | "\n        f"Combat episodes {episode_summary['episodes']} | "\n        f"Correlations {correlation['publishable_engagements']} publishable | "\n        f"{format_duration(duration)}"\n    )\n\n    return {\n        "refreshed": True,\n        "snapshots": len(combat_snapshots),\n        "expected_snapshots": len(snapshots),\n        "latest_game_date": latest,\n        "wars": combat_summary["wars"],\n        "battles": combat_summary["battles"],\n        "episodes": episode_summary["episodes"],\n        "paths": [\n            str(combat_debug),\n            str(correlation_debug),\n            str(episode_debug),\n        ],\n        "errors": [],\n        "duration_seconds": duration,\n    }\n\n\n'''
    if "def refresh_processed_combat_diagnostics(" not in updated:
        anchor = "def process_unprocessed(db: Database, campaign_id: int) -> dict:\n"
        if anchor not in updated:
            raise RuntimeError("Could not locate process_unprocessed anchor.")
        updated = updated.replace(anchor, function + anchor, 1)

    ast.parse(updated, filename="historian/history_processor.py")
    write_if_changed(path, original, updated, log)


def patch_presentation_history(log: list[str]) -> None:
    path = ROOT / "historian" / "presentation_history.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        "    result: list = []\n    for snapshot in db.all_snapshots(campaign_id):\n",
        "    result: list = []\n    for snapshot in db.processed_snapshots(campaign_id):\n",
        label="processed-only presentation cache input",
    )

    old_doc = '''    Review Campaign remains the evidence-building step. Timeline and Scribes read\n    only the database plus already-populated snapshot-cache components and then\n    synthesize the same Historical Event Layer in memory. Neither renderer\n    reparses Ironman saves or mutates campaign evidence.\n'''
    new_doc = '''    Review Campaign remains the deepest evidence-building step. Timeline,\n    Scribes and the War Journal read only the database plus already-populated\n    cache components for snapshots that completed normal History processing.\n    None of these renderers reparses Ironman saves or mutates campaign evidence.\n'''
    if new_doc not in updated and old_doc in updated:
        updated = updated.replace(old_doc, new_doc, 1)

    ast.parse(updated, filename="historian/presentation_history.py")
    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    old_import = "from historian.history_processor import construct_campaign, process_unprocessed, review_campaign\n"
    new_import = '''from historian.history_processor import (\n    construct_campaign,\n    process_unprocessed,\n    refresh_processed_combat_diagnostics,\n    review_campaign,\n)\n'''
    updated = replace_once(
        updated,
        old_import,
        new_import,
        label="history processor import",
    )

    live_old = '''                if result["processed"]:\n                    _refresh_first_contact_history_for_journal(\n                        campaign_id,\n                        "LIVE HISTORY",\n                    )\n'''
    live_new = '''                if result["processed"]:\n                    combat_sync = refresh_processed_combat_diagnostics(\n                        DB,\n                        campaign_id,\n                    )\n                    if not combat_sync.get("refreshed", False):\n                        warning(\n                            "LIVE HISTORY - combat diagnostics could not be synchronized "\n                            "from cache; existing diagnostic files were left unchanged."\n                        )\n\n                    _refresh_first_contact_history_for_journal(\n                        campaign_id,\n                        "LIVE HISTORY",\n                    )\n'''
    updated = replace_once(
        updated,
        live_old,
        live_new,
        label="Live History combat diagnostic sync",
    )

    manual_old = '''    result = process_unprocessed(\n        DB,\n        ACTIVE_CAMPAIGN_ID,\n    )\n\n    _refresh_first_contact_history_for_journal(\n'''
    manual_new = '''    result = process_unprocessed(\n        DB,\n        ACTIVE_CAMPAIGN_ID,\n    )\n\n    combat_sync = None\n    if int(result.get("remaining", 0) or 0) == 0:\n        combat_sync = refresh_processed_combat_diagnostics(\n            DB,\n            ACTIVE_CAMPAIGN_ID,\n        )\n        if not combat_sync.get("refreshed", False):\n            warning(\n                "UPDATE HISTORY - combat diagnostics could not be synchronized "\n                "from cache; existing diagnostic files were left unchanged."\n            )\n\n    _refresh_first_contact_history_for_journal(\n'''
    updated = replace_once(
        updated,
        manual_old,
        manual_new,
        label="manual Update History combat diagnostic sync",
    )

    message_old = '''        if politics_warnings:\n            message += (\n                f" Politics/Diplomacy produced {len(politics_warnings)} warning(s); "\n                "core history progress was still saved and will not be replayed."\n            )\n\n    return {\n'''
    message_new = '''        if combat_sync and combat_sync.get("refreshed", False):\n            message += (\n                f" Combat diagnostics synchronized through "\n                f"{combat_sync.get('latest_game_date', 'the latest processed snapshot')}."\n            )\n        if politics_warnings:\n            message += (\n                f" Politics/Diplomacy produced {len(politics_warnings)} warning(s); "\n                "core history progress was still saved and will not be replayed."\n            )\n\n    return {\n'''
    updated = replace_once(
        updated,
        message_old,
        message_new,
        label="manual Update History sync response message",
    )

    return_old = '''        "journal_path": str(journal),\n        "journal_url": "/journal",\n        "message": message,\n'''
    return_new = '''        "journal_path": str(journal),\n        "journal_url": "/journal",\n        "combat_diagnostics": combat_sync,\n        "message": message,\n'''
    updated = replace_once(
        updated,
        return_old,
        return_new,
        label="manual Update History sync response payload",
    )

    ast.parse(updated, filename="app.py")
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.54\n- Fixes stale combat diagnostics after incremental Update History / Live History processing.\n- Adds a cache-only synchronization pass for `Combat_Evidence_Debug.txt`, `Combat_Correlation_Debug.txt` and `Combat_Episode_Debug.txt` once the normal History queue reaches zero.\n- Synchronization consumes processed snapshots only and refuses to reopen raw `.sav` files; if a processed cache is missing/stale, existing diagnostics are preserved and Review Campaign is recommended.\n- Manual Update History can synchronize the combat diagnostics even when zero new saves are waiting.\n- Live History retains v0.0.53 queue-first scheduling and runs the diagnostic sync only after catch-up.\n- War Journal, Timeline and Scribes cached evidence readers now ignore archived-but-unprocessed snapshots.\n- No SQLite schema change, parsed-cache component version bump, archived-save rewrite or processed-flag reset.\n\n'''
    if section not in original:
        anchor = "# Changelog\n\n"
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
    data["version"] = "0.0.54"
    data["architecture"] = "modular-foundation-33-processed-combat-diagnostic-sync"
    data["combat_diagnostic_sync"] = {
        "status": "active-cache-only-after-history-catch-up",
        "outputs": [
            "diagnostics/Combat_Evidence_Debug.txt",
            "diagnostics/Combat_Correlation_Debug.txt",
            "diagnostics/Combat_Episode_Debug.txt",
        ],
        "snapshot_scope": "processed snapshots only",
        "manual_update_runs_with_zero_new_saves": True,
        "live_history_runs_after_queue_zero": True,
        "raw_save_fallback": False,
        "cache_version_change": False,
        "database_schema_change": False,
    }
    presentation = data.get("presentation_history")
    if not isinstance(presentation, dict):
        presentation = {}
    presentation["snapshot_scope"] = "processed snapshots only"
    data["presentation_history"] = presentation
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def validate_readme(log: list[str]) -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "v0.0.54 — Processed Combat Diagnostic Synchronization",
        "Combat_Evidence_Debug.txt",
        "cache-only",
        "processed snapshots",
        "No SQLite schema change",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("README.md is not the v0.0.54 README: " + ", ".join(missing))
    log.append("Validated README.md v0.0.54 diagnostic synchronization documentation.")


def validate_source(log: list[str]) -> None:
    checks = {
        ROOT / "historian" / "snapshot_cache.py": (
            "cache_only: bool = False",
            "diagnostic synchronization refused to reparse the raw save",
        ),
        ROOT / "historian" / "history_processor.py": (
            "def refresh_processed_combat_diagnostics",
            "COMBAT DIAGNOSTIC SYNC COMPLETE",
            "cache_only=True",
        ),
        ROOT / "historian" / "presentation_history.py": (
            "db.processed_snapshots(campaign_id)",
        ),
        ROOT / "app.py": (
            "refresh_processed_combat_diagnostics",
            '"combat_diagnostics": combat_sync',
        ),
    }
    for path, tokens in checks.items():
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            ast.parse(text, filename=str(path.relative_to(ROOT)))
        for token in tokens:
            if token not in text:
                raise RuntimeError(f"{path.relative_to(ROOT)} missing expected v0.0.54 token: {token}")
    log.append("Validated v0.0.54 combat diagnostic synchronization source.")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.54 processed combat diagnostic synchronization migration started.",
        "No archived Stellaris saves, processed flags, SQLite schema or parsed-cache component versions are intentionally changed.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.54 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.54 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        validate_readme(log)
        patch_version(log)
        patch_snapshot_cache(log)
        patch_history_processor(log)
        patch_presentation_history(log)
        patch_app(log)
        patch_changelog(log)
        patch_manifest(log)
        validate_source(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.54 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.54 migration failed.")
        print("Original source backups are retained under backups\\v0.0.54 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.54 processed combat diagnostic synchronization migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Installed processed-only cache synchronization for the three combat diagnostic text files.",
        "Manual Update History can synchronize combat diagnostics even when no new save is waiting.",
        "Live History synchronizes combat diagnostics only after the normal History queue reaches zero.",
        "War Journal, Timeline and Scribes cached presentation input is now limited to processed snapshots.",
        "Cache-only diagnostic sync refuses raw-save fallback; Review Campaign remains the repair/deep-forensics path.",
        "No full cache rebuild is required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.54 processed combat diagnostic synchronization migration complete.")
    print("Combat diagnostics now catch up from processed snapshot cache after History queue catch-up.")
    print("The synchronization is cache-only and will not reopen raw saves.")
    print("War Journal / Timeline / Scribes cached evidence now ignores unprocessed snapshots.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
