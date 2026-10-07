from __future__ import annotations

from .models import DiplomaticRelationState, PoliticsSnapshot


def snapshot_to_dict(snapshot: PoliticsSnapshot) -> dict:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "game_date": snapshot.game_date,
        "player_country_id": snapshot.player_country_id,
        "government_type": snapshot.government_type,
        "authority": snapshot.authority,
        "ethics": list(snapshot.ethics),
        "civics": list(snapshot.civics),
        "ruler_id": snapshot.ruler_id,
        "ruler_name": snapshot.ruler_name,
        "agenda_fields": [[key, value] for key, value in snapshot.agenda_fields],
        "traditions": list(snapshot.traditions),
        "relations": {
            str(country_id): {
                "country_name": relation.country_name,
                "scalars": [[key, value] for key, value in relation.scalars],
                "blocks": list(relation.blocks),
            }
            for country_id, relation in snapshot.relations.items()
        },
    }


def snapshot_from_dict(data: dict, *, snapshot_id: int) -> PoliticsSnapshot:
    relations: dict[int, DiplomaticRelationState] = {}
    for raw_id, value in (data.get("relations") or {}).items():
        if not isinstance(value, dict):
            continue
        country_id = int(raw_id)
        relations[country_id] = DiplomaticRelationState(
            country_id=country_id,
            country_name=str(value.get("country_name") or f"Country {country_id}"),
            scalars=tuple(
                (str(item[0]), str(item[1]))
                for item in (value.get("scalars") or [])
                if isinstance(item, (list, tuple)) and len(item) == 2
            ),
            blocks=tuple(str(item) for item in (value.get("blocks") or [])),
        )

    return PoliticsSnapshot(
        snapshot_id=snapshot_id,
        game_date=str(data.get("game_date") or ""),
        player_country_id=(
            int(data["player_country_id"])
            if data.get("player_country_id") is not None
            else None
        ),
        government_type=(
            str(data["government_type"])
            if data.get("government_type") is not None
            else None
        ),
        authority=(
            str(data["authority"])
            if data.get("authority") is not None
            else None
        ),
        ethics=tuple(str(item) for item in (data.get("ethics") or [])),
        civics=tuple(str(item) for item in (data.get("civics") or [])),
        ruler_id=(
            int(data["ruler_id"])
            if data.get("ruler_id") is not None
            else None
        ),
        ruler_name=(
            str(data["ruler_name"])
            if data.get("ruler_name") is not None
            else None
        ),
        agenda_fields=tuple(
            (str(item[0]), str(item[1]))
            for item in (data.get("agenda_fields") or [])
            if isinstance(item, (list, tuple)) and len(item) == 2
        ),
        traditions=tuple(str(item) for item in (data.get("traditions") or [])),
        relations=relations,
    )
