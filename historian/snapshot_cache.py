from __future__ import annotations

from pathlib import Path
import json
import os
import shutil

from .domains.people import CACHE_COMPONENT_NAME as LEADER_COMPONENT_NAME
from .domains.people import CACHE_COMPONENT_VERSION as LEADER_COMPONENT_VERSION
from .domains.people.models import LeaderSnapshot
from .domains.people.parser import extract_leader_snapshot
from .domains.people.cache import (
    snapshot_from_dict as leader_snapshot_from_dict,
    snapshot_to_dict as leader_snapshot_to_dict,
)
from .save_reader import (
    EmpireProfile,
    empire_profile_from_text,
    read_save_texts,
)
from .domains.worlds import (
    CACHE_COMPONENT_NAME as WORLD_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as WORLD_COMPONENT_VERSION,
    WorldSnapshot,
    extract_world_snapshot,
)
from .domains.worlds.cache import (
    snapshot_from_dict as world_snapshot_from_dict,
    snapshot_to_dict as world_snapshot_to_dict,
)
from .domains.ships import (
    CACHE_COMPONENT_NAME as SHIP_FLEET_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as SHIP_FLEET_COMPONENT_VERSION,
    ShipFleetSnapshot,
    extract_ship_fleet_snapshot,
)
from .domains.ships.cache import (
    snapshot_from_dict as ship_snapshot_from_dict,
    snapshot_to_dict as ship_snapshot_to_dict,
)
from .domains.science import (
    CACHE_COMPONENT_NAME as SCIENCE_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as SCIENCE_COMPONENT_VERSION,
    ScienceSnapshot,
    extract_science_snapshot,
)
from .domains.science.cache import (
    snapshot_from_dict as science_snapshot_from_dict,
    snapshot_to_dict as science_snapshot_to_dict,
)

from .domains.combat import (
    CACHE_COMPONENT_NAME as COMBAT_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as COMBAT_COMPONENT_VERSION,
    CombatSnapshot,
    extract_combat_snapshot,
)
from .domains.combat.cache import (
    snapshot_from_dict as combat_snapshot_from_dict,
    snapshot_to_dict as combat_snapshot_to_dict,
)
from .domains.technology import (
    CACHE_COMPONENT_NAME as TECHNOLOGY_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as TECHNOLOGY_COMPONENT_VERSION,
    TechnologySnapshot,
    extract_technology_snapshot,
)
from .domains.technology.cache import (
    snapshot_from_dict as technology_snapshot_from_dict,
    snapshot_to_dict as technology_snapshot_to_dict,
)
from .domains.politics import (
    CACHE_COMPONENT_NAME as POLITICS_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as POLITICS_COMPONENT_VERSION,
    PoliticsSnapshot,
    extract_politics_snapshot,
)
from .domains.politics.cache import (
    snapshot_from_dict as politics_snapshot_from_dict,
    snapshot_to_dict as politics_snapshot_to_dict,
)


CACHE_SCHEMA_VERSION = 1
PROFILE_COMPONENT_VERSION = 1


def campaign_cache_dir(
    archive_dir: Path,
) -> Path:
    return Path(
        archive_dir
    ) / ".historian_cache"


def _cache_path(
    cache_dir: Path,
    source_sha256: str,
) -> Path:
    return cache_dir / f"{source_sha256}.json"


def _profile_to_dict(
    profile: EmpireProfile,
) -> dict:
    return {
        "empire_name": profile.empire_name,
        "game_date": profile.game_date,
        "version": profile.version,
        "player_country_id": profile.player_country_id,
        "government_type": profile.government_type,
        "authority": profile.authority,
        "origin": profile.origin,
        "ethics": list(
            profile.ethics
        ),
        "civics": list(
            profile.civics
        ),
    }


def _profile_from_dict(
    data: dict,
) -> EmpireProfile:
    return EmpireProfile(
        empire_name=data[
            "empire_name"
        ],
        game_date=data[
            "game_date"
        ],
        version=data.get(
            "version"
        ),
        player_country_id=data.get(
            "player_country_id"
        ),
        government_type=data.get(
            "government_type"
        ),
        authority=data.get(
            "authority"
        ),
        origin=data.get(
            "origin"
        ),
        ethics=tuple(
            data.get(
                "ethics",
                [],
            )
        ),
        civics=tuple(
            data.get(
                "civics",
                [],
            )
        ),
    )







def _fingerprint(
    path: Path,
) -> tuple[int, int]:
    stat = path.stat()

    return (
        stat.st_size,
        stat.st_mtime_ns,
    )


def _load_container(
    path: Path,
    *,
    source_sha256: str,
    size: int,
    mtime_ns: int,
) -> dict | None:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    if payload.get(
        "cache_schema_version"
    ) != CACHE_SCHEMA_VERSION:
        return None

    if payload.get(
        "source_sha256"
    ) != source_sha256:
        return None

    if (
        payload.get(
            "archive_size"
        ) != size
        or payload.get(
            "archive_mtime_ns"
        ) != mtime_ns
    ):
        return None

    return payload


def _component_data(
    payload: dict | None,
    name: str,
    version: int,
) -> dict | None:
    if payload is None:
        return None

    component = payload.get(
        "components",
        {},
    ).get(
        name,
        {},
    )

    if component.get(
        "version"
    ) != version:
        return None

    data = component.get(
        "data"
    )

    return (
        data
        if isinstance(
            data,
            dict,
        )
        else None
    )


def _write(
    path: Path,
    *,
    source_sha256: str,
    size: int,
    mtime_ns: int,
    profile: EmpireProfile,
    ship_snapshot: ShipFleetSnapshot,
    leader_snapshot: LeaderSnapshot,
    world_snapshot: WorldSnapshot,
    science_snapshot: ScienceSnapshot,
    combat_snapshot: CombatSnapshot,
    technology_snapshot: TechnologySnapshot,
    politics_snapshot: PoliticsSnapshot | None,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "archive_size": size,
        "archive_mtime_ns": mtime_ns,
        "components": {
            "profile": {
                "version": PROFILE_COMPONENT_VERSION,
                "data": _profile_to_dict(
                    profile
                ),
            },
            SHIP_FLEET_COMPONENT_NAME: {
                "version": SHIP_FLEET_COMPONENT_VERSION,
                "data": ship_snapshot_to_dict(
                    ship_snapshot
                ),
            },
            LEADER_COMPONENT_NAME: {
                "version": LEADER_COMPONENT_VERSION,
                "data": leader_snapshot_to_dict(leader_snapshot),
            },
            WORLD_COMPONENT_NAME: {
                "version": WORLD_COMPONENT_VERSION,
                "data": world_snapshot_to_dict(
                    world_snapshot
                ),
            },
            SCIENCE_COMPONENT_NAME: {
                "version": SCIENCE_COMPONENT_VERSION,
                "data": science_snapshot_to_dict(
                    science_snapshot
                ),
            },
            COMBAT_COMPONENT_NAME: {
                "version": COMBAT_COMPONENT_VERSION,
                "data": combat_snapshot_to_dict(
                    combat_snapshot
                ),
            },
            TECHNOLOGY_COMPONENT_NAME: {
                "version": TECHNOLOGY_COMPONENT_VERSION,
                "data": technology_snapshot_to_dict(
                    technology_snapshot
                ),
            },
            POLITICS_COMPONENT_NAME: {
                "version": POLITICS_COMPONENT_VERSION,
                "data": (
                    politics_snapshot_to_dict(politics_snapshot)
                    if politics_snapshot is not None
                    else None
                ),
            },
        },
    }

    temp = path.with_suffix(
        ".tmp"
    )

    temp.write_text(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(
                ",",
                ":",
            ),
        ),
        encoding="utf-8",
        newline="\n",
    )

    os.replace(
        temp,
        path,
    )


def clear_campaign_cache(
    archive_dir: Path,
) -> int:
    """
    Delete the campaign's disposable parsed-snapshot cache.

    Returns the number of cached JSON files that existed before deletion.
    Archived Stellaris .sav files are never touched.
    """
    cache_dir = campaign_cache_dir(
        archive_dir
    )

    if not cache_dir.exists():
        return 0

    cached_files = sum(
        1
        for path in cache_dir.rglob(
            "*.json"
        )
        if path.is_file()
    )

    shutil.rmtree(
        cache_dir
    )

    return cached_files


def load_or_parse_snapshot(
    *,
    archive_path: Path,
    source_save: Path,
    source_sha256: str,
    snapshot_id: int,
    cache_dir: Path,
) -> tuple[
    EmpireProfile,
    ShipFleetSnapshot,
    LeaderSnapshot,
    WorldSnapshot,
    ScienceSnapshot,
    CombatSnapshot,
    TechnologySnapshot,
    PoliticsSnapshot | None,
    str,
]:
    """
    Return profile, ship/fleet state, leader state, world state, science evidence, combat evidence, technology evidence, politics/diplomacy evidence and cache status.

    cache status is one of:
      hit    - all current parser components came from the persistent cache
      extend - the cache container/profile was valid but one or more parser
               components were upgraded and refreshed from one raw save read
      miss   - the cache was missing/invalid and the raw save was fully parsed
    """
    archive_path = Path(
        archive_path
    )
    cache_dir = Path(
        cache_dir
    )

    size, mtime_ns = _fingerprint(
        archive_path
    )

    path = _cache_path(
        cache_dir,
        source_sha256,
    )

    payload = _load_container(
        path,
        source_sha256=source_sha256,
        size=size,
        mtime_ns=mtime_ns,
    )

    profile_data = _component_data(
        payload,
        "profile",
        PROFILE_COMPONENT_VERSION,
    )

    ship_data = _component_data(
        payload,
        SHIP_FLEET_COMPONENT_NAME,
        SHIP_FLEET_COMPONENT_VERSION,
    )

    leader_data = _component_data(
        payload,
        LEADER_COMPONENT_NAME,
        LEADER_COMPONENT_VERSION,
    )

    world_data = _component_data(
        payload,
        WORLD_COMPONENT_NAME,
        WORLD_COMPONENT_VERSION,
    )

    science_data = _component_data(
        payload,
        SCIENCE_COMPONENT_NAME,
        SCIENCE_COMPONENT_VERSION,
    )

    combat_data = _component_data(
        payload,
        COMBAT_COMPONENT_NAME,
        COMBAT_COMPONENT_VERSION,
    )

    technology_data = _component_data(
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
    ship_snapshot = None
    leader_snapshot = None
    world_snapshot = None
    science_snapshot = None
    combat_snapshot = None
    technology_snapshot = None
    politics_snapshot = None

    try:
        if profile_data is not None:
            profile = _profile_from_dict(
                profile_data
            )

        if ship_data is not None:
            ship_snapshot = ship_snapshot_from_dict(
                ship_data,
                snapshot_id=snapshot_id,
            )

        if leader_data is not None:
            leader_snapshot = leader_snapshot_from_dict(
                leader_data,
                snapshot_id=snapshot_id,
            )

        if world_data is not None:
            world_snapshot = world_snapshot_from_dict(
                world_data,
                snapshot_id=snapshot_id,
            )

        if science_data is not None:
            science_snapshot = science_snapshot_from_dict(
                science_data,
                snapshot_id=snapshot_id,
            )

        if combat_data is not None:
            combat_snapshot = combat_snapshot_from_dict(
                combat_data,
                snapshot_id=snapshot_id,
            )

        if technology_data is not None:
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
        KeyError,
        TypeError,
        ValueError,
    ):
        profile = None
        ship_snapshot = None
        leader_snapshot = None
        world_snapshot = None
        science_snapshot = None
        combat_snapshot = None
        technology_snapshot = None
        politics_snapshot = None

    if (
        profile is not None
        and ship_snapshot is not None
        and leader_snapshot is not None
        and world_snapshot is not None
        and science_snapshot is not None
        and combat_snapshot is not None
        and technology_snapshot is not None
        and politics_snapshot is not None
    ):
        return (
            profile,
            ship_snapshot,
            leader_snapshot,
            world_snapshot,
            science_snapshot,
            combat_snapshot,
            technology_snapshot,
            politics_snapshot,
            "hit",
        )

    # A valid cache container may contain older component versions. Reuse
    # the profile and refresh only the parsing components that need current raw
    # save data. Leaders are refreshed whenever ship/fleet parsing changes
    # because assignments can depend on the newly parsed ship/fleet state.
    if profile is not None:
        _, gamestate = read_save_texts(
            archive_path
        )

        ship_was_refreshed = (
            ship_snapshot is None
        )

        if ship_snapshot is None:
            ship_snapshot = extract_ship_fleet_snapshot(
                archive_path,
                source_save=source_save,
                snapshot_id=snapshot_id,
                profile=profile,
                gamestate=gamestate,
            )

        if (
            leader_snapshot is None
            or ship_was_refreshed
        ):
            leader_snapshot = extract_leader_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
                ship_snapshot=ship_snapshot,
            )

        if world_snapshot is None:
            world_snapshot = extract_world_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
                leader_names={
                    leader_id: leader.name
                    for leader_id, leader in leader_snapshot.leaders.items()
                },
            )

        if science_snapshot is None:
            science_snapshot = extract_science_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
                ship_snapshot=ship_snapshot,
                leader_snapshot=leader_snapshot,
            )

        if combat_snapshot is None:
            combat_snapshot = extract_combat_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
                ship_snapshot=ship_snapshot,
            )

        if technology_snapshot is None:
            technology_snapshot = extract_technology_snapshot(
                gamestate=gamestate,
                profile=profile,
                source_save=source_save,
                snapshot_id=snapshot_id,
            )

        if politics_snapshot is None:
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
            path,
            source_sha256=source_sha256,
            size=size,
            mtime_ns=mtime_ns,
            profile=profile,
            ship_snapshot=ship_snapshot,
            leader_snapshot=leader_snapshot,
            world_snapshot=world_snapshot,
            science_snapshot=science_snapshot,
            combat_snapshot=combat_snapshot,
            technology_snapshot=technology_snapshot,
            politics_snapshot=politics_snapshot,
        )

        return (
            profile,
            ship_snapshot,
            leader_snapshot,
            world_snapshot,
            science_snapshot,
            combat_snapshot,
            technology_snapshot,
            politics_snapshot,
            "extend",
        )

    # Full miss. One ZIP read is shared by all current parsers.
    meta, gamestate = read_save_texts(
        archive_path
    )

    profile = empire_profile_from_text(
        meta,
        gamestate,
    )

    ship_snapshot = extract_ship_fleet_snapshot(
        archive_path,
        source_save=source_save,
        snapshot_id=snapshot_id,
        profile=profile,
        gamestate=gamestate,
    )

    leader_snapshot = extract_leader_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
        ship_snapshot=ship_snapshot,
    )

    world_snapshot = extract_world_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
        leader_names={
            leader_id: leader.name
            for leader_id, leader in leader_snapshot.leaders.items()
        },
    )

    science_snapshot = extract_science_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
        ship_snapshot=ship_snapshot,
        leader_snapshot=leader_snapshot,
    )

    combat_snapshot = extract_combat_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
        ship_snapshot=ship_snapshot,
    )

    technology_snapshot = extract_technology_snapshot(
        gamestate=gamestate,
        profile=profile,
        source_save=source_save,
        snapshot_id=snapshot_id,
    )

    try:
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
        path,
        source_sha256=source_sha256,
        size=size,
        mtime_ns=mtime_ns,
        profile=profile,
        ship_snapshot=ship_snapshot,
        leader_snapshot=leader_snapshot,
        world_snapshot=world_snapshot,
        science_snapshot=science_snapshot,
        combat_snapshot=combat_snapshot,
        technology_snapshot=technology_snapshot,
        politics_snapshot=politics_snapshot,
    )

    return (
        profile,
        ship_snapshot,
        leader_snapshot,
        world_snapshot,
        science_snapshot,
        combat_snapshot,
        technology_snapshot,
        politics_snapshot,
        "miss",
    )
