from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3


SCHEMA = """
PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    source_folder TEXT NOT NULL,
    source_save TEXT NOT NULL,
    empire_name TEXT NOT NULL,
    game_version TEXT,
    archive_dir TEXT NOT NULL,
    first_game_date TEXT,
    latest_game_date TEXT,
    created_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    sequence_no INTEGER,
    kind TEXT NOT NULL CHECK(kind IN ('start','periodic')),
    game_date TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    archive_filename TEXT NOT NULL,
    archive_path TEXT NOT NULL,
    source_mtime REAL,
    source_size INTEGER,
    captured_utc TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    processed_utc TEXT,
    UNIQUE(campaign_id, sha256),
    UNIQUE(campaign_id, archive_filename)
);

CREATE TABLE IF NOT EXISTS history_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    game_date TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    government_type TEXT,
    authority TEXT,
    origin TEXT,
    ethics TEXT,
    civics TEXT,
    created_utc TEXT NOT NULL,
    UNIQUE(snapshot_id)
);

CREATE TABLE IF NOT EXISTS ship_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    ship_id INTEGER NOT NULL,
    first_seen_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    construction_date TEXT,
    name TEXT NOT NULL,
    ship_type TEXT NOT NULL,
    opening_name TEXT,
    opening_ship_type TEXT,
    opening_construction_date TEXT,
    opening_fleet_id INTEGER,
    opening_fleet_name TEXT,
    opening_commander_id INTEGER,
    opening_commander_name TEXT,
    latest_fleet_id INTEGER,
    latest_fleet_name TEXT,
    latest_commander_id INTEGER,
    latest_commander_name TEXT,
    status TEXT NOT NULL,
    baseline_present INTEGER NOT NULL DEFAULT 0,
    first_snapshot_id INTEGER,
    last_snapshot_id INTEGER,
    UNIQUE(campaign_id, ship_id)
);

CREATE TABLE IF NOT EXISTS fleet_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    fleet_id INTEGER NOT NULL,
    first_seen_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    name TEXT NOT NULL,
    ship_class TEXT NOT NULL,
    opening_name TEXT,
    opening_ship_class TEXT,
    opening_ship_count INTEGER,
    opening_home_base TEXT,
    opening_commander_id INTEGER,
    opening_commander_name TEXT,
    latest_ship_count INTEGER NOT NULL DEFAULT 0,
    latest_home_base TEXT,
    latest_commander_id INTEGER,
    latest_commander_name TEXT,
    status TEXT NOT NULL,
    baseline_present INTEGER NOT NULL DEFAULT 0,
    first_snapshot_id INTEGER,
    last_snapshot_id INTEGER,
    UNIQUE(campaign_id, fleet_id)
);

CREATE TABLE IF NOT EXISTS ship_build_provenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    ship_id INTEGER NOT NULL,
    build_location TEXT NOT NULL,
    build_location_starbase_id INTEGER,
    evidence_kind TEXT NOT NULL,
    confidence TEXT NOT NULL,
    source_snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE SET NULL,
    source_game_date TEXT,
    created_utc TEXT NOT NULL,
    UNIQUE(campaign_id, ship_id)
);

CREATE TABLE IF NOT EXISTS ship_fleet_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    game_date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    ship_id INTEGER,
    fleet_id INTEGER,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    visible INTEGER NOT NULL DEFAULT 1,
    confidence TEXT NOT NULL DEFAULT 'high',
    date_kind TEXT NOT NULL DEFAULT 'between_snapshots',
    created_utc TEXT NOT NULL,
    UNIQUE(campaign_id, event_key)
);

CREATE TABLE IF NOT EXISTS leader_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    leader_id INTEGER NOT NULL,
    first_seen_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    name TEXT NOT NULL,
    leader_class TEXT NOT NULL,
    latest_level INTEGER,
    latest_experience REAL,
    recruitment_date TEXT,
    gender TEXT,
    traits TEXT NOT NULL DEFAULT '[]',
    trait_names TEXT NOT NULL DEFAULT '[]',
    latest_assignment_type TEXT,
    latest_assignment_id INTEGER,
    latest_assignment TEXT,
    latest_council_role TEXT,
    latest_is_ruler INTEGER NOT NULL DEFAULT 0,
    ever_ruler INTEGER NOT NULL DEFAULT 0,
    latest_is_heir INTEGER NOT NULL DEFAULT 0,
    ever_heir INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    baseline_present INTEGER NOT NULL DEFAULT 0,
    first_snapshot_id INTEGER,
    last_snapshot_id INTEGER,
    UNIQUE(campaign_id, leader_id)
);

CREATE TABLE IF NOT EXISTS leader_deep_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    leader_id INTEGER NOT NULL,
    species_id INTEGER,
    species_name TEXT,
    portrait TEXT,
    creator_country_id INTEGER,
    tier_key TEXT,
    tier_name TEXT,
    recorded_date TEXT,
    date_added TEXT,
    raw_age INTEGER,
    ethic_key TEXT,
    ethic_name TEXT,
    job_key TEXT,
    job_name TEXT,
    background_planet_id INTEGER,
    background_planet_name TEXT,
    custom_description_key TEXT,
    custom_description_name TEXT,
    bonus_skill_level INTEGER,
    raw_record_keys TEXT NOT NULL DEFAULT '[]',
    raw_flag_values TEXT NOT NULL DEFAULT '[]',
    raw_variable_values TEXT NOT NULL DEFAULT '[]',
    event_target_aliases TEXT NOT NULL DEFAULT '[]',
    death_date TEXT,
    death_reason_key TEXT,
    death_reason_value TEXT,
    death_evidence_kind TEXT,
    death_first_observed_date TEXT,
    updated_utc TEXT NOT NULL,
    UNIQUE(campaign_id, leader_id)
);

CREATE TABLE IF NOT EXISTS leader_career_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    game_date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    leader_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    visible INTEGER NOT NULL DEFAULT 0,
    confidence TEXT NOT NULL DEFAULT 'high',
    date_kind TEXT NOT NULL DEFAULT 'between_snapshots',
    created_utc TEXT NOT NULL,
    UNIQUE(campaign_id, event_key)
);

CREATE TABLE IF NOT EXISTS world_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    planet_id INTEGER NOT NULL,
    latest_colony_id INTEGER,
    first_seen_date TEXT NOT NULL,
    last_seen_date TEXT NOT NULL,
    colonize_date TEXT,
    name TEXT NOT NULL,
    system_id INTEGER,
    system_name TEXT,
    planet_class_key TEXT,
    planet_class_name TEXT,
    planet_size INTEGER,
    original_owner_id INTEGER,
    latest_owner_id INTEGER,
    latest_controller_id INTEGER,
    latest_governor_id INTEGER,
    latest_governor_name TEXT,
    latest_population INTEGER,
    latest_employable_pops INTEGER,
    latest_designation_key TEXT,
    latest_designation_name TEXT,
    latest_ascension_tier INTEGER,
    latest_district_count INTEGER NOT NULL DEFAULT 0,
    latest_building_count INTEGER NOT NULL DEFAULT 0,
    latest_is_capital INTEGER NOT NULL DEFAULT 0,
    ever_capital INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    baseline_present INTEGER NOT NULL DEFAULT 0,
    first_snapshot_id INTEGER,
    last_snapshot_id INTEGER,
    UNIQUE(campaign_id, planet_id)
);

CREATE TABLE IF NOT EXISTS world_history_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    snapshot_id INTEGER REFERENCES snapshots(id) ON DELETE CASCADE,
    game_date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    planet_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    visible INTEGER NOT NULL DEFAULT 0,
    confidence TEXT NOT NULL DEFAULT 'high',
    date_kind TEXT NOT NULL DEFAULT 'between_snapshots',
    created_utc TEXT NOT NULL,
    UNIQUE(campaign_id, event_key)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_campaign
ON snapshots(campaign_id, id);

CREATE INDEX IF NOT EXISTS idx_snapshots_processed
ON snapshots(campaign_id, processed);

CREATE INDEX IF NOT EXISTS idx_history_campaign
ON history_entries(campaign_id, id);

CREATE INDEX IF NOT EXISTS idx_ship_registry_campaign
ON ship_registry(campaign_id, ship_id);

CREATE INDEX IF NOT EXISTS idx_fleet_registry_campaign
ON fleet_registry(campaign_id, fleet_id);

CREATE INDEX IF NOT EXISTS idx_ship_build_provenance_campaign
ON ship_build_provenance(campaign_id, ship_id);

CREATE INDEX IF NOT EXISTS idx_ship_fleet_events_campaign
ON ship_fleet_events(campaign_id, game_date, id);

CREATE INDEX IF NOT EXISTS idx_leader_registry_campaign
ON leader_registry(campaign_id, leader_id);

CREATE INDEX IF NOT EXISTS idx_leader_deep_evidence_campaign
ON leader_deep_evidence(campaign_id, leader_id);

CREATE INDEX IF NOT EXISTS idx_leader_career_events_campaign
ON leader_career_events(campaign_id, game_date, id);

CREATE INDEX IF NOT EXISTS idx_world_registry_campaign
ON world_registry(campaign_id, planet_id);

CREATE INDEX IF NOT EXISTS idx_world_history_events_campaign
ON world_history_events(campaign_id, game_date, id);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def _initialise(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA)

    def get_campaign_by_source(self, source_key: str):
        with self.connect() as con:
            return con.execute(
                "SELECT * FROM campaigns WHERE source_key=?",
                (source_key,),
            ).fetchone()

    def create_campaign(
        self,
        source_key: str,
        source_folder: str,
        source_save: str,
        empire_name: str,
        game_version: str | None,
        archive_dir: str,
        game_date: str,
    ) -> int:
        now = utc_now()

        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO campaigns(
                    source_key,
                    source_folder,
                    source_save,
                    empire_name,
                    game_version,
                    archive_dir,
                    first_game_date,
                    latest_game_date,
                    created_utc,
                    updated_utc
                )
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    source_key,
                    source_folder,
                    source_save,
                    empire_name,
                    game_version,
                    archive_dir,
                    game_date,
                    game_date,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def update_campaign(
        self,
        campaign_id: int,
        empire_name: str,
        game_version: str | None,
        game_date: str,
    ) -> None:
        with self.connect() as con:
            con.execute(
                """
                UPDATE campaigns
                SET empire_name=?,
                    game_version=?,
                    latest_game_date=?,
                    updated_utc=?
                WHERE id=?
                """,
                (
                    empire_name,
                    game_version,
                    game_date,
                    utc_now(),
                    campaign_id,
                ),
            )

    def campaign(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                "SELECT * FROM campaigns WHERE id=?",
                (campaign_id,),
            ).fetchone()

    def snapshot_hash_exists(self, campaign_id: int, sha256: str) -> bool:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT 1
                FROM snapshots
                WHERE campaign_id=? AND sha256=?
                """,
                (campaign_id, sha256),
            ).fetchone()

            return row is not None

    def snapshot_count(self, campaign_id: int) -> int:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT COUNT(*) AS count
                FROM snapshots
                WHERE campaign_id=?
                """,
                (campaign_id,),
            ).fetchone()

            return int(row["count"])

    def next_sequence(self, campaign_id: int) -> int:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT MAX(sequence_no) AS n
                FROM snapshots
                WHERE campaign_id=? AND kind='periodic'
                """,
                (campaign_id,),
            ).fetchone()

            current = row["n"] if row and row["n"] is not None else 0
            return int(current) + 1

    def insert_snapshot(
        self,
        campaign_id: int,
        *,
        sequence_no: int | None,
        kind: str,
        game_date: str,
        sha256: str,
        archive_filename: str,
        archive_path: str,
        source_mtime: float,
        source_size: int,
    ) -> int:
        with self.connect() as con:
            cur = con.execute(
                """
                INSERT INTO snapshots(
                    campaign_id,
                    sequence_no,
                    kind,
                    game_date,
                    sha256,
                    archive_filename,
                    archive_path,
                    source_mtime,
                    source_size,
                    captured_utc,
                    processed
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,0)
                """,
                (
                    campaign_id,
                    sequence_no,
                    kind,
                    game_date,
                    sha256,
                    archive_filename,
                    archive_path,
                    source_mtime,
                    source_size,
                    utc_now(),
                ),
            )
            return int(cur.lastrowid)

    def latest_snapshots(self, campaign_id: int, limit: int = 10):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM snapshots
                WHERE campaign_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (campaign_id, limit),
            ).fetchall()

    def all_snapshots(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM snapshots
                WHERE campaign_id=?
                ORDER BY id ASC
                """,
                (campaign_id,),
            ).fetchall()

    def previous_snapshot(self, campaign_id: int, snapshot_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM snapshots
                WHERE campaign_id=? AND id<?
                ORDER BY id DESC
                LIMIT 1
                """,
                (campaign_id, snapshot_id),
            ).fetchone()

    def unprocessed_snapshots(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM snapshots
                WHERE campaign_id=? AND processed=0
                ORDER BY id ASC
                """,
                (campaign_id,),
            ).fetchall()

    def unprocessed_count(self, campaign_id: int) -> int:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT COUNT(*) AS count
                FROM snapshots
                WHERE campaign_id=? AND processed=0
                """,
                (campaign_id,),
            ).fetchone()

            return int(row["count"])

    def mark_processed(self, snapshot_id: int) -> None:
        with self.connect() as con:
            con.execute(
                """
                UPDATE snapshots
                SET processed=1,
                    processed_utc=?
                WHERE id=?
                """,
                (
                    utc_now(),
                    snapshot_id,
                ),
            )

    def mark_all_processed(
        self,
        campaign_id: int,
    ) -> int:
        """Mark every archived snapshot in a campaign as processed."""
        now = utc_now()

        with self.connect() as con:
            cur = con.execute(
                """
                UPDATE snapshots
                SET processed=1,
                    processed_utc=?
                WHERE campaign_id=?
                  AND processed=0
                """,
                (
                    now,
                    campaign_id,
                ),
            )

            return int(
                cur.rowcount
                if cur.rowcount is not None
                else 0
            )

    def add_history_entry(
        self,
        *,
        campaign_id: int,
        snapshot_id: int,
        game_date: str,
        entry_type: str,
        title: str,
        body: str,
        government_type: str | None,
        authority: str | None,
        origin: str | None,
        ethics: str | None,
        civics: str | None,
    ) -> None:
        with self.connect() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO history_entries(
                    campaign_id,
                    snapshot_id,
                    game_date,
                    entry_type,
                    title,
                    body,
                    government_type,
                    authority,
                    origin,
                    ethics,
                    civics,
                    created_utc
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    campaign_id,
                    snapshot_id,
                    game_date,
                    entry_type,
                    title,
                    body,
                    government_type,
                    authority,
                    origin,
                    ethics,
                    civics,
                    utc_now(),
                ),
            )

    def replace_history_entries(
        self,
        campaign_id: int,
        entries: list[dict],
    ) -> None:
        now = utc_now()

        with self.connect() as con:
            con.execute(
                "DELETE FROM history_entries WHERE campaign_id=?",
                (campaign_id,),
            )

            self._insert_history_entries(
                con,
                campaign_id,
                entries,
                now,
            )

    def _insert_history_entries(
        self,
        con: sqlite3.Connection,
        campaign_id: int,
        entries: list[dict],
        now: str,
    ) -> None:
        for entry in entries:
            con.execute(
                """
                INSERT INTO history_entries(
                    campaign_id,
                    snapshot_id,
                    game_date,
                    entry_type,
                    title,
                    body,
                    government_type,
                    authority,
                    origin,
                    ethics,
                    civics,
                    created_utc
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    campaign_id,
                    entry["snapshot_id"],
                    entry["game_date"],
                    entry["entry_type"],
                    entry["title"],
                    entry["body"],
                    entry.get("government_type"),
                    entry.get("authority"),
                    entry.get("origin"),
                    entry.get("ethics"),
                    entry.get("civics"),
                    now,
                ),
            )

    def history_entries(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT
                    h.*,
                    s.archive_filename,
                    s.processed AS snapshot_processed
                FROM history_entries h
                JOIN snapshots s ON s.id=h.snapshot_id
                WHERE h.campaign_id=?
                ORDER BY h.id ASC
                """,
                (campaign_id,),
            ).fetchall()

    def processed_count(self, campaign_id: int) -> int:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT COUNT(*) AS count
                FROM snapshots
                WHERE campaign_id=? AND processed=1
                """,
                (campaign_id,),
            ).fetchone()

            return int(row["count"])

    # ------------------------------------------------------------------
    # Ship / fleet derived history
    # ------------------------------------------------------------------

    def ship_registry_count(self, campaign_id: int) -> int:
        with self.connect() as con:
            row = con.execute(
                "SELECT COUNT(*) AS count FROM ship_registry WHERE campaign_id=?",
                (campaign_id,),
            ).fetchone()
            return int(row["count"])

    def ship_registry(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT
                    s.*,
                    p.build_location,
                    p.build_location_starbase_id,
                    p.evidence_kind AS build_location_evidence,
                    p.confidence AS build_location_confidence,
                    p.source_snapshot_id AS build_location_source_snapshot_id,
                    p.source_game_date AS build_location_source_game_date
                FROM ship_registry s
                LEFT JOIN ship_build_provenance p
                  ON p.campaign_id=s.campaign_id
                 AND p.ship_id=s.ship_id
                WHERE s.campaign_id=?
                ORDER BY
                    s.baseline_present DESC,
                    s.first_seen_date,
                    s.name,
                    s.ship_id
                """,
                (campaign_id,),
            ).fetchall()

    def fleet_registry(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM fleet_registry
                WHERE campaign_id=?
                ORDER BY baseline_present DESC, first_seen_date, name, fleet_id
                """,
                (campaign_id,),
            ).fetchall()

    def ship_fleet_events(self, campaign_id: int, visible_only: bool = True):
        sql = """
            SELECT
                e.*,
                p.build_location AS build_location,
                p.evidence_kind AS build_location_evidence,
                p.confidence AS build_location_confidence,
                p.source_game_date AS build_location_source_game_date
            FROM ship_fleet_events e
            LEFT JOIN ship_build_provenance p
              ON p.campaign_id=e.campaign_id
             AND p.ship_id=e.ship_id
            WHERE e.campaign_id=?
        """

        params: list = [campaign_id]

        if visible_only:
            sql += " AND e.visible=1"

        sql += " ORDER BY e.game_date ASC, e.id ASC"

        with self.connect() as con:
            return con.execute(
                sql,
                params,
            ).fetchall()

    def leader_registry(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM leader_registry
                WHERE campaign_id=?
                ORDER BY
                    baseline_present DESC,
                    ever_ruler DESC,
                    ever_heir DESC,
                    first_seen_date,
                    name,
                    leader_id
                """,
                (campaign_id,),
            ).fetchall()

    def leader_deep_evidence(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM leader_deep_evidence
                WHERE campaign_id=?
                ORDER BY leader_id
                """,
                (campaign_id,),
            ).fetchall()

    def leader_career_events(
        self,
        campaign_id: int,
        visible_only: bool = False,
    ):
        sql = """
            SELECT *
            FROM leader_career_events
            WHERE campaign_id=?
        """

        params: list = [campaign_id]

        if visible_only:
            sql += " AND visible=1"

        sql += " ORDER BY game_date ASC, id ASC"

        with self.connect() as con:
            return con.execute(
                sql,
                params,
            ).fetchall()

    def world_registry(self, campaign_id: int):
        with self.connect() as con:
            return con.execute(
                """
                SELECT *
                FROM world_registry
                WHERE campaign_id=?
                ORDER BY
                    baseline_present DESC,
                    ever_capital DESC,
                    first_seen_date,
                    name,
                    planet_id
                """,
                (campaign_id,),
            ).fetchall()

    def world_history_events(
        self,
        campaign_id: int,
        visible_only: bool = False,
    ):
        sql = """
            SELECT *
            FROM world_history_events
            WHERE campaign_id=?
        """

        params: list = [campaign_id]

        if visible_only:
            sql += " AND visible=1"

        sql += " ORDER BY game_date ASC, id ASC"

        with self.connect() as con:
            return con.execute(
                sql,
                params,
            ).fetchall()

    def apply_world_delta(
        self,
        campaign_id: int,
        data: dict,
    ) -> None:
        now = utc_now()

        with self.connect() as con:
            for world in data.get("worlds", []):
                con.execute(
                    """
                    INSERT INTO world_registry(
                        campaign_id, planet_id, latest_colony_id, first_seen_date,
                        last_seen_date, colonize_date, name, system_id, system_name,
                        planet_class_key, planet_class_name, planet_size,
                        original_owner_id, latest_owner_id, latest_controller_id,
                        latest_governor_id, latest_governor_name, latest_population,
                        latest_employable_pops, latest_designation_key,
                        latest_designation_name, latest_ascension_tier,
                        latest_district_count, latest_building_count,
                        latest_is_capital, ever_capital, status, baseline_present,
                        first_snapshot_id, last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(campaign_id, planet_id) DO UPDATE SET
                        latest_colony_id=excluded.latest_colony_id,
                        last_seen_date=excluded.last_seen_date,
                        colonize_date=COALESCE(world_registry.colonize_date, excluded.colonize_date),
                        name=excluded.name,
                        system_id=excluded.system_id,
                        system_name=excluded.system_name,
                        planet_class_key=excluded.planet_class_key,
                        planet_class_name=excluded.planet_class_name,
                        planet_size=excluded.planet_size,
                        original_owner_id=COALESCE(world_registry.original_owner_id, excluded.original_owner_id),
                        latest_owner_id=excluded.latest_owner_id,
                        latest_controller_id=excluded.latest_controller_id,
                        latest_governor_id=excluded.latest_governor_id,
                        latest_governor_name=excluded.latest_governor_name,
                        latest_population=excluded.latest_population,
                        latest_employable_pops=excluded.latest_employable_pops,
                        latest_designation_key=excluded.latest_designation_key,
                        latest_designation_name=excluded.latest_designation_name,
                        latest_ascension_tier=excluded.latest_ascension_tier,
                        latest_district_count=excluded.latest_district_count,
                        latest_building_count=excluded.latest_building_count,
                        latest_is_capital=excluded.latest_is_capital,
                        ever_capital=MAX(world_registry.ever_capital, excluded.ever_capital),
                        status='present',
                        baseline_present=MAX(world_registry.baseline_present, excluded.baseline_present),
                        last_snapshot_id=excluded.last_snapshot_id
                    """,
                    (
                        campaign_id,
                        world["planet_id"],
                        world.get("latest_colony_id"),
                        world["first_seen_date"],
                        world["last_seen_date"],
                        world.get("colonize_date"),
                        world["name"],
                        world.get("system_id"),
                        world.get("system_name"),
                        world.get("planet_class_key"),
                        world.get("planet_class_name"),
                        world.get("planet_size"),
                        world.get("original_owner_id"),
                        world.get("latest_owner_id"),
                        world.get("latest_controller_id"),
                        world.get("latest_governor_id"),
                        world.get("latest_governor_name"),
                        world.get("latest_population"),
                        world.get("latest_employable_pops"),
                        world.get("latest_designation_key"),
                        world.get("latest_designation_name"),
                        world.get("latest_ascension_tier"),
                        world.get("latest_district_count", 0),
                        world.get("latest_building_count", 0),
                        world.get("latest_is_capital", 0),
                        world.get("ever_capital", 0),
                        world.get("status", "present"),
                        world.get("baseline_present", 0),
                        world.get("first_snapshot_id"),
                        world.get("last_snapshot_id"),
                    ),
                )

            for planet_id in data.get("missing_planet_ids", []):
                con.execute(
                    """
                    UPDATE world_registry
                    SET status='no_longer_owned',
                        latest_is_capital=0
                    WHERE campaign_id=? AND planet_id=?
                    """,
                    (campaign_id, planet_id),
                )

            for event in data.get("events", []):
                con.execute(
                    """
                    INSERT OR IGNORE INTO world_history_events(
                        campaign_id, event_key, snapshot_id, game_date,
                        event_type, planet_id, title, body, visible, confidence,
                        date_kind, created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event["event_type"],
                        event["planet_id"],
                        event["title"],
                        event["body"],
                        event.get("visible", 0),
                        event.get("confidence", "high"),
                        event.get("date_kind", "between_snapshots"),
                        now,
                    ),
                )

    def apply_leader_delta(
        self,
        campaign_id: int,
        data: dict,
    ) -> None:
        now = utc_now()

        with self.connect() as con:
            for leader in data.get("leaders", []):
                con.execute(
                    """
                    INSERT INTO leader_registry(
                        campaign_id, leader_id, first_seen_date, last_seen_date,
                        name, leader_class, latest_level, latest_experience,
                        recruitment_date, gender, traits, trait_names,
                        latest_assignment_type, latest_assignment_id,
                        latest_assignment, latest_council_role, latest_is_ruler,
                        ever_ruler, latest_is_heir, ever_heir, status,
                        baseline_present, first_snapshot_id, last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(campaign_id, leader_id) DO UPDATE SET
                        last_seen_date=excluded.last_seen_date,
                        name=excluded.name,
                        leader_class=excluded.leader_class,
                        latest_level=excluded.latest_level,
                        latest_experience=excluded.latest_experience,
                        recruitment_date=COALESCE(
                            leader_registry.recruitment_date,
                            excluded.recruitment_date
                        ),
                        gender=COALESCE(excluded.gender, leader_registry.gender),
                        traits=excluded.traits,
                        trait_names=excluded.trait_names,
                        latest_assignment_type=excluded.latest_assignment_type,
                        latest_assignment_id=excluded.latest_assignment_id,
                        latest_assignment=excluded.latest_assignment,
                        latest_council_role=excluded.latest_council_role,
                        latest_is_ruler=excluded.latest_is_ruler,
                        ever_ruler=MAX(leader_registry.ever_ruler, excluded.ever_ruler),
                        latest_is_heir=excluded.latest_is_heir,
                        ever_heir=MAX(leader_registry.ever_heir, excluded.ever_heir),
                        status='present',
                        baseline_present=MAX(
                            leader_registry.baseline_present,
                            excluded.baseline_present
                        ),
                        last_snapshot_id=excluded.last_snapshot_id
                    """,
                    (
                        campaign_id,
                        leader["leader_id"],
                        leader["first_seen_date"],
                        leader["last_seen_date"],
                        leader["name"],
                        leader["leader_class"],
                        leader.get("latest_level"),
                        leader.get("latest_experience"),
                        leader.get("recruitment_date"),
                        leader.get("gender"),
                        json.dumps(list(leader.get("traits", ())), ensure_ascii=True),
                        json.dumps(list(leader.get("trait_names", ())), ensure_ascii=True),
                        leader.get("latest_assignment_type"),
                        leader.get("latest_assignment_id"),
                        leader.get("latest_assignment"),
                        leader.get("latest_council_role"),
                        leader.get("latest_is_ruler", 0),
                        leader.get("ever_ruler", 0),
                        leader.get("latest_is_heir", 0),
                        leader.get("ever_heir", 0),
                        leader.get("status", "present"),
                        leader.get("baseline_present", 0),
                        leader.get("first_snapshot_id"),
                        leader.get("last_snapshot_id"),
                    ),
                )

            for leader in data.get("leaders", []):
                con.execute(
                    """
                    INSERT INTO leader_deep_evidence(
                        campaign_id, leader_id, species_id, species_name, portrait,
                        creator_country_id, tier_key, tier_name, recorded_date, date_added,
                        raw_age, ethic_key, ethic_name, job_key, job_name,
                        background_planet_id, background_planet_name,
                        custom_description_key, custom_description_name, bonus_skill_level,
                        raw_record_keys, raw_flag_values, raw_variable_values, event_target_aliases,
                        death_date, death_reason_key, death_reason_value,
                        death_evidence_kind, death_first_observed_date, updated_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(campaign_id, leader_id) DO UPDATE SET
                        species_id=COALESCE(excluded.species_id, leader_deep_evidence.species_id),
                        species_name=COALESCE(excluded.species_name, leader_deep_evidence.species_name),
                        portrait=COALESCE(excluded.portrait, leader_deep_evidence.portrait),
                        creator_country_id=COALESCE(excluded.creator_country_id, leader_deep_evidence.creator_country_id),
                        tier_key=COALESCE(excluded.tier_key, leader_deep_evidence.tier_key),
                        tier_name=COALESCE(excluded.tier_name, leader_deep_evidence.tier_name),
                        recorded_date=COALESCE(excluded.recorded_date, leader_deep_evidence.recorded_date),
                        date_added=COALESCE(excluded.date_added, leader_deep_evidence.date_added),
                        raw_age=COALESCE(excluded.raw_age, leader_deep_evidence.raw_age),
                        ethic_key=COALESCE(excluded.ethic_key, leader_deep_evidence.ethic_key),
                        ethic_name=COALESCE(excluded.ethic_name, leader_deep_evidence.ethic_name),
                        job_key=COALESCE(excluded.job_key, leader_deep_evidence.job_key),
                        job_name=COALESCE(excluded.job_name, leader_deep_evidence.job_name),
                        background_planet_id=COALESCE(excluded.background_planet_id, leader_deep_evidence.background_planet_id),
                        background_planet_name=COALESCE(excluded.background_planet_name, leader_deep_evidence.background_planet_name),
                        custom_description_key=COALESCE(excluded.custom_description_key, leader_deep_evidence.custom_description_key),
                        custom_description_name=COALESCE(excluded.custom_description_name, leader_deep_evidence.custom_description_name),
                        bonus_skill_level=COALESCE(excluded.bonus_skill_level, leader_deep_evidence.bonus_skill_level),
                        raw_record_keys=excluded.raw_record_keys,
                        raw_flag_values=excluded.raw_flag_values,
                        raw_variable_values=excluded.raw_variable_values,
                        event_target_aliases=excluded.event_target_aliases,
                        death_date=COALESCE(excluded.death_date, leader_deep_evidence.death_date),
                        death_reason_key=COALESCE(excluded.death_reason_key, leader_deep_evidence.death_reason_key),
                        death_reason_value=COALESCE(excluded.death_reason_value, leader_deep_evidence.death_reason_value),
                        death_evidence_kind=COALESCE(excluded.death_evidence_kind, leader_deep_evidence.death_evidence_kind),
                        death_first_observed_date=COALESCE(excluded.death_first_observed_date, leader_deep_evidence.death_first_observed_date),
                        updated_utc=excluded.updated_utc
                    """,
                    (
                        campaign_id, leader["leader_id"], leader.get("species_id"),
                        leader.get("species_name"), leader.get("portrait"),
                        leader.get("creator_country_id"), leader.get("tier_key"),
                        leader.get("tier_name"), leader.get("recorded_date"),
                        leader.get("date_added"), leader.get("raw_age"),
                        leader.get("ethic_key"), leader.get("ethic_name"),
                        leader.get("job_key"), leader.get("job_name"),
                        leader.get("background_planet_id"), leader.get("background_planet_name"),
                        leader.get("custom_description_key"), leader.get("custom_description_name"),
                        leader.get("bonus_skill_level"),
                        json.dumps(list(leader.get("raw_record_keys", ())), ensure_ascii=True),
                        json.dumps([list(pair) for pair in leader.get("raw_flag_values", ())], ensure_ascii=True),
                        json.dumps([list(pair) for pair in leader.get("raw_variable_values", ())], ensure_ascii=True),
                        json.dumps(list(leader.get("event_target_aliases", ())), ensure_ascii=True),
                        leader.get("death_date"), leader.get("death_reason_key"),
                        leader.get("death_reason_value"), leader.get("death_evidence_kind"),
                        leader.get("death_first_observed_date"), now,
                    ),
                )

            for update in data.get("dead_leader_updates", []):
                con.execute(
                    """
                    UPDATE leader_deep_evidence
                    SET death_date=?, death_reason_key=?, death_reason_value=?,
                        death_evidence_kind=?, death_first_observed_date=?, updated_utc=?
                    WHERE campaign_id=? AND leader_id=?
                    """,
                    (
                        update.get("death_date"), update.get("death_reason_key"),
                        update.get("death_reason_value"), update.get("death_evidence_kind"),
                        update.get("death_first_observed_date"), now, campaign_id,
                        update["leader_id"],
                    ),
                )

            status_rows = data.get("missing_leader_statuses") or [
                {"leader_id": leader_id, "status": "missing_unconfirmed", "event_target_aliases": ()}
                for leader_id in data.get("missing_leader_ids", [])
            ]
            for status_row in status_rows:
                leader_id = int(status_row["leader_id"])
                status = status_row.get("status") or "missing_unconfirmed"
                con.execute(
                    """
                    UPDATE leader_registry
                    SET status=?,
                        latest_is_ruler=0,
                        latest_is_heir=0
                    WHERE campaign_id=? AND leader_id=?
                    """,
                    (status, campaign_id, leader_id),
                )

                aliases = tuple(status_row.get("event_target_aliases") or ())
                if aliases:
                    existing_row = con.execute(
                        """
                        SELECT event_target_aliases
                        FROM leader_deep_evidence
                        WHERE campaign_id=? AND leader_id=?
                        """,
                        (campaign_id, leader_id),
                    ).fetchone()
                    existing_aliases = set()
                    if existing_row and existing_row[0]:
                        try:
                            existing_aliases.update(json.loads(existing_row[0]))
                        except (TypeError, ValueError, json.JSONDecodeError):
                            pass
                    existing_aliases.update(aliases)
                    con.execute(
                        """
                        UPDATE leader_deep_evidence
                        SET event_target_aliases=?, updated_utc=?
                        WHERE campaign_id=? AND leader_id=?
                        """,
                        (
                            json.dumps(sorted(existing_aliases), ensure_ascii=True),
                            now, campaign_id, leader_id,
                        ),
                    )

            for event in data.get("events", []):
                con.execute(
                    """
                    INSERT OR IGNORE INTO leader_career_events(
                        campaign_id, event_key, snapshot_id, game_date,
                        event_type, leader_id, title, body, visible, confidence,
                        date_kind, created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event["event_type"],
                        event["leader_id"],
                        event["title"],
                        event["body"],
                        event.get("visible", 0),
                        event.get("confidence", "high"),
                        event.get("date_kind", "between_snapshots"),
                        now,
                    ),
                )

    def apply_ship_fleet_delta(
        self,
        campaign_id: int,
        data: dict,
    ) -> None:
        now = utc_now()

        with self.connect() as con:
            for ship in data.get("ships", []):
                con.execute(
                    """
                    INSERT INTO ship_registry(
                        campaign_id,
                        ship_id,
                        first_seen_date,
                        last_seen_date,
                        construction_date,
                        name,
                        ship_type,
                        opening_name,
                        opening_ship_type,
                        opening_construction_date,
                        opening_fleet_id,
                        opening_fleet_name,
                        opening_commander_id,
                        opening_commander_name,
                        latest_fleet_id,
                        latest_fleet_name,
                        latest_commander_id,
                        latest_commander_name,
                        status,
                        baseline_present,
                        first_snapshot_id,
                        last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(campaign_id, ship_id) DO UPDATE SET
                        last_seen_date=excluded.last_seen_date,
                        construction_date=COALESCE(
                            ship_registry.construction_date,
                            excluded.construction_date
                        ),
                        name=excluded.name,
                        ship_type=excluded.ship_type,
                        opening_name=COALESCE(ship_registry.opening_name, excluded.opening_name),
                        opening_ship_type=COALESCE(ship_registry.opening_ship_type, excluded.opening_ship_type),
                        opening_construction_date=COALESCE(ship_registry.opening_construction_date, excluded.opening_construction_date),
                        opening_fleet_id=COALESCE(ship_registry.opening_fleet_id, excluded.opening_fleet_id),
                        opening_fleet_name=COALESCE(ship_registry.opening_fleet_name, excluded.opening_fleet_name),
                        opening_commander_id=COALESCE(ship_registry.opening_commander_id, excluded.opening_commander_id),
                        opening_commander_name=COALESCE(ship_registry.opening_commander_name, excluded.opening_commander_name),
                        latest_fleet_id=excluded.latest_fleet_id,
                        latest_fleet_name=excluded.latest_fleet_name,
                        latest_commander_id=excluded.latest_commander_id,
                        latest_commander_name=excluded.latest_commander_name,
                        status='present',
                        baseline_present=MAX(
                            ship_registry.baseline_present,
                            excluded.baseline_present
                        ),
                        last_snapshot_id=excluded.last_snapshot_id
                    """,
                    (
                        campaign_id,
                        ship["ship_id"],
                        ship["first_seen_date"],
                        ship["last_seen_date"],
                        ship.get("construction_date"),
                        ship["name"],
                        ship["ship_type"],
                        ship.get("opening_name"),
                        ship.get("opening_ship_type"),
                        ship.get("opening_construction_date"),
                        ship.get("opening_fleet_id"),
                        ship.get("opening_fleet_name"),
                        ship.get("opening_commander_id"),
                        ship.get("opening_commander_name"),
                        ship.get("latest_fleet_id"),
                        ship.get("latest_fleet_name"),
                        ship.get("latest_commander_id"),
                        ship.get("latest_commander_name"),
                        ship["status"],
                        ship.get("baseline_present", 0),
                        ship.get("first_snapshot_id"),
                        ship.get("last_snapshot_id"),
                    ),
                )

            for fleet in data.get("fleets", []):
                con.execute(
                    """
                    INSERT INTO fleet_registry(
                        campaign_id,
                        fleet_id,
                        first_seen_date,
                        last_seen_date,
                        name,
                        ship_class,
                        opening_name,
                        opening_ship_class,
                        opening_ship_count,
                        opening_home_base,
                        opening_commander_id,
                        opening_commander_name,
                        latest_ship_count,
                        latest_home_base,
                        latest_commander_id,
                        latest_commander_name,
                        status,
                        baseline_present,
                        first_snapshot_id,
                        last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(campaign_id, fleet_id) DO UPDATE SET
                        last_seen_date=excluded.last_seen_date,
                        name=excluded.name,
                        ship_class=excluded.ship_class,
                        opening_name=COALESCE(fleet_registry.opening_name, excluded.opening_name),
                        opening_ship_class=COALESCE(fleet_registry.opening_ship_class, excluded.opening_ship_class),
                        opening_ship_count=COALESCE(fleet_registry.opening_ship_count, excluded.opening_ship_count),
                        opening_home_base=COALESCE(fleet_registry.opening_home_base, excluded.opening_home_base),
                        opening_commander_id=COALESCE(fleet_registry.opening_commander_id, excluded.opening_commander_id),
                        opening_commander_name=COALESCE(fleet_registry.opening_commander_name, excluded.opening_commander_name),
                        latest_ship_count=excluded.latest_ship_count,
                        latest_home_base=excluded.latest_home_base,
                        latest_commander_id=excluded.latest_commander_id,
                        latest_commander_name=excluded.latest_commander_name,
                        status='present',
                        baseline_present=MAX(
                            fleet_registry.baseline_present,
                            excluded.baseline_present
                        ),
                        last_snapshot_id=excluded.last_snapshot_id
                    """,
                    (
                        campaign_id,
                        fleet["fleet_id"],
                        fleet["first_seen_date"],
                        fleet["last_seen_date"],
                        fleet["name"],
                        fleet["ship_class"],
                        fleet.get("opening_name"),
                        fleet.get("opening_ship_class"),
                        fleet.get("opening_ship_count"),
                        fleet.get("opening_home_base"),
                        fleet.get("opening_commander_id"),
                        fleet.get("opening_commander_name"),
                        fleet.get("latest_ship_count", 0),
                        fleet.get("latest_home_base"),
                        fleet.get("latest_commander_id"),
                        fleet.get("latest_commander_name"),
                        fleet["status"],
                        fleet.get("baseline_present", 0),
                        fleet.get("first_snapshot_id"),
                        fleet.get("last_snapshot_id"),
                    ),
                )

            for provenance in data.get("build_provenance", []):
                con.execute(
                    """
                    INSERT INTO ship_build_provenance(
                        campaign_id,
                        ship_id,
                        build_location,
                        build_location_starbase_id,
                        evidence_kind,
                        confidence,
                        source_snapshot_id,
                        source_game_date,
                        created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(campaign_id, ship_id) DO UPDATE SET
                        build_location=excluded.build_location,
                        build_location_starbase_id=excluded.build_location_starbase_id,
                        evidence_kind=excluded.evidence_kind,
                        confidence=excluded.confidence,
                        source_snapshot_id=excluded.source_snapshot_id,
                        source_game_date=excluded.source_game_date,
                        created_utc=excluded.created_utc
                    """,
                    (
                        campaign_id,
                        provenance["ship_id"],
                        provenance["build_location"],
                        provenance.get("build_location_starbase_id"),
                        provenance["evidence_kind"],
                        provenance["confidence"],
                        provenance.get("source_snapshot_id"),
                        provenance.get("source_game_date"),
                        now,
                    ),
                )

            for ship_id in data.get("missing_ship_ids", []):
                con.execute(
                    """
                    UPDATE ship_registry
                    SET status='missing_unconfirmed'
                    WHERE campaign_id=? AND ship_id=?
                    """,
                    (campaign_id, ship_id),
                )

            for fleet_id in data.get("missing_fleet_ids", []):
                con.execute(
                    """
                    UPDATE fleet_registry
                    SET status='missing_unconfirmed'
                    WHERE campaign_id=? AND fleet_id=?
                    """,
                    (campaign_id, fleet_id),
                )

            for event in data.get("events", []):
                con.execute(
                    """
                    INSERT OR IGNORE INTO ship_fleet_events(
                        campaign_id,
                        event_key,
                        snapshot_id,
                        game_date,
                        event_type,
                        ship_id,
                        fleet_id,
                        title,
                        body,
                        visible,
                        confidence,
                        date_kind,
                        created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event["event_type"],
                        event.get("ship_id"),
                        event.get("fleet_id"),
                        event["title"],
                        event["body"],
                        event.get("visible", 1),
                        event.get("confidence", "high"),
                        event.get("date_kind", "between_snapshots"),
                        now,
                    ),
                )

    def replace_review_data(
        self,
        campaign_id: int,
        *,
        history_entries: list[dict],
        ship_rows: list[dict],
        fleet_rows: list[dict],
        ship_fleet_events: list[dict],
        ship_build_provenance: list[dict],
        leader_rows: list[dict],
        leader_career_events: list[dict],
        world_rows: list[dict],
        world_events: list[dict],
    ) -> None:
        """
        Atomically replace all current derived Historian data for a campaign.
        Archive snapshots and processed flags are deliberately untouched.
        """
        now = utc_now()

        with self.connect() as con:
            con.execute(
                "DELETE FROM history_entries WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM ship_fleet_events WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM ship_build_provenance WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM ship_registry WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM fleet_registry WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM leader_career_events WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM leader_deep_evidence WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM leader_registry WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM world_history_events WHERE campaign_id=?",
                (campaign_id,),
            )
            con.execute(
                "DELETE FROM world_registry WHERE campaign_id=?",
                (campaign_id,),
            )

            self._insert_history_entries(
                con,
                campaign_id,
                history_entries,
                now,
            )

            for ship in ship_rows:
                con.execute(
                    """
                    INSERT INTO ship_registry(
                        campaign_id, ship_id, first_seen_date, last_seen_date,
                        construction_date, name, ship_type, opening_name,
                        opening_ship_type, opening_construction_date,
                        opening_fleet_id, opening_fleet_name, opening_commander_id,
                        opening_commander_name, latest_fleet_id, latest_fleet_name,
                        latest_commander_id, latest_commander_name, status,
                        baseline_present, first_snapshot_id, last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        ship["ship_id"],
                        ship["first_seen_date"],
                        ship["last_seen_date"],
                        ship.get("construction_date"),
                        ship["name"],
                        ship["ship_type"],
                        ship.get("opening_name"),
                        ship.get("opening_ship_type"),
                        ship.get("opening_construction_date"),
                        ship.get("opening_fleet_id"),
                        ship.get("opening_fleet_name"),
                        ship.get("opening_commander_id"),
                        ship.get("opening_commander_name"),
                        ship.get("latest_fleet_id"),
                        ship.get("latest_fleet_name"),
                        ship.get("latest_commander_id"),
                        ship.get("latest_commander_name"),
                        ship["status"],
                        ship.get("baseline_present", 0),
                        ship.get("first_snapshot_id"),
                        ship.get("last_snapshot_id"),
                    ),
                )

            for fleet in fleet_rows:
                con.execute(
                    """
                    INSERT INTO fleet_registry(
                        campaign_id, fleet_id, first_seen_date, last_seen_date,
                        name, ship_class, opening_name, opening_ship_class,
                        opening_ship_count, opening_home_base, opening_commander_id,
                        opening_commander_name, latest_ship_count, latest_home_base,
                        latest_commander_id, latest_commander_name, status,
                        baseline_present, first_snapshot_id, last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        fleet["fleet_id"],
                        fleet["first_seen_date"],
                        fleet["last_seen_date"],
                        fleet["name"],
                        fleet["ship_class"],
                        fleet.get("opening_name"),
                        fleet.get("opening_ship_class"),
                        fleet.get("opening_ship_count"),
                        fleet.get("opening_home_base"),
                        fleet.get("opening_commander_id"),
                        fleet.get("opening_commander_name"),
                        fleet.get("latest_ship_count", 0),
                        fleet.get("latest_home_base"),
                        fleet.get("latest_commander_id"),
                        fleet.get("latest_commander_name"),
                        fleet["status"],
                        fleet.get("baseline_present", 0),
                        fleet.get("first_snapshot_id"),
                        fleet.get("last_snapshot_id"),
                    ),
                )

            for provenance in ship_build_provenance:
                con.execute(
                    """
                    INSERT INTO ship_build_provenance(
                        campaign_id,
                        ship_id,
                        build_location,
                        build_location_starbase_id,
                        evidence_kind,
                        confidence,
                        source_snapshot_id,
                        source_game_date,
                        created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        provenance["ship_id"],
                        provenance["build_location"],
                        provenance.get("build_location_starbase_id"),
                        provenance["evidence_kind"],
                        provenance["confidence"],
                        provenance.get("source_snapshot_id"),
                        provenance.get("source_game_date"),
                        now,
                    ),
                )

            for event in ship_fleet_events:
                con.execute(
                    """
                    INSERT INTO ship_fleet_events(
                        campaign_id, event_key, snapshot_id, game_date,
                        event_type, ship_id, fleet_id, title, body, visible,
                        confidence, date_kind, created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event["event_type"],
                        event.get("ship_id"),
                        event.get("fleet_id"),
                        event["title"],
                        event["body"],
                        event.get("visible", 1),
                        event.get("confidence", "high"),
                        event.get("date_kind", "between_snapshots"),
                        now,
                    ),
                )

            for leader in leader_rows:
                con.execute(
                    """
                    INSERT INTO leader_registry(
                        campaign_id, leader_id, first_seen_date, last_seen_date,
                        name, leader_class, latest_level, latest_experience,
                        recruitment_date, gender, traits, trait_names,
                        latest_assignment_type, latest_assignment_id,
                        latest_assignment, latest_council_role, latest_is_ruler,
                        ever_ruler, latest_is_heir, ever_heir, status,
                        baseline_present, first_snapshot_id, last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        leader["leader_id"],
                        leader["first_seen_date"],
                        leader["last_seen_date"],
                        leader["name"],
                        leader["leader_class"],
                        leader.get("latest_level"),
                        leader.get("latest_experience"),
                        leader.get("recruitment_date"),
                        leader.get("gender"),
                        json.dumps(list(leader.get("traits", ())), ensure_ascii=True),
                        json.dumps(list(leader.get("trait_names", ())), ensure_ascii=True),
                        leader.get("latest_assignment_type"),
                        leader.get("latest_assignment_id"),
                        leader.get("latest_assignment"),
                        leader.get("latest_council_role"),
                        leader.get("latest_is_ruler", 0),
                        leader.get("ever_ruler", 0),
                        leader.get("latest_is_heir", 0),
                        leader.get("ever_heir", 0),
                        leader.get("status", "present"),
                        leader.get("baseline_present", 0),
                        leader.get("first_snapshot_id"),
                        leader.get("last_snapshot_id"),
                    ),
                )

            for leader in leader_rows:
                con.execute(
                    """
                    INSERT INTO leader_deep_evidence(
                        campaign_id, leader_id, species_id, species_name, portrait,
                        creator_country_id, tier_key, tier_name, recorded_date, date_added,
                        raw_age, ethic_key, ethic_name, job_key, job_name,
                        background_planet_id, background_planet_name,
                        custom_description_key, custom_description_name, bonus_skill_level,
                        raw_record_keys, raw_flag_values, raw_variable_values, event_target_aliases,
                        death_date, death_reason_key, death_reason_value,
                        death_evidence_kind, death_first_observed_date, updated_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id, leader["leader_id"], leader.get("species_id"),
                        leader.get("species_name"), leader.get("portrait"),
                        leader.get("creator_country_id"), leader.get("tier_key"),
                        leader.get("tier_name"), leader.get("recorded_date"),
                        leader.get("date_added"), leader.get("raw_age"),
                        leader.get("ethic_key"), leader.get("ethic_name"),
                        leader.get("job_key"), leader.get("job_name"),
                        leader.get("background_planet_id"), leader.get("background_planet_name"),
                        leader.get("custom_description_key"), leader.get("custom_description_name"),
                        leader.get("bonus_skill_level"),
                        json.dumps(list(leader.get("raw_record_keys", ())), ensure_ascii=True),
                        json.dumps([list(pair) for pair in leader.get("raw_flag_values", ())], ensure_ascii=True),
                        json.dumps([list(pair) for pair in leader.get("raw_variable_values", ())], ensure_ascii=True),
                        json.dumps(list(leader.get("event_target_aliases", ())), ensure_ascii=True),
                        leader.get("death_date"), leader.get("death_reason_key"),
                        leader.get("death_reason_value"), leader.get("death_evidence_kind"),
                        leader.get("death_first_observed_date"), now,
                    ),
                )

            for event in leader_career_events:
                con.execute(
                    """
                    INSERT INTO leader_career_events(
                        campaign_id, event_key, snapshot_id, game_date,
                        event_type, leader_id, title, body, visible, confidence,
                        date_kind, created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event["event_type"],
                        event["leader_id"],
                        event["title"],
                        event["body"],
                        event.get("visible", 0),
                        event.get("confidence", "high"),
                        event.get("date_kind", "between_snapshots"),
                        now,
                    ),
                )

            for world in world_rows:
                con.execute(
                    """
                    INSERT INTO world_registry(
                        campaign_id, planet_id, latest_colony_id, first_seen_date,
                        last_seen_date, colonize_date, name, system_id, system_name,
                        planet_class_key, planet_class_name, planet_size,
                        original_owner_id, latest_owner_id, latest_controller_id,
                        latest_governor_id, latest_governor_name, latest_population,
                        latest_employable_pops, latest_designation_key,
                        latest_designation_name, latest_ascension_tier,
                        latest_district_count, latest_building_count,
                        latest_is_capital, ever_capital, status, baseline_present,
                        first_snapshot_id, last_snapshot_id
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        world["planet_id"],
                        world.get("latest_colony_id"),
                        world["first_seen_date"],
                        world["last_seen_date"],
                        world.get("colonize_date"),
                        world["name"],
                        world.get("system_id"),
                        world.get("system_name"),
                        world.get("planet_class_key"),
                        world.get("planet_class_name"),
                        world.get("planet_size"),
                        world.get("original_owner_id"),
                        world.get("latest_owner_id"),
                        world.get("latest_controller_id"),
                        world.get("latest_governor_id"),
                        world.get("latest_governor_name"),
                        world.get("latest_population"),
                        world.get("latest_employable_pops"),
                        world.get("latest_designation_key"),
                        world.get("latest_designation_name"),
                        world.get("latest_ascension_tier"),
                        world.get("latest_district_count", 0),
                        world.get("latest_building_count", 0),
                        world.get("latest_is_capital", 0),
                        world.get("ever_capital", 0),
                        world.get("status", "present"),
                        world.get("baseline_present", 0),
                        world.get("first_snapshot_id"),
                        world.get("last_snapshot_id"),
                    ),
                )

            for event in world_events:
                con.execute(
                    """
                    INSERT INTO world_history_events(
                        campaign_id, event_key, snapshot_id, game_date,
                        event_type, planet_id, title, body, visible, confidence,
                        date_kind, created_utc
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        campaign_id,
                        event["event_key"],
                        event.get("snapshot_id"),
                        event["game_date"],
                        event["event_type"],
                        event["planet_id"],
                        event["title"],
                        event["body"],
                        event.get("visible", 0),
                        event.get("confidence", "high"),
                        event.get("date_kind", "between_snapshots"),
                        now,
                    ),
                )
