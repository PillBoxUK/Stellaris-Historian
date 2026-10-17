"""Read-only, campaign-local political and exploration evidence.

Native-save observations are hashed and never promoted into exact historical
occurrence dates without a saved date. A changed state is first observable
between two retained archives, not necessarily on the latter archive's date.
The ledger is additive: a parse failure never invalidates the main Historian DB.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import zipfile
from pathlib import Path

from .core.stellaris_text import (_find_named_block, _numeric_record, _top_numeric_records,
                                  _scalar, _int_scalar, _id_list_from_block, _extract_braced_after)
from .domains.worlds.parser import _display_name_from_record
from .domains.ships.parser import _owned_fleet_ids
from .save_reader import empire_profile_from_text
from .core.stellaris_text import indexed_scan_scope

VERSION = 4
# Native situation definitions identify an ongoing crisis, not its exact
# trigger date, every intermediate event or its eventual resolution.
_REVOLT_KEY = re.compile(r'(?:revolt|rebellion|uprising|unrest|riot|discontent)', re.I)


def _direct_scalar(record: str | None, key: str) -> str | None:
    """Read a *direct* assignment, not e.g. target.type before situation.type.

    The native Stellaris save uses a consistent indent for siblings; selecting
    only the shallowest assignments avoids values from nested references.
    """
    if not record:
        return None
    pattern = re.compile(r'(?m)^([ \t]*)([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(?:"([^"\n]*)"|([^\s{}]+))')
    rows = [(len(m.group(1)), m.group(2), m.group(3) if m.group(3) is not None else m.group(4))
            for m in pattern.finditer(record)]
    if not rows:
        return None
    depth = min(r[0] for r in rows)
    return next((v for indent, name, v in rows if indent == depth and name == key), None)


def _observed_player_situations(text: str, country_id: int, colony_conditions: dict) -> dict[str, dict]:
    """Return situation state only when the country and target are in scope.

    Neither anonymous global situation flags nor other empires' situations
    belong in the player's chronicle. Unknown targets are excluded.
    """
    outer = _find_named_block(text, 'situations')
    situations = _find_named_block(outer or '', 'situations')
    if not situations:
        return {}
    owned_colonies = {int(p['colony_id']): p for p in colony_conditions.values()
                      if p.get('colony_id') is not None}
    owned_planets = {int(p['planet_id']): p for p in colony_conditions.values()}
    result = {}
    for situation_id, record in _top_numeric_records(situations):
        country = _direct_scalar(record, 'country')
        if country != str(country_id):
            continue
        type_key = _direct_scalar(record, 'type')
        if not type_key or type_key.lower() == 'none':
            continue
        target = _find_named_block(record, 'target')
        target_type = (_direct_scalar(target, 'type') or 'none').lower()
        target_id = _direct_scalar(target, 'id')
        world = None
        if target_type == 'colony':
            if not target_id or not target_id.isdigit() or int(target_id) not in owned_colonies:
                continue
            world = owned_colonies[int(target_id)]
        elif target_type == 'planet':
            if not target_id or not target_id.isdigit() or int(target_id) not in owned_planets:
                continue
            world = owned_planets[int(target_id)]
        elif target_type == 'country':
            if target_id != str(country_id):
                continue
        elif target_type != 'none':
            # Do not expose unknown subjects, which may be foreign.
            continue
        row = {'id': situation_id, 'key': type_key,
               'target_type': target_type, 'target_id': target_id,
               'colony_id': world.get('colony_id') if world else None,
               'planet_id': world.get('planet_id') if world else None,
               'world': world.get('name') if world else None,
               'stage': None, 'progress': None, 'approach': _direct_scalar(record, 'approach')}
        for field in ('stage', 'progress'):
            raw = _direct_scalar(record, field)
            try:
                row[field] = int(raw) if field == 'stage' else float(raw)
            except (TypeError, ValueError, OverflowError):
                pass
        result[str(situation_id)] = row
    return result


def _observed_player_spy_networks(text: str, country_id: int) -> dict[str, dict]:
    """Player-owned network objects, not foreign secrets or implied operations.

    The game may allocate empty/passive owner-target records automatically.
    A bare network is evidence of a saved relationship structure ONLY: it does
    not establish an assigned envoy, operational intelligence or active spying.
    Never promote an unknown/inaccessible target into a named civilisation.
    """
    block = _find_named_block(text, 'spy_networks')
    result = {}
    for net_id, record in _top_numeric_records(block):
        if _direct_scalar(record, 'owner') != str(country_id):
            continue
        raw_target = _direct_scalar(record, 'target')
        if not raw_target or not raw_target.isdigit() or int(raw_target) in (country_id, 4294967295):
            continue
        row = {'network_id': net_id, 'owner_id': country_id,
               'target_id': int(raw_target), 'active_evidence': False}
        for field in ('infiltration', 'infiltration_level', 'network_size'):
            value = _direct_scalar(record, field)
            try:
                if value is not None:
                    number = float(value)
                    if 0 <= number <= 1e8:
                        row[field] = number
                        if number > 0: row['active_evidence'] = True
            except (TypeError, ValueError, OverflowError):
                pass
        for field in ('spymaster', 'envoy', 'leader'):
            value = _direct_scalar(record, field)
            if value and value.isdigit() and int(value) not in (0, 4294967295):
                row[field] = int(value)
                row['active_evidence'] = True
        result[str(net_id)] = row
    return result


def _is_revolt_situation(state: dict) -> bool:
    return bool(_REVOLT_KEY.search(str(state.get('key') or '')))


def _crisis_key(state: dict) -> tuple:
    """IDs may be reused; include definition and entity to prevent conflation."""
    return (str(state['id']), state['key'], state.get('target_type'), state.get('target_id'))


def revolt_evidence(observations: list[dict]) -> list[dict]:
    """Hash-linked observational ledger; never convert progress into event dates."""
    result = []
    for obs in observations:
        for state in (obs.get('active_situations') or {}).values():
            if _is_revolt_situation(state):
                result.append({'date': obs['date'], 'sha256': obs.get('snapshot_sha256',''), **state})
    return result
# Candidates are research leads, never evidence of a specific riots/bribery event.
_CIVIC_INCIDENT_TOKEN = re.compile(r'(?:crime|criminal|corrupt|brib|riot|unrest|revolt|protest|disorder|anti_crime)', re.I)


def _observed_colony_conditions(text: str, country: str, source_save: Path | None = None) -> dict[str, dict]:
    """Collect *player-owned* social-state facts from save records only.

    Modern Stellaris owned_planets contains colony IDs, whose carrier/reference
    points at a planet record. Values are observations, not event occurrence dates.
    Do not infer that a riot, bribery or arrest occurred from these numbers.
    """
    colonies = _find_named_block(text, 'colony')
    planets = _find_named_block(text, 'planet')
    result: dict[str, dict] = {}
    for ref in _id_list_from_block(country, 'owned_planets'):
        colony = _numeric_record(colonies, int(ref)) if colonies else None
        planet_id = _int_scalar(_find_named_block(colony, 'carrier'), 'reference') if colony else None
        if planet_id is None:
            planet_id = int(ref)  # legacy Stellaris save layout
        planet = _numeric_record(planets, planet_id)
        if not planet:
            continue
        state = colony or planet
        planet_name = _display_name_from_record(planet, source_save or Path('.'), fallback=f'World {planet_id}', suffix='planet')
        values: dict[str, float | None] = {}
        for metric in ('crime', 'stability'):
            token = _scalar(state, metric)
            try:
                value = float(token) if token is not None else None
                if value is not None and not (-1e9 < value < 1e9):
                    value = None
            except (ValueError, OverflowError, TypeError):
                value = None
            values[metric] = value
        # Read planet-scoped state, not country-wide events or arbitrary matches.
        candidate_flags = []
        flags = _find_named_block(planet, 'flags') or ''
        for key in re.findall(r'(?m)^\s*([A-Za-z_][A-Za-z_0-9.]*)\s*=', flags):
            if _CIVIC_INCIDENT_TOKEN.search(key):
                candidate_flags.append(key)
        modifier_candidates = []
        for raw in re.findall(r'(?m)^\s*(?:planet_modifier|modifier)\s*=\s*"?([A-Za-z_][A-Za-z_0-9.]*)"?', planet):
            if _CIVIC_INCIDENT_TOKEN.search(raw):
                modifier_candidates.append(raw)
        for timed in re.finditer(r'(?m)^\s*timed_modifier\s*=\s*\{', planet):
            # Top-level block helper, not a free-text scan across unrelated planets.
            block = _extract_braced_after(planet, timed.start()) or ''
            for raw in re.findall(r'(?m)^\s*modifier\s*=\s*"?([A-Za-z_][A-Za-z_0-9.]*)"?', block):
                if _CIVIC_INCIDENT_TOKEN.search(raw):
                    modifier_candidates.append(raw)
        result[str(planet_id)] = {
            'planet_id': planet_id,
            'colony_id': int(ref) if colony else None,
            'name': planet_name,
            **values,
            'incident_flag_candidates': sorted(set(candidate_flags)),
            'incident_modifier_candidates': sorted(set(modifier_candidates)),
        }
    return result
_DATE = re.compile(r'^\d{4}\.\d{2}\.\d{2}$')
_MAX_SYSTEM_EVENTS = 3500


def ledger_path(archive: Path) -> Path:
    return Path(archive) / 'Civic_Frontier_History.sqlite3'


def _db(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=40)
    conn.execute('''CREATE TABLE IF NOT EXISTS observations (
      sha256 TEXT PRIMARY KEY, game_date TEXT NOT NULL,
      archive_filename TEXT NOT NULL, player_country_id INTEGER NOT NULL,
      payload TEXT NOT NULL, parser_version INTEGER NOT NULL)''')
    conn.execute('CREATE INDEX IF NOT EXISTS civic_date_idx ON observations(game_date)')
    return conn


def _tokens(block: str | None) -> list[str]:
    if not block:
        return []
    return [v for v in re.findall(r'"([^"\n]+)"|(?<!\w)([A-Za-z_][A-Za-z0-9_.:-]+)', block)
            for v in [v[0] or v[1]] if v and v not in ('yes', 'no')]


def _human(key: str | None) -> str:
    return ' '.join(re.sub(r'^(?:civic|ethic|auth|gov|agenda|tr|policy|starbase_level)_', '', str(key or '')).replace('_', ' ').split()).title()


def _system_names(galaxy: str | None, ids: set[int]) -> dict[int, str]:
    if not galaxy or not ids:
        return {}
    result = {}
    for ident in ids:
        record = _numeric_record(galaxy, ident)
        if not record:
            continue
        name = _find_named_block(record, 'name')
        key = _scalar(name, 'key') if name else _scalar(record, 'name')
        if key:
            result[ident] = (re.sub(r'_system$', '', key.removeprefix('SPEC_')).replace('_', ' ')
                         if key.startswith('SPEC_') else
                         key[5:].replace('_',' ') if key.startswith('NAME_') else key.replace('_',' '))
    return result


def extract_observation(meta: str, text: str, source_save: Path | None = None, profile=None) -> dict:
    profile = profile or empire_profile_from_text(meta, text)
    country_id = profile.player_country_id
    if country_id is None:
        raise ValueError('Player country is not resolved')
    country = _numeric_record(_find_named_block(text, 'country'), country_id)
    if not country:
        raise ValueError('Player country record not found')
    government = _find_named_block(country, 'government') or ''
    agenda = _scalar(government, 'council_agenda')
    policies = sorted(set(_tokens(_find_named_block(country, 'policy_flags'))))
    council_slots = sorted(set(_tokens(_find_named_block(government, 'picked_council_types'))))
    sectors = {}
    for sector_id, record in _top_numeric_records(_find_named_block(text, 'sectors')):
        if _int_scalar(record, 'owner') != country_id:
            continue
        raw_name = _scalar(_find_named_block(record, 'name'), 'key')
        sectors[str(sector_id)] = {'name': _human(raw_name).replace('Name ', '') if raw_name else f'Sector {sector_id}',
                                  'type': _scalar(record, 'type') or '',
                                  'capital': _int_scalar(record, 'local_capital')}

    # The player's owned_fleets list is authoritative for both mobile and
    # stationary ship ownership. Original owner is NOT used: captured stations
    # can have a different historical creator.
    fleet_block = _find_named_block(text, 'fleet')
    owned_fleets = _owned_fleet_ids(text, country_id)
    static = {'shipclass_mining_station': 'mining', 'shipclass_research_station': 'research',
              'shipclass_observation_station': 'observation', 'shipclass_orbital_station': 'orbital'}
    station_ships: dict[int, str] = {}
    for fid in owned_fleets:
        record = _numeric_record(fleet_block, fid)
        if not record:
            continue
        role = static.get(_scalar(record, 'ship_class') or '')
        if role or (_scalar(record, 'ship_class') == 'shipclass_starbase'):
            found = _find_named_block(record, 'ships') or ''
            for ship_id in re.findall(r'(?<!\d)\d+(?!\d)', found):
                station_ships[int(ship_id)] = role or 'starbase'
    ships = _find_named_block(text, 'ships')
    station_ids: set[int] = set()
    stations: dict[str, dict] = {}
    for ship_id, role in station_ships.items():
        record = _numeric_record(ships, ship_id)
        if not record:
            continue
        pos = _find_named_block(record, 'coordinate')
        system_id = _int_scalar(pos, 'origin')
        if system_id is not None and system_id != 4294967295:
            station_ids.add(system_id)
        created = _scalar(record, 'construction_date')
        stations[str(ship_id)] = {'role': role, 'system_id': system_id,
                                  'built': created if created and _DATE.fullmatch(created) else None}
    starbase_manager = _find_named_block(_find_named_block(text, 'starbase_mgr') or '', 'starbases')
    for base_id, record in _top_numeric_records(starbase_manager):
        sid = _int_scalar(record, 'station')
        if sid is None or sid not in station_ships:
            continue
        if str(sid) not in stations:
            continue
        row = stations[str(sid)]
        row['role'] = 'starbase'
        row['level'] = _scalar(record, 'level') or ''
        # A module/building list is stored as keyed scalars, not anonymous quoted values.
        row['modules'] = sorted(re.findall(r'(?m)(?:^|\s)\d+\s*=\s*"?([a-z_][a-z0-9_]*)',
                                           _find_named_block(record, 'modules') or ''))
        row['buildings'] = sorted(re.findall(r'(?m)(?:^|\s)\d+\s*=\s*"?([a-z_][a-z0-9_]*)',
                                             _find_named_block(record, 'buildings') or ''))

    # Native discovery list marks recognition of a star system by a country.
    # This does NOT establish completion of a scientific survey.
    galaxy = _find_named_block(text, 'galactic_object')
    discovered = set()
    for system_id, record in _top_numeric_records(galaxy):
        discovery = _find_named_block(record, 'discovery')
        if discovery and str(country_id) in re.findall(r'(?<!\d)\d+(?!\d)', discovery):
            discovered.add(system_id)
    names = _system_names(galaxy, station_ids | discovered)
    for row in stations.values():
        if row.get('system_id') in names:
            row['system'] = names[row['system_id']]
    colony_conditions = _observed_colony_conditions(text, country, source_save)
    return {'date': profile.game_date, 'player_country_id': country_id,
            'government': {'type': profile.government_type, 'authority': profile.authority,
                           'ethics': sorted(profile.ethics), 'civics': sorted(profile.civics),
                           'ruler_id': _int_scalar(country,'ruler'), 'agenda': agenda,
                           'council_positions': council_slots, 'policies': policies},
            'sectors': sectors, 'stations': stations,
            'colony_conditions': colony_conditions,
            'active_situations': _observed_player_situations(text, country_id, colony_conditions),
            'spy_networks': _observed_player_spy_networks(text, country_id),
            'discovered_systems': {str(i): names.get(i, f'System {i}') for i in sorted(discovered)}}


def capture(archive: Path, save: Path, sha256: str, *, meta: str | None = None,
            gamestate: str | None = None, profile=None) -> dict:
    """Read one save only if a current-version observation is missing.

    If gamestate is supplied by core parsing there is NO additional save unzip.
    """
    path = ledger_path(archive)
    with _db(path) as conn:
        row=conn.execute('SELECT game_date FROM observations WHERE sha256=? AND parser_version=?',
                         (sha256,VERSION)).fetchone()
        if row:
            return {'cached':True, 'date':row[0], 'seconds':0.}
    started=time.perf_counter()
    if meta is None or gamestate is None:
        with zipfile.ZipFile(save) as z:
            meta=z.read('meta').decode('utf-8','replace')
            gamestate=z.read('gamestate').decode('utf-8','replace')
    with indexed_scan_scope():
        payload=extract_observation(meta,gamestate,source_save=save,profile=profile)
    with _db(path) as conn:
        conn.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)',
                     (sha256,payload['date'],Path(save).name,payload['player_country_id'],
                      json.dumps(payload,ensure_ascii=False,separators=(',',':')),VERSION))
    return {'cached':False, 'date':payload['date'], 'seconds':time.perf_counter()-started}


def read_observations(archive: Path, snapshots) -> list[dict]:
    path=ledger_path(archive)
    if not path.is_file():
        return []
    allowed={str(s['sha256']):s for s in snapshots if int(s['processed'])}
    if not allowed:
        return []
    with _db(path) as conn:
        rows=conn.execute('SELECT sha256,game_date,payload FROM observations WHERE parser_version IN (1,2,3,4)').fetchall()
    result=[]
    for sha,date,payload in rows:
        original=allowed.get(sha)
        if not original or str(original['game_date'])!=date:
            continue
        try:
            entry=json.loads(payload)
            entry['snapshot_id']=int(original['id'])
            entry['snapshot_sha256']=sha
            result.append(entry)
        except (ValueError,TypeError):
            continue
    return sorted(result,key=lambda e:(e['date'],e['snapshot_id']))


def _narrative_date(date: str) -> str:
    months = ('January','February','March','April','May','June',
              'July','August','September','October','November','December')
    try:
        y,m,d=map(int,date.split('.'))
        return f'{d} {months[m-1]} {y}' if 1<=m<=12 else date
    except (ValueError,IndexError):
        return date


def timeline_events(observations: list[dict]) -> list[dict]:
    """Native state transitions; observation dates aren't rewritten as exact dates."""
    events=[]
    prev=None
    emitted=set()
    def add(when,title,body,category,kind,source,id='',importance=70):
        key=(when,title,source,id)
        if key in emitted:return
        emitted.add(key)
        events.append({'date':when,'title':title,'body':body,'category':category,
                       'date_kind':kind,'source':source,'evidence':f'Native state comparison; {source}. State changes are not automatic proof of specific permitted actions.',
                       'importance':importance})
    for row in observations:
        when=row['date']; govt=row['government']
        if prev:
            before=prev['government']
            for field,title in [('type','Government reorganised'),('authority','Authority reformed')]:
                if govt.get(field) and govt.get(field)!=before.get(field):
                    add(when,title,f'By {_narrative_date(when)}, the government had shifted from {_human(before.get(field))} to {_human(govt[field])}.',
                        'Politics','first_observed','country.government.'+field,importance=91)
            for field,label in [('ethics','political outlook'),('civics','governing institutions')]:
                old=set(before.get(field) or ());new=set(govt.get(field) or ())
                if old!=new and new:
                    added=', '.join(_human(k) for k in sorted(new-old))
                    dropped=', '.join(_human(k) for k in sorted(old-new))
                    sentence=f'The civilisation’s {label} changed.'
                    if added:sentence+=f' Newly present: {added}.'
                    if dropped:sentence+=f' No longer present: {dropped}.'
                    add(when,'A change in the '+label,sentence,'Politics','first_observed','country.government.'+field,importance=88)
            if govt.get('agenda') and govt.get('agenda')!=before.get('agenda'):
                add(when,'A new council agenda',f'By {_narrative_date(when)}, the governing council had turned its attention to {_human(govt["agenda"])}.',
                    'Politics','first_observed','country.government.council_agenda',importance=78)
            if govt.get('ruler_id') and govt['ruler_id']!=before.get('ruler_id'):
                add(when,'Change in the leadership',f'By {_narrative_date(when)}, a new ruler had assumed the highest office of the state.',
                    'Politics','first_observed','country.ruler',importance=86)
            # An active native revolt situation confirms a brewing crisis.
            # Its disappearance does NOT prove a revolt happened or that an
            # uprising was quelled: the save may no longer retain the reason.
            old_crises = {_crisis_key(v): v for v in (prev.get('active_situations') or {}).values()
                           if _is_revolt_situation(v)}
            new_crises = {_crisis_key(v): v for v in (row.get('active_situations') or {}).values()
                           if _is_revolt_situation(v)}
            for ident, state in new_crises.items():
                world = state.get('world')
                location = world or 'the empire'
                source = f'situations.situations.{state["id"]}.type'
                if ident not in old_crises:
                    add(when, f'Threat of revolt on {location}' if world else 'A revolt crisis confronts the realm',
                        f'By {_narrative_date(when)}, a revolt crisis was active '
                        +(f'on {location}.' if world else 'within the empire.'),
                        'Politics','first_observed',source,str(ident),importance=94)
                elif (state.get('stage') is not None and old_crises[ident].get('stage') is not None
                      and state['stage'] != old_crises[ident]['stage']):
                    add(when, f'The unrest on {location} enters a new phase' if world else 'A revolt crisis enters a new phase',
                        f'By {_narrative_date(when)}, the active revolt crisis '
                        +(f'on {location}' if world else 'within the empire')
                        +' had moved into another phase. Its eventual outcome remained uncertain.',
                        'Politics','first_observed',source+'.stage',str(ident),importance=83)
            for ident, state in old_crises.items():
                if ident not in new_crises:
                    world = state.get('world')
                    location = world or 'the empire'
                    add(when, f'The revolt crisis on {location} leaves the active record' if world else 'The revolt crisis leaves the active record',
                        f'By {_narrative_date(when)}, the revolt crisis '
                        +(f'on {location}' if world else 'within the empire')
                        +' no longer appeared among the government’s active situations. '
                        'Whether it ended in compromise, suppression or another outcome is not established.',
                        'Politics','first_observed',f'situations.situations.{state["id"]}',str(ident),importance=87)
            oldp=set(before.get('policies') or ());newp=set(govt.get('policies') or ())
            newly_active=sorted(newp-oldp)
            removed=sorted(oldp-newp)
            if newly_active or removed:
                story = 'The government revised its policy framework.'
                if newly_active:
                    story += ' Newly recorded provisions included '+', '.join(_human(k) for k in newly_active)+'.'
                if removed:
                    story += ' Provisions no longer listed included '+', '.join(_human(k) for k in removed)+'.'
                
                add(when,'The laws and policies of the realm evolve',story,
                    'Politics','first_observed','country.policy_flags',importance=77)
            oldc=set(before.get('council_positions') or ())
            newc=set(govt.get('council_positions') or ())
            if newc!=oldc and newc:
                positions=', '.join(_human(k) for k in sorted(newc))
                add(when,'The governing council is reorganised',
                    f'By {_narrative_date(when)}, the council’s offices included {positions}.',
                    'Politics','first_observed','country.government.picked_council_types',importance=83)
            for sid,sec in row.get('sectors',{}).items():
                if sid not in prev.get('sectors',{}):
                    add(when,f'{sec["name"]} comes under sector administration',
                        f'By {_narrative_date(when)}, a sector administration named {sec["name"]} had been established within the realm.',
                        'Politics','first_observed','sectors.owner',sid,importance=74)
            past=prev.get('stations',{});now=row.get('stations',{})
            formerly_controlled={s.get('system_id') for s in past.values() if s.get('role')=='starbase'}
            newly_controlled={s.get('system_id') for s in now.values() if s.get('role')=='starbase'}
            for system_id in sorted((newly_controlled-formerly_controlled)-{None}):
                source=next((s for s in now.values() if s.get('role')=='starbase'
                             and s.get('system_id')==system_id),None)
                if source and source.get('system') and not source['system'].startswith('System '):
                    name=source['system']
                    add(when,f'{name} enters imperial control',
                        f'By {_narrative_date(when)}, the {name} system was secured by a starbase under the civilisation’s authority.',
                        'Expansion','first_observed','country.owned_fleets and starbase_mgr',str(system_id),importance=87)
            for sid,station in now.items():
                prior=past.get(sid)
                role=station.get('role','station')
                location=' in the '+station['system']+' system' if station.get('system') else ''
                label={'mining':'mining station','research':'research station','observation':'observation station',
                       'orbital':'orbital station','starbase':'starbase'}.get(role,'station')
                if prior is None:
                    date=station.get('built')
                    exact=bool(date and _DATE.fullmatch(date) and prev['date']<date<=when)
                    stamp=date if exact else when
                    description=(f'On {_narrative_date(stamp)}, a {label} was completed{location}.' if exact
                                 else f'By {_narrative_date(when)}, a {label} had entered service{location}.')
                    add(stamp,f'{label.title()} established{location}',description,'Infrastructure',
                        'exact_save_field' if exact else 'first_observed','ships and starbase_mgr',sid,importance=68)
                elif role=='starbase':
                    if station.get('level') and station.get('level')!=prior.get('level'):
                        add(when,f'Starbase expanded{location}',
                            f'By {_narrative_date(when)}, the starbase{location} had been developed to {_human(station["level"])}.',
                            'Infrastructure','first_observed','starbase_mgr.starbases.level',sid,importance=78)
                    for field,word in [('modules','modules'),('buildings','facilities')]:
                        added=set(station.get(field,[]))-set(prior.get(field,[]))
                        if added:
                            add(when,f'New starbase {word}{location}',
                                f'By {_narrative_date(when)}, the starbase{location} had gained '+', '.join(_human(x) for x in sorted(added))+'.',
                                'Infrastructure','first_observed','starbase_mgr.starbases.'+field,sid,importance=61)
            # Discovery flags are observations of *knowledge*, NOT full surveys.
            # A cap avoids dumping every galactic system into printed chronicle.
            recent = set(row.get('discovered_systems',{}))-set(prev.get('discovered_systems',{}))
            if len(events)<_MAX_SYSTEM_EVENTS:
                for system_id in sorted(recent, key=int):
                    name=row['discovered_systems'][system_id]
                    if name.startswith('System '):continue
                    add(when,f'{name} enters the charts',
                        f'By {_narrative_date(when)}, the {name} system had entered the civilisation’s known stellar charts.',
                        'Exploration','first_observed','galactic_object.discovery',system_id,importance=57)
        else:
            for state in (row.get('active_situations') or {}).values():
                if not _is_revolt_situation(state):
                    continue
                world = state.get('world')
                location = world or 'the empire'
                add(when, f'A revolt crisis already looms over {location}' if world else 'A revolt crisis is active',
                    f'At the opening of this surviving observation sequence, a revolt crisis was already active '
                    +(f'on {location}.' if world else 'within the empire.'),
                    'Politics','opening_observation',f'situations.situations.{state["id"]}.type',
                    str(_crisis_key(state)),importance=93)
        prev=row
    return sorted(events,key=lambda e:(e['date'],-e['importance'],e['title']))


def render_civic_frontier_history(db, campaign_id: int) -> Path:
    """Readable, supplementary evidence browser; main history stays narrative-first."""
    from html import escape
    import os
    import tempfile

    campaign=db.campaign(campaign_id)
    if campaign is None:
        raise ValueError('No campaign selected')
    archive=Path(str(campaign['archive_dir']))
    observations=read_observations(archive,db.all_snapshots(campaign_id))
    events=timeline_events(observations)
    latest=observations[-1] if observations else None
    h=lambda value:escape('' if value is None else str(value),quote=True)
    counts=(len(latest.get('stations',{})) if latest else 0)
    # Social state is displayed only in the supporting evidence register.
    # No riot, bribery, arrests, official motive or exact incident date is
    # inferred by this page or injected into the Imperial Annals.
    social_rows = []
    for observation in observations:
        for planet_id, state in sorted((observation.get('colony_conditions') or {}).items(), key=lambda x: int(x[0])):
            if state.get('crime') is None and state.get('stability') is None and not (state.get('incident_flag_candidates') or state.get('incident_modifier_candidates')):
                continue
            social_rows.append((observation, state))
    crisis_rows = revolt_evidence(observations)
    recent_crises = crisis_rows[-1500:]
    import csv
    csv_path = archive / 'Public_Order_Crisis_Observations.csv'
    fd_csv, tmp_csv = tempfile.mkstemp(prefix='.civic_crisis_', suffix='.csv', dir=archive)
    try:
        with os.fdopen(fd_csv, 'w', encoding='utf-8-sig', newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(('Archive date', 'Native situation ID', 'Definition', 'World', 'Stage',
                             'Progress', 'Approach key', 'Target type', 'Target ID', 'Save SHA-256'))
            for item in crisis_rows:
                writer.writerow((item['date'], item['id'], item['key'], item.get('world') or '',
                                 item.get('stage'), item.get('progress'), item.get('approach') or '',
                                 item.get('target_type'), item.get('target_id'), item['sha256']))
        os.replace(tmp_csv, csv_path)
    finally:
        if os.path.exists(tmp_csv):
            os.unlink(tmp_csv)
    crisis_table = ''.join(
        '<tr><td>'+h(state['date'])+'</td><td>'+h(state.get('world') or 'Empire-wide')+'</td><td><code>'+
        h(state['key'])+'</code></td><td>'+h(state.get('stage') if state.get('stage') is not None else '—')+
        '</td><td>'+h(round(state['progress'], 2) if state.get('progress') is not None else '—')+
        '</td><td><code>'+h(state.get('approach') or '—')+'</code></td><td><code>'+
        h(str(state['sha256'])[:16])+'</code></td></tr>'
        for state in recent_crises
    )
    crises_section = ("""<details class="social-evidence" id="revolt-evidence" open><summary>Planetary revolt &amp; civic crisis tracking — """+
        str(len(crisis_rows))+""" saved situation observations</summary><p>Native active-situation state for the selected civilisation only. Dates show when an archived save contained this crisis, not when it began. Stage, progress and approaches are raw save values; a missing later situation does not prove victory, suppression, independence or a peaceful outcome. <a href="Public_Order_Crisis_Observations.csv">Export the complete save-backed crisis ledger (CSV)</a>.</p><div class="social-scroll"><table><thead><tr><th>Archive date</th><th>Location</th><th>Native situation definition</th><th>Stage</th><th>Progress</th><th>Approach key</th><th>Save hash prefix</th></tr></thead><tbody>"""+
        crisis_table+"""</tbody></table></div></details>""") if crisis_rows else (
        '<div class="empty">No active revolt situation has yet been extracted from the processed archives. '
        'An in-game warning is not itself historical evidence; make sure new saves are processed.</div>')
    shown_social = social_rows[-1500:]  # bound generated HTML for century-long campaigns
    social_table = ''.join(
        '<tr><td>'+h(obs['date'])+'</td><td>'+h(state.get('name'))+'</td><td>'+
        h('—' if state.get('crime') is None else round(state['crime'],2))+'</td><td>'+
        h('—' if state.get('stability') is None else round(state['stability'],2))+'</td><td>'+
        h(', '.join(state.get('incident_flag_candidates',[])+state.get('incident_modifier_candidates',[])) or '—')+'</td><td><code>'+
        h(str(obs.get('snapshot_sha256',''))[:16])+'</code></td></tr>'
        for obs,state in shown_social
    )
    social_section = ('''<details class="social-evidence" id="social-evidence"><summary>Public order evidence — '''+
        str(len(social_rows))+''' save observations</summary><p>Showing the latest '''+str(len(shown_social))+''' observations; the full SHA-indexed ledger remains in SQLite. Save-backed colony statistics and candidate flags. They cannot, by themselves, prove riots, official bribery, arrests, motives or event dates. A change is only established between the adjacent archived observations. SHA-256 is shown for provenance.</p><div class="social-scroll"><table><thead><tr><th>Archive date</th><th>World</th><th>Crime (raw)</th><th>Stability (raw)</th><th>Candidate save keys (unverified)</th><th>Save hash prefix</th></tr></thead><tbody>'''+
        social_table+'''</tbody></table></div></details>''') if social_rows else ''
    story=''.join(
        f'<article class="item" data-kind="{h(e["category"])}" data-text="{h((e["title"]+" "+e["body"]).lower())}">'
        f'<div class="meta"><span>{h(_narrative_date(e["date"]))}</span><span>{h(e["category"])}</span></div>'
        f'<h3>{h(e["title"])}</h3><p>{h(e["body"])}</p>'
        f'<details><summary>Source and dating</summary><small>{h(e["evidence"])} '
        f'Dating: {h(e["date_kind"])}</small></details></article>'
        for e in events
    )
    if not observations:
        story='<div class="empty">This campaign has no indexed civic and frontier observations yet. '
        story+='Use <strong>Manage Campaign → Update Historical Timeline</strong> to inspect its archived saves.</div>'
    counters=f'''<div class="counts"><div><strong>{len(observations)}</strong><span>observed save states</span></div>
      <div><strong>{len(events)}</strong><span>historical changes</span></div>
      <div><strong>{counts}</strong><span>stations in the latest observed state</span></div></div>'''
    html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{h(campaign['empire_name'])} — Civic and Frontier History</title>
<style>
:root{{--bg:#101b29;--panel:#192839;--edge:#394f61;--ink:#f4ede1;--faded:#b3c3d2;--gold:#dabb87}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.62 system-ui,Segoe UI,sans-serif}}
header{{padding:35px max(18px,calc((100vw - 1080px)/2)) 20px;border-bottom:1px solid var(--edge);background:linear-gradient(130deg,#1b3348,#111b28)}}
a{{color:var(--gold)}}a:hover{{color:#fff}}h1{{font:normal clamp(29px,4vw,45px)/1.17 Georgia,serif;margin:13px 0}}
.kicker{{font:700 12px system-ui;letter-spacing:.18em;color:var(--gold)}}p{{color:var(--faded)}}
main{{max-width:1120px;margin:0 auto;padding:25px 20px 90px}}
.counts{{display:flex;flex-wrap:wrap;gap:12px;margin-top:20px}}.counts>div{{flex:1;min-width:160px;background:#192f42;border:1px solid #436078;padding:12px 15px;border-radius:8px}}
.counts strong{{display:block;font:normal 30px Georgia,serif;color:#fff}}.counts span{{font-size:12px;color:var(--faded)}}
.filters{{position:sticky;top:0;z-index:10;background:#101b29f7;border-bottom:1px solid var(--edge);padding:13px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.filters button,.filters input{{padding:9px 11px;background:#213549;color:#f0e1c9;border:1px solid #4c6278;border-radius:6px;font:600 13px system-ui}}
.filters button[aria-pressed="true"]{{background:#684c2c;color:white;border-color:#b58e55}}
.filters input{{min-width:160px;flex:1}}.list{{display:grid;gap:13px;max-width:860px;margin-top:18px}}.item{{padding:20px 23px;border:1px solid var(--edge);border-radius:9px;background:var(--panel)}}
.meta{{display:flex;gap:12px;color:var(--gold);font:700 11px system-ui;text-transform:uppercase;letter-spacing:.06em}}
.item h3{{font:normal 24px/1.28 Georgia,serif;margin:9px 0}}.item p{{color:#e1e6e7;margin:8px 0 0}}
.item details{{margin-top:16px;border-top:1px solid var(--edge);padding-top:9px;color:var(--faded);font-size:12px}}
.social-evidence{{background:var(--panel);border:1px solid var(--edge);padding:18px;border-radius:9px;margin:18px 0 30px}}
.social-evidence>summary{{cursor:pointer;color:var(--gold);font-weight:700}}
.social-scroll{{overflow-x:auto}}.social-evidence table{{width:100%;border-collapse:collapse;min-width:760px}}
.social-evidence td,.social-evidence th{{border-bottom:1px solid var(--edge);padding:8px;text-align:left;font-size:13px}}
.social-evidence code{{font-size:11px}}.social-evidence p{{font-size:13px}}
.item summary{{cursor:pointer;color:var(--gold)}}.item small{{display:block;margin:9px 0;overflow-wrap:anywhere}}.empty{{padding:22px;border:1px dashed var(--edge);border-radius:8px}}
@media(max-width:580px){{.item{{padding:15px}}.filters input{{width:100%;flex-basis:100%}}}}
</style>
<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head><body><header><nav><a href="/campaign">Campaign</a> · <a href="/timeline">The Imperial Annals</a> · <a href="/empire-archive">Empire Archive</a></nav>
<div class="kicker">HISTORICAL OBSERVATORY · CIVIC & FRONTIER HISTORY</div><h1>{h(campaign['empire_name'])}</h1>
<p>Governments, political crises, council changes, colonies and infrastructure — supporting the main historical timeline.</p>{counters}</header>
<main><p>The observation dates below record what changed between archived Ironman saves. The first archive establishes a starting state, not a claim that every building, office or station was founded on 1 January 2200. A system becoming known is not necessarily a completed survey.</p>
{crises_section}
{social_section}
<div class="filters"><input id="search" type="search" placeholder="Search dates, systems, offices or stations" aria-label="Search events">
<button data-kind="All" aria-pressed="true">All</button><button data-kind="Politics">Politics</button><button data-kind="Exploration">Exploration</button>
<button data-kind="Expansion">Expansion</button><button data-kind="Infrastructure">Infrastructure</button></div>
<div id="result-count" aria-live="polite"></div><section class="list" id="records">{story}</section></main>
<script>(()=>{{let kind='All';const q=document.getElementById('search');const records=[...document.querySelectorAll('.item')];function apply(){{let count=0;const term=q.value.trim().toLowerCase();records.forEach(el=>{{const show=(kind==='All'||kind===el.dataset.kind)&&el.dataset.text.includes(term);el.hidden=!show;if(show)count++}});document.getElementById('result-count').textContent=count+' matching historical changes';}}q.addEventListener('input',apply);document.querySelectorAll('[data-kind]').forEach(b=>b.addEventListener('click',()=>{{kind=b.dataset.kind;document.querySelectorAll('[data-kind]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));apply()}}));apply();}})();</script></body></html>'''
    dest=archive/'Civic_Frontier_History.html'
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.civic_frontier_',suffix='.html',dir=archive)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            out.write(html)
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return dest


def render_intelligence_history(db, campaign_id: int) -> Path:
    """Read-only audit of player-owned networks, with no operational fiction."""
    import html
    import os
    import tempfile
    campaign = db.campaign(campaign_id)
    if campaign is None:
        raise ValueError('Campaign not found')
    archive = Path(str(campaign['archive_dir']))
    observations = read_observations(archive, db.all_snapshots(campaign_id))
    # Group each stable owner/target/network id as an observation history.
    tracks = {}
    for obs in observations:
        for net in (obs.get('spy_networks') or {}).values():
            key = (net['network_id'], net['owner_id'], net['target_id'])
            tracks.setdefault(key, []).append((obs, net))
    rows = []
    for (_ident, owner, target), history in sorted(tracks.items(), key=lambda x:(x[0][2], x[0][0])):
        first, initial = history[0]
        last, latest = history[-1]
        active = [obs for obs, net in history if net.get('active_evidence')]
        title = (f'Network {initial["network_id"]} — foreign country {target}')
        detail = (f'First saved appearance: {first["date"]} · '
                  f'last preserved appearance: {last["date"]} · '
                  f'{len(history)} dated snapshots.')
        signal = ('Explicit operational indicator in saved network fields.' if active else
                  'Only a passive owner-target record is retained; activity is not established.')
        source = f'SHA-256: {first.get("snapshot_sha256", "unknown")}'
        rows.append('<article><h2>'+html.escape(title)+'</h2><p>'+html.escape(detail)+
                    '</p><p>'+html.escape(signal)+'</p><small>'+html.escape(source)+'</small></article>')
    body = ''.join(rows) or ('<p>No player-owned spy-network observations are yet available. '
                              'Older archives can be re-indexed with Update Historical Timeline.</p>')
    page = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Intelligence Network Register — Stellaris Historian</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#080f17;color:#dcefe9;font:15px/1.65 Segoe UI,system-ui,sans-serif}header,main,footer{padding:22px clamp(18px,5vw,65px)}header{background:#101e29;border-bottom:1px solid #284f54}a{color:#8cdef0}nav{display:flex;gap:20px;flex-wrap:wrap}main{max-width:1200px;margin:auto}h1{color:#d1f6e7;font:normal clamp(26px,4vw,44px) Georgia,serif}h2{color:#9de8df;font:600 20px Georgia,serif}article{background:#10232c;border:1px solid #31505c;border-radius:9px;padding:16px 19px;margin-bottom:13px}p{margin:9px 0}small{color:#90b1bc;overflow-wrap:anywhere}footer{border-top:1px solid #284f54;color:#9db5b8}</style>
</head><body><header><nav><a href="/campaign">Campaign</a><a href="/timeline">The Imperial Annals</a><a href="/civic-frontier-history">Civic &amp; Frontier History</a></nav>
<h1>Intelligence Network Register</h1><p>Player-owned network structures recovered from processed Ironman saves. Network creation and espionage actions are not automatically the same event.</p></header>
<main>""" + body + """</main><footer>Stellaris Historian · PillBoxUK · <a href="https://github.com/PillBoxUK/Stellaris-Historian">Open-source project</a><p>Target identifiers are internal country references, not evidence of an empire's public identity. No screenshot is used as evidence.</p></footer></body></html>"""
    path = archive / 'Intelligence_Network_Register.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.intelligence_', suffix='.html', dir=archive)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(page)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path
