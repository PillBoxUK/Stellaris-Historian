from __future__ import annotations

from dataclasses import asdict

from .models import DeadLeaderState, LeaderSnapshot, LeaderState


def snapshot_to_dict(snapshot: LeaderSnapshot) -> dict:
    return {
        "game_date": snapshot.game_date,
        "leaders": {
            str(key): {
                **asdict(value),
                "traits": list(value.traits),
                "trait_names": list(value.trait_names),
                "raw_keys": list(value.raw_keys),
                "flag_values": [list(pair) for pair in value.flag_values],
                "variable_values": [list(pair) for pair in value.variable_values],
            }
            for key, value in snapshot.leaders.items()
        },
        "dead_leaders": {
            str(key): {
                **asdict(value),
                "raw_keys": list(value.raw_keys),
            }
            for key, value in snapshot.dead_leaders.items()
        },
        "active_record_keys": list(snapshot.active_record_keys),
        "active_flag_keys": list(snapshot.active_flag_keys),
        "active_variable_keys": list(snapshot.active_variable_keys),
        "dead_record_keys": list(snapshot.dead_record_keys),
        "last_notification_id": snapshot.last_notification_id,
        "last_event_id": snapshot.last_event_id,
        "selected_player_event_count": snapshot.selected_player_event_count,
        "tombstoned_leader_ids": list(snapshot.tombstoned_leader_ids),
        "saved_event_target_names": {
            str(key): list(value)
            for key, value in snapshot.saved_event_target_names.items()
        },
    }


def snapshot_from_dict(
    data: dict,
    *,
    snapshot_id: int,
) -> LeaderSnapshot:
    leaders: dict[int, LeaderState] = {}

    for key, value in data.get("leaders", {}).items():
        payload = dict(value)
        payload["traits"] = tuple(payload.get("traits", []))
        payload["trait_names"] = tuple(payload.get("trait_names", []))
        payload["raw_keys"] = tuple(payload.get("raw_keys", []))
        payload["flag_values"] = tuple(
            (str(pair[0]), str(pair[1]))
            for pair in payload.get("flag_values", [])
            if isinstance(pair, (list, tuple)) and len(pair) >= 2
        )
        payload["variable_values"] = tuple(
            (str(pair[0]), str(pair[1]))
            for pair in payload.get("variable_values", [])
            if isinstance(pair, (list, tuple)) and len(pair) >= 2
        )
        leaders[int(key)] = LeaderState(**payload)

    dead_leaders: dict[int, DeadLeaderState] = {}
    for key, value in data.get("dead_leaders", {}).items():
        payload = dict(value)
        payload["raw_keys"] = tuple(payload.get("raw_keys", []))
        dead_leaders[int(key)] = DeadLeaderState(**payload)

    return LeaderSnapshot(
        snapshot_id=snapshot_id,
        game_date=data["game_date"],
        leaders=leaders,
        dead_leaders=dead_leaders,
        active_record_keys=tuple(data.get("active_record_keys", [])),
        active_flag_keys=tuple(data.get("active_flag_keys", [])),
        active_variable_keys=tuple(data.get("active_variable_keys", [])),
        dead_record_keys=tuple(data.get("dead_record_keys", [])),
        last_notification_id=data.get("last_notification_id"),
        last_event_id=data.get("last_event_id"),
        selected_player_event_count=int(data.get("selected_player_event_count", 0) or 0),
        tombstoned_leader_ids=tuple(int(v) for v in data.get("tombstoned_leader_ids", [])),
        saved_event_target_names={
            int(key): tuple(value or ())
            for key, value in data.get("saved_event_target_names", {}).items()
        },
    )
