from __future__ import annotations

from dataclasses import asdict

from .models import (
    ArchaeologySiteState,
    ScienceSnapshot,
    SituationState,
    SpecialProjectState,
)


def snapshot_to_dict(snapshot: ScienceSnapshot) -> dict:
    return {
        "game_date": snapshot.game_date,
        "player_country_id": snapshot.player_country_id,
        "archaeology_sites": {
            str(key): asdict(value)
            for key, value in snapshot.archaeology_sites.items()
        },
        "special_projects": {
            str(key): asdict(value)
            for key, value in snapshot.special_projects.items()
        },
        "situations": {
            str(key): asdict(value)
            for key, value in snapshot.situations.items()
        },
        "anomaly_ids": list(snapshot.anomaly_ids),
    }


def snapshot_from_dict(data: dict, *, snapshot_id: int) -> ScienceSnapshot:
    archaeology_sites = {
        int(key): ArchaeologySiteState(
            **{
                **value,
                "player_completion_dates": tuple(value.get("player_completion_dates", ())),
            }
        )
        for key, value in data.get("archaeology_sites", {}).items()
    }

    special_projects = {
        int(key): SpecialProjectState(**value)
        for key, value in data.get("special_projects", {}).items()
    }

    situations = {
        int(key): SituationState(**value)
        for key, value in data.get("situations", {}).items()
    }

    return ScienceSnapshot(
        snapshot_id=snapshot_id,
        game_date=data["game_date"],
        player_country_id=int(data["player_country_id"]),
        archaeology_sites=archaeology_sites,
        special_projects=special_projects,
        situations=situations,
        anomaly_ids=tuple(int(value) for value in data.get("anomaly_ids", ())),
    )
