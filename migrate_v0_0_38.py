from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parent
MARKER = ROOT / "data" / ".migration_v0_0_38_complete"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "MIGRATION_v0.0.38.log"

REQUIRED_FILES = [
    "app.py",
    "start.bat",
    "historian/__init__.py",
    "historian/history_processor.py",
    "historian/historical_events.py",
    "historian/scribes.py",
    "historian/domains/combat/__init__.py",
    "historian/domains/combat/models.py",
    "historian/domains/combat/parser.py",
    "historian/domains/combat/cache.py",
    "historian/domains/combat/diagnostic.py",
    "historian/domains/combat/correlation.py",
    "historian/domains/combat/correlation_diagnostic.py",
    "historian_manifest.json",
    "docs/ARCHITECTURE.md",
    "docs/CHANGELOG.md",
    "docs/MIGRATION_v0.0.38.md",
]

COMPILE_CHECKS = [
    "app.py",
    "historian/history_processor.py",
    "historian/historical_events.py",
    "historian/scribes.py",
    "historian/domains/combat/__init__.py",
    "historian/domains/combat/models.py",
    "historian/domains/combat/parser.py",
    "historian/domains/combat/cache.py",
    "historian/domains/combat/diagnostic.py",
    "historian/domains/combat/correlation.py",
    "historian/domains/combat/correlation_diagnostic.py",
]


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_log(lines: list[str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if MARKER.exists():
        return 0

    log = [
        f"[{stamp()}] Stellaris Historian v0.0.38 combat reconstruction/event-layer validation started.",
        "No database schema, archived save or processed flag is modified by this migration.",
    ]

    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        log.append("ABORTED: required v0.0.38 files are missing:")
        log.extend(f"  - {name}" for name in missing)
        write_log(log)
        print("ERROR: v0.0.38 files are incomplete. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    try:
        for name in COMPILE_CHECKS:
            py_compile.compile(str(ROOT / name), doraise=True)
    except py_compile.PyCompileError as exc:
        log.append(f"ABORTED: compile validation failed: {exc}")
        write_log(log)
        print("ERROR: v0.0.38 compile validation failed. Nothing was changed.")
        print(f"See: {LOG_PATH}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        "Stellaris Historian v0.0.38 combat reconstruction and historical event validation completed.\n",
        encoding="utf-8",
    )

    log.extend([
        "Combat cache component advanced from v2 to v3; all other domain cache components remain valid.",
        "Review Campaign will extend existing snapshots with direct player fleet combat telemetry and relation-counter context.",
        "Added direct fleet combat reconstruction from retained combat/fleet_stats/combat_stats records.",
        "Direct telemetry can preserve exact combat start date, player fleet, commander, system, opposing country/fleet and fleet loss counters.",
        "Added conservative same-date combat-activity correlation and possible-loss windows.",
        "Diplomatic killed_ships counters remain directional raw evidence; v0.0.38 does not assign unproven semantic direction.",
        "Added Combat_Correlation_Debug.txt and Historical_Event_Debug.txt.",
        "Added presentation-neutral Historical Event Layer foundation for future Journal/Timeline/Scribes convergence.",
        "Expanded Scribes military prose to prefer direct battle telemetry where available without inventing victory/defeat or unsupported causes.",
        "Migration completed successfully.",
    ])
    write_log(log)

    print("v0.0.38 combat reconstruction and historical event validation complete.")
    print(f"Migration log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
