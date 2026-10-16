"""Read-only, on-demand inter-snapshot control comparison for ended formal wars.

No Ironman save is altered; reports are cached outside the game's save archives.
Identifies current control through *fleet membership*, never original_owner.
"""
from __future__ import annotations

from pathlib import Path
import json
import os
import re
import tempfile
import zipfile

from .core.stellaris_text import _find_named_block, _scalar
from .domains.combat.parser import _find_top_level_block_fast

# Numeric object entries in Stellaris' native tab-indented, multi-line save format.
_RECORD_START = re.compile(r'(?m)^(\t+)(\d+)=\s*\n\1\{')
_FLEET_ID = re.compile(r'\bfleet\s*=\s*(\d+)')
_NUMBER = re.compile(r'(?<!\w)\d+(?!\w)')


def _records(block: str | None) -> dict[int, str]:
    if not block:
        return {}
    markers = list(_RECORD_START.finditer(block))
    if not markers:
        return {}
    minimum = min(len(m.group(1)) for m in markers)
    top = [m for m in markers if len(m.group(1)) == minimum]
    return {int(m.group(2)): block[m.end():top[i + 1].start() if i + 1 < len(top) else len(block)]
            for i, m in enumerate(top)}


def _display_name(raw: str | None, fallback: str) -> str:
    if not raw:
        return fallback
    # Prefer literal Stellaris name keys. Avoid proclaiming unresolved localisation.
    name = _find_named_block(raw, "name")
    if not name:
        direct = _scalar(raw, "name")
        return direct.strip() if direct and len(direct) < 90 else fallback
    keys = re.findall(r'\bkey="([^"]+)"', name)
    if not keys:
        return fallback
    if any(k.startswith("%") or k.startswith("$") for k in keys):
        return fallback
    # Some system names are displayed directly; otherwise keep the raw key.
    key = keys[0]
    if key.startswith("NAME_"):
        key = key[5:].replace("_", " ")
    return key.replace("_", " ") if len(key) < 90 and not key.startswith(("EMPIRE_DESIGN_", "PRESCRIPTED_")) else fallback


def _ownership_map(save_path: Path) -> tuple[dict[int, dict], dict[int, str]]:
    if not save_path.is_file():
        raise FileNotFoundError(f"Archived snapshot missing: {save_path.name}")
    with zipfile.ZipFile(save_path) as archive:
        game = archive.read("gamestate").decode("utf-8", errors="replace")
    systems = _records(_find_top_level_block_fast(game, "galactic_object"))
    countries = _records(_find_top_level_block_fast(game, "country"))
    stations_block = _find_named_block(_find_top_level_block_fast(game, "starbase_mgr") or "", "starbases")
    starbases = _records(stations_block)
    ships = _records(_find_top_level_block_fast(game, "ships"))
    # No ownership inferred when country lists are absent or ambiguous.
    fleet_owner: dict[int, set[int]] = {}
    for cid, record in countries.items():
        mgr = _find_named_block(record, "fleets_manager")
        owned = _find_named_block(mgr or "", "owned_fleets")
        for fid in _FLEET_ID.findall(owned or ""):
            fleet_owner.setdefault(int(fid), set()).add(cid)
    owners: dict[int, dict] = {}
    for sid, record in systems.items():
        sbids = [int(x) for x in _NUMBER.findall(_find_named_block(record, "starbases") or "")]
        valid: set[int] = set()
        fleet_ids: set[int] = set()
        for sbid in sbids:
            sb = starbases.get(sbid)
            station_id = _scalar(sb, "station")
            station = ships.get(int(station_id)) if station_id and station_id.isdigit() else None
            fid = _scalar(station, "fleet")
            if fid and fid.isdigit():
                fleet_ids.add(int(fid))
                valid.update(fleet_owner.get(int(fid), set()))
        if len(valid) == 1:
            owners[sid] = {
                "owner_id": next(iter(valid)),
                "system_id": sid,
                "system_name": _display_name(record, f"System {sid}"),
                "starbase_ids": sorted(set(sbids)),
                "station_fleet_ids": sorted(fleet_ids),
            }
    names = {cid: _display_name(record, f"Country {cid}") for cid, record in countries.items()}
    return owners, names


def _safe_path(row) -> Path:
    """Use only the DB's archived filename; never accept a browser-supplied path."""
    return Path(str(row["archive_path"]))


def _report(before_path: Path, after_path: Path, *, before_date: str, after_date: str,
            war_id: int, participants: tuple[int, ...], player_country_id: int) -> dict:
    previous, prev_names = _ownership_map(before_path)
    current, current_names = _ownership_map(after_path)
    names = {**prev_names, **current_names}
    changed = []
    for sid in sorted(previous.keys() & current.keys()):
        old, new = previous[sid], current[sid]
        if old["owner_id"] == new["owner_id"]:
            continue
        # Stable station fleet across snapshots strongly supports a genuine owner transition.
        fleet_shared = bool(set(old["station_fleet_ids"]) & set(new["station_fleet_ids"]))
        changed.append({
            "system_id": sid,
            "system_name": new["system_name"] if not new["system_name"].startswith("System ") else old["system_name"],
            "previous_owner_id": old["owner_id"],
            "later_owner_id": new["owner_id"],
            "previous_owner_name": names.get(old["owner_id"], f"Country {old['owner_id']}"),
            "later_owner_name": names.get(new["owner_id"], f"Country {new['owner_id']}"),
            "same_station_fleet": fleet_shared,
            "war_participant_pair": old["owner_id"] in participants and new["owner_id"] in participants,
        })
    changed.sort(key=lambda entry: (entry["later_owner_id"] != player_country_id, entry["system_name"].casefold()))
    gained = [x for x in changed if x["later_owner_id"] == player_country_id and x["previous_owner_id"] != player_country_id]
    lost = [x for x in changed if x["previous_owner_id"] == player_country_id and x["later_owner_id"] != player_country_id]
    return {
        "war_id": war_id,
        "before_date": before_date,
        "after_date": after_date,
        "systems_compared": len(previous.keys() & current.keys()),
        "player_gained": len(gained),
        "player_lost": len(lost),
        "changed_count": len(changed),
        "changes": changed,
        "evidence_scope": "starbase control through saved station-fleet membership",
        "disclaimer": "Changes between two archived snapshots, correlated with a war disappearing in the same interval. Exact peace terms, causal mechanism, planet-level ownership and settlement day are not established.",
    }


def analyze_war_aftermath(db, campaign_id: int, war_id: int, before_date: str,
                          after_date: str, participants: tuple[int, ...], player_country_id: int) -> dict:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found")
    snaps = {str(s["game_date"]): s for s in db.processed_snapshots(campaign_id)}
    earlier, later = snaps.get(before_date), snaps.get(after_date)
    if earlier is None or later is None:
        raise ValueError("Both archive-boundary snapshots must be processed before comparison")
    source1, source2 = _safe_path(earlier), _safe_path(later)
    if not source1.is_file() or not source2.is_file():
        raise FileNotFoundError("One or both archived files are missing")
    # Cache contains only derived facts, never raw save bytes, and is kept
    # under the campaign folder, not at the application root.
    folder = Path(str(campaign["archive_dir"])) / ".historian_evidence"
    cache = folder / f"war_{war_id}_{before_date}_{after_date}.json"
    key = [str(earlier["sha256"]), str(later["sha256"]), sorted(participants), player_country_id, 1]
    if cache.is_file():
        try:
            obj = json.loads(cache.read_text(encoding="utf-8"))
            if obj.get("source_signature") == key:
                return obj["report"]
        except (ValueError, OSError, KeyError, TypeError):
            pass
    report = _report(source1, source2, before_date=before_date, after_date=after_date,
                     war_id=war_id, participants=participants, player_country_id=player_country_id)
    folder.mkdir(exist_ok=True, parents=True)
    fd, temp = tempfile.mkstemp(prefix="war_aftermath_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"source_signature": key, "report": report}, handle, indent=2, ensure_ascii=False)
        os.replace(temp, cache)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return report
