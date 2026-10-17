"""Annual Government Census - historical rosters from 1 January save caches.

Never project latest leader_registry data backwards. For each exact year boundary,
load only the hash-matched, versioned snapshot cache belonging to that date.
No archive files, SQL evidence or caches are modified here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import re
import sqlite3

from .domains.people import CACHE_COMPONENT_NAME, CACHE_COMPONENT_VERSION
from .local_database_browser import readonly_connection
from .publication_names import usable_name, publication_assignment
from .verified_milestones import service_milestones


def _read_cache(archive: Path, snap: dict) -> tuple[dict | None, str]:
    """Read one already-parsed save, verifying its source and parser version."""
    source_hash = str(snap.get('sha256') or '')
    if len(source_hash) != 64 or any(c not in '0123456789abcdef' for c in source_hash.lower()):
        return None, 'missing SHA-256'
    cache_file = archive / '.historian_cache' / (source_hash + '.json')
    source = Path(str(snap.get('archive_path') or ''))
    try:
        stat = source.stat()
        value = json.loads(cache_file.read_text('utf-8'))
    except (OSError, ValueError, TypeError):
        return None, 'archived save or parsed cache is unavailable'
    if not isinstance(value, dict) or value.get('cache_schema_version') != 1:
        return None, 'incompatible cache schema'
    if value.get('source_sha256') != source_hash:
        return None, 'cache source hash mismatch'
    if value.get('archive_size') != stat.st_size or value.get('archive_mtime_ns') != stat.st_mtime_ns:
        return None, 'cache fingerprint no longer matches the archive'
    part = (value.get('components') or {}).get(CACHE_COMPONENT_NAME) or {}
    if part.get('version') != CACHE_COMPONENT_VERSION:
        return None, 'leader parser cache needs refreshing'
    data = part.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('leaders'), dict):
        return None, 'leader roster is missing from cache'
    if data.get('game_date') != snap.get('game_date'):
        return None, 'leader cache date mismatch'
    return data, ''


def _label(identifier: str | None) -> str:
    if not identifier:
        return ''
    value = str(identifier)
    for prefix in ('gov_', 'auth_', 'civic_', 'leader_trait_', 'trait_ruler_'):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value.replace('_', ' ').strip().title()


def _str(value: Any) -> str:
    return str(value).strip() if value is not None else ''


def _people_from(data: dict, ruler_id: Any, ruler_name: str) -> list[dict]:
    people = []
    try:
        ruler_id = int(ruler_id)
    except (TypeError, ValueError):
        ruler_id = None
    for identifier, raw in data.get('leaders', {}).items():
        if not isinstance(raw, dict):
            continue
        try:
            lid = int(identifier)
        except (ValueError, TypeError):
            continue
        # Names and roles are drawn from the actual historic snapshot, never
        # the latest registry row; the state may have changed since then.
        name = _str(raw.get('name')) if usable_name(raw.get('name')) else 'An unnamed officeholder'
        raw_traits = raw.get('traits') or []
        traits = raw.get('trait_names') or []
        if not isinstance(traits, list):
            traits = []
        if not isinstance(raw_traits, list):
            raw_traits = []
        # Retain trait evidence even when localisation is incomplete.
        clean_traits = [(_str(traits[i]) if i < len(traits) and usable_name(traits[i]) else _label(t)) for i, t in enumerate(raw_traits)]
        if len(traits) > len(raw_traits):
            clean_traits.extend(_str(t) for t in traits[len(raw_traits):] if usable_name(t))
        clean_traits = list(dict.fromkeys(t for t in clean_traits if t))
        is_ruler = (lid == ruler_id) or bool(raw.get('is_ruler'))
        office = _str(raw.get('council_role_name')) if usable_name(raw.get('council_role_name')) else _label(raw.get('council_role_key'))
        assignment_type = _str(raw.get('location_type')).lower()
        assignment = publication_assignment(raw.get('assignment_name'), assignment_type)
        rank = _label(raw.get('leader_class')) or 'Leader'
        if is_ruler:
            group = 'Ruler'
        elif office:
            group = 'Council'
        elif assignment_type in ('planet', 'colony', 'sector'):
            group = 'Administration'
        else:
            group = 'Other service'
        people.append({
            'leader_id': lid,
            'name': name,
            'leader_class': rank,
            'group': group,
            'ruler': is_ruler,
            'council_office': office,
            'assignment': assignment,
            'assignment_type': assignment_type,
            'level': raw.get('level'),
            'traits': clean_traits,
            'recruitment_date': _str(raw.get('recruitment_date')),
        })
    order = {'Ruler': 0, 'Council': 1, 'Administration': 2, 'Other service': 3}
    return sorted(people, key=lambda p: (order[p['group']], p['name'].casefold(), p['leader_id']))


def annual_censuses(db_path: Path, campaign_id: int, archive_dir: Path | None = None) -> list[dict]:
    """Return one record for each 1 Jan, or the initial saved date for a mid-year opening.

    Available=False means exactly that: we have not inferred a roster from a
    later or earlier save. No census event should be published for these years.
    """
    with readonly_connection(db_path) as con:
        campaign = con.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
        if campaign is None:
            raise ValueError('Campaign not found.')
        beginning = str(campaign['first_game_date'] or '')
        ending = str(campaign['latest_game_date'] or '')
        if not (len(beginning) >= 10 and len(ending) >= 10):
            return []
        if archive_dir is None:
            archive_dir = Path(str(campaign['archive_dir']))
        # Only exact matching dates are accepted. Same-date archives are sorted
        # by capture sequence, preserving distinct states and choosing the last.
        snaps = con.execute('''SELECT id,game_date,sha256,archive_path,sequence_no
            FROM snapshots WHERE campaign_id=? AND processed=1
            ORDER BY game_date, COALESCE(sequence_no,-1), id''', (campaign_id,)).fetchall()
        snapshot_by_date = {str(s['game_date']): dict(s) for s in snaps}
        political = {}
        for row in con.execute('''SELECT snapshot_id,game_date,state_json FROM politics_states
            WHERE campaign_id=? ORDER BY game_date,id''', (campaign_id,)):
            try:
                state = json.loads(row['state_json'] or '{}')
            except (TypeError, ValueError):
                continue
            if isinstance(state, dict):
                political[int(row['snapshot_id'])] = state
    years = range(int(beginning[:4]), int(ending[:4]) + 1)
    dates = [f'{y}.01.01' for y in years if beginning <= f'{y}.01.01' <= ending]
    if beginning not in dates:
        dates.insert(0, beginning)
    out = []
    for date in dates:
        year = date[:4]
        snap = snapshot_by_date.get(date)
        row = {'year': year, 'date': date, 'available': False, 'people': [],
               'government': '', 'authority': '', 'ruler_name': '',
               'source': None, 'reason': '', 'opening': date == beginning}
        if snap is None:
            row['reason'] = 'No processed save exists on this exact date.'
            out.append(row)
            continue
        data, error = _read_cache(archive_dir, snap)
        if data is None:
            row['reason'] = error
            out.append(row)
            continue
        state = political.get(int(snap['id'])) or {}
        people = _people_from(data, state.get('ruler_id'), _str(state.get('ruler_name')))
        row.update({
            'available': True,
            'people': people,
            'government': _label(state.get('government_type')),
            'authority': _label(state.get('authority')),
            'ruler_name': _str(state.get('ruler_name')),
            'source': {'snapshot_id': snap['id'], 'sha256': snap['sha256'], 'game_date': snap['game_date']},
        })
        out.append(row)
    # Annotate exact-date people tiles; never backfill unavailable censuses.
    anniversaries = service_milestones(out)
    by_person_date = {(m['date'], m['leader_id']): m['years'] for m in anniversaries}
    for census in out:
        for person in census.get('people', []):
            years = by_person_date.get((census['date'], person['leader_id']))
            if years is not None:
                person['service_milestone'] = f'{years}-year documented service milestone'
    return out



def _career_highlights(db_path: Path, campaign_id: int, censuses: list[dict]) -> None:
    """Add documented, person-attributed career developments to roster tiles.

    Exact date is not implied for first-observed events. Only events with a
    stable leader ID and a retained career record are used. This is read-only.
    """
    try:
        with readonly_connection(db_path) as con:
            evidence = con.execute(
                'SELECT game_date, event_type, leader_id, body FROM leader_career_events '
                'WHERE campaign_id=? AND event_type IN '
                '("leader_traits_gained", "leader_level_changed", "leader_council_changed") '
                'ORDER BY game_date, id', (campaign_id,)).fetchall()
    except (sqlite3.OperationalError, OSError):
        return
    developments: dict[int, list[tuple[str, str]]] = {}
    for event in evidence:
        date = str(event['game_date'] or '')
        kind = str(event['event_type'] or '')
        body = str(event['body'] or '')
        label = ''
        if kind == 'leader_traits_gained':
            match = re.search(r'newly observed traits?:\s*(.+?)\.?$', body, re.I)
            if match:
                traits = match.group(1).rstrip('.').strip()
                if traits and usable_name(traits):
                    label = f'New expertise: {traits}'
        elif kind == 'leader_level_changed':
            match = re.search(r'leader level changed from (\d+) to (\d+)', body, re.I)
            if match and int(match.group(2)) > int(match.group(1)):
                label = f'Advanced to level {int(match.group(2))}'
        elif kind == 'leader_council_changed':
            match = re.search(r'council role (.+?)\.$', body, re.I)
            if match and usable_name(match.group(1)):
                label = f'Council office: {match.group(1)}'
        if label:
            developments.setdefault(int(event['leader_id']), []).append((date,label))
    for census in censuses:
        if not census.get('available'):
            continue
        for person in census.get('people') or []:
            records = [f'By {date}: {label}' for date,label in developments.get(person['leader_id'], ()) if date <= census['date']]
            if records:
                person['career_highlights'] = records[-3:]


def census_prose(item: dict, empire_name: str) -> str:
    """A date-bound civic chronicle, never a projected modern-day leader list.

    This prose describes only the one verified saved snapshot. The census
    does not assert when an officeholder was appointed or acquired a trait.
    """
    if not item.get('available'):
        return ''
    folks = item['people']
    year = item['year']
    date = item['date']
    when = f'At the start of the surviving record on {date}' if item['opening'] else f'On 1 January {year}'
    government = item.get('government') or ''
    authority = item.get('authority') or ''
    if government and authority:
        intro = f'{when}, {empire_name} was governed by its {government}, exercising {authority.lower()} authority.'
    elif government:
        intro = f'{when}, {empire_name} was governed by its {government}.'
    elif authority:
        intro = f'{when}, {empire_name} operated under {authority.lower()} authority.'
    else:
        intro = f'{when}, the leadership of {empire_name} was preserved in a government census.'

    ruler = next((p for p in folks if p['ruler']), None)
    name = ruler['name'] if ruler else (item.get('ruler_name') or '')
    if name and usable_name(name):
        intro += f' {name} held the highest office at that time.'

    def account(p: dict) -> str:
        who = p['name']
        role = p.get('leader_class') or 'leader'
        office = p.get('council_office') or ''
        assignment = p.get('assignment') or ''
        if office:
            account = f'{who}, the {role.lower()} serving as {office}'
        else:
            article = 'an' if role[0].casefold() in 'aeiou' else 'a'
            account = f'{who}, {article} {role.lower()}'
        if assignment:
            account += (f', {assignment}' if assignment.startswith(('aboard ', 'with ', 'on ', 'in '))
                        else f', assigned to {assignment}')
        traits = [t for t in p.get('traits', []) if usable_name(t)]
        if traits:
            account += f' (recorded traits: {", ".join(traits)})'
        return account

    paragraphs = [intro]
    groups = [
        ('Ruler', 'The ruler’s professional record included'),
        ('Council', 'The governing council included'),
        ('Administration', 'Planetary and sector administration included'),
        ('Other service', f'Elsewhere in {empire_name}’s service were'),
    ]
    for group, introduction in groups:
        members = [p for p in folks if p['group'] == group]
        if members:
            paragraphs.append(introduction + ' ' + '; '.join(account(p) for p in members) + '.')
    # This is a *state census*, not an accession or appointment chronicle.
    return '\n\n'.join(paragraphs)


HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Annual Government Census — Historian</title><style>
:root{color-scheme:dark;font-family:system-ui,Segoe UI,sans-serif;background:#0d1623;color:#e7f0f8}*{box-sizing:border-box}body{margin:0}a{color:#eac48b}header{padding:28px max(24px,calc((100vw - 1200px)/2));background:linear-gradient(135deg,#223e53,#142337);border-bottom:1px solid #3b5269}.kicker{font:700 11px system-ui;letter-spacing:.14em;text-transform:uppercase;color:#d8b477}h1,h2{font-family:Georgia,serif;font-weight:normal}h1{font-size:clamp(32px,4.6vw,48px);margin:9px 0}header p{color:#bfcedd}.links{display:flex;gap:18px;flex-wrap:wrap;font-size:13px}main{max-width:1200px;margin:auto;padding:22px 18px 80px}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}input,select{background:#1b3044;border:1px solid #52687d;color:#fff;border-radius:7px;font:inherit;padding:11px;min-width:140px}input{flex:1;min-width:200px}.info{background:#1d3041;border-left:3px solid #ceaa70;padding:12px 16px;font-size:13px;color:#cfdeea;line-height:1.6}.summary{color:#a9c0d1;font-size:13px;margin:14px 0}.census-footer{background:#142337;border-top:2px solid #b68a51;padding:20px max(24px,calc((100vw - 1200px)/2));color:#b3c7d7;font:12px/1.65 system-ui}.census-footer a{color:#eac48b}.census{background:#17293b;border:1px solid #395269;border-radius:12px;padding:22px;margin:18px 0;scroll-margin-top:24px}.head{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}.head h2{margin:0}.meta{color:#a5bdd0;font-size:12px}.group{margin:16px 0 0}.group h3{font:650 13px system-ui;color:#eac48b;margin-bottom:8px;letter-spacing:.045em}.roster{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:9px}.person{padding:14px;border-radius:8px;border:1px solid #3e526a;background:#203449}.person strong{font-size:15px}.person p{margin:5px 0;color:#c0d1df;font-size:13px}.traits{display:flex;gap:5px;flex-wrap:wrap}.service-milestone{font-weight:700!important;color:#f0cc8f!important}.career-highlights{margin:8px 0 0;padding-left:18px;color:#bddad4;font:12px/1.55 system-ui}.career-highlights li{margin:4px 0}.trait{font:12px system-ui;color:#e4d1b5;padding:4px 8px;border-radius:20px;border:1px solid #6a6864}.empty{padding:14px;color:#c2b4a1;background:#302d2b;border-radius:8px}body.hide-nonmatches .person[hidden]{display:none}@media print{header,.controls,.summary{display:none}body{color:#222;background:#fff}.census{break-inside:auto;border:0;border-bottom:1px solid #777;background:#fff;padding:0 0 18px}.person{color:#222;background:#fff;break-inside:avoid-page}.person p{color:#333}.trait{color:#444}}@media(max-width:600px){header{padding:20px}.census{padding:13px}.roster{grid-template-columns:1fr}}
</style>
<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head><body><header><nav class="links"><a href="/campaign">Campaign</a><a href="/timeline">The Imperial Annals</a><a href="/government-people">Government & People</a><a href="/database">Database Explorer</a></nav><div class="kicker" style="margin-top:22px">Historical Observatory · 1 January</div><h1 id="title"></h1><p>A year-by-year roster of actual archived officeholders, assignments, traits and leaders in service.</p></header><main><p class="info">These censuses are derived from snapshots on the <b>exact displayed dates</b>. They do not retrospectively apply a leader's later promotions, traits or assignments to earlier years. Office changes between saves may not be visible. Unavailable years are marked as such rather than reconstructed from future records.</p><div class="controls"><label for="year">Year</label><select id="year"></select><input id="find" placeholder="Search people, posts, traits or years" aria-label="Search censuses"><label><input type="checkbox" id="all" style="min-width:0"> All years</label></div><div id="summary" class="summary"></div><div id="records"></div></main>
<footer class="census-footer" aria-label="Source and project credits"><strong>Stellaris Historian</strong> · PillBoxUK · <a href="https://github.com/PillBoxUK/Stellaris-Historian" target="_blank" rel="noopener noreferrer">Source code on GitHub ↗</a><br>
Unofficial fan project. The records are derived only from archived Ironman saves and the historical evidence database.</footer><script id="census-data" type="application/json">__DATA__</script><script>
'use strict'; const obj=JSON.parse(document.getElementById('census-data').textContent),years=document.getElementById('year'),search=document.getElementById('find'),all=document.getElementById('all'),records=document.getElementById('records');document.getElementById('title').textContent=obj.empire+' · Annual Census';
const E=(tag,cl,txt)=>{let n=document.createElement(tag);if(cl)n.className=cl;if(txt!==undefined)n.textContent=String(txt);return n};
for(let i of obj.censuses){let o=E('option','',i.year+(i.available?'':' · unavailable'));o.value=i.date;years.append(o)}
function render(){records.replaceChildren();let q=search.value.trim().toLocaleLowerCase(),chosen=years.value,n=0;let rows=obj.censuses.filter(i=>(all.checked||i.date===chosen)&&(!q||([i.year,i.date,i.government,i.ruler_name,...i.people.flatMap(p=>[p.name,p.council_office,p.assignment,...p.traits])].join(' ').toLocaleLowerCase().includes(q))));
for(let i of rows){n++;let box=E('section','census');box.id='census-'+i.year;let head=E('div','head');head.append(E('h2','',i.date+' · Government Census'),E('span','meta',i.available?(i.people.length+' active leaders · '+(i.government||'Government unknown')):'Census unavailable'));box.append(head);
if(!i.available){box.append(E('p','empty',i.reason+' Rerun Update Historical Timeline if historic caches were cleaned.'));records.append(box);continue}
let names=E('p','meta','Source: archived save '+i.source.game_date+' · snapshot #'+i.source.snapshot_id+' · SHA-256 '+i.source.sha256.slice(0,12)+'…');box.append(names);
for(let group of ['Ruler','Council','Administration','Other service']){let set=i.people.filter(p=>p.group===group);if(!set.length)continue;let sect=E('div','group');sect.append(E('h3','',group));let tiles=E('div','roster');for(let p of set){let tile=E('div','person');tile.append(E('strong','',p.name));let labels=[p.leader_class,p.council_office,p.assignment].filter(Boolean);tile.append(E('p','',labels.join(' · ')));let tags=E('div','traits');if(p.traits.length){for(let t of p.traits)tags.append(E('span','trait',t))}else tags.append(E('span','meta','No traits recorded'));tile.append(tags);if(p.service_milestone)tile.append(E('p','service-milestone','✦ '+p.service_milestone));if(p.career_highlights?.length){let ul=E('ul','career-highlights');for(let s of p.career_highlights)ul.append(E('li','',s));tile.append(ul)}sect.append();tiles.append(tile)}sect.append(tiles);box.append(sect)}if(!i.people.length)box.append(E('p','empty','No active leader entries available in this saved state.'));records.append(box)}document.getElementById('summary').textContent=n+' census record(s) shown; '+obj.censuses.filter(c=>c.available).length+' years with verified dated rosters.';}
let initial=location.hash.match(/^#census-(\d{4})$/);if(initial){const o=[...years.options].find(x=>x.value.startsWith(initial[1]+'.'));if(o)years.value=o.value}years.addEventListener('change',()=>{location.hash='census-'+years.value.slice(0,4);render()});search.addEventListener('input',()=>{if(search.value)all.checked=true;render()});all.addEventListener('change',render);render();
</script></body></html>'''


def render_annual_census(db_path: Path, campaign_id: int) -> str:
    with readonly_connection(db_path) as con:
        campaign = con.execute('SELECT empire_name FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
    if campaign is None:
        raise ValueError('Campaign not found.')
    records = annual_censuses(db_path, campaign_id)
    _career_highlights(db_path, campaign_id, records)
    payload = {'empire': str(campaign['empire_name']), 'censuses': records}
    data = json.dumps(payload, separators=(',', ':'), ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return HTML.replace('__DATA__', data)
