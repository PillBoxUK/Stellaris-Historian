"""v0.0.84 — read-only Imperial Situation Dashboard.

Historical values come from processed, hash/fingerprint/parse-version matched
Stellaris snapshot caches and the campaign's separate Civic & Frontier ledger.
No raw saves are parsed, no historical database row is ever modified, and no
missing interval is interpolated. This is an investigation page, not Annals prose.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Any
import json
import re
import sqlite3
import time

from .local_database_browser import readonly_connection

COMPONENTS = {'worlds': 2, 'technology': 1, 'ship_fleet': 2, 'leaders': 5}
CACHE_TTL = 20
_CACHE: dict[tuple, tuple[float, dict]] = {}
_LOCK = Lock()
_DATE = re.compile(r'^\d{4}\.\d{2}\.\d{2}$')


def _name(raw: Any) -> str:
    if not raw:
        return 'Not established'
    text = str(raw)
    for prefix in ('gov_', 'auth_', 'ethic_', 'civic_'):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.replace('_', ' ').title()


def _num(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _cache_file(archive: Path, snapshot: dict) -> tuple[dict | None, str]:
    """Use only the exact fingerprinted source state; don't read an archive ZIP."""
    digest = str(snapshot['sha256'] or '').lower()
    if not re.fullmatch('[0-9a-f]{64}', digest):
        return None, 'Invalid archive hash'
    candidate = archive / '.historian_cache' / (digest + '.json')
    # Files can be moved to a new installation root. Prefer stored path, then
    # the validated local campaign archive path.
    source = Path(str(snapshot.get('archive_path') or ''))
    if not source.is_file():
        source = archive / str(snapshot.get('archive_filename') or '')
    try:
        stat = source.stat()
        payload = json.loads(candidate.read_text('utf-8'))
    except (OSError, ValueError, TypeError):
        return None, 'Cache or archived save unavailable'
    if not isinstance(payload, dict) or payload.get('cache_schema_version') != 1:
        return None, 'Unsupported cache schema'
    if (str(payload.get('source_sha256') or '').lower() != digest
            or payload.get('archive_size') != stat.st_size
            or payload.get('archive_mtime_ns') != stat.st_mtime_ns):
        return None, 'Cache archive fingerprint mismatch'
    return payload, ''


def _component(payload: dict | None, name: str) -> dict | None:
    if not isinstance(payload, dict):
        return None
    item = (payload.get('components') or {}).get(name)
    if not isinstance(item, dict) or item.get('version') != COMPONENTS[name]:
        return None
    data = item.get('data')
    return data if isinstance(data, dict) else None


def _civic(archive: Path, snapshots: list[dict]) -> dict[int, dict]:
    """Read the campaign-local immutable observation ledger without CREATE."""
    path = archive / 'Civic_Frontier_History.sqlite3'
    if not path.is_file():
        return {}
    allowed = {str(s['sha256']): s for s in snapshots}
    out = {}
    try:
        with readonly_connection(path) as con:
            for sha, when, raw in con.execute(
                'SELECT sha256,game_date,payload FROM observations WHERE parser_version=1'
            ):
                snap = allowed.get(sha)
                if snap is None or snap['game_date'] != when:
                    continue
                item = json.loads(raw)
                if isinstance(item, dict) and item.get('date') == when:
                    out[int(snap['id'])] = item
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return {}
    return out


def _worlds(data: dict | None) -> tuple[int | None, int | None, list[dict]]:
    if data is None:
        return None, None, []
    country = _num(data.get('player_country_id'))
    worlds = []
    for item in (data.get('worlds') or {}).values():
        if not isinstance(item, dict):
            continue
        # Cache parser extracts player-controlled worlds; check owner too if present.
        if country is not None and _num(item.get('owner_id')) != country:
            continue
        worlds.append(item)
    amounts = [_num(item.get('population')) for item in worlds]
    total = sum(x for x in amounts if x is not None) if any(x is not None for x in amounts) else None
    return len(worlds), total, worlds


def _civic_counts(data: dict | None) -> dict:
    if data is None:
        return {'known_systems': None, 'controlled_systems': None, 'stations': None, 'mining_stations': None, 'research_stations': None, 'starbases': None}
    stations = list((data.get('stations') or {}).values())
    stationary = [s for s in stations if isinstance(s, dict)]
    bases = [s for s in stationary if s.get('role') == 'starbase']
    owned = {s.get('system_id') for s in bases if s.get('system_id') is not None}
    return {'known_systems': len(data.get('discovered_systems') or {}),
            'controlled_systems': len(owned), 'stations': len(stationary),
            'mining_stations': sum(s.get('role') == 'mining' for s in stationary),
            'research_stations': sum(s.get('role') == 'research' for s in stationary),
            'starbases': len(bases)}


def _crew(data: dict | None, ruler_id: Any) -> dict:
    if data is None:
        return {'count': None, 'council': [], 'ruler': None}
    raw = list((data.get('leaders') or {}).items())
    people = []
    for key, value in raw:
        if not isinstance(value, dict):
            continue
        role = value.get('council_role_name')
        traits = [str(x) for x in value.get('trait_names') or [] if x]
        entry = {'id': str(key), 'name': str(value.get('name') or 'Unnamed leader'),
                 'class': str(value.get('leader_class') or 'leader').title(),
                 'office': role, 'level': _num(value.get('level')),
                 'traits': traits[:8], 'assignment': value.get('assignment_name') or ''}
        if str(key) == str(ruler_id) or value.get('is_ruler'):
            entry['is_ruler'] = True
        people.append(entry)
    ruler = next((p for p in people if p.get('is_ruler')), None)
    council = [p for p in people if p['office'] and not p.get('is_ruler')]
    council.sort(key=lambda p: str(p['office']).casefold())
    return {'count': len(people), 'council': council[:10], 'ruler': ruler}


def _recent(con, campaign_id: int) -> list[dict]:
    sources = [
        ('leader_career_events', 'people', "visible=1"),
        ('politics_history_events', 'politics', "visible=1"),
        ('world_history_events', 'worlds', "visible=1"),
        ('ship_fleet_events', 'military', "visible=1"),
    ]
    events = []
    for table, family, where in sources:
        try:
            rows = con.execute(f'''SELECT game_date,event_type,title,body,date_kind
                FROM {table} WHERE campaign_id=? AND {where}
                ORDER BY game_date DESC,id DESC LIMIT 220''', (campaign_id,)).fetchall()
        except sqlite3.Error:
            continue
        for r in rows:
            title = str(r['title'] or '').strip()
            if not title:
                continue
            events.append({'date': r['game_date'], 'type': family, 'title': title,
                           'detail': str(r['body'] or '')[:440], 'dating': str(r['date_kind'] or 'observed')})
    # Background history_entries includes technical checkpoint spam; do not publish.
    # Same-day different events remain separate, but exact duplicated notices don't.
    events.sort(key=lambda e: e['date'], reverse=True)
    result = []
    known = set()
    for item in events:
        key = (item['date'], item['title'].casefold(), item['type'])
        if key in known:
            continue
        known.add(key)
        result.append(item)
        if len(result) >= 180:
            break
    return result


def _file_mtime(path: Path) -> int:
    try:
        st = path.stat()
        return st.st_mtime_ns
    except OSError:
        return 0


def dashboard_data(db_path: Path, campaign_id: int, *, force: bool = False) -> dict:
    start = time.perf_counter()
    with readonly_connection(db_path) as con:
        c = con.execute('SELECT * FROM campaigns WHERE id=?', (int(campaign_id),)).fetchone()
        if c is None:
            raise ValueError('Campaign not found')
        campaign = dict(c)
        archive = Path(campaign['archive_dir'])
        raw_snapshots = con.execute('''SELECT id,sequence_no,game_date,sha256,archive_filename,archive_path
            FROM snapshots WHERE campaign_id=? AND processed=1
            ORDER BY game_date, COALESCE(sequence_no,-1), id''', (campaign_id,)).fetchall()
        snapshots = [dict(s) for s in raw_snapshots if _DATE.fullmatch(str(s['game_date']))]
        if not snapshots:
            return {'empire': campaign['empire_name'], 'latest_date': campaign['latest_game_date'],
                    'empty': True, 'message': 'No processed historical snapshots yet.', 'series': [], 'events': []}
        latest = snapshots[-1]
        summary = {'empire': campaign['empire_name'], 'first_date': snapshots[0]['game_date'],
                   'latest_date': latest['game_date'], 'latest_snapshot_id': latest['id'],
                   'processed_saves': len(snapshots)}
        newest_political = con.execute('''SELECT state_json FROM politics_states
            WHERE campaign_id=? AND snapshot_id=? ORDER BY id DESC LIMIT 1''', (campaign_id, latest['id'])).fetchone()
        latest_political = {}
        if newest_political:
            try:
                latest_political = json.loads(newest_political['state_json'] or '{}')
            except (TypeError, ValueError):
                pass
        events = _recent(con, campaign_id)
    sidecar = archive / 'Civic_Frontier_History.sqlite3'
    cache_dir = archive / '.historian_cache'
    freshness = (int(campaign_id), str(db_path), latest['id'], len(snapshots),
                 _file_mtime(db_path), _file_mtime(sidecar),
                 _file_mtime(cache_dir / (latest['sha256'] + '.json')))
    if not force:
        with _LOCK:
            item = _CACHE.get(freshness)
            if item and time.monotonic() - item[0] < CACHE_TTL:
                return item[1]
    ledger = _civic(archive, snapshots)
    series = []
    newest_worlds = []
    newest_leaders = None
    valid_core = 0
    invalid = 0
    # Iterate chronological saves and retain distinct same-day archived changes.
    for snap in snapshots:
        blob, issue = _cache_file(archive, snap)
        valid_core += blob is not None
        invalid += blob is None
        world_data = _component(blob, 'worlds')
        tech_data = _component(blob, 'technology')
        ship_data = _component(blob, 'ship_fleet')
        people_data = _component(blob, 'leaders')
        if world_data and world_data.get('game_date') != snap['game_date']:
            world_data = None
        if tech_data and tech_data.get('game_date') != snap['game_date']:
            tech_data = None
        if ship_data and ship_data.get('game_date') != snap['game_date']:
            ship_data = None
        if people_data and people_data.get('game_date') != snap['game_date']:
            people_data = None
        nworlds, pop, worlds = _worlds(world_data)
        fleets = len(ship_data.get('fleets') or {}) if ship_data is not None else None
        ships = len(ship_data.get('ships') or {}) if ship_data is not None else None
        tech = len(tech_data.get('technologies') or {}) if tech_data is not None else None
        civic = _civic_counts(ledger.get(int(snap['id'])))
        point = {'date': snap['game_date'], 'snapshot_id': snap['id'],
                 'population': pop, 'colonies': nworlds, 'fleets': fleets,
                 'ships': ships, 'technologies': tech,
                 'leaders': len(people_data.get('leaders') or {}) if people_data is not None else None,
                 **civic}
        series.append(point)
        if snap['id'] == latest['id']:
            newest_worlds = worlds
            newest_leaders = people_data
    # An entirely missing latest cache should never turn an old value into a
    # current figure, even if older registries happen to show a value.
    current = series[-1]
    worlds_sorted = sorted(newest_worlds, key=lambda w: _num(w.get('population')) or 0, reverse=True)
    top_worlds = [{'name': w.get('name') or 'Unnamed world',
                   'population': _num(w.get('population')),
                   'designation': w.get('designation_name') or '',
                   'system': w.get('system_name') or ''} for w in worlds_sorted[:8]]
    ruler_id = latest_political.get('ruler_id')
    personnel = _crew(newest_leaders, ruler_id)
    if personnel['ruler'] is None and latest_political.get('ruler_name'):
        personnel['ruler'] = {'name': latest_political['ruler_name'], 'class': 'Ruler',
                              'office': 'Head of state', 'traits': [], 'assignment': ''}
    response = {**summary, 'empty': False,
                'current': current,
                'coverage': {'snapshot_count': len(snapshots), 'core_valid': valid_core,
                             'core_unavailable': invalid, 'civic_states': len(ledger),
                             'population_points': sum(x['population'] is not None for x in series),
                             'technology_points': sum(x['technologies'] is not None for x in series)},
                'government': {'type': _name(latest_political.get('government_type')),
                               'authority': _name(latest_political.get('authority')),
                               'ethics': [_name(e) for e in latest_political.get('ethics') or []],
                               'civics': [_name(e) for e in latest_political.get('civics') or []],
                               'ruler_name': latest_political.get('ruler_name') or ''},
                'people': personnel, 'top_worlds': top_worlds,
                'series': series, 'events': events,
                'notes': {'population': 'Raw population values from Stellaris world-cache records; no assumed scale conversion.',
                          'systems': 'Controlled system counts are the number of systems with player-owned starbase evidence, not necessarily every claimed system.',
                          'dating': 'State differences are first observed by a saved date; do not interpret them as exact event dates.',
                          'gaps': 'Missing, stale or unavailable caches create gaps in trend data; values are never filled from a later save.'}}
    # Retain only the newest few campaigns, for bounded memory use.
    with _LOCK:
        if len(_CACHE) > 6:
            _CACHE.clear()
        _CACHE[freshness] = (time.monotonic(), response)
    return response
