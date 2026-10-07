from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import json

from .db import Database
from .historical_events import HistoricalEvent, synthesize_historical_events
from .domains.combat import (
    CACHE_COMPONENT_NAME as COMBAT_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as COMBAT_COMPONENT_VERSION,
    CombatEpisode,
    CorrelatedEngagement,
    derive_combat_episodes,
    derive_correlated_engagements,
    derive_direct_combat_episodes,
)
from .domains.combat.cache import snapshot_from_dict as combat_snapshot_from_dict
from .domains.science import (
    CACHE_COMPONENT_NAME as SCIENCE_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as SCIENCE_COMPONENT_VERSION,
)
from .domains.science.cache import snapshot_from_dict as science_snapshot_from_dict
from .domains.ships import (
    CACHE_COMPONENT_NAME as SHIP_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as SHIP_COMPONENT_VERSION,
)
from .domains.ships.cache import snapshot_from_dict as ship_snapshot_from_dict
from .domains.technology import (
    CACHE_COMPONENT_NAME as TECHNOLOGY_COMPONENT_NAME,
    CACHE_COMPONENT_VERSION as TECHNOLOGY_COMPONENT_VERSION,
)
from .domains.technology.cache import snapshot_from_dict as technology_snapshot_from_dict


@dataclass(frozen=True)
class PresentationHistory:
    """Shared evidence bundle consumed by polished presentation views.

    Review Campaign remains the evidence-building step. Timeline and Scribes read
    only the database plus already-populated snapshot-cache components and then
    synthesize the same Historical Event Layer in memory. Neither renderer
    reparses Ironman saves or mutates campaign evidence.
    """

    events: tuple[HistoricalEvent, ...]
    combat_episodes: tuple[CombatEpisode, ...]
    combat_engagements: tuple[CorrelatedEngagement, ...]
    combat_snapshots: tuple[object, ...]
    ship_snapshots: tuple[object, ...]
    science_snapshots: tuple[object, ...]
    technology_snapshots: tuple[object, ...]


def _local_archive_dir(db: Database, campaign) -> Path:
    configured = Path(str(campaign["archive_dir"]))
    if configured.exists():
        return configured

    # A copied/backed-up database can retain a Windows archive path even while
    # being inspected elsewhere. Keep the existing fallback used by Historian's
    # other cache readers so presentation remains deterministic in test copies.
    name = PureWindowsPath(str(campaign["archive_dir"])).name
    fallback = db.path.parent / "campaigns" / name
    return fallback if fallback.exists() else configured


def _cached_component_snapshots(
    db: Database,
    campaign_id: int,
    *,
    component_name: str,
    component_version: int,
    loader,
) -> list:
    campaign = db.campaign(campaign_id)
    if campaign is None:
        return []

    cache_dir = _local_archive_dir(db, campaign) / ".historian_cache"
    if not cache_dir.exists():
        return []

    result: list = []
    for snapshot in db.all_snapshots(campaign_id):
        path = cache_dir / f"{snapshot['sha256']}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        component = payload.get("components", {}).get(component_name, {})
        if int(component.get("version", 0) or 0) != int(component_version):
            continue
        data = component.get("data")
        if not isinstance(data, dict):
            continue
        try:
            result.append(loader(data, snapshot_id=int(snapshot["id"])))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def build_presentation_history(db: Database, campaign_id: int) -> PresentationHistory:
    """Recreate the presentation-neutral Historical Event Layer from cached evidence.

    The database already contains the reviewed people/world/ship histories. Rawer
    science/combat/technology state remains in the per-snapshot cache. Combining
    those sources here gives Timeline and Scribes exactly the same event model
    that Review Campaign writes to Historical_Event_Debug.txt.
    """
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError("Campaign does not exist.")

    ship_snapshots = _cached_component_snapshots(
        db,
        campaign_id,
        component_name=SHIP_COMPONENT_NAME,
        component_version=SHIP_COMPONENT_VERSION,
        loader=ship_snapshot_from_dict,
    )
    combat_snapshots = _cached_component_snapshots(
        db,
        campaign_id,
        component_name=COMBAT_COMPONENT_NAME,
        component_version=COMBAT_COMPONENT_VERSION,
        loader=combat_snapshot_from_dict,
    )
    science_snapshots = _cached_component_snapshots(
        db,
        campaign_id,
        component_name=SCIENCE_COMPONENT_NAME,
        component_version=SCIENCE_COMPONENT_VERSION,
        loader=science_snapshot_from_dict,
    )
    technology_snapshots = _cached_component_snapshots(
        db,
        campaign_id,
        component_name=TECHNOLOGY_COMPONENT_NAME,
        component_version=TECHNOLOGY_COMPONENT_VERSION,
        loader=technology_snapshot_from_dict,
    )

    correlated_engagements = derive_correlated_engagements(
        ship_snapshots,
        combat_snapshots,
    ) if ship_snapshots and combat_snapshots else []
    direct_episodes = derive_direct_combat_episodes(combat_snapshots) if combat_snapshots else []
    combat_episodes = derive_combat_episodes(
        combat_snapshots,
        correlated_engagements,
        direct_episodes,
    ) if combat_snapshots else []

    history_entries = [dict(row) for row in db.history_entries(campaign_id)]
    ship_history = {
        "events": [dict(row) for row in db.ship_fleet_events(campaign_id, visible_only=False)]
    }
    leader_history = {
        "events": [dict(row) for row in db.leader_career_events(campaign_id, visible_only=False)]
    }
    world_history = {
        "events": [dict(row) for row in db.world_history_events(campaign_id, visible_only=False)]
    }
    politics_events = [
        dict(row) for row in db.politics_events(campaign_id, visible_only=False)
    ]

    events = synthesize_historical_events(
        history_entries=history_entries,
        ship_history=ship_history,
        leader_history=leader_history,
        world_history=world_history,
        science_snapshots=science_snapshots,
        combat_engagements=correlated_engagements,
        direct_combat_episodes=direct_episodes,
        combat_episodes=combat_episodes,
        technology_snapshots=technology_snapshots,
        politics_events=politics_events,
    )

    return PresentationHistory(
        events=tuple(events),
        combat_episodes=tuple(combat_episodes),
        combat_engagements=tuple(correlated_engagements),
        combat_snapshots=tuple(combat_snapshots),
        ship_snapshots=tuple(ship_snapshots),
        science_snapshots=tuple(science_snapshots),
        technology_snapshots=tuple(technology_snapshots),
    )
