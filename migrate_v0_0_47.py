from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import py_compile
import shutil

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_47_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.47.log"
BACKUP_ROOT = ROOT / "backups" / "v0.0.47"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "README.md",
    "README_v0.0.47.md",
    "historian/__init__.py",
    "historian/db.py",
    "historian/history_processor.py",
    "historian/historical_events.py",
    "historian/journal.py",
    "historian/presentation_history.py",
    "historian/snapshot_cache.py",
    "historian/domains/politics/__init__.py",
    "historian/domains/politics/probe.py",
    "historian/domains/politics/models.py",
    "historian/domains/politics/parser.py",
    "historian/domains/politics/cache.py",
    "historian/domains/politics/history.py",
    "historian/domains/politics/journal.py",
    "static/campaign.html",
    "static/campaign.js",
    "static/style.css",
    "historian_manifest.json",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.47.md",
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
    log.append(f"Backed up {relative} -> backups/v0.0.47/{relative}")


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
        raise RuntimeError(f"Could not locate v0.0.46 anchor for {label}.")
    log.append(f"Installed: {label}")
    return text.replace(old, new, 1)


def replace_all(text: str, old: str, new: str, label: str, log: list[str], minimum: int = 1) -> str:
    if old not in text:
        if new in text:
            log.append(f"Already installed: {label}")
            return text
        raise RuntimeError(f"Could not locate v0.0.46 anchor for {label}.")
    count = text.count(old)
    if count < minimum:
        raise RuntimeError(f"Expected at least {minimum} anchors for {label}; found {count}.")
    log.append(f"Installed: {label} ({count} occurrence(s))")
    return text.replace(old, new)


def patch_version(log: list[str]) -> None:
    path = ROOT / "historian" / "__init__.py"
    original = path.read_text(encoding="utf-8")
    updated = original.replace('__version__ = "0.0.46"', '__version__ = "0.0.47"', 1)
    if updated == original and '__version__ = "0.0.47"' not in original:
        raise RuntimeError("Could not update historian version from v0.0.46.")
    write_if_changed(path, original, updated, log)


def patch_db(log: list[str]) -> None:
    path = ROOT / "historian" / "db.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    schema_anchor = '''CREATE INDEX IF NOT EXISTS idx_snapshots_campaign
ON snapshots(campaign_id, id);
'''
    schema_replacement = '''CREATE TABLE IF NOT EXISTS politics_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    game_date TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_utc TEXT NOT NULL,
    UNIQUE(campaign_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS politics_history_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    game_date TEXT NOT NULL,
    category TEXT NOT NULL,
    event_type TEXT NOT NULL,
    subject_id INTEGER,
    subject_name TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    visible INTEGER NOT NULL DEFAULT 0,
    confidence TEXT NOT NULL DEFAULT 'high',
    date_kind TEXT NOT NULL DEFAULT 'first_observed',
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_utc TEXT NOT NULL,
    UNIQUE(campaign_id, event_key)
);

CREATE INDEX IF NOT EXISTS idx_politics_states_campaign
ON politics_states(campaign_id, snapshot_id);

CREATE INDEX IF NOT EXISTS idx_politics_events_campaign
ON politics_history_events(campaign_id, game_date, id);

CREATE INDEX IF NOT EXISTS idx_snapshots_campaign
ON snapshots(campaign_id, id);
'''
    updated = replace_once(updated, schema_anchor, schema_replacement, "Politics/Diplomacy database schema", log)

    method_anchor = '''    def replace_review_data(
        self,
        campaign_id: int,
'''
    method_replacement = '''    def apply_politics_delta(
        self,
        campaign_id: int,
        data: dict,
    ) -> None:
        now = utc_now()
        state = data.get("state") or {}
        snapshot_id = state.get("snapshot_id")
        game_date = state.get("game_date")

        with self.connect() as con:
            if snapshot_id is not None and game_date:
                con.execute(
                    """
                    INSERT INTO politics_states(
                        campaign_id, snapshot_id, game_date, state_json, created_utc
                    )
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(campaign_id, snapshot_id) DO UPDATE SET
                        game_date=excluded.game_date,
                        state_json=excluded.state_json,
                        created_utc=excluded.created_utc
                    """,
                    (
                        campaign_id,
                        int(snapshot_id),
                        str(game_date),
                        json.dumps(state, ensure_ascii=True, separators=(",", ":")),
                        now,
                    ),
                )

            for event in data.get("events", []):
                con.execute(
                    """
                    INSERT OR IGNORE INTO politics_history_events(
                        campaign_id, event_key, snapshot_id, game_date, category,
                        event_type, subject_id, subject_name, title, body, visible,
                        confidence, date_kind, attributes_json, created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event.get("category", "politics"),
                        event["event_type"],
                        event.get("subject_id"),
                        event.get("subject_name"),
                        event["title"],
                        event["body"],
                        event.get("visible", 0),
                        event.get("confidence", "high"),
                        event.get("date_kind", "first_observed"),
                        json.dumps(event.get("attributes") or {}, ensure_ascii=True, separators=(",", ":")),
                        now,
                    ),
                )

    def replace_politics_data(
        self,
        campaign_id: int,
        *,
        states: list[dict],
        events: list[dict],
    ) -> None:
        now = utc_now()
        with self.connect() as con:
            con.execute("DELETE FROM politics_history_events WHERE campaign_id=?", (campaign_id,))
            con.execute("DELETE FROM politics_states WHERE campaign_id=?", (campaign_id,))

            for row in states:
                state = row.get("state") or {}
                con.execute(
                    """
                    INSERT INTO politics_states(
                        campaign_id, snapshot_id, game_date, state_json, created_utc
                    )
                    VALUES(?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        int(row["snapshot_id"]),
                        str(row["game_date"]),
                        json.dumps(state, ensure_ascii=True, separators=(",", ":")),
                        now,
                    ),
                )

            for event in events:
                con.execute(
                    """
                    INSERT INTO politics_history_events(
                        campaign_id, event_key, snapshot_id, game_date, category,
                        event_type, subject_id, subject_name, title, body, visible,
                        confidence, date_kind, attributes_json, created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event.get("category", "politics"),
                        event["event_type"],
                        event.get("subject_id"),
                        event.get("subject_name"),
                        event["title"],
                        event["body"],
                        event.get("visible", 0),
                        event.get("confidence", "high"),
                        event.get("date_kind", "first_observed"),
                        json.dumps(event.get("attributes") or {}, ensure_ascii=True, separators=(",", ":")),
                        now,
                    ),
                )

    def politics_states(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT * FROM politics_states
                WHERE campaign_id=?
                ORDER BY snapshot_id ASC
                """,
                (campaign_id,),
            ).fetchall()

    def politics_events(self, campaign_id: int, *, visible_only: bool = False):
        query = """
            SELECT * FROM politics_history_events
            WHERE campaign_id=?
        """
        params: list[object] = [campaign_id]
        if visible_only:
            query += " AND visible=1"
        query += " ORDER BY game_date ASC, id ASC"
        with self.connect() as con:
            return con.execute(query, params).fetchall()

    def replace_review_data(
        self,
        campaign_id: int,
'''
    updated = replace_once(updated, method_anchor, method_replacement, "Politics/Diplomacy database methods", log)
    write_if_changed(path, original, updated, log)


def patch_snapshot_cache(log: list[str]) -> None:
    path = ROOT / "historian" / "snapshot_cache.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_anchor = '''from .domains.technology.cache import (
    snapshot_from_dict as technology_snapshot_from_dict,
    snapshot_to_dict as technology_snapshot_to_dict,
)
'''
    import_replacement = import_anchor + '''from .domains.politics import (
    CACHE_COMPONENT_NAME as POLITICS_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as POLITICS_COMPONENT_VERSION,
    PoliticsSnapshot,
    extract_politics_snapshot,
)
from .domains.politics.cache import (
    snapshot_from_dict as politics_snapshot_from_dict,
    snapshot_to_dict as politics_snapshot_to_dict,
)
'''
    updated = replace_once(updated, import_anchor, import_replacement, "Politics cache imports", log)

    updated = replace_once(
        updated,
        '''    combat_snapshot: CombatSnapshot,
    technology_snapshot: TechnologySnapshot,
) -> None:
''',
        '''    combat_snapshot: CombatSnapshot,
    technology_snapshot: TechnologySnapshot,
    politics_snapshot: PoliticsSnapshot,
) -> None:
''',
        "Politics cache write signature",
        log,
    )

    updated = replace_once(
        updated,
        '''            TECHNOLOGY_COMPONENT_NAME: {
                "version": TECHNOLOGY_COMPONENT_VERSION,
                "data": technology_snapshot_to_dict(
                    technology_snapshot
                ),
            },
        },
''',
        '''            TECHNOLOGY_COMPONENT_NAME: {
                "version": TECHNOLOGY_COMPONENT_VERSION,
                "data": technology_snapshot_to_dict(
                    technology_snapshot
                ),
            },
            POLITICS_COMPONENT_NAME: {
                "version": POLITICS_COMPONENT_VERSION,
                "data": politics_snapshot_to_dict(
                    politics_snapshot
                ),
            },
        },
''',
        "Politics cache component payload",
        log,
    )

    updated = replace_once(
        updated,
        '''    CombatSnapshot,
    TechnologySnapshot,
    str,
]:
''',
        '''    CombatSnapshot,
    TechnologySnapshot,
    PoliticsSnapshot,
    str,
]:
''',
        "Politics cache return annotation",
        log,
    )

    updated = replace_once(
        updated,
        "Return profile, ship/fleet state, leader state, world state, science evidence, combat evidence, technology evidence and cache status.",
        "Return profile, ship/fleet state, leader state, world state, science evidence, combat evidence, technology evidence, politics/diplomacy evidence and cache status.",
        "Politics cache docstring",
        log,
    )

    updated = replace_once(
        updated,
        '''    technology_data = _component_data(
        payload,
        TECHNOLOGY_COMPONENT_NAME,
        TECHNOLOGY_COMPONENT_VERSION,
    )

    profile = None
''',
        '''    technology_data = _component_data(
        payload,
        TECHNOLOGY_COMPONENT_NAME,
        TECHNOLOGY_COMPONENT_VERSION,
    )

    politics_data = _component_data(
        payload,
        POLITICS_COMPONENT_NAME,
        POLITICS_COMPONENT_VERSION,
    )

    profile = None
''',
        "Politics cache component read",
        log,
    )

    updated = replace_once(
        updated,
        '''    combat_snapshot = None
    technology_snapshot = None

    try:
''',
        '''    combat_snapshot = None
    technology_snapshot = None
    politics_snapshot = None

    try:
''',
        "Politics cache local state",
        log,
    )

    updated = replace_once(
        updated,
        '''        if technology_data is not None:
            technology_snapshot = technology_snapshot_from_dict(
                technology_data,
                snapshot_id=snapshot_id,
            )

    except (
''',
        '''        if technology_data is not None:
            technology_snapshot = technology_snapshot_from_dict(
                technology_data,
                snapshot_id=snapshot_id,
            )

        if politics_data is not None:
            politics_snapshot = politics_snapshot_from_dict(
                politics_data,
                snapshot_id=snapshot_id,
            )

    except (
''',
        "Politics cache deserialize",
        log,
    )

    updated = replace_once(
        updated,
        '''        combat_snapshot = None
        technology_snapshot = None

    if (
''',
        '''        combat_snapshot = None
        technology_snapshot = None
        politics_snapshot = None

    if (
''',
        "Politics cache reset on invalid component",
        log,
    )

    updated = replace_once(
        updated,
        '''        and combat_snapshot is not None
        and technology_snapshot is not None
    ):
''',
        '''        and combat_snapshot is not None
        and technology_snapshot is not None
        and politics_snapshot is not None
    ):
''',
        "Politics cache hit condition",
        log,
    )

    updated = replace_all(
        updated,
        '''            combat_snapshot,
            technology_snapshot,
            "hit",
''',
        '''            combat_snapshot,
            technology_snapshot,
            politics_snapshot,
            "hit",
''',
        "Politics cache hit return",
        log,
    )

    extend_anchor = '''        if technology_snapshot is None:
            technology_snapshot = extract_technology_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
            )

        _write(
'''
    extend_replacement = '''        if technology_snapshot is None:
            technology_snapshot = extract_technology_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
            )

        if politics_snapshot is None:
            politics_snapshot = extract_politics_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
                leader_snapshot=leader_snapshot,
            )

        _write(
'''
    updated = replace_once(updated, extend_anchor, extend_replacement, "Politics cache extension parser", log)

    updated = replace_once(
        updated,
        '''            combat_snapshot=combat_snapshot,
            technology_snapshot=technology_snapshot,
        )
''',
        '''            combat_snapshot=combat_snapshot,
            technology_snapshot=technology_snapshot,
            politics_snapshot=politics_snapshot,
        )
''',
        "Politics cache extend write call",
        log,
    )
    updated = replace_once(
        updated,
        '''        combat_snapshot=combat_snapshot,
        technology_snapshot=technology_snapshot,
    )
''',
        '''        combat_snapshot=combat_snapshot,
        technology_snapshot=technology_snapshot,
        politics_snapshot=politics_snapshot,
    )
''',
        "Politics cache full-miss write call",
        log,
    )

    updated = replace_once(
        updated,
        '''            combat_snapshot,
            technology_snapshot,
            "extend",
''',
        '''            combat_snapshot,
            technology_snapshot,
            politics_snapshot,
            "extend",
''',
        "Politics cache extend return",
        log,
    )

    full_anchor = '''    technology_snapshot = extract_technology_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
    )

    _write(
'''
    full_replacement = '''    technology_snapshot = extract_technology_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
    )

    politics_snapshot = extract_politics_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
        leader_snapshot=leader_snapshot,
    )

    _write(
'''
    updated = replace_once(updated, full_anchor, full_replacement, "Politics full-miss parser", log)

    updated = replace_once(
        updated,
        '''        combat_snapshot,
        technology_snapshot,
        "miss",
''',
        '''        combat_snapshot,
        technology_snapshot,
        politics_snapshot,
        "miss",
''',
        "Politics cache miss return",
        log,
    )

    write_if_changed(path, original, updated, log)


def patch_history_processor(log: list[str]) -> None:
    path = ROOT / "historian" / "history_processor.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    import_anchor = '''from .domains.technology import (
    technology_evidence_summary,
    write_technology_diagnostic,
)
'''
    import_replacement = import_anchor + '''from .domains.politics import (
    derive_full_politics_history,
    politics_transition_data,
    write_politics_database_diagnostic,
    write_politics_history_diagnostic,
)
'''
    updated = replace_once(updated, import_anchor, import_replacement, "Politics history imports", log)

    updated = replace_all(
        updated,
        '''                current_technology,
                current_cache_status,
''',
        '''                current_technology,
                current_politics,
                current_cache_status,
''',
        "Incremental current politics tuple",
        log,
    )
    updated = replace_all(
        updated,
        '''                current_combat,
                current_technology,
            )
''',
        '''                current_combat,
                current_technology,
                current_politics,
            )
''',
        "Incremental parsed-run politics tuple",
        log,
    )
    updated = replace_once(
        updated,
        '''            previous_combat = None
            previous_technology = None

            if previous_row is not None:
''',
        '''            previous_combat = None
            previous_technology = None
            previous_politics = None

            if previous_row is not None:
''',
        "Incremental previous politics state",
        log,
    )
    updated = replace_once(
        updated,
        '''                        previous_combat,
                        previous_technology,
                    ) = parsed_in_run[
''',
        '''                        previous_combat,
                        previous_technology,
                        previous_politics,
                    ) = parsed_in_run[
''',
        "Incremental previous cached politics tuple",
        log,
    )
    updated = replace_once(
        updated,
        '''                        previous_combat,
                        previous_technology,
                        previous_cache_status,
                    ) = load_or_parse_snapshot(
''',
        '''                        previous_combat,
                        previous_technology,
                        previous_politics,
                        previous_cache_status,
                    ) = load_or_parse_snapshot(
''',
        "Incremental previous parsed politics tuple",
        log,
    )
    updated = replace_once(
        updated,
        '''                        previous_combat,
                        previous_technology,
                    )

                    _record_cache_status(
''',
        '''                        previous_combat,
                        previous_technology,
                        previous_politics,
                    )

                    _record_cache_status(
''',
        "Incremental previous run-cache politics tuple",
        log,
    )
    updated = replace_once(
        updated,
        '''            world_delta = world_transition_data(
                previous_worlds,
                current_worlds,
                baseline=(snapshot["kind"] == "start"),
            )

            activity(
''',
        '''            world_delta = world_transition_data(
                previous_worlds,
                current_worlds,
                baseline=(snapshot["kind"] == "start"),
            )

            politics_delta = politics_transition_data(
                previous_politics,
                current_politics,
                baseline=(snapshot["kind"] == "start"),
            )

            activity(
''',
        "Incremental politics transition",
        log,
    )
    updated = replace_all(
        updated,
        '''                f"Techs {len(current_technology.technologies)} | "
                f"Queued builds {len(current_state.build_orders)}"
''',
        '''                f"Techs {len(current_technology.technologies)} | "
                f"Relations {len(current_politics.relations)} | "
                f"Traditions {len(current_politics.traditions)} | "
                f"Queued builds {len(current_state.build_orders)}"
''',
        "Incremental politics activity counts",
        log,
    )
    updated = replace_once(
        updated,
        '''            db.apply_world_delta(
                campaign_id,
                world_delta,
            )

            db.mark_processed(
''',
        '''            db.apply_world_delta(
                campaign_id,
                world_delta,
            )

            db.apply_politics_delta(
                campaign_id,
                politics_delta,
            )

            db.mark_processed(
''',
        "Incremental politics database apply",
        log,
    )
    updated = replace_once(
        updated,
        '''    remaining = db.unprocessed_count(
        campaign_id
    )
''',
        '''    try:
        politics_live_debug = write_politics_database_diagnostic(
            db,
            campaign_id,
        )
        activity(
            "Politics / diplomacy structured history updated - "
            f"diagnostics\\{politics_live_debug.name}"
        )
    except Exception as exc:
        error(f"POLITICS / DIPLOMACY HISTORY DIAGNOSTIC - {exc}")

    remaining = db.unprocessed_count(
        campaign_id
    )
''',
        "Incremental politics diagnostic",
        log,
    )

    # Review and Construct share the same append/derive flow.
    updated = replace_all(
        updated,
        '''    technology_snapshots = []
    errors: list[str] = []
''',
        '''    technology_snapshots = []
    politics_snapshots = []
    errors: list[str] = []
''',
        "Review/Construct politics snapshot lists",
        log,
        minimum=2,
    )
    updated = replace_all(
        updated,
        '''                technology_snapshot,
                cache_status,
            ) = load_or_parse_snapshot(
''',
        '''                technology_snapshot,
                politics_snapshot,
                cache_status,
            ) = load_or_parse_snapshot(
''',
        "Review/Construct politics tuples",
        log,
        minimum=2,
    )
    updated = replace_all(
        updated,
        '''            technology_snapshots.append(
                technology_snapshot
            )

            activity(
''',
        '''            technology_snapshots.append(
                technology_snapshot
            )
            politics_snapshots.append(
                politics_snapshot
            )

            activity(
''',
        "Review/Construct politics append",
        log,
        minimum=2,
    )
    updated = replace_all(
        updated,
        '''                f"Techs {len(technology_snapshot.technologies)} | "
                f"Queued builds {len(parsed_snapshot.build_orders)}"
''',
        '''                f"Techs {len(technology_snapshot.technologies)} | "
                f"Relations {len(politics_snapshot.relations)} | "
                f"Traditions {len(politics_snapshot.traditions)} | "
                f"Queued builds {len(parsed_snapshot.build_orders)}"
''',
        "Review/Construct politics activity counts",
        log,
        minimum=2,
    )
    updated = replace_all(
        updated,
        '''    technology_summary = technology_evidence_summary(
        technology_snapshots
    )
    correlated_engagements = derive_correlated_engagements(
''',
        '''    technology_summary = technology_evidence_summary(
        technology_snapshots
    )
    politics_derived = derive_full_politics_history(
        politics_snapshots
    )
    correlated_engagements = derive_correlated_engagements(
''',
        "Review/Construct politics derivation",
        log,
        minimum=2,
    )
    updated = replace_all(
        updated,
        '''        combat_episodes=combat_episodes,
        technology_snapshots=technology_snapshots,
    )
''',
        '''        combat_episodes=combat_episodes,
        technology_snapshots=technology_snapshots,
        politics_events=politics_derived["events"],
    )
''',
        "Review/Construct historical politics integration",
        log,
        minimum=2,
    )

    # Insert a separate atomic politics replacement immediately after the existing domain rebuild.
    db_call = '''    db.replace_review_data(
        campaign_id,
'''
    first = updated.find(db_call)
    if first < 0:
        raise RuntimeError("Could not locate Review replace_review_data call.")
    # Add the call after each complete replace_review_data(...) block using the stable following diagnostic anchor.
    updated = replace_all(
        updated,
        '''    diagnostic_dir = _diagnostics_dir(Path(campaign["archive_dir"]))
''',
        '''    db.replace_politics_data(
        campaign_id,
        states=politics_derived["states"],
        events=politics_derived["events"],
    )

    diagnostic_dir = _diagnostics_dir(Path(campaign["archive_dir"]))
''',
        "Review/Construct politics database rebuild",
        log,
        minimum=2,
    )

    updated = replace_all(
        updated,
        '''    technology_debug = write_technology_diagnostic(
        diagnostic_dir,
        technology_snapshots,
    )
    activity(f"Technology evidence diagnostic updated - diagnostics\\\\{technology_debug.name}")
''',
        '''    technology_debug = write_technology_diagnostic(
        diagnostic_dir,
        technology_snapshots,
    )
    activity(f"Technology evidence diagnostic updated - diagnostics\\\\{technology_debug.name}")
    politics_history_debug = write_politics_history_diagnostic(
        diagnostic_dir,
        politics_derived,
    )
    activity(
        "Politics / diplomacy structured history updated - "
        f"diagnostics\\\\{politics_history_debug.name}"
    )
''',
        "Review/Construct politics diagnostic",
        log,
        minimum=2,
    )

    write_if_changed(path, original, updated, log)


def patch_historical_events(log: list[str]) -> None:
    path = ROOT / "historian" / "historical_events.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        '''from pathlib import Path
import re
''',
        '''from pathlib import Path
import json
import re
''',
        "Historical politics JSON import",
        log,
    )
    updated = replace_once(
        updated,
        '''    combat_episodes: list[CombatEpisode] | None = None,
    technology_snapshots: list,
) -> list[HistoricalEvent]:
''',
        '''    combat_episodes: list[CombatEpisode] | None = None,
    technology_snapshots: list,
    politics_events: list[dict] | None = None,
) -> list[HistoricalEvent]:
''',
        "Historical politics argument",
        log,
    )

    insert_anchor = '''    if technology_snapshots:
        technology = derive_technology_history(technology_snapshots)
'''
    politics_block = '''    for row in (politics_events or []):
        if not int(row.get("visible", 0)):
            continue
        event_type = str(row.get("event_type") or "politics_evidence")
        importance = {
            "government_state_changed": 94,
            "council_agenda_state_changed": 78,
            "tradition_first_observed": 68,
            "diplomatic_contact_first_observed": 72,
            "communications_state_changed": 80,
            "communications_block_changed": 80,
            "hostility_state_changed": 88,
            "hostility_block_changed": 88,
            "neutral_state_changed": 74,
            "neutral_block_changed": 74,
            "relation_value_changed": 38,
        }.get(event_type, 55)
        raw_attributes = row.get("attributes")
        if raw_attributes is None and row.get("attributes_json"):
            try:
                raw_attributes = json.loads(row.get("attributes_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                raw_attributes = {}
        if not isinstance(raw_attributes, dict):
            raw_attributes = {}
        events.append(HistoricalEvent(
            game_date=str(row["game_date"]),
            category=str(row.get("category") or "politics"),
            event_type=event_type,
            title=str(row["title"]),
            summary=_neutralize_evidence_text(row["body"]),
            confidence=str(row.get("confidence", "high")),
            date_kind=str(row.get("date_kind", "first_observed")),
            source="politics_diplomacy_history",
            importance=importance,
            attributes=_pairs(**raw_attributes),
        ))

'''
    updated = replace_once(updated, insert_anchor, politics_block + insert_anchor, "Historical politics event synthesis", log)
    write_if_changed(path, original, updated, log)


def patch_presentation_history(log: list[str]) -> None:
    path = ROOT / "historian" / "presentation_history.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        '''    world_history = {
        "events": [dict(row) for row in db.world_history_events(campaign_id, visible_only=False)]
    }

    events = synthesize_historical_events(
''',
        '''    world_history = {
        "events": [dict(row) for row in db.world_history_events(campaign_id, visible_only=False)]
    }
    politics_events = [
        dict(row) for row in db.politics_events(campaign_id, visible_only=False)
    ]

    events = synthesize_historical_events(
''',
        "Presentation politics database read",
        log,
    )
    updated = replace_once(
        updated,
        '''        combat_episodes=combat_episodes,
        technology_snapshots=technology_snapshots,
    )
''',
        '''        combat_episodes=combat_episodes,
        technology_snapshots=technology_snapshots,
        politics_events=politics_events,
    )
''',
        "Presentation politics event synthesis",
        log,
    )
    write_if_changed(path, original, updated, log)


def patch_journal(log: list[str]) -> None:
    path = ROOT / "historian" / "journal.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = replace_once(
        updated,
        '''from .domains.science.journal import render_science_section
''',
        '''from .domains.science.journal import render_science_section
from .domains.politics.journal import render_politics_section
''',
        "Politics journal import",
        log,
    )

    updated = replace_once(
        updated,
        '''    science_html = render_science_section(
        db,
        campaign_id,
    )
''',
        '''    politics_html = render_politics_section(
        db,
        campaign_id,
    )

    science_html = render_science_section(
        db,
        campaign_id,
    )
''',
        "Politics journal rendering",
        log,
    )

    updated = replace_once(
        updated,
        '''    if people_html.strip():
        nav_links.append(
            '<a href="#people-history">People &amp; Politics</a>'
        )

    if science_html.strip():
''',
        '''    if people_html.strip():
        nav_links.append(
            '<a href="#people-history">People &amp; Leaders</a>'
        )

    if politics_html.strip():
        nav_links.append(
            '<a href="#politics-diplomacy">Politics &amp; Diplomacy</a>'
        )

    if science_html.strip():
''',
        "Politics journal navigation",
        log,
    )

    updated = replace_once(
        updated,
        '''  {
    f'<div id="people-history" class="journal-anchor">{people_html}</div>'
    if people_html.strip()
    else ''
  }

  {
    f'<div id="science-exploration" class="journal-anchor">{science_html}</div>'
''',
        '''  {
    f'<div id="people-history" class="journal-anchor">{people_html}</div>'
    if people_html.strip()
    else ''
  }

  {
    f'<div id="politics-diplomacy" class="journal-anchor">{politics_html}</div>'
    if politics_html.strip()
    else ''
  }

  {
    f'<div id="science-exploration" class="journal-anchor">{science_html}</div>'
''',
        "Politics journal section",
        log,
    )

    write_if_changed(path, original, updated, log)


def patch_app(log: list[str]) -> None:
    path = ROOT / "app.py"
    original = path.read_text(encoding="utf-8")
    updated = original

    global_anchor = '''ACTIVE_CAMPAIGN_ID: int | None = None
server: uvicorn.Server | None = None
'''
    global_replacement = '''ACTIVE_CAMPAIGN_ID: int | None = None
server: uvicorn.Server | None = None
LIVE_HISTORY_ENABLED = False
LIVE_HISTORY_BUSY = False
LIVE_HISTORY_STATUS = "OFF"
LIVE_HISTORY_STOP = threading.Event()
LIVE_HISTORY_THREAD: threading.Thread | None = None
'''
    updated = replace_once(updated, global_anchor, global_replacement, "Live History globals", log)

    helper_anchor = '''def safe_name(value: str, max_len: int = 60) -> str:
'''
    helper_replacement = '''def _live_history_loop() -> None:
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
                    render_journal(DB, campaign_id)

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


def safe_name(value: str, max_len: int = 60) -> str:
'''
    updated = replace_once(updated, helper_anchor, helper_replacement, "Live History worker", log)

    updated = replace_once(
        updated,
        '''    WATCHER.start()

    try:
        yield
    finally:
        WATCHER.stop()
''',
        '''    WATCHER.start()
    _start_live_history_worker()

    try:
        yield
    finally:
        _stop_live_history_worker()
        WATCHER.stop()
''',
        "Live History lifespan",
        log,
    )

    updated = replace_once(
        updated,
        '''async def api_start_campaign(request: Request):
    global ACTIVE_CAMPAIGN_ID
''',
        '''async def api_start_campaign(request: Request):
    global ACTIVE_CAMPAIGN_ID, LIVE_HISTORY_ENABLED, LIVE_HISTORY_STATUS

    if LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Live History is finishing an automatic update. Wait for it to finish before selecting another campaign.",
        )
''',
        "Live History campaign selection globals",
        log,
    )
    updated = replace_once(
        updated,
        '''    ACTIVE_CAMPAIGN_ID = int(campaign["id"])

    WATCHER.select_campaign(
''',
        '''    ACTIVE_CAMPAIGN_ID = int(campaign["id"])
    LIVE_HISTORY_ENABLED = False
    LIVE_HISTORY_STATUS = "OFF"

    WATCHER.select_campaign(
''',
        "Live History resets on campaign selection",
        log,
    )

    updated = replace_all(
        updated,
        '''            "monitoring": False,
        }
''',
        '''            "monitoring": False,
            "live_history_enabled": False,
            "live_history_busy": False,
            "live_history_status": "OFF",
        }
''',
        "Live History empty campaign API state",
        log,
        minimum=2,
    )
    updated = replace_once(
        updated,
        '''        "monitoring": True,
        "watcher_status": WATCHER.status,
''',
        '''        "monitoring": True,
        "watcher_status": WATCHER.status,
        "live_history_enabled": LIVE_HISTORY_ENABLED,
        "live_history_busy": LIVE_HISTORY_BUSY,
        "live_history_status": LIVE_HISTORY_STATUS,
''',
        "Live History active campaign API state",
        log,
    )

    updated = replace_once(
        updated,
        '''def api_update_history():
    if ACTIVE_CAMPAIGN_ID is None:
''',
        '''def api_update_history():
    if LIVE_HISTORY_ENABLED or LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Live History is ON or finishing an automatic update. Wait for it to become fully OFF before running Update History manually.",
        )

    if ACTIVE_CAMPAIGN_ID is None:
''',
        "Manual Update guard while Live History is on",
        log,
    )

    api_anchor = '''@app.post("/api/review-campaign")
def api_review_campaign():
'''
    api_replacement = '''@app.post("/api/live-history")
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
'''
    updated = replace_once(updated, api_anchor, api_replacement, "Live History toggle API", log)

    updated = replace_once(
        updated,
        '''def api_review_campaign():
    if ACTIVE_CAMPAIGN_ID is None:
''',
        '''def api_review_campaign():
    if LIVE_HISTORY_ENABLED or LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Wait for Live History to be fully OFF before running Review Campaign.",
        )

    if ACTIVE_CAMPAIGN_ID is None:
''',
        "Review guard while Live History is on",
        log,
    )
    updated = replace_once(
        updated,
        '''def api_construct_campaign():
    if ACTIVE_CAMPAIGN_ID is None:
''',
        '''def api_construct_campaign():
    if LIVE_HISTORY_ENABLED or LIVE_HISTORY_BUSY:
        raise HTTPException(
            409,
            "Wait for Live History to be fully OFF before running Construct Campaign.",
        )

    if ACTIVE_CAMPAIGN_ID is None:
''',
        "Construct guard while Live History is on",
        log,
    )

    write_if_changed(path, original, updated, log)


def patch_campaign_ui(log: list[str]) -> None:
    html_path = ROOT / "static" / "campaign.html"
    original = html_path.read_text(encoding="utf-8")
    updated = original
    updated = replace_once(
        updated,
        '''  <button id="update-history" type="button">
    Update History
  </button>

  <button id="review-campaign" type="button">
''',
        '''  <button id="update-history" type="button">
    Update History
  </button>

  <button id="live-history" class="live-history-button" type="button" aria-pressed="false">
    Live History: OFF
  </button>

  <button id="review-campaign" type="button">
''',
        "Live History button",
        log,
    )
    updated = updated.replace('/static/style.css?v=005', '/static/style.css?v=006', 1)
    updated = updated.replace('/static/campaign.js?v=009', '/static/campaign.js?v=010', 1)
    write_if_changed(html_path, original, updated, log)

    js_path = ROOT / "static" / "campaign.js"
    original = js_path.read_text(encoding="utf-8")
    updated = original
    updated = replace_once(
        updated,
        '''const updateButton = document.getElementById("update-history");
const reviewButton = document.getElementById("review-campaign");
''',
        '''const updateButton = document.getElementById("update-history");
const liveHistoryButton = document.getElementById("live-history");
const reviewButton = document.getElementById("review-campaign");
''',
        "Live History JS control",
        log,
    )
    updated = replace_once(
        updated,
        '''  const unprocessed = Number(data.unprocessed_count ?? 0);
  const archived = Number(data.archive_count ?? 0);

  updateButton.disabled =
    actionInProgress || unprocessed === 0;

  reviewButton.disabled =
    actionInProgress || unprocessed > 0 || archived === 0;

  constructButton.disabled =
    actionInProgress || archived === 0;
''',
        '''  const unprocessed = Number(data.unprocessed_count ?? 0);
  const archived = Number(data.archive_count ?? 0);
  const liveEnabled = Boolean(data.live_history_enabled);
  const liveBusy = Boolean(data.live_history_busy);
  const liveBlocking = liveEnabled || liveBusy;

  updateButton.disabled =
    actionInProgress || liveBlocking || unprocessed === 0;

  liveHistoryButton.disabled = actionInProgress;

  reviewButton.disabled =
    actionInProgress || liveBlocking || unprocessed > 0 || archived === 0;

  constructButton.disabled =
    actionInProgress || liveBlocking || archived === 0;
''',
        "Live History action availability",
        log,
    )
    updated = replace_once(
        updated,
        '''  updateButton.title = unprocessed === 0
    ? "No archived saves are waiting for history."
    : `Process ${unprocessed} archived save(s) waiting for history.`;

  reviewButton.title = unprocessed > 0
''',
        '''  updateButton.title = liveBlocking
    ? "Live History is ON or finishing an automatic history update."
    : (unprocessed === 0
      ? "No archived saves are waiting for history."
      : `Process ${unprocessed} archived save(s) waiting for history.`);

  liveHistoryButton.textContent = liveEnabled
    ? "Live History: ON"
    : (liveBusy ? "Live History: STOPPING" : "Live History: OFF");
  liveHistoryButton.classList.toggle("live-on", liveEnabled);
  liveHistoryButton.setAttribute("aria-pressed", liveEnabled ? "true" : "false");
  liveHistoryButton.title = data.live_history_status || (liveEnabled ? "Live History is ON." : "Live History is OFF.");

  reviewButton.title = liveBlocking
    ? "Wait for Live History to be fully OFF before running Review Campaign."
    : (unprocessed > 0
''',
        "Live History button state",
        log,
    )
    updated = replace_once(
        updated,
        '''    ? `Run Update History first. ${unprocessed} archived save(s) are waiting for history.`
    : "Re-read the full processed campaign using the current Historian logic.";

  constructButton.title = archived > 0
    ? "Discard generated analysis/cache and rebuild the campaign from every archived save."
    : "No archived saves are available to construct.";
''',
        '''      ? `Run Update History first. ${unprocessed} archived save(s) are waiting for history.`
      : "Re-read the full processed campaign using the current Historian logic.");

  constructButton.title = liveBlocking
    ? "Wait for Live History to be fully OFF before constructing the campaign."
    : (archived > 0
      ? "Discard generated analysis/cache and rebuild the campaign from every archived save."
      : "No archived saves are available to construct.");
''',
        "Live History review/construct titles",
        log,
    )

    event_anchor = '''updateButton.addEventListener("click", async () => {
'''
    event_replacement = '''liveHistoryButton.addEventListener("click", async () => {
  const currentlyEnabled = Boolean(latestCampaignState?.live_history_enabled);
  actionInProgress = true;
  applyActionAvailability();
  status.textContent = `${currentlyEnabled ? "Turning off" : "Turning on"} Live History...`;

  try{
    const response = await fetch(
      "/api/live-history",
      {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({enabled:!currentlyEnabled})
      }
    );
    const data = await response.json();
    if(!response.ok){
      throw new Error(data.detail || "Could not change Live History state.");
    }
    status.textContent = data.enabled
      ? "Live History is ON. New archived saves will be processed automatically."
      : (data.busy
        ? "Live History is stopping after the current automatic history update finishes."
        : "Live History is OFF. Update History is manual again.");
    await loadActive();
  }catch(error){
    status.textContent = `Live History toggle failed: ${error.message}`;
  }finally{
    actionInProgress = false;
    applyActionAvailability();
  }
});

updateButton.addEventListener("click", async () => {
'''
    updated = replace_once(updated, event_anchor, event_replacement, "Live History JS toggle event", log)
    write_if_changed(js_path, original, updated, log)

    css_path = ROOT / "static" / "style.css"
    original = css_path.read_text(encoding="utf-8")
    updated = original
    css_anchor = '''button:hover{background:#294c66}
button:disabled{opacity:.45;cursor:not-allowed}

.close-button{
'''
    css_replacement = '''button:hover{background:#294c66}
button:disabled{opacity:.45;cursor:not-allowed}

.live-history-button{
  border-color:#5b6672;
  background:#252d36;
}

.live-history-button.live-on{
  border-color:#4c8a65;
  background:#214b32;
  color:#e7fff0;
}

.live-history-button.live-on:hover{
  background:#2a6241;
}

.close-button{
'''
    updated = replace_once(updated, css_anchor, css_replacement, "Live History CSS", log)
    write_if_changed(css_path, original, updated, log)


def patch_readme(log: list[str]) -> None:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    updated = original
    updated = updated.replace("## Current version\n\nv0.0.46", "## Current version\n\nv0.0.47", 1)
    if "Live History ON/OFF" not in updated:
        anchor = "- Watches Stellaris Ironman saves automatically\n"
        if anchor not in updated:
            raise RuntimeError("Could not locate README feature-list anchor.")
        updated = updated.replace(
            anchor,
            anchor + "- Live History ON/OFF can automatically process newly archived saves\n",
            1,
        )
    if "structured Politics/Diplomacy" not in updated:
        anchor = "- Tracks politics and diplomatic raw evidence through an evidence-only deep probe\n"
        if anchor in updated:
            updated = updated.replace(
                anchor,
                "- Tracks structured Politics/Diplomacy evidence for government, ruler, agendas, traditions and diplomatic relation-state changes\n",
                1,
            )
    updated = updated.replace(
        "The current codebase includes migration and historical tracking work through version 0.0.46.",
        "The current codebase includes migration and historical tracking work through version 0.0.47.",
        1,
    )
    write_if_changed(path, original, updated, log)


def patch_manifest(log: list[str]) -> None:
    path = ROOT / "historian_manifest.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["version"] = "0.0.47"
    data["architecture"] = "modular-foundation-22-live-history-structured-politics-diplomacy"
    politics = data.setdefault("domains", {}).setdefault("politics", {})
    politics["status"] = "modular-structured-evidence-first"
    politics["cache_component"] = "politics_diplomacy"
    politics["cache_version"] = 1
    layer = data.setdefault("historical_event_layer", {})
    layer["status"] = "v0.0.47-shared-presentation-source-with-structured-politics-diplomacy"
    layer["purpose"] = (
        "normalized source/confidence/date-kind events with structured attributes; Timeline and Scribes consume "
        "the same synthesized presentation source. v0.0.47 adds conservative Politics/Diplomacy events."
    )
    diagnostics = data.setdefault("diagnostics", {}).setdefault("files", [])
    if "Politics_History_Debug.txt" not in diagnostics:
        diagnostics.append("Politics_History_Debug.txt")
    data["live_history"] = {
        "status": "active-opt-in",
        "default": "off",
        "behaviour": "when enabled, process newly archived saves through the normal incremental history pipeline and refresh Historical_Journal.html",
        "safety": "Review Campaign and Construct Campaign require Live History to be off",
    }
    data["politics_diplomacy_history"] = {
        "status": "structured-evidence-first",
        "cache_component": "politics_diplomacy",
        "cache_version": 1,
        "database_tables": ["politics_states", "politics_history_events"],
        "published_evidence": [
            "government profile changes",
            "council agenda field transitions",
            "tradition first observations",
            "first archived appearance of player relation records",
            "communications/hostility/neutral-state raw field changes",
        ],
        "retained_not_normally_published": [
            "ruler identity mirror of People-domain evidence",
            "relation-value changes",
        ],
        "rule": "No treaty, election, faction, alliance, rivalry, succession cause or diplomatic motive is inferred from unfamiliar raw fields.",
    }
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    write_if_changed(path, original, updated, log)


def patch_changelog(log: list[str]) -> None:
    path = ROOT / "docs" / "CHANGELOG.md"
    original = path.read_text(encoding="utf-8")
    section = '''## v0.0.47
- Added a **Live History ON/OFF** toggle beside Update History. It is OFF by default and, when enabled, processes newly archived saves through the existing incremental history pipeline and refreshes `Historical_Journal.html` automatically.
- Added `politics_diplomacy` snapshot-cache component v1 so Politics/Diplomacy evidence shares the same raw-save read as the other structured domains.
- Added structured Politics/Diplomacy state and event persistence in `politics_states` and `politics_history_events`.
- Added conservative government-state changes, ruler identity observations, council-agenda field transitions, tradition first-observations, first archived appearance of diplomatic relation records, communications/hostility/neutral-state changes and relation-value changes.
- Relation-value transitions are retained but hidden from the normal public event stream to avoid chronology noise.
- Ruler identity is retained in Politics/Diplomacy, while the People domain remains authoritative for public ruler career/succession milestones.
- Added `diagnostics/Politics_History_Debug.txt`, a dedicated Politics & Diplomacy section in the Historical Journal, and integrated visible Politics/Diplomacy evidence into the shared Historical Event Layer used by Timeline and Scribes.
- Review Campaign and Construct Campaign require Live History to be OFF to avoid concurrent history rebuilds.
- Existing cache containers extend in place when the new Politics/Diplomacy component is first needed; no destructive cache reset is required.

'''
    if section not in original:
        anchor = (
            "# Stellaris Historian Changelog\n\n"
            if "# Stellaris Historian Changelog\n\n" in original
            else "# Changelog\n\n"
        )
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
        f"[{stamp()}] Stellaris Historian v0.0.47 Live History / structured Politics-Diplomacy migration started.",
        "Archived Stellaris saves are not modified or deleted by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.47 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.47 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for relative in (
            "historian/domains/politics/models.py",
            "historian/domains/politics/parser.py",
            "historian/domains/politics/cache.py",
            "historian/domains/politics/history.py",
            "historian/domains/politics/journal.py",
            "historian/domains/politics/__init__.py",
        ):
            py_compile.compile(str(ROOT / relative), doraise=True)

        patch_version(log)
        patch_db(log)
        patch_snapshot_cache(log)
        patch_history_processor(log)
        patch_historical_events(log)
        patch_presentation_history(log)
        patch_journal(log)
        patch_app(log)
        patch_campaign_ui(log)
        patch_readme(log)
        patch_manifest(log)
        patch_changelog(log)

        for relative in (
            "app.py",
            "historian/db.py",
            "historian/snapshot_cache.py",
            "historian/history_processor.py",
            "historian/historical_events.py",
            "historian/presentation_history.py",
            "historian/journal.py",
        ):
            py_compile.compile(str(ROOT / relative), doraise=True)

    except (py_compile.PyCompileError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        log.append(f"ABORTED: v0.0.47 migration/validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.47 validation failed.")
        print("Original source backups are retained under backups\\v0.0.47 where changes were attempted.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.47 Live History / structured Politics-Diplomacy migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Politics/Diplomacy cache component v1 is active.",
        "Existing cache containers are extended on demand; no destructive cache reset is performed.",
        "Live History is OFF by default after each app start/campaign selection.",
        "Turn Live History ON beside Update History to process new archived saves automatically.",
        "Review Campaign and Construct Campaign require Live History OFF.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.47 Live History / structured Politics-Diplomacy migration complete.")
    print("Live History is OFF by default; enable it beside Update History when ready to play.")
    print("Existing snapshot caches will extend in place as Politics/Diplomacy evidence is needed.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
