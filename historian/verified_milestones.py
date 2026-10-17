"""Save-backed service anniversaries and conservative milestone classification.

This is a read-only publication layer. Annual censuses must originate from
hash-matched, processed Ironman save caches. No screenshot, generated PDF,
latest-only leader row, or calendar interpolation can establish a campaign fact.
"""
from __future__ import annotations

from typing import Iterable

SERVICE_YEARS = frozenset((1, 5, 10, 15, 20, 25, 50, 75, 100, 150, 200))


def _valid_census(census: dict) -> bool:
    date = str(census.get('date') or '')
    source = census.get('source') or {}
    return (bool(census.get('available')) and date.endswith('.01.01')
            and source.get('game_date') == date
            and bool(source.get('sha256')) and source.get('snapshot_id') is not None)


def service_milestones(censuses: Iterable[dict]) -> list[dict]:
    """Recognise anniversary spans *only* across consecutive exact January rosters.

    Same stable leader ID must appear in every intervening exact roster. This
    proves appearance at each census, NOT unbroken employment between saves.
    A missing/unprocessed annual cache or an absent ID resets that ID's series.
    """
    result = []
    tracks: dict[int, dict] = {}
    last_year: int | None = None
    for census in sorted(censuses, key=lambda c: str(c.get('date') or '')):
        date = str(census.get('date') or '')
        try:
            year = int(date[:4])
        except (ValueError, TypeError):
            tracks.clear(); last_year = None
            continue
        if not _valid_census(census) or (last_year is not None and year != last_year + 1):
            tracks.clear()
        if not _valid_census(census):
            last_year = year
            continue
        last_year = year
        observed = set()
        for person in census.get('people') or []:
            try:
                leader_id = int(person['leader_id'])
            except (TypeError, ValueError, KeyError):
                continue
            name = str(person.get('name') or '').strip()
            if not name or name.casefold().startswith(('an unnamed', 'unknown', 'leader #')):
                continue
            if leader_id <= 0 or leader_id == 4294967295 or leader_id in observed:
                continue
            observed.add(leader_id)
            track = tracks.get(leader_id)
            if track is None:
                track = {'start': year, 'first_date': date, 'first_sha': str(census['source']['sha256']),
                         'first_snapshot': census['source']['snapshot_id'], 'count': 0}
                tracks[leader_id] = track
            track['count'] += 1
            elapsed = year - track['start']
            if elapsed not in SERVICE_YEARS:
                continue
            office = str(person.get('council_office') or '')
            group = str(person.get('group') or '')
            role = str(person.get('leader_class') or 'public servant')
            # Only the current position is asserted, never uninterrupted office.
            evidence = (f'Leader ID {leader_id}; first exact census {track["first_date"]} '
                        f'(snapshot #{track["first_snapshot"]}; SHA-256 {track["first_sha"]}); '
                        f'anniversary exact census {date} '
                        f'(snapshot #{census["source"]["snapshot_id"]}; '
                        f'SHA-256 {census["source"]["sha256"]}); '
                        f'{track["count"]} consecutive verified 1 January census observations. '
                        'Full intermediate fingerprints are available from their dated census records. '
                        'Continuous service between archived dates is not proven. '
                        'Neither boundary proves an appointment date.')
            result.append({'date': date, 'name': name, 'leader_id': leader_id,
                           'years': elapsed, 'role': role, 'group': group,
                           'office': office, 'first_date': track['first_date'],
                           'evidence': evidence})
        for leader_id in tuple(tracks):
            if leader_id not in observed:
                del tracks[leader_id]
    return result


def classify_milestone(*, title: str, category: str, source: str, importance: int, leader_id=None) -> bool:
    """Mark existing proven events; a marker does not change event provenance."""
    if source in ('annual_government_census', 'opening_save'):
        return False
    if source in ('annual_verified_service', 'player_country.timeline_events', 'technology_history'):
        return True
    text = title.casefold()
    if leader_id is not None and source == 'leader_career_events':
        return True  # native recruitment, role, promotion or proven death only
    if category in ('Expansion', 'Technology', 'War', 'Politics', 'Science', 'Navy', 'People', 'Infrastructure'):
        return any(token in text for token in (
            'founded', 'commissioned', 'enters imperial control', 'victory',
            'develops new traits', 'reaches professional level', 'joins the council', 'dies', 'death of',
            'mastered', 'first contact', 'established', 'discovered',
            'first ', 'enters service', 'the origins of'))
    return False
