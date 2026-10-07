from __future__ import annotations

from .models import TechnologyEvent, TechnologySnapshot


def _date_key(value: str) -> tuple[int, int, int]:
    try:
        year, month, day = value.split(".")[:3]
        return int(year), int(month), int(day)
    except (ValueError, AttributeError):
        return (999999, 99, 99)


def derive_technology_history(snapshots: list[TechnologySnapshot]) -> dict:
    if not snapshots:
        return {
            "opening": [],
            "events": [],
            "latest": [],
        }

    ordered = sorted(snapshots, key=lambda item: _date_key(item.game_date))
    opening = sorted(
        ordered[0].technologies.values(),
        key=lambda item: (item.name.lower(), item.key),
    )

    events: list[TechnologyEvent] = []
    previous = ordered[0]

    for current in ordered[1:]:
        for key, state in current.technologies.items():
            before = previous.technologies.get(key)
            if before is None:
                events.append(
                    TechnologyEvent(
                        game_date=current.game_date,
                        previous_game_date=previous.game_date,
                        key=key,
                        name=state.name,
                        level=state.level,
                        event_type="technology_first_observed",
                    )
                )
            elif state.level > before.level:
                events.append(
                    TechnologyEvent(
                        game_date=current.game_date,
                        previous_game_date=previous.game_date,
                        key=key,
                        name=state.name,
                        level=state.level,
                        event_type="technology_level_increased",
                    )
                )
        previous = current

    events.sort(key=lambda item: (_date_key(item.game_date), item.name.lower(), item.key))
    latest = sorted(
        ordered[-1].technologies.values(),
        key=lambda item: (item.name.lower(), item.key),
    )
    return {
        "opening": opening,
        "events": events,
        "latest": latest,
    }


def technology_evidence_summary(snapshots: list[TechnologySnapshot]) -> dict[str, int]:
    history = derive_technology_history(snapshots)
    return {
        "opening_technologies": len(history["opening"]),
        "technology_events": len(history["events"]),
        "latest_technologies": len(history["latest"]),
    }
