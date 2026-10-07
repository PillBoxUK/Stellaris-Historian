from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ShipState:
    ship_id: int
    name: str
    ship_type: str
    ship_size: str | None
    construction_date: str | None
    fleet_id: int | None
    fleet_name: str | None
    commander_id: int | None
    commander_name: str | None
    design_id: int | None = None


@dataclass(frozen=True)
class FleetState:
    fleet_id: int
    name: str
    ship_class: str
    ship_ids: tuple[int, ...]
    home_base: str | None
    commander_id: int | None
    commander_name: str | None


@dataclass(frozen=True)
class ShipyardState:
    starbase_id: int
    name: str
    station_ship_id: int | None
    queue_id: int | None


@dataclass(frozen=True)
class BuildOrderState:
    item_id: int
    starbase_id: int
    starbase_name: str
    design_id: int | None
    target_fleet_id: int | None
    target_fleet_template_id: int | None


@dataclass(frozen=True)
class ShipFleetSnapshot:
    snapshot_id: int
    game_date: str
    ships: dict[int, ShipState]
    fleets: dict[int, FleetState]
    shipyards: dict[int, ShipyardState] = field(default_factory=dict)
    build_orders: tuple[BuildOrderState, ...] = ()
