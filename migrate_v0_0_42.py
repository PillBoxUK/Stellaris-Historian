from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import sqlite3

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_42_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.42.log"
DB_PATH = ROOT / "data" / "historian.db"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "historian/__init__.py",
    "historian/db.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/domains/people/__init__.py",
    "historian/domains/people/models.py",
    "historian/domains/people/cache.py",
    "historian/domains/people/parser.py",
    "historian/domains/people/history.py",
    "historian/domains/people/evidence_diagnostic.py",
    "historian/domains/people/exit_diagnostic.py",
    "historian_manifest.json",
    "README_v0.0.42.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.42.md",
]

COMPILE_CHECKS = [
    "app.py",
    "historian/db.py",
    "historian/history_processor.py",
    "historian/snapshot_cache.py",
    "historian/domains/people/models.py",
    "historian/domains/people/cache.py",
    "historian/domains/people/parser.py",
    "historian/domains/people/history.py",
    "historian/domains/people/evidence_diagnostic.py",
    "historian/domains/people/exit_diagnostic.py",
]

CREATE_DEEP_TABLE = """
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
)
"""


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_deep_table(log: list[str]) -> None:
    if not DB_PATH.exists():
        log.append("Historian database does not yet exist; normal application schema creation will create leader_deep_evidence.")
        return

    with sqlite3.connect(DB_PATH) as con:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute(CREATE_DEEP_TABLE)
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(leader_deep_evidence)")
        }
        # Defensive compatibility for a partially applied development build.
        if "event_target_aliases" not in columns:
            con.execute(
                "ALTER TABLE leader_deep_evidence "
                "ADD COLUMN event_target_aliases TEXT NOT NULL DEFAULT '[]'"
            )
            log.append("Added missing event_target_aliases column to leader_deep_evidence.")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_leader_deep_evidence_campaign "
            "ON leader_deep_evidence(campaign_id, leader_id)"
        )
        con.commit()
    log.append("Verified additive leader_deep_evidence database table and index.")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.42 character deep-evidence migration started.",
        "Archived saves, campaign identity and processed flags are not modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.42 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.42 files are incomplete. Nothing was intentionally changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.42 compile validation failed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        ensure_deep_table(log)
    except sqlite3.Error as exc:
        log.append(f"ABORTED: database migration failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.42 database migration failed.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.42 character deep-evidence migration completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "People cache component advances from v4 to v5.",
        "Leader species/portrait/tier/raw date/age/ethic/job/background/custom-description/flags/variables can now be preserved.",
        "Retained dead_leader records and active-leader =none tombstones are distinguished conservatively.",
        "Retained exact-ID saved_event_target aliases are preserved for future event-chain interpretation.",
        "Character_Evidence_Debug.txt and Raw_Evidence_Probe.txt are generated by Review/Construct.",
        "Review Campaign is required once so People v5 can be refreshed from archived raw saves.",
        "Construct Campaign is not required.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.42 character deep-evidence migration complete.")
    print("People cache component is now v5; run Review Campaign once.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
