"""Save-native research queues, stored as optional and rebuildable sidecar evidence.

No changes to canonical history or its migrations. Failed research collection must
never block the normal save-processing transaction.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import zipfile
from pathlib import Path

from .core.stellaris_text import _extract_braced_after, _find_named_block
from .domains.technology.parser import _player_country_record_fast
from .save_reader import _player_country_id

_DISCIPLINES = ('physics', 'society', 'engineering')
_DATE = re.compile(r'^\d{4}\.\d{2}\.\d{2}$')
_TECH = re.compile(r'(?m)^\s*technology\s*=\s*"([^"\n]+)"')
_PROGRESS = re.compile(r'(?m)^\s*progress\s*=\s*([0-9.]+)')
_QUEUE_DATE = re.compile(r'(?m)^\s*date\s*=\s*"?(\d{4}\.\d{2}\.\d{2})"?')
_META_DATE = re.compile(r'(?m)^\s*date\s*=\s*"?(\d{4}\.\d{2}\.\d{2})"?')


def ledger_path(archive_dir: Path) -> Path:
    return Path(archive_dir) / 'Research_History.sqlite3'


def _db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=20)
    conn.execute('''CREATE TABLE IF NOT EXISTS observations (
        sha256 TEXT PRIMARY KEY, game_date TEXT NOT NULL,
        archive_filename TEXT NOT NULL, player_country_id INTEGER NOT NULL,
        queues_json TEXT NOT NULL, captured_seconds REAL NOT NULL,
        parser_version INTEGER NOT NULL DEFAULT 1
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS research_observations_date ON observations(game_date)')
    return conn


def _queue_entries(block: str) -> list[dict]:
    """Extract top-level anonymous queue items without crossing nested braces."""
    result = []
    pos = 0
    while True:
        start = block.find('{', pos)
        if start < 0:
            break
        inner = _extract_braced_after(block, start)
        if inner is None:
            break
        # Each queue item is an anonymous braced record. Queue entry text is
        # short; its nested brackets, if any, do not contaminate the next item.
        tech = _TECH.search(inner)
        if tech:
            progress = _PROGRESS.search(inner)
            date = _QUEUE_DATE.search(inner)
            item = {'key':tech.group(1), 'progress':None, 'queue_date':date.group(1) if date else None}
            if progress:
                try:
                    item['progress'] = max(0, float(progress.group(1)))
                except ValueError:
                    pass
            result.append(item)
        # Find the actual matched block end (not its first internal close).
        depth, quoted, escaped = 0, False, False
        for i in range(start, len(block)):
            c = block[i]
            if quoted:
                if escaped: escaped = False
                elif c == '\\': escaped = True
                elif c == '"': quoted = False
                continue
            if c == '"': quoted = True
            elif c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    pos = i+1
                    break
        else:
            break
    return result


def parse_research_save(path: Path) -> dict:
    started=time.perf_counter()
    with zipfile.ZipFile(path) as z:
        metadata = z.read('meta').decode('utf-8', 'replace')
        gamestate = z.read('gamestate').decode('utf-8', 'replace')
    meta_match = _META_DATE.search(metadata)
    if not meta_match:
        raise ValueError('Save metadata has no native game date')
    game_date = meta_match.group(1)
    country_id = _player_country_id(gamestate)
    if country_id is None:
        raise ValueError('Save has no resolvable player country ID')
    country = _player_country_record_fast(gamestate, country_id)
    if country is None:
        raise ValueError('Save has no resolvable player country technology status')
    status = _find_named_block(country, 'tech_status')
    if status is None:
        raise ValueError('Player country has no tech_status block')
    queues = {}
    for discipline in _DISCIPLINES:
        queue = _find_named_block(status, discipline+'_queue')
        rows = _queue_entries(queue or '')
        for row in rows:
            if row['queue_date'] and row['queue_date'] > game_date:
                # An impossible future queue date must not be made into a timeline date.
                row['queue_date'] = None
        queues[discipline] = rows
    return {'game_date':game_date, 'player_country_id':country_id,
            'queues':queues, 'seconds':time.perf_counter()-started}


def capture_observation(archive_dir: Path, archive_file: Path, sha256: str) -> dict:
    """Idempotent; opens the save only if this particular hash is not indexed."""
    dbfile = ledger_path(archive_dir)
    with _db(dbfile) as conn:
        row = conn.execute('SELECT game_date FROM observations WHERE sha256=?',(sha256,)).fetchone()
        if row:
            return {'cached':True, 'game_date':row[0], 'seconds':0.0}
    content = parse_research_save(archive_file)
    with _db(dbfile) as conn:
        conn.execute('''INSERT OR IGNORE INTO observations
            (sha256,game_date,archive_filename,player_country_id,queues_json,captured_seconds)
            VALUES (?,?,?,?,?,?)''',
            (sha256,content['game_date'],archive_file.name,content['player_country_id'],
             json.dumps(content['queues'],separators=(',',':')),content['seconds']))
    return {'cached':False, 'game_date':content['game_date'], 'seconds':content['seconds']}


def read_observations(archive_dir: Path, snapshots: list) -> list[dict]:
    """Use only hashed, successfully processed canonical snapshots for the active campaign."""
    path = ledger_path(archive_dir)
    if not path.is_file():
        return []
    allowed = {str(row['sha256']):row for row in snapshots if int(row['processed'])}
    if not allowed:
        return []
    with _db(path) as conn:
        rows = conn.execute('SELECT sha256,game_date,queues_json FROM observations ORDER BY game_date,archive_filename').fetchall()
    results=[]
    for sha,date,raw in rows:
        row=allowed.get(sha)
        if row is None or str(row['game_date'])!=date:
            continue
        try:
            q=json.loads(raw)
            if not isinstance(q,dict):continue
        except (ValueError,TypeError):continue
        results.append({'game_date':date,'sha256':sha,'snapshot_id':int(row['id']),'queues':q})
    results.sort(key=lambda r:(r['game_date'],r['snapshot_id']))
    return results


def research_events(observations: list[dict]) -> list[dict]:
    """Report queue arrivals, changing active selections and revisited selections.

    If a new selection follows another, we cannot infer that its predecessor
    was cancelled: it may simply have been completed between snapshots.
    """
    result=[]
    last={}
    seen_by_discipline={name:set() for name in _DISCIPLINES}
    emitted=set()
    for row in observations:
        date=row['game_date']
        for discipline in _DISCIPLINES:
            entries=row['queues'].get(discipline) or []
            active = entries[0] if entries else None
            prior = last.get(discipline)
            if active and isinstance(active,dict) and active.get('key'):
                key=str(active['key'])
                prior_key = str(prior['key']) if prior else None
                if prior_key != key:
                    first = key not in seen_by_discipline[discipline]
                    event_kind = 'first_observed' if first else 'resumed_observed'
                    # A saved queue date can predate the first observation, but
                    # must not be projected before the preceding observed state.
                    native_date=active.get('queue_date')
                    after = prior.get('game_date') if prior else None
                    anchored = (first and native_date and _DATE.fullmatch(native_date)
                                and native_date <= date and (not after or native_date > after))
                    when=native_date if anchored else date
                    event={'date':when,'observed_date':date,'discipline':discipline,
                           'key':key,'queue_date':native_date,'progress':active.get('progress'),
                           'previous_key':prior_key,'kind':event_kind,
                           'precision':'native_queue_date' if anchored else 'first_observed'}
                    identity=(when,discipline,key,event_kind)
                    if identity not in emitted:
                        result.append(event);emitted.add(identity)
                seen_by_discipline[discipline].add(key)
                last[discipline]={**active,'game_date':date}
            else:
                # Empty queue means nothing active in this discipline on this save.
                last[discipline]=None
    return result


def render_research_history(db, campaign_id: int) -> Path:
    """A read-only dossier for every retained Physics/Society/Engineering queue observation."""
    from html import escape
    from collections import defaultdict
    from .domains.technology.parser import _humanise_technology_key
    from .localisation import resolve_localisation_key

    campaign=db.campaign(campaign_id)
    if campaign is None:
        raise ValueError('No active campaign')
    archive=Path(campaign['archive_dir'])
    observations=read_observations(archive,list(db.all_snapshots(campaign_id)))
    subjects=defaultdict(list)
    changes=research_events(observations)
    lookup={}
    source_save=Path(campaign['source_save'])
    def label(k):
        if k not in lookup:
            # Resolve each unique key once, not for each save or timeline row.
            lookup[k] = resolve_localisation_key(source_save,k) or _humanise_technology_key(k)
        return lookup[k]
    for row in observations:
        for branch in _DISCIPLINES:
            for position,item in enumerate(row['queues'].get(branch,[]) or []):
                if isinstance(item,dict) and item.get('key'):
                    subjects[(branch,item['key'])].append({
                        'date':row['game_date'],'queue_date':item.get('queue_date'),
                        'progress':item.get('progress'),'position':position+1})
    event_lookup=defaultdict(list)
    for item in changes:
        event_lookup[(item['discipline'],item['key'])].append(item)
    blocks=[]
    for (branch,key),points in sorted(subjects.items(),key=lambda x:(x[0][0],x[1][0]['date'],x[0][1])):
        first,last=points[0],points[-1]
        progress=last['progress']
        full_name=label(key)
        markers=event_lookup[(branch,key)]
        progress_label=f'{progress:,.1f}' if isinstance(progress,(int,float)) else 'Not retained'
        def _item(row):
            amount=row['progress']
            display=(f'{amount:,.1f} points' if isinstance(amount,(int,float)) else 'Progress unavailable')
            desc=f"<strong>{escape(row['date'])}</strong> — {escape(display)}"
            if row['position']!=1:
                desc+=' · Queued behind another project'
            if row['queue_date']:
                desc+=f" · Native queue date {escape(row['queue_date'])}"
            return '<li>'+desc+'</li>'
        episodes=(' · '.join(escape(ev['observed_date']) for ev in markers))
        blocks.append(f'''<article class="project" data-discipline="{escape(branch)}" data-name="{escape(full_name.casefold())}">
          <div class="project-header"><span class="branch">{escape(branch.upper())}</span>
          <span class="muted">{len(points)} archived observations · First observed {escape(first['date'])}</span></div>
          <h2>{escape(full_name)}</h2>
          <p>By {escape(last['date'])}, recorded progress stood at <strong>{escape(progress_label)} research points</strong>.
          The project had appeared in the research queue {len(points)} times among the retained archives.
          {('The leading research selection changed to this project at '+episodes+'.') if markers else ''}</p>
          <details><summary>Inspect all {len(points)} dated observations</summary>
          <ol class="observations">{''.join(_item(row) for row in points)}</ol></details></article>''')
    title=escape(campaign['empire_name'])
    warning=('No research observations have been indexed for this campaign yet. '
             'Turn Live History OFF, then run Manage Campaign → Rewrite Timeline to scan older saves.' if not observations else
             f"Research queue evidence has been read from {len(observations)} processed archive saves. "
             "Research queue dates, snapshot progress and first sightings do not prove uninterrupted research or a specific cancellation decision.")
    output='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Research History — '''+title+'''</title><style>
    :root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f5efe3;color:#263849;font:15px/1.65 system-ui,Arial,sans-serif}nav{background:#152c40;padding:15px max(22px,calc((100vw - 1050px)/2));display:flex;gap:22px;flex-wrap:wrap}nav a{color:#f4d5a1;text-decoration:none;font-weight:700}header{background:linear-gradient(115deg,#203b51,#10202f);padding:45px max(20px,calc((100vw - 1050px)/2));color:#fff4de}header .eyebrow{letter-spacing:.17em;font-size:12px;color:#f2c988}header h1{font:normal clamp(35px,5vw,59px) Georgia,serif;margin:13px 0}header p{max-width:850px;color:#d5e0e7}main{max-width:1110px;margin:auto;padding:22px 25px 70px}.explain{background:#fff9ed;border-left:5px solid #b98448;padding:17px 20px;margin-bottom:20px;border-radius:4px}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:22px 0}.toolbar button,.toolbar input{border:1px solid #bdab93;background:#fffaf0;border-radius:5px;padding:10px 13px;color:#203347}.toolbar button{cursor:pointer;font-weight:700}.toolbar button.active{background:#1f3b54;color:white}.toolbar input{flex:1;min-width:180px}.results{color:#6c5a47;font-size:13px}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px}.project{background:#fffdfa;border:1px solid #d6c8b3;padding:21px;border-radius:8px;box-shadow:0 5px 17px #735b3314}.project[hidden]{display:none}.project-header{display:flex;align-items:center;gap:8px;justify-content:space-between;flex-wrap:wrap}.branch{border:1px solid #c8a76e;border-radius:20px;padding:1px 9px;color:#80562e;font:bold 10px system-ui;letter-spacing:.12em}.muted{color:#687b87;font-size:12px}.project h2{font:normal 24px Georgia,serif;color:#203447;margin:15px 0 7px}.project p{color:#4a5966;font:14px/1.7 Georgia,serif}.project details{border-top:1px solid #e0d5c6;margin-top:17px;padding-top:12px}.project summary{cursor:pointer;color:#745631;font-weight:700;font-size:13px}.observations{padding-left:20px;max-height:315px;overflow:auto}.observations li{font-size:12px;margin:8px 0;color:#455363}@media(max-width:670px){.cards{grid-template-columns:1fr}main{padding:18px 12px}}@media print{nav,.toolbar{display:none}.cards{display:block}.project{break-inside:avoid;margin:10px 0}}
    </style>
<link rel="stylesheet" href="/static/historian-theme.css?v=087">
<script src="/static/historian-theme.js?v=087"></script>
</head><body><nav><a href="/campaign">Campaign</a><a href="/timeline">Imperial Annals</a><a href="/time-machine">Time Machine</a><a href="/empire-archive">Empire Archive</a></nav>
    <header><div class="eyebrow">THE IMPERIAL ANNALS · THE SCIENTIFIC RECORD</div><h1>Research History</h1>
    <p>'''+title+''' · The pursuits of Physics, Society and Engineering across the archived centuries.</p></header>
    <main><section class="explain">'''+escape(warning)+'''</section>
    <div class="toolbar" aria-label="Research disciplines"><button type="button" data-branch="all" class="active">All research</button><button type="button" data-branch="physics">Physics</button><button type="button" data-branch="society">Society</button><button type="button" data-branch="engineering">Engineering</button>
    <input id="find" type="search" placeholder="Find a technology…" aria-label="Search research projects"><span class="results" id="count"></span></div>
    <div class="cards">'''+''.join(blocks)+'''</div></main>
    <script>(()=>{const buttons=[...document.querySelectorAll('[data-branch]')],panels=[...document.querySelectorAll('.project')],find=document.querySelector('#find');let branch='all';function run(){const term=find.value.trim().toLowerCase();let n=0;panels.forEach(p=>{p.hidden=!(branch==='all'||p.dataset.discipline===branch)||!p.dataset.name.includes(term);if(!p.hidden)n++});document.querySelector('#count').textContent=n+' projects';}buttons.forEach(b=>b.addEventListener('click',()=>{branch=b.dataset.branch;buttons.forEach(c=>c.classList.toggle('active',c===b));run()}));find.addEventListener('input',run);run();})();</script></body></html>'''
    output_path=archive/'Research_History.html'
    import os,tempfile
    output_path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.research_',suffix='.html',dir=archive)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:f.write(output)
        os.replace(tmp,output_path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return output_path
