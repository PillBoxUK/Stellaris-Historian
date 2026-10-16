from __future__ import annotations

from datetime import datetime
from pathlib import Path
import ast
import json
import re
import shutil


ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_53_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.53.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.53"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "docs/CHANGELOG.md",
    "historian/__init__.py",
    "historian/db.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/domains/politics/first_contact_history.py",
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
    log.append(f"Backed up {relative} -> backups/v0.0.53/{relative}")


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
        raise RuntimeError(f"Could not locate v0.0.52 anchor for {label}.")
    return text.replace(old, new, 1)


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('__version__ = "0.0.52"', '__version__ = "0.0.53"', 1)
    if updated == original and '__version__ = "0.0.53"' not in original:
        raise RuntimeError("Could not update historian version from 0.0.52 to 0.0.53.")
    write_if_changed(path, original, updated, log)


def patch_database(log: list[str]) -> None:
    path = ROOT / "historian" / "db.py"
    original = path.read_text(encoding="utf-8")
    insert = '''    def processed_snapshots(self, campaign_id: int):\n        """Return only snapshots that completed normal History processing."""\n        with self.connect() as con:\n            return con.execute(\n                """\n                SELECT *\n                FROM snapshots\n                WHERE campaign_id=? AND processed=1\n                ORDER BY id ASC\n                """,\n                (campaign_id,),\n            ).fetchall()\n\n'''
    if insert in original:
        updated = original
    else:
        anchor = "    def previous_snapshot(self, campaign_id: int, snapshot_id: int):\n"
        if anchor not in original:
            raise RuntimeError("Could not locate db.py previous_snapshot anchor.")
        updated = original.replace(anchor, insert + anchor, 1)
    ast.parse(updated, filename="historian/db.py")
    write_if_changed(path, original, updated, log)


def patch_first_contact_history(log: list[str]) -> None:
    path = ROOT / "historian" / "domains" / "politics" / "first_contact_history.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        "    rows = [dict(row) for row in db.all_snapshots(campaign_id)]\n",
        "    archived_snapshot_count = len(db.all_snapshots(campaign_id))\n"
        "    rows = [dict(row) for row in db.processed_snapshots(campaign_id)]\n"
        "    ignored_unprocessed = max(0, archived_snapshot_count - len(rows))\n",
        label="First Contact processed-only snapshot selection",
    )
    updated = replace_once(
        updated,
        '        "archived_snapshots": len(rows),\n',
        '        "archived_snapshots": archived_snapshot_count,\n'
        '        "processed_snapshots_considered": len(rows),\n'
        '        "unprocessed_snapshots_ignored": ignored_unprocessed,\n',
        label="First Contact payload snapshot counts",
    )
    updated = replace_once(
        updated,
        '        f"Archived snapshots: {len(rows)}",\n',
        '        f"Archived snapshots: {archived_snapshot_count}",\n'
        '        f"Processed snapshots considered: {len(rows)}",\n'
        '        f"Unprocessed snapshots ignored: {ignored_unprocessed}",\n',
        label="First Contact debug snapshot counts",
    )
    ast.parse(updated, filename="historian/domains/politics/first_contact_history.py")
    write_if_changed(path, original, updated, log)


def patch_snapshot_cache(log: list[str]) -> None:
    path = ROOT / "historian" / "snapshot_cache.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    if "import time\n" not in updated:
        updated = replace_once(updated, "import shutil\n", "import shutil\nimport time\n", label="snapshot cache time import")

    updated = replace_once(
        updated,
        "    cache_dir: Path,\n) -> tuple[\n",
        "    cache_dir: Path,\n    timings: dict[str, float] | None = None,\n) -> tuple[\n",
        label="snapshot cache timings parameter",
    )

    helper = '''    def mark_timing(name: str, started: float) -> None:\n        if timings is not None:\n            timings[name] = time.perf_counter() - started\n\n'''
    if helper not in updated:
        anchor = "    archive_path = Path(\n        archive_path\n    )\n"
        if anchor not in updated:
            raise RuntimeError("Could not locate snapshot cache function body anchor.")
        updated = updated.replace(anchor, helper + anchor, 1)

    pairs = [
        (
            '''    if profile is not None:\n        _, gamestate = read_save_texts(\n            archive_path\n        )\n''',
            '''    if profile is not None:\n        phase_started = time.perf_counter()\n        _, gamestate = read_save_texts(\n            archive_path\n        )\n        mark_timing("zip_read", phase_started)\n''',
            "extend ZIP timing",
        ),
        (
            '''        if ship_snapshot is None:\n            ship_snapshot = extract_ship_fleet_snapshot(\n''',
            '''        if ship_snapshot is None:\n            phase_started = time.perf_counter()\n            ship_snapshot = extract_ship_fleet_snapshot(\n''',
            "extend ship timing start",
        ),
        (
            '''                profile=profile,\n                gamestate=gamestate,\n            )\n\n        if (\n            leader_snapshot is None\n''',
            '''                profile=profile,\n                gamestate=gamestate,\n            )\n            mark_timing("ships", phase_started)\n\n        if (\n            leader_snapshot is None\n''',
            "extend ship timing end",
        ),
        (
            '''        ):\n            leader_snapshot = extract_leader_snapshot(\n''',
            '''        ):\n            phase_started = time.perf_counter()\n            leader_snapshot = extract_leader_snapshot(\n''',
            "extend people timing start",
        ),
        (
            '''                snapshot_id=snapshot_id,\n                ship_snapshot=ship_snapshot,\n            )\n\n        if world_snapshot is None:\n''',
            '''                snapshot_id=snapshot_id,\n                ship_snapshot=ship_snapshot,\n            )\n            mark_timing("people", phase_started)\n\n        if world_snapshot is None:\n''',
            "extend people timing end",
        ),
        (
            '''        if world_snapshot is None:\n            world_snapshot = extract_world_snapshot(\n''',
            '''        if world_snapshot is None:\n            phase_started = time.perf_counter()\n            world_snapshot = extract_world_snapshot(\n''',
            "extend world timing start",
        ),
        (
            '''                    for leader_id, leader in leader_snapshot.leaders.items()\n                },\n            )\n\n        if science_snapshot is None:\n''',
            '''                    for leader_id, leader in leader_snapshot.leaders.items()\n                },\n            )\n            mark_timing("worlds", phase_started)\n\n        if science_snapshot is None:\n''',
            "extend world timing end",
        ),
        (
            '''        if science_snapshot is None:\n            science_snapshot = extract_science_snapshot(\n''',
            '''        if science_snapshot is None:\n            phase_started = time.perf_counter()\n            science_snapshot = extract_science_snapshot(\n''',
            "extend science timing start",
        ),
        (
            '''                ship_snapshot=ship_snapshot,\n                leader_snapshot=leader_snapshot,\n            )\n\n        if combat_snapshot is None:\n''',
            '''                ship_snapshot=ship_snapshot,\n                leader_snapshot=leader_snapshot,\n            )\n            mark_timing("science", phase_started)\n\n        if combat_snapshot is None:\n''',
            "extend science timing end",
        ),
        (
            '''        if combat_snapshot is None:\n            combat_snapshot = extract_combat_snapshot(\n''',
            '''        if combat_snapshot is None:\n            phase_started = time.perf_counter()\n            combat_snapshot = extract_combat_snapshot(\n''',
            "extend combat timing start",
        ),
        (
            '''                snapshot_id=snapshot_id,\n                ship_snapshot=ship_snapshot,\n            )\n\n        if technology_snapshot is None:\n''',
            '''                snapshot_id=snapshot_id,\n                ship_snapshot=ship_snapshot,\n            )\n            mark_timing("combat", phase_started)\n\n        if technology_snapshot is None:\n''',
            "extend combat timing end",
        ),
        (
            '''        if technology_snapshot is None:\n            technology_snapshot = extract_technology_snapshot(\n''',
            '''        if technology_snapshot is None:\n            phase_started = time.perf_counter()\n            technology_snapshot = extract_technology_snapshot(\n''',
            "extend technology timing start",
        ),
        (
            '''                source_save=source_save,\n                snapshot_id=snapshot_id,\n            )\n\n        if politics_snapshot is None:\n''',
            '''                source_save=source_save,\n                snapshot_id=snapshot_id,\n            )\n            mark_timing("technology", phase_started)\n\n        if politics_snapshot is None:\n''',
            "extend technology timing end",
        ),
        (
            '''        if politics_snapshot is None:\n            try:\n                politics_snapshot = extract_politics_snapshot(\n''',
            '''        if politics_snapshot is None:\n            phase_started = time.perf_counter()\n            try:\n                politics_snapshot = extract_politics_snapshot(\n''',
            "extend politics timing start",
        ),
        (
            '''                politics_snapshot = None\n\n        _write(\n''',
            '''                politics_snapshot = None\n            finally:\n                mark_timing("politics", phase_started)\n\n        phase_started = time.perf_counter()\n        _write(\n''',
            "extend politics/cache-write timing",
        ),
        (
            '''            technology_snapshot=technology_snapshot,\n            politics_snapshot=politics_snapshot,\n        )\n\n        return (\n''',
            '''            technology_snapshot=technology_snapshot,\n            politics_snapshot=politics_snapshot,\n        )\n        mark_timing("cache_write", phase_started)\n\n        return (\n''',
            "extend cache-write timing end",
        ),
        (
            '''    # Full miss. One ZIP read is shared by all current parsers.\n    meta, gamestate = read_save_texts(\n        archive_path\n    )\n\n    profile = empire_profile_from_text(\n        meta,\n        gamestate,\n    )\n\n    ship_snapshot = extract_ship_fleet_snapshot(\n''',
            '''    # Full miss. One ZIP read is shared by all current parsers.\n    phase_started = time.perf_counter()\n    meta, gamestate = read_save_texts(\n        archive_path\n    )\n    mark_timing("zip_read", phase_started)\n\n    phase_started = time.perf_counter()\n    profile = empire_profile_from_text(\n        meta,\n        gamestate,\n    )\n    mark_timing("profile", phase_started)\n\n    phase_started = time.perf_counter()\n    ship_snapshot = extract_ship_fleet_snapshot(\n''',
            "miss ZIP/profile/ship timing start",
        ),
        (
            '''        profile=profile,\n        gamestate=gamestate,\n    )\n\n    leader_snapshot = extract_leader_snapshot(\n''',
            '''        profile=profile,\n        gamestate=gamestate,\n    )\n    mark_timing("ships", phase_started)\n\n    phase_started = time.perf_counter()\n    leader_snapshot = extract_leader_snapshot(\n''',
            "miss ship timing end",
        ),
        (
            '''        snapshot_id=snapshot_id,\n        ship_snapshot=ship_snapshot,\n    )\n\n    world_snapshot = extract_world_snapshot(\n''',
            '''        snapshot_id=snapshot_id,\n        ship_snapshot=ship_snapshot,\n    )\n    mark_timing("people", phase_started)\n\n    phase_started = time.perf_counter()\n    world_snapshot = extract_world_snapshot(\n''',
            "miss people timing",
        ),
        (
            '''            for leader_id, leader in leader_snapshot.leaders.items()\n        },\n    )\n\n    science_snapshot = extract_science_snapshot(\n''',
            '''            for leader_id, leader in leader_snapshot.leaders.items()\n        },\n    )\n    mark_timing("worlds", phase_started)\n\n    phase_started = time.perf_counter()\n    science_snapshot = extract_science_snapshot(\n''',
            "miss world timing",
        ),
        (
            '''        ship_snapshot=ship_snapshot,\n        leader_snapshot=leader_snapshot,\n    )\n\n    combat_snapshot = extract_combat_snapshot(\n''',
            '''        ship_snapshot=ship_snapshot,\n        leader_snapshot=leader_snapshot,\n    )\n    mark_timing("science", phase_started)\n\n    phase_started = time.perf_counter()\n    combat_snapshot = extract_combat_snapshot(\n''',
            "miss science timing",
        ),
        (
            '''        snapshot_id=snapshot_id,\n        ship_snapshot=ship_snapshot,\n    )\n\n    technology_snapshot = extract_technology_snapshot(\n''',
            '''        snapshot_id=snapshot_id,\n        ship_snapshot=ship_snapshot,\n    )\n    mark_timing("combat", phase_started)\n\n    phase_started = time.perf_counter()\n    technology_snapshot = extract_technology_snapshot(\n''',
            "miss combat timing",
        ),
        (
            '''        source_save=source_save,\n        snapshot_id=snapshot_id,\n    )\n\n    try:\n        politics_snapshot = extract_politics_snapshot(\n''',
            '''        source_save=source_save,\n        snapshot_id=snapshot_id,\n    )\n    mark_timing("technology", phase_started)\n\n    phase_started = time.perf_counter()\n    try:\n        politics_snapshot = extract_politics_snapshot(\n''',
            "miss technology/politics timing",
        ),
        (
            '''    except Exception:\n        politics_snapshot = None\n\n    _write(\n''',
            '''    except Exception:\n        politics_snapshot = None\n    finally:\n        mark_timing("politics", phase_started)\n\n    phase_started = time.perf_counter()\n    _write(\n''',
            "miss politics/cache-write timing",
        ),
        (
            '''        technology_snapshot=technology_snapshot,\n        politics_snapshot=politics_snapshot,\n    )\n\n    return (\n''',
            '''        technology_snapshot=technology_snapshot,\n        politics_snapshot=politics_snapshot,\n    )\n    mark_timing("cache_write", phase_started)\n\n    return (\n''',
            "miss cache-write timing end",
        ),
    ]

    for old, new, label in pairs:
        updated = replace_once(updated, old, new, label=label)

    ast.parse(updated, filename="historian/snapshot_cache.py")
    write_if_changed(path, original, updated, log)


def patch_history_processor(log: list[str]) -> None:
    path = ROOT / "historian" / "history_processor.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    helper = '''def _format_parse_timings(timings: dict[str, float], total: float) -> str:\n    order = (\n        ("zip_read", "ZIP"),\n        ("profile", "Profile"),\n        ("ships", "Ships"),\n        ("people", "People"),\n        ("worlds", "Worlds"),\n        ("science", "Science"),\n        ("combat", "Combat"),\n        ("technology", "Tech"),\n        ("politics", "Politics"),\n        ("cache_write", "CacheWrite"),\n    )\n    parts = [\n        f"{label} {format_duration(timings[key])}"\n        for key, label in order\n        if key in timings\n    ]\n    parts.append(f"Total {format_duration(total)}")\n    return " | ".join(parts)\n\n\n'''
    if helper not in updated:
        anchor = "def _humanise(raw: str | None) -> str | None:\n"
        if anchor not in updated:
            raise RuntimeError("Could not locate history_processor.py _humanise anchor.")
        updated = updated.replace(anchor, helper + anchor, 1)

    old = '''            (\n                profile,\n                current_state,\n                current_leaders,\n                current_worlds,\n                current_science,\n                current_combat,\n                current_technology,\n                current_politics,\n                current_cache_status,\n            ) = load_or_parse_snapshot(\n                archive_path=Path(snapshot["archive_path"]),\n                source_save=source_save,\n                source_sha256=snapshot["sha256"],\n                snapshot_id=snapshot_id,\n                cache_dir=cache_dir,\n            )\n'''
    new = '''            parse_timings: dict[str, float] = {}\n            parse_started = time.perf_counter()\n            (\n                profile,\n                current_state,\n                current_leaders,\n                current_worlds,\n                current_science,\n                current_combat,\n                current_technology,\n                current_politics,\n                current_cache_status,\n            ) = load_or_parse_snapshot(\n                archive_path=Path(snapshot["archive_path"]),\n                source_save=source_save,\n                source_sha256=snapshot["sha256"],\n                snapshot_id=snapshot_id,\n                cache_dir=cache_dir,\n                timings=parse_timings,\n            )\n            parse_elapsed = time.perf_counter() - parse_started\n            if current_cache_status != "hit":\n                activity(\n                    "         PERF "\n                    f"{current_cache_status.upper()} | "\n                    f"{_format_parse_timings(parse_timings, parse_elapsed)}"\n                )\n'''
    updated = replace_once(updated, old, new, label="History parser timing telemetry")
    ast.parse(updated, filename="historian/history_processor.py")
    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    old = '''                result = process_unprocessed(DB, campaign_id)\n\n                if result["processed"]:\n                    _refresh_first_contact_history_for_journal(\n                        campaign_id,\n                        "LIVE HISTORY",\n                    )\n                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")\n                    journal_started = time.perf_counter()\n                    render_journal(DB, campaign_id)\n                    activity(\n                        "LIVE HISTORY - Historical_Journal.html refresh complete - "\n                        f"{format_duration(time.perf_counter() - journal_started)}"\n                    )\n\n                if result["errors"]:\n                    LIVE_HISTORY_ENABLED = False\n                    LIVE_HISTORY_STATUS = (\n                        "OFF - processing error: " + result["errors"][0]\n                    )\n                    error("LIVE HISTORY STOPPED - " + result["errors"][0])\n                else:\n                    LIVE_HISTORY_STATUS = (\n                        "ON - waiting for the next archived save"\n                        if LIVE_HISTORY_ENABLED\n                        else "OFF"\n                    )\n'''
    new = '''                result = process_unprocessed(DB, campaign_id)\n\n                if result["errors"]:\n                    LIVE_HISTORY_ENABLED = False\n                    LIVE_HISTORY_STATUS = (\n                        "OFF - processing error: " + result["errors"][0]\n                    )\n                    error("LIVE HISTORY STOPPED - " + result["errors"][0])\n                    continue\n\n                remaining = int(result.get("remaining", 0) or 0)\n                if remaining > 0:\n                    LIVE_HISTORY_STATUS = (\n                        f"ON - catching up: {remaining} archived save(s) still waiting"\n                    )\n                    activity(\n                        "LIVE HISTORY - history queue still has "\n                        f"{remaining} save(s); expensive First Contact / journal "\n                        "refresh deferred until the queue is caught up."\n                    )\n                    continue\n\n                # A save can arrive after process_unprocessed() counted zero.\n                # Give archive/history priority and never begin the expensive\n                # presentation refresh while new history work is already waiting.\n                if DB.unprocessed_count(campaign_id) > 0:\n                    LIVE_HISTORY_STATUS = "ON - new save arrived; continuing history catch-up"\n                    activity(\n                        "LIVE HISTORY - a new archived save arrived before presentation "\n                        "refresh; continuing history catch-up first."\n                    )\n                    continue\n\n                if result["processed"]:\n                    _refresh_first_contact_history_for_journal(\n                        campaign_id,\n                        "LIVE HISTORY",\n                    )\n                    activity("LIVE HISTORY - refreshing Historical_Journal.html...")\n                    journal_started = time.perf_counter()\n                    render_journal(DB, campaign_id)\n                    activity(\n                        "LIVE HISTORY - Historical_Journal.html refresh complete - "\n                        f"{format_duration(time.perf_counter() - journal_started)}"\n                    )\n\n                LIVE_HISTORY_STATUS = (\n                    "ON - waiting for the next archived save"\n                    if LIVE_HISTORY_ENABLED\n                    else "OFF"\n                )\n'''
    updated = replace_once(original, old, new, label="Live History queue-first scheduling")
    ast.parse(updated, filename="app.py")
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = """## v0.0.53\n- Makes Live History queue-first: when newly archived saves remain unprocessed, Historian immediately continues History processing instead of rebuilding First Contact history and the Historical Journal between batches.\n- Adds a second queue check before expensive presentation refreshes so a newly arrived save gets priority over journal work.\n- Restricts structured First Contact rebuilding to snapshots that have completed normal History processing, preventing the First Contact stage from parsing waiting saves ahead of the History queue.\n- Adds per-domain timing telemetry for cache misses/extensions (`ZIP`, `Profile`, `Ships`, `People`, `Worlds`, `Science`, `Combat`, `Tech`, `Politics`, `CacheWrite`) so the next optimisation pass can target the real parser bottleneck.\n- Adds processed/ignored snapshot counts to the First Contact diagnostic.\n- No SQLite schema change, parsed-cache version bump, archived-save rewrite or full cache rebuild.\n\n"""
    if "## v0.0.53\n" in original:
        updated = original
    else:
        anchor = "# Changelog\n\n"
        if anchor not in original:
            raise RuntimeError("Could not locate CHANGELOG heading.")
        updated = original.replace(anchor, anchor + section, 1)
    write_if_changed(path, original, updated, log)


def patch_manifest(log: list[str]) -> None:
    path = ROOT / "historian_manifest.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["version"] = "0.0.53"
    data["architecture"] = "modular-foundation-32-live-history-queue-first-performance"
    data["live_history_performance"] = {
        "status": "queue-first-with-parser-timing-telemetry",
        "history_queue_priority": True,
        "presentation_refresh_deferred_while_unprocessed": True,
        "first_contact_processed_snapshots_only": True,
        "per_domain_cache_miss_timing": True,
        "database_schema_change": False,
        "cache_version_change": False,
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def validate_readme(log: list[str]) -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = [
        "v0.0.53 — Live History Queue-First Performance",
        "Queue-first Live History",
        "Processed-only First Contact",
        "Parser timing telemetry",
        "No SQLite schema change",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("README.md is not the v0.0.53 performance README: " + ", ".join(missing))
    log.append("Validated README.md v0.0.53 performance documentation.")


def validate_source(log: list[str]) -> None:
    checks = {
        "app.py": ["history queue still has", "refresh deferred until the queue is caught up"],
        "historian/db.py": ["def processed_snapshots"],
        "historian/history_processor.py": ["PERF ", "_format_parse_timings"],
        "historian/snapshot_cache.py": ["timings: dict[str, float] | None", 'mark_timing("ships"'],
        "historian/domains/politics/first_contact_history.py": ["processed_snapshots", "Unprocessed snapshots ignored"],
    }
    for name, tokens in checks.items():
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=name)
        missing = [token for token in tokens if token not in text]
        if missing:
            raise RuntimeError(f"{name} missing expected v0.0.53 token(s): {', '.join(missing)}")
    log.append("Validated v0.0.53 queue-first/performance source changes.")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.53 Live History performance migration started.",
        "No archived Stellaris saves, campaign history rows, processed flags or parsed-cache component versions are intentionally changed.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.53 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.53 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        validate_readme(log)
        patch_version(log)
        patch_database(log)
        patch_first_contact_history(log)
        patch_snapshot_cache(log)
        patch_history_processor(log)
        patch_app(log)
        patch_changelog(log)
        patch_manifest(log)
        validate_source(log)
    except (SyntaxError, RuntimeError, OSError, json.JSONDecodeError, re.error) as exc:
        log.append(f"ABORTED: v0.0.53 source migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.53 migration failed.")
        print("Original source backups are retained under backups\\v0.0.53 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.53 Live History performance migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Live History now gives waiting History saves priority over First Contact/journal presentation refreshes.",
        "Structured First Contact history now ignores unprocessed snapshots until normal History processing completes.",
        "Cache misses/extensions now emit per-domain timing telemetry for targeted follow-up optimisation.",
        "No SQLite schema change, parsed-cache version bump, archive rewrite or full cache rebuild is required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.53 Live History performance migration complete.")
    print("Live History now catches up the save queue before expensive First Contact / journal refreshes.")
    print("First Contact no longer parses snapshots that are still waiting for normal History processing.")
    print("Cache misses/extensions now print per-domain PERF timings for bottleneck analysis.")
    print("No full cache rebuild is required.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
