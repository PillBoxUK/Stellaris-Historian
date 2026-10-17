from __future__ import annotations

from collections import defaultdict

from .models import TechnologyEvent, TechnologySnapshot, TechnologyState


def _date_key(value: str | None) -> tuple[int, int, int]:
    """Stable comparison key; discard placeholder and invalid game dates."""
    try:
        year, month, day = map(int, str(value).split("."))
        if year > 0 and 1 <= month <= 12 and 1 <= day <= 31:
            return year, month, day
    except (TypeError, ValueError):
        pass
    return (999999, 99, 99)


def _dated_groups(snapshots: list[TechnologySnapshot]) -> tuple[list[tuple[str, dict[str, TechnologyState]]], dict]:
    """Collapse saves stamped with the same in-game day before deriving events.

    On a single dated day we can prove that a researched level was *observed*;
    we cannot infer which of several same-day saves happened first. Taking the
    maximum observed completed level gives a monotone evidence ledger without
    an invented within-day acquisition interval. Cumulative high-water levels
    later prevent missing/partial snapshots from creating phantom re-acquisitions.
    """
    by_date: dict[tuple[int, int, int], list[TechnologySnapshot]] = defaultdict(list)
    invalid = 0
    for snapshot in snapshots:
        key = _date_key(snapshot.game_date)
        if key[0] == 999999:
            invalid += 1
        else:
            by_date[key].append(snapshot)

    groups = []
    conflicting_days = 0
    for date in sorted(by_date):
        group = by_date[date]
        levels: dict[str, TechnologyState] = {}
        for snapshot in group:
            for key, state in snapshot.technologies.items():
                if state.level < 1:
                    continue
                prior = levels.get(key)
                if prior is None or state.level > prior.level:
                    levels[key] = state
        # A differing set/level among archives from one date must not be
        # interpreted as an exact progression or ordered series of discoveries.
        if len(group) > 1:
            fingerprints = {
                frozenset((key, state.level) for key, state in row.technologies.items()
                          if state.level > 0)
                for row in group
            }
            if len(fingerprints) > 1:
                conflicting_days += 1
        groups.append((f'{date[0]}.{date[1]:02d}.{date[2]:02d}', levels))

    audit = {
        'snapshots': len(snapshots),
        'dated_snapshots': sum(map(len, by_date.values())),
        'invalid_date_snapshots': invalid,
        'distinct_dates': len(groups),
        'same_date_additional_snapshots': sum(max(0, len(group) - 1) for group in by_date.values()),
        'same_date_disagreement_days': conflicting_days,
        'first_date': groups[0][0] if groups else None,
        'last_date': groups[-1][0] if groups else None,
    }
    return groups, audit


def technology_coverage_audit(snapshots: list[TechnologySnapshot]) -> dict:
    """Report coverage quality without modifying any underlying evidence."""
    return _dated_groups(snapshots)[1]


def technology_window_label(event: TechnologyEvent) -> str:
    """Conservative human-readable evidence window, including legacy bad bounds.

    A previous archive on the *same* date cannot justify the claim that a
    technology was gained strictly after that date but also by that date.
    """
    upper = str(event.game_date)
    previous = str(event.previous_game_date or '')
    upper_key = _date_key(upper)
    lower_key = _date_key(previous)
    if upper_key[0] == 999999:
        return 'archive date uncertain; acquisition interval not established'
    if not previous or lower_key[0] == 999999:
        return f'by {upper} (earlier bound not established)'
    if lower_key < upper_key:
        return f'after {previous} and by {upper}'
    if lower_key == upper_key:
        return f'observed by {upper}; same-day archive order does not establish a narrower window'
    return f'observed by {upper}; preceding archive date is inconsistent and cannot bound acquisition'


def derive_technology_history(snapshots: list[TechnologySnapshot]) -> dict:
    groups, audit = _dated_groups(snapshots)
    if not groups:
        return {'opening': [], 'events': [], 'latest': [], 'coverage': audit}

    first_date, first_levels = groups[0]
    opening = sorted(first_levels.values(), key=lambda item: (item.name.lower(), item.key))
    seen_levels = {key: state.level for key, state in first_levels.items()}
    events: list[TechnologyEvent] = []
    previous_date = first_date

    for current_date, technologies in groups[1:]:
        for key, state in technologies.items():
            old_level = seen_levels.get(key, 0)
            if state.level > old_level:
                events.append(TechnologyEvent(
                    game_date=current_date,
                    previous_game_date=previous_date,
                    key=key,
                    name=state.name,
                    level=state.level,
                    event_type=('technology_first_observed' if old_level == 0
                                else 'technology_level_increased'),
                ))
                seen_levels[key] = state.level
        previous_date = current_date

    events.sort(key=lambda item: (_date_key(item.game_date), item.name.lower(), item.key))
    latest = sorted(groups[-1][1].values(), key=lambda item: (item.name.lower(), item.key))
    return {'opening': opening, 'events': events, 'latest': latest, 'coverage': audit}


def technology_evidence_summary(snapshots: list[TechnologySnapshot]) -> dict[str, int]:
    history = derive_technology_history(snapshots)
    audit = history['coverage']
    return {
        'opening_technologies': len(history['opening']),
        'technology_events': len(history['events']),
        'latest_technologies': len(history['latest']),
        'distinct_archive_dates': audit['distinct_dates'],
        'same_day_extra_archives': audit['same_date_additional_snapshots'],
        'same_day_disagreement_days': audit['same_date_disagreement_days'],
        'invalid_date_archives': audit['invalid_date_snapshots'],
    }
