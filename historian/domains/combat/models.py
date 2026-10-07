from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BattleState:
    battle_key: str
    war_id: int
    battle_index: int
    date: str
    battle_type: str
    system_id: int | None
    system_name: str | None
    planet_id: int | None
    planet_name: str | None
    attacker_country_ids: tuple[int, ...]
    defender_country_ids: tuple[int, ...]
    attacker_victory: bool | None
    attacker_losses: int | None
    defender_losses: int | None
    player_side: str
    player_victory: bool | None
    player_losses: int | None
    enemy_losses: int | None


@dataclass(frozen=True)
class WarState:
    war_id: int
    name: str
    start_date: str | None
    player_side: str
    attacker_country_ids: tuple[int, ...]
    defender_country_ids: tuple[int, ...]
    attacker_war_goal: str | None
    defender_war_goal: str | None
    attacker_war_exhaustion: float | None
    defender_war_exhaustion: float | None
    battles: tuple[BattleState, ...]


@dataclass(frozen=True)
class ShipCombatActivityState:
    ship_id: int
    ship_name: str
    ship_type: str
    last_combat_activity: str
    fleet_id: int | None
    fleet_name: str | None
    commander_id: int | None
    commander_name: str | None
    system_id: int | None
    system_name: str | None


@dataclass(frozen=True)
class StarbaseCombatActivityState:
    starbase_id: int
    starbase_name: str
    station_ship_id: int
    last_combat_activity: str
    system_id: int | None
    system_name: str | None


@dataclass(frozen=True)
class EnemyFleetCombatState:
    fleet_id: int | None
    country_id: int | None
    country_name: str | None
    fleet_name: str | None
    ship_count: int | None
    ships_lost: int | None


@dataclass(frozen=True)
class FleetCombatStatsState:
    combat_key: str
    player_fleet_id: int
    player_fleet_name: str
    commander_name: str | None
    start_date: str
    system_id: int | None
    system_name: str | None
    player_ship_count: int | None
    player_ships_lost: int | None
    enemy_fleets: tuple[EnemyFleetCombatState, ...]


@dataclass(frozen=True)
class RelationKillCounterState:
    """Directional relation-counter evidence involving the player country.

    Stellaris stores `killed_ships` inside each side's diplomatic relation
    record. v0.0.38 deliberately preserves the two directional values without
    assigning semantic labels such as "kills inflicted" or "ships lost" until
    that engine-level meaning is independently established.
    """

    other_country_id: int
    other_country_name: str
    player_relation_counter: int
    reciprocal_relation_counter: int
    hostile: bool
    first_contact_hostility: bool
    communications: bool | None


@dataclass(frozen=True)
class CombatSnapshot:
    snapshot_id: int
    game_date: str
    player_country_id: int
    wars: dict[int, WarState]
    battles: dict[str, BattleState]
    ship_activity: dict[int, ShipCombatActivityState] = field(default_factory=dict)
    starbase_activity: dict[int, StarbaseCombatActivityState] = field(default_factory=dict)
    fleet_combat_stats: dict[str, FleetCombatStatsState] = field(default_factory=dict)
    relation_kill_counters: dict[int, RelationKillCounterState] = field(default_factory=dict)
