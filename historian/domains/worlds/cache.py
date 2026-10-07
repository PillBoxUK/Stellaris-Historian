from __future__ import annotations

from dataclasses import asdict

from .models import WorldSnapshot, WorldState


def snapshot_to_dict(snapshot: WorldSnapshot) -> dict:
    return {
        "game_date": snapshot.game_date,
        "player_country_id": snapshot.player_country_id,
        "worlds": {
            str(key): asdict(value)
            for key, value in snapshot.worlds.items()
        },
    }


def snapshot_from_dict(
    data: dict,
    *,
    snapshot_id: int,
) -> WorldSnapshot:
    worlds = {
        int(key): WorldState(**value)
        for key, value in data.get("worlds", {}).items()
    }

    return WorldSnapshot(
        snapshot_id=snapshot_id,
        game_date=data["game_date"],
        player_country_id=int(data["player_country_id"]),
        worlds=worlds,
    )
