"""On-demand, read-only military evidence from immutable archived Ironman saves.

Deliberately outside the live-save parser: never trigger a whole-history rebuild,
never turn a tactical `attacker_victory` flag or ship-loss count into a verdict.
Per-save mini-indexes are content-addressed and can be discarded safely.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import zipfile
from pathlib import Path

from .core.stellaris_text import _find_named_block, _int_scalar, _record_name, _scalar
from .domains.combat.parser import _anonymous_blocks, _find_top_level_block_fast
from .war_aftermath import _records, _display_name

_REVISION = 2
_INVALID = 4294967295


def _real_id(value):
    return value if value is not None and value != _INVALID else None


def _local_name(record: str, source: Path, fallback: str) -> str:
    try:
        name = _record_name(record, source, fallback=fallback).strip()
    except (ValueError, KeyError, OSError):
        name = fallback
    if name and not any(ch in name for ch in ("%", "$")):
        # _record_name sometimes humanises the raw Stellaris localisation key
        # without removing its internal language/planet prefix.
        name = re.sub(r"^[A-Z]{2,8}\d* PLANET ", "", name)
        return name
    return fallback


def _exhaustion_only(path: Path, war_id: int) -> list[dict]:
    """Upgrade a previous military v1 projection without reparsing starbases.

    Reading one war's compact battle records from the original archived save is
    significantly cheaper than re-resolving all planets, stations and ship
    memberships. Raw saves remain immutable and authoritative.
    """
    with zipfile.ZipFile(path) as archive:
        game = archive.read("gamestate").decode("utf-8", errors="replace")
    war = _records(_find_top_level_block_fast(game, "war")).get(war_id)
    if not war:
        return []
    out = []
    for index, battle in enumerate(_anonymous_blocks(_find_named_block(war, "battles")), 1):
        kind = _scalar(battle, "type")
        if kind not in ("ships", "armies"):
            continue
        out.append({"index": index, "date": _scalar(battle, "date"), "type": kind,
                    "attackers": [int(v) for v in re.findall(r"\d+", _find_named_block(battle, "attackers") or "")],
                    "defenders": [int(v) for v in re.findall(r"\d+", _find_named_block(battle, "defenders") or "")],
                    "attacker_exhaustion_raw": _scalar(battle, "attacker_war_exhaustion"),
                    "defender_exhaustion_raw": _scalar(battle, "defender_war_exhaustion")})
    return out


def _one_save(path: Path, war_id: int, player_id: int, parties: set[int]) -> dict:
    with zipfile.ZipFile(path) as archive:
        game = archive.read("gamestate").decode("utf-8", errors="replace")
    wars = _records(_find_top_level_block_fast(game, "war"))
    war = wars.get(war_id)
    battles = []
    exhaustion_evidence = []
    if war:
        for index, battle in enumerate(_anonymous_blocks(_find_named_block(war, "battles")), 1):
            battle_type = _scalar(battle, "type")
            if battle_type in ("ships", "armies"):
                exhaustion_evidence.append({
                    "index": index, "date": _scalar(battle, "date"), "type": battle_type,
                    "attackers": [int(v) for v in re.findall(r"\d+", _find_named_block(battle, "attackers") or "")],
                    "defenders": [int(v) for v in re.findall(r"\d+", _find_named_block(battle, "defenders") or "")],
                    "attacker_exhaustion_raw": _scalar(battle, "attacker_war_exhaustion"),
                    "defender_exhaustion_raw": _scalar(battle, "defender_war_exhaustion"),
                })
            if battle_type != "armies":
                continue
            attackers = tuple(int(v) for v in re.findall(r"\d+", _find_named_block(battle, "attackers") or ""))
            defenders = tuple(int(v) for v in re.findall(r"\d+", _find_named_block(battle, "defenders") or ""))
            if player_id not in attackers + defenders:
                continue
            date = _scalar(battle, "date")
            battles.append({
                "index": index,
                "colony_id": _real_id(_int_scalar(battle, "colony")),
                "date": date if date and not date.startswith("0.") else None,
                "player_tactical_side": "attacker" if player_id in attackers else "defender",
                "attacker_country_ids": list(attackers), "defender_country_ids": list(defenders),
                "attacker_victory_raw": _scalar(battle, "attacker_victory"),
                "attacker_losses_raw": _int_scalar(battle, "attacker_losses"),
                "defender_losses_raw": _int_scalar(battle, "defender_losses"),
            })

    # Planet (not colony) records contain owner/controller and the colony id.
    planets = {}
    for planet_id, rec in _records(_find_top_level_block_fast(game, "planets")).items():
        colony_id = _real_id(_int_scalar(rec, "colony"))
        if colony_id is None:
            continue
        owner = _real_id(_int_scalar(rec, "owner"))
        controller = _real_id(_int_scalar(rec, "controller"))
        if owner not in parties and controller not in parties:
            continue
        planets[str(colony_id)] = {
            "planet_id": planet_id, "colony_id": colony_id,
            "name": _local_name(rec, path, f"Planet {planet_id}"),
            "owner_id": owner, "controller_id": controller,
        }

    # A station's current controller is established by its FLEET membership in
    # a country's owned_fleets list, not by original_owner or its location.
    fleets_to_country = {}
    for country_id, rec in _records(_find_top_level_block_fast(game, "country")).items():
        if country_id not in parties:
            continue
        owned = _find_named_block(_find_named_block(rec, "fleets_manager") or "", "owned_fleets")
        for fid in re.findall(r"\bfleet\s*=\s*(\d+)", owned or ""):
            fleets_to_country.setdefault(int(fid), set()).add(country_id)
    starbases = _records(_find_named_block(_find_top_level_block_fast(game, "starbase_mgr") or "", "starbases"))
    station_ids = {}
    for sbid, rec in starbases.items():
        station = _real_id(_int_scalar(rec, "station"))
        if station is not None:
            station_ids[station] = sbid
    ship_records = _records(_find_top_level_block_fast(game, "ships"))
    systems = _records(_find_top_level_block_fast(game, "galactic_object"))
    station_evidence = []
    for station_id, sbid in station_ids.items():
        rec = ship_records.get(station_id)
        if not rec:
            continue
        fleet = _real_id(_int_scalar(rec, "fleet"))
        owners = fleets_to_country.get(fleet, set())
        if len(owners) != 1:
            continue
        country_id = next(iter(owners))
        if country_id == player_id:
            continue
        date = _scalar(rec, "last_combat_activity")
        if not date or date.startswith("0."):
            continue
        coordinate = _find_named_block(rec, "coordinate")
        system_id = _real_id(_int_scalar(coordinate, "origin"))
        sysrec = systems.get(system_id, "")
        station_evidence.append({
            "starbase_id": sbid, "station_ship_id": station_id,
            "controller_id": country_id, "combat_activity_date": date,
            "system_id": system_id,
            "system_name": _local_name(sysrec, path, f"System {system_id}") if system_id is not None else None,
        })
    return {"battles": battles, "planets": planets, "opponent_stations": station_evidence, "battle_exhaustion": exhaustion_evidence}


def _cached_save(cache_dir: Path, row, war_id: int, player_id: int, parties: set[int], stats: dict | None = None) -> dict:
    sha = str(row["sha256"])
    filename = cache_dir / f"military_v{_REVISION}_{war_id}_{sha}.json"
    signature = [_REVISION, war_id, player_id, sorted(parties), sha]
    if filename.exists():
        try:
            saved = json.loads(filename.read_text(encoding="utf-8"))
            if saved.get("signature") == signature and isinstance(saved.get("value"), dict):
                if stats is not None: stats["cache_hits"] += 1
                return saved["value"]
        except (OSError, ValueError, TypeError):
            pass
    path = Path(str(row["archive_path"]))
    if not path.is_file():
        raise FileNotFoundError(f"Missing archived save: {path.name}")
    # A v0.0.68 cache already contains validated occupation and station
    # evidence. Preserve it and add only the new battle-local fields; a forced
    # reparse of dozens of 50 MB saves would waste minutes after upgrading.
    legacy = cache_dir / f"military_v1_{war_id}_{sha}.json"
    data = None
    if legacy.exists():
        try:
            original = json.loads(legacy.read_text(encoding="utf-8"))
            if (original.get("signature") == [1, war_id, player_id, sorted(parties), sha]
                and isinstance(original.get("value"), dict)
                and all(k in original["value"] for k in ("battles", "planets", "opponent_stations"))):
                if stats is not None: stats["raw_reads"] += 1
                data = {**original["value"], "battle_exhaustion": _exhaustion_only(path, war_id)}
                if stats is not None: stats["legacy_reused"] += 1
        except (OSError, ValueError, TypeError):
            pass
    if data is None:
        if stats is not None: stats["raw_reads"] += 1
        data = _one_save(path, war_id, player_id, parties)
    cache_dir.mkdir(exist_ok=True, parents=True)
    fd, tmp = tempfile.mkstemp(prefix="military_", suffix=".tmp", dir=str(cache_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump({"signature": signature, "value": data}, file, ensure_ascii=False)
        os.replace(tmp, filename)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return data


def investigate_war(db, campaign_id: int, war_id: int, player_id: int,
                    participants: tuple[int, ...], start: str, end: str,
                    progress=None) -> dict:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found")
    parties = set(participants)
    cache_dir = Path(str(campaign["archive_dir"])) / ".historian_evidence"
    # One pre-war snapshot is needed to bound the first observed occupation.
    rows = sorted(db.processed_snapshots(campaign_id), key=lambda x: tuple(int(v) for v in x["game_date"].split(".")))
    eligible = [i for i, r in enumerate(rows) if start <= str(r["game_date"]) <= end]
    if not eligible:
        raise ValueError("No processed saves are available for the selected war")
    first = max(0, eligible[0] - 1)
    selected = rows[first:eligible[-1] + 1]
    # Bound expensive first-time archive investigations; disclose any truncation.
    truncated = len(selected) > 48
    if truncated:
        selected = selected[-48:]
    observations = []
    stats = {"cache_hits": 0, "raw_reads": 0, "legacy_reused": 0}
    if progress is not None:
        progress(0, len(selected), "Preparing archives", stats.copy())
    for i, row in enumerate(selected, 1):
        date = str(row["game_date"])
        observations.append((date, _cached_save(cache_dir, row, war_id, player_id, parties, stats)))
        if progress is not None:
            progress(i, len(selected), date, stats.copy())
    first_battles = {}
    first_exhaustion = {}
    control_changes = []
    starbase_activities = {}
    previous_planets = None
    previous_date = None
    for date, observation in observations:
        planets = observation["planets"]
        for entry in observation.get("battle_exhaustion", []):
            idx = entry["index"]
            if idx not in first_exhaustion:
                first_exhaustion[idx] = {**entry, "first_archive": date}
        for battle in observation["battles"]:
            index = battle["index"]
            if index not in first_battles:
                planet = planets.get(str(battle["colony_id"]), {})
                first_battles[index] = {**battle,
                    "first_archive": date,
                    "planet_name": planet.get("name", f"Colony {battle['colony_id']}"),
                    "date_evidence": "exact_save_field" if battle["date"] else "first_observed_only"}
        if previous_planets is not None:
            for colony_id, after in planets.items():
                before = previous_planets.get(colony_id)
                if before and before.get("controller_id") != after.get("controller_id"):
                    control_changes.append({
                        "colony_id": int(colony_id), "planet_name": after["name"],
                        "owner_id": after["owner_id"],
                        "previous_controller_id": before.get("controller_id"),
                        "later_controller_id": after.get("controller_id"),
                        "before_date": previous_date, "after_date": date,
                        "occupation_observed": after.get("owner_id") != after.get("controller_id"),
                    })
        for sb in observation["opponent_stations"]:
            if not start <= sb["combat_activity_date"] <= end:
                continue
            key = (sb["starbase_id"], sb["combat_activity_date"])
            starbase_activities.setdefault(key, {**sb, "first_observed": date})
        previous_date, previous_planets = date, planets
    return {
        "war_id": war_id, "first_archive": observations[0][0], "last_archive": observations[-1][0],
        "snapshots_examined": len(observations), "partial_window": truncated,
        "ground_battles": sorted(first_battles.values(), key=lambda b: b["index"]),
        "battle_exhaustion_evidence": sorted(first_exhaustion.values(), key=lambda b: b["index"]),
        "planetary_controller_changes": control_changes,
        "enemy_starbase_activity": sorted(starbase_activities.values(), key=lambda x: (x["combat_activity_date"], x["starbase_id"])),
        "disclaimer": "Ground battles with placeholder dates are located by first archived observation, not assigned a fictional battle day. Changes in planetary controller do not prove permanent annexation. Starbase activity proves recorded combat timing, not that a specific station caused particular ship losses. Battle-level exhaustion fields are raw per-battle observations and cannot be added to reconstruct current war exhaustion. Formal tactical winner flags remain unverified.",
    }
