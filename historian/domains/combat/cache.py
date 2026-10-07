from __future__ import annotations

from dataclasses import asdict

from .models import (
    BattleState,
    CombatSnapshot,
    EnemyFleetCombatState,
    FleetCombatStatsState,
    RelationKillCounterState,
    ShipCombatActivityState,
    StarbaseCombatActivityState,
    WarState,
)


def _battle_from_dict(value: dict) -> BattleState:
    return BattleState(
        **{
            **value,
            "attacker_country_ids": tuple(
                int(item) for item in value.get("attacker_country_ids", ())
            ),
            "defender_country_ids": tuple(
                int(item) for item in value.get("defender_country_ids", ())
            ),
        }
    )


def snapshot_to_dict(snapshot: CombatSnapshot) -> dict:
    return {
        "game_date": snapshot.game_date,
        "player_country_id": snapshot.player_country_id,
        "wars": {
            str(key): {
                **asdict(value),
                "battles": [asdict(battle) for battle in value.battles],
            }
            for key, value in snapshot.wars.items()
        },
        "battles": {
            key: asdict(value)
            for key, value in snapshot.battles.items()
        },
        "ship_activity": {
            str(key): asdict(value)
            for key, value in snapshot.ship_activity.items()
        },
        "starbase_activity": {
            str(key): asdict(value)
            for key, value in snapshot.starbase_activity.items()
        },
        "fleet_combat_stats": {
            key: asdict(value)
            for key, value in snapshot.fleet_combat_stats.items()
        },
        "relation_kill_counters": {
            str(key): asdict(value)
            for key, value in snapshot.relation_kill_counters.items()
        },
    }


def snapshot_from_dict(data: dict, *, snapshot_id: int) -> CombatSnapshot:
    wars: dict[int, WarState] = {}
    for key, value in data.get("wars", {}).items():
        battles = tuple(
            _battle_from_dict(item)
            for item in value.get("battles", ())
        )
        wars[int(key)] = WarState(
            **{
                **value,
                "war_id": int(value.get("war_id", key)),
                "attacker_country_ids": tuple(
                    int(item) for item in value.get("attacker_country_ids", ())
                ),
                "defender_country_ids": tuple(
                    int(item) for item in value.get("defender_country_ids", ())
                ),
                "battles": battles,
            }
        )

    battles = {
        key: _battle_from_dict(value)
        for key, value in data.get("battles", {}).items()
    }

    ship_activity = {
        int(key): ShipCombatActivityState(**value)
        for key, value in data.get("ship_activity", {}).items()
    }

    starbase_activity = {
        int(key): StarbaseCombatActivityState(**value)
        for key, value in data.get("starbase_activity", {}).items()
    }

    fleet_combat_stats = {}
    for key, value in data.get("fleet_combat_stats", {}).items():
        enemies = tuple(
            EnemyFleetCombatState(**enemy)
            for enemy in value.get("enemy_fleets", ())
        )
        fleet_combat_stats[key] = FleetCombatStatsState(
            **{**value, "enemy_fleets": enemies}
        )

    relation_kill_counters = {
        int(key): RelationKillCounterState(**value)
        for key, value in data.get("relation_kill_counters", {}).items()
    }

    return CombatSnapshot(
        snapshot_id=snapshot_id,
        game_date=data["game_date"],
        player_country_id=int(data["player_country_id"]),
        wars=wars,
        battles=battles,
        ship_activity=ship_activity,
        starbase_activity=starbase_activity,
        fleet_combat_stats=fleet_combat_stats,
        relation_kill_counters=relation_kill_counters,
    )
