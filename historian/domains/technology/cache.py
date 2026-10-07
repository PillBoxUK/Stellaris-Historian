from __future__ import annotations

from .models import TechnologySnapshot, TechnologyState


def snapshot_to_dict(snapshot: TechnologySnapshot) -> dict:
    return {
        "game_date": snapshot.game_date,
        "player_country_id": snapshot.player_country_id,
        "technologies": {
            key: {
                "key": state.key,
                "name": state.name,
                "level": state.level,
            }
            for key, state in snapshot.technologies.items()
        },
    }


def snapshot_from_dict(data: dict, *, snapshot_id: int) -> TechnologySnapshot:
    technologies = {
        str(key): TechnologyState(
            key=str(value.get("key", key)),
            name=str(value.get("name") or value.get("key") or key),
            level=int(value.get("level", 1)),
        )
        for key, value in data.get("technologies", {}).items()
        if isinstance(value, dict)
    }
    return TechnologySnapshot(
        snapshot_id=snapshot_id,
        game_date=str(data["game_date"]),
        player_country_id=int(data["player_country_id"]),
        technologies=technologies,
    )
