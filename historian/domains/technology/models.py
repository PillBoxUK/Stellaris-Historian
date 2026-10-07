from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TechnologyState:
    key: str
    name: str
    level: int


@dataclass(frozen=True)
class TechnologySnapshot:
    snapshot_id: int
    game_date: str
    player_country_id: int
    technologies: dict[str, TechnologyState] = field(default_factory=dict)


@dataclass(frozen=True)
class TechnologyEvent:
    game_date: str
    previous_game_date: str | None
    key: str
    name: str
    level: int
    event_type: str
