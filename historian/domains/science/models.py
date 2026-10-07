from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchaeologySiteState:
    site_id: int
    type_key: str
    title: str
    planet_id: int | None
    location_name: str | None
    visible_to_player: bool
    last_excavator_country: int | None
    excavator_fleet_id: int | None
    excavator_fleet_name: str | None
    scientist_id: int | None
    scientist_name: str | None
    chapter_index: int | None
    clues: int | None
    difficulty: int | None
    days_left: int | None
    player_completion_dates: tuple[str, ...]


@dataclass(frozen=True)
class SpecialProjectState:
    project_id: int
    project_key: str
    title: str
    planet_id: int | None
    location_name: str | None
    linked_ship_id: int | None
    linked_ship_name: str | None
    scientist_id: int | None
    scientist_name: str | None
    ai_research_date: str | None


@dataclass(frozen=True)
class SituationState:
    situation_id: int
    type_key: str
    title: str
    progress: float | None
    last_month_progress: float | None
    approach_key: str | None
    target_type: str | None
    target_id: int | None


@dataclass(frozen=True)
class ScienceSnapshot:
    snapshot_id: int
    game_date: str
    player_country_id: int
    archaeology_sites: dict[int, ArchaeologySiteState]
    special_projects: dict[int, SpecialProjectState]
    situations: dict[int, SituationState]
    anomaly_ids: tuple[int, ...]
