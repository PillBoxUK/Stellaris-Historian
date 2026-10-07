from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_47_1_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.47.1.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.47.1"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "README_v0.0.47.1.md",
    "historian/__init__.py",
    "historian/db.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian_manifest.json",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.47.1.md",
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
    log.append(f"Backed up {relative} -> backups/v0.0.47.1/{relative}")


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
        raise RuntimeError(f"Could not locate v0.0.47 anchor for {label}.")
    log.append(f"Installed: {label}")
    return text.replace(old, new, 1)


def replace_all(text: str, old: str, new: str, label: str, log: list[str], minimum: int = 1) -> str:
    if old not in text:
        if new in text:
            log.append(f"Already installed: {label}")
            return text
        raise RuntimeError(f"Could not locate v0.0.47 anchor for {label}.")
    count = text.count(old)
    if count < minimum:
        raise RuntimeError(f"Expected at least {minimum} v0.0.47 anchors for {label}; found {count}.")
    log.append(f"Installed: {label} ({count} occurrence(s))")
    return text.replace(old, new)


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    if '__version__ = "0.0.47.1"' in original:
        return
    if '__version__ = "0.0.47"' not in original:
        raise RuntimeError("v0.0.47.1 requires Stellaris Historian v0.0.47.")
    updated = original.replace('__version__ = "0.0.47"', '__version__ = "0.0.47.1"', 1)
    write_if_changed(path, original, updated, log)


def patch_db(log: list[str]) -> None:
    path = ROOT / "historian" / "db.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    anchor = '''    def mark_all_processed(
        self,
        campaign_id: int,
    ) -> int:
'''
    methods = '''    def reconcile_processed_snapshots(self, campaign_id: int) -> int:
        """Recover durable progress when a history row exists but processed=1 was never reached.

        v0.0.47 could commit the normal history entry and then fail in the new
        Politics/Diplomacy stage before setting snapshots.processed.  Those rows
        are safe to resume past: the normal history transaction already exists.
        """
        now = utc_now()
        with self.connect() as con:
            cur = con.execute(
                """
                UPDATE snapshots
                SET processed=1,
                    processed_utc=COALESCE(processed_utc, ?)
                WHERE campaign_id=?
                  AND processed=0
                  AND EXISTS (
                      SELECT 1
                      FROM history_entries h
                      WHERE h.campaign_id=snapshots.campaign_id
                        AND h.snapshot_id=snapshots.id
                  )
                """,
                (now, campaign_id),
            )
            return int(cur.rowcount if cur.rowcount is not None else 0)

    def checkpoint(self) -> None:
        """Ask SQLite to checkpoint committed WAL pages into historian.db."""
        con = self.connect()
        try:
            con.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        finally:
            con.close()

    def mark_all_processed(
        self,
        campaign_id: int,
    ) -> int:
'''
    updated = replace_once(updated, anchor, methods, "durable progress reconciliation/checkpoint methods", log)
    write_if_changed(path, original, updated, log)


def patch_snapshot_cache(log: list[str]) -> None:
    path = ROOT / "historian" / "snapshot_cache.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        '''    technology_snapshot: TechnologySnapshot,
    politics_snapshot: PoliticsSnapshot,
) -> None:
''',
        '''    technology_snapshot: TechnologySnapshot,
    politics_snapshot: PoliticsSnapshot | None,
) -> None:
''',
        "optional Politics cache write",
        log,
    )

    updated = replace_once(
        updated,
        '''            POLITICS_COMPONENT_NAME: {
                "version": POLITICS_COMPONENT_VERSION,
                "data": politics_snapshot_to_dict(
                    politics_snapshot
                ),
            },
''',
        '''            POLITICS_COMPONENT_NAME: {
                "version": POLITICS_COMPONENT_VERSION,
                "data": (
                    politics_snapshot_to_dict(politics_snapshot)
                    if politics_snapshot is not None
                    else None
                ),
            },
''',
        "nullable Politics cache payload",
        log,
    )

    updated = replace_once(
        updated,
        '''    PoliticsSnapshot,
    str,
]:
''',
        '''    PoliticsSnapshot | None,
    str,
]:
''',
        "optional Politics return annotation",
        log,
    )

    extend_old = '''        if politics_snapshot is None:
            politics_snapshot = extract_politics_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
                leader_snapshot=leader_snapshot,
            )

        _write(
'''
    extend_new = '''        if politics_snapshot is None:
            try:
                politics_snapshot = extract_politics_snapshot(
                    gamestate=gamestate,
                    profile=profile,
                    source_save=source_save,
                    snapshot_id=snapshot_id,
                    leader_snapshot=leader_snapshot,
                )
            except Exception:
                # Politics/Diplomacy is an additive evidence domain.  A parser
                # problem must never invalidate the already supported history
                # components or force the same save through Update History again.
                politics_snapshot = None

        _write(
'''
    updated = replace_once(updated, extend_old, extend_new, "non-blocking Politics cache extension", log)

    full_old = '''    politics_snapshot = extract_politics_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
        leader_snapshot=leader_snapshot,
    )

    _write(
'''
    full_new = '''    try:
        politics_snapshot = extract_politics_snapshot(
            gamestate=gamestate,
            profile=profile,
            source_save=source_save,
            snapshot_id=snapshot_id,
            leader_snapshot=leader_snapshot,
        )
    except Exception:
        politics_snapshot = None

    _write(
'''
    updated = replace_once(updated, full_old, full_new, "non-blocking Politics full parse", log)

    write_if_changed(path, original, updated, log)


def patch_history_processor(log: list[str]) -> None:
    path = ROOT / "historian" / "history_processor.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        '''def process_unprocessed(db: Database, campaign_id: int) -> dict:
    started = time.perf_counter()
    snapshots = db.unprocessed_snapshots(campaign_id)
''',
        '''def process_unprocessed(db: Database, campaign_id: int) -> dict:
    started = time.perf_counter()

    # v0.0.47 could commit the normal history row but fail before setting the
    # snapshot processed flag if the new Politics/Diplomacy stage raised. Repair
    # those durable rows before deciding what actually still needs processing.
    recovered = db.reconcile_processed_snapshots(campaign_id)
    if recovered:
        warning(
            f"UPDATE HISTORY - recovered {recovered} already-written snapshot(s) "
            "from durable SQL history; they will not be replayed."
        )

    snapshots = db.unprocessed_snapshots(campaign_id)
''',
        "resume from durable SQL history",
        log,
    )

    updated = replace_once(
        updated,
        '''    processed = 0
    errors: list[str] = []
    cache = _cache_counter()
''',
        '''    processed = 0
    errors: list[str] = []
    politics_warnings: list[str] = []
    cache = _cache_counter()
''',
        "Politics warning collection",
        log,
    )

    updated = replace_once(
        updated,
        '''            politics_delta = politics_transition_data(
                previous_politics,
                current_politics,
                baseline=(snapshot["kind"] == "start"),
            )

            activity(
''',
        '''            politics_delta = None
            if current_politics is not None:
                politics_delta = politics_transition_data(
                    previous_politics,
                    current_politics,
                    baseline=(snapshot["kind"] == "start"),
                )
            else:
                politics_warnings.append(
                    f"{snapshot['archive_filename']}: Politics/Diplomacy evidence could not be parsed; core history was retained."
                )

            activity(
''',
        "optional incremental Politics transition",
        log,
    )

    updated = replace_once(
        updated,
        '''                f"Techs {len(current_technology.technologies)} | "
                f"Relations {len(current_politics.relations)} | "
                f"Traditions {len(current_politics.traditions)} | "
                f"Queued builds {len(current_state.build_orders)}"
''',
        '''                f"Techs {len(current_technology.technologies)} | "
                f"Relations {len(current_politics.relations) if current_politics is not None else 0} | "
                f"Traditions {len(current_politics.traditions) if current_politics is not None else 0} | "
                f"Queued builds {len(current_state.build_orders)}"
''',
        "safe incremental Politics activity counts",
        log,
    )

    updated = replace_once(
        updated,
        '''            db.apply_politics_delta(
                campaign_id,
                politics_delta,
            )

            db.mark_processed(
                snapshot_id
            )
            processed += 1
''',
        '''            # Core Historian progress is durable independently of the
            # additive Politics/Diplomacy domain.  Never make an already-written
            # snapshot replay from the start because a new evidence domain fails.
            db.mark_processed(
                snapshot_id
            )
            processed += 1

            if politics_delta is not None:
                try:
                    db.apply_politics_delta(
                        campaign_id,
                        politics_delta,
                    )
                except Exception as exc:
                    message = (
                        f"{snapshot['archive_filename']}: Politics/Diplomacy persistence warning: {exc}"
                    )
                    politics_warnings.append(message)
                    error(f"POLITICS / DIPLOMACY - {message}")
''',
        "core progress independent of Politics persistence",
        log,
    )

    updated = replace_once(
        updated,
        '''    remaining = db.unprocessed_count(
        campaign_id
    )

    activity(
''',
        '''    remaining = db.unprocessed_count(
        campaign_id
    )

    try:
        db.checkpoint()
        activity("SQLite WAL checkpoint complete - durable progress flushed to historian.db.")
    except Exception as exc:
        warning(f"SQLITE CHECKPOINT - {exc}")

    activity(
''',
        "post-update SQLite checkpoint",
        log,
    )

    updated = replace_once(
        updated,
        '''        "processed": processed,
        "errors": errors,
        "remaining": remaining,
''',
        '''        "processed": processed,
        "recovered": recovered,
        "errors": errors,
        "politics_warnings": politics_warnings,
        "remaining": remaining,
''',
        "incremental progress result details",
        log,
    )

    # Review/Construct: tolerate a missing Politics snapshot without losing the
    # supported domains.  Available Politics snapshots still reconstruct in order.
    updated = replace_all(
        updated,
        '''            politics_snapshots.append(
                politics_snapshot
            )

            activity(
''',
        '''            if politics_snapshot is not None:
                politics_snapshots.append(
                    politics_snapshot
                )

            activity(
''',
        "Review/Construct optional Politics append",
        log,
        minimum=2,
    )

    updated = replace_all(
        updated,
        '''                f"Techs {len(technology_snapshot.technologies)} | "
                f"Relations {len(politics_snapshot.relations)} | "
                f"Traditions {len(politics_snapshot.traditions)} | "
                f"Queued builds {len(parsed_snapshot.build_orders)}"
''',
        '''                f"Techs {len(technology_snapshot.technologies)} | "
                f"Relations {len(politics_snapshot.relations) if politics_snapshot is not None else 0} | "
                f"Traditions {len(politics_snapshot.traditions) if politics_snapshot is not None else 0} | "
                f"Queued builds {len(parsed_snapshot.build_orders)}"
''',
        "Review/Construct safe Politics counts",
        log,
        minimum=2,
    )

    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    old = '''    errors = result["errors"]

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
'''
    new = '''    errors = result["errors"]
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
'''
    updated = replace_once(updated, old, new, "Update History durable-progress message", log)

    updated = replace_once(
        updated,
        '''        "errors": errors,
        "journal_path": str(journal),
''',
        '''        "errors": errors,
        "politics_warnings": politics_warnings,
        "recovered": recovered,
        "journal_path": str(journal),
''',
        "Update History durable-progress API fields",
        log,
    )

    write_if_changed(path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original.replace("## Current version\n\nv0.0.47", "## Current version\n\nv0.0.47.1", 1)
    updated = updated.replace(
        "The current codebase includes migration and historical tracking work through version 0.0.47.",
        "The current codebase includes migration and historical tracking work through version 0.0.47.1.",
        1,
    )
    write_if_changed(path, original, updated, log)


def patch_manifest(log: list[str]) -> None:
    path = ROOT / "historian_manifest.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["version"] = "0.0.47.1"
    data["architecture"] = "modular-foundation-22-durable-incremental-history-hotfix"
    data["incremental_history"] = {
        "status": "durable-sql-resume",
        "progress_source": "snapshots.processed plus history_entries reconciliation",
        "wal_checkpoint_after_update": True,
        "politics_failure_blocks_core_progress": False,
        "rule": "A Politics/Diplomacy parser or persistence warning must not cause an already-written core snapshot to replay on the next Update History run."
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.47.1\n- Fixed Update History replaying snapshots whose normal history row had already been committed but whose `processed` flag was never reached after a Politics/Diplomacy failure.\n- Update History now reconciles such half-finished v0.0.47 rows from durable `history_entries` before selecting work.\n- Core history progress is marked processed independently of the additive Politics/Diplomacy persistence stage.\n- Politics/Diplomacy parser failures no longer invalidate otherwise-supported snapshot history.\n- Added a passive SQLite WAL checkpoint after each Update History batch so committed progress is flushed into `historian.db` when possible.\n- Review/Construct tolerate unavailable Politics snapshots while preserving the supported domains.\n- No archived `.sav` files are changed or deleted.\n\n'''
    if section not in original:
        anchor = "# Stellaris Historian Changelog\n\n" if "# Stellaris Historian Changelog\n\n" in original else "# Changelog\n\n"
        if anchor not in original:
            raise RuntimeError("Could not locate CHANGELOG heading.")
        updated = original.replace(anchor, anchor + section, 1)
    else:
        updated = original
    write_if_changed(path, original, updated, log)


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.47.1 durable incremental-history hotfix started.",
        "Archived Stellaris saves are not modified or deleted by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.47.1 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.47.1 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        patch_version(log)
        patch_db(log)
        patch_snapshot_cache(log)
        patch_history_processor(log)
        patch_app(log)
        patch_readme(log)
        patch_manifest(log)
        patch_changelog(log)

        for relative in (
            "app.py",
            "historian/db.py",
            "historian/snapshot_cache.py",
            "historian/history_processor.py",
        ):
            py_compile.compile(str(ROOT / relative), doraise=True)

    except (py_compile.PyCompileError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.47.1 migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.47.1 validation failed.")
        print("Original source backups are retained under backups\\v0.0.47.1 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.47.1 durable incremental-history hotfix completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Existing SQL history rows can now reconcile missing processed flags from the v0.0.47 failure window.",
        "Core history progress no longer depends on Politics/Diplomacy persistence succeeding.",
        "Politics/Diplomacy parsing is non-blocking for core history.",
        "Update History requests a passive WAL checkpoint after each batch.",
        "No Construct Campaign is required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.47.1 durable incremental-history hotfix complete.")
    print("Update History will resume from durable SQL progress instead of replaying already-written snapshots.")
    print("Politics/Diplomacy warnings no longer block core history progress.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
