from __future__ import annotations

from dataclasses import asdict

from .models import BuildOrderState, FleetState, ShipFleetSnapshot, ShipState, ShipyardState


def snapshot_to_dict(snapshot: ShipFleetSnapshot) -> dict:
    return {
        "game_date": snapshot.game_date,
        "ships": {str(key): asdict(value) for key, value in snapshot.ships.items()},
        "fleets": {
            str(key): {**asdict(value), "ship_ids": list(value.ship_ids)}
            for key, value in snapshot.fleets.items()
        },
        "shipyards": {str(key): asdict(value) for key, value in snapshot.shipyards.items()},
        "build_orders": [asdict(value) for value in snapshot.build_orders],
    }


def snapshot_from_dict(data: dict, *, snapshot_id: int) -> ShipFleetSnapshot:
    ships = {
        int(key): ShipState(**value)
        for key, value in data.get("ships", {}).items()
    }

    fleets: dict[int, FleetState] = {}
    for key, value in data.get("fleets", {}).items():
        payload = dict(value)
        payload["ship_ids"] = tuple(payload.get("ship_ids", []))
        fleets[int(key)] = FleetState(**payload)

    shipyards = {
        int(key): ShipyardState(**value)
        for key, value in data.get("shipyards", {}).items()
    }

    build_orders = tuple(
        BuildOrderState(**value)
        for value in data.get("build_orders", [])
    )

    return ShipFleetSnapshot(
        snapshot_id=snapshot_id,
        game_date=data["game_date"],
        ships=ships,
        fleets=fleets,
        shipyards=shipyards,
        build_orders=build_orders,
    )
