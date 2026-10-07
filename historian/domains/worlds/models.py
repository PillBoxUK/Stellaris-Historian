from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorldState:
    planet_id: int
    colony_id: int | None
    name: str
    system_id: int | None
    system_name: str | None
    planet_class_key: str | None
    planet_class_name: str | None
    planet_size: int | None
    colonize_date: str | None
    owner_id: int | None
    original_owner_id: int | None
    controller_id: int | None
    governor_id: int | None
    governor_name: str | None
    population: int | None
    employable_pops: int | None
    designation_key: str | None
    designation_name: str | None
    ascension_tier: int | None
    district_count: int
    building_count: int
    is_capital: bool


@dataclass(frozen=True)
class WorldSnapshot:
    snapshot_id: int
    game_date: str
    player_country_id: int
    worlds: dict[int, WorldState]
