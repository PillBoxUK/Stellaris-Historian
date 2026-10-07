from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiplomaticRelationState:
    country_id: int
    country_name: str
    scalars: tuple[tuple[str, str], ...] = ()
    blocks: tuple[str, ...] = ()

    @property
    def scalar_map(self) -> dict[str, str]:
        return dict(self.scalars)


@dataclass(frozen=True)
class PoliticsSnapshot:
    snapshot_id: int
    game_date: str
    player_country_id: int | None
    government_type: str | None
    authority: str | None
    ethics: tuple[str, ...] = ()
    civics: tuple[str, ...] = ()
    ruler_id: int | None = None
    ruler_name: str | None = None
    agenda_fields: tuple[tuple[str, str], ...] = ()
    traditions: tuple[str, ...] = ()
    relations: dict[int, DiplomaticRelationState] = field(default_factory=dict)
