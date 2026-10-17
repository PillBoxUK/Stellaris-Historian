"""Native player-country timeline events, retained exactly and conservatively.

Only milestones whose meanings are clear enough to publish are narrated. Native
entity references remain in sidecar evidence, never guessed as opponent names.
"""
from __future__ import annotations
from pathlib import Path
import json, os, re, tempfile, sqlite3
from .save_reader import read_save_texts, _player_country_id
from .core.stellaris_text import _find_named_block, _indented_numeric_record, _braced_content_and_end

_DEFINITIONS = {
    'timeline_first_war_won': ('War','First wartime victory', 'The civilisation secured its first recorded victory in war.'),
    'timeline_war_won': ('War','Victory in war', 'Another victory in war was entered into the history of the civilisation.'),
    'timeline_first_precursor_discovered': ('Exploration','Signs of an ancient precursor', 'Explorers encountered the first evidence of an ancient precursor civilisation.'),
    'timeline_first_arc_site': ('Exploration','First archaeological discovery', 'An archaeological site entered the civilisation’s history, opening a new investigation into the distant past.'),
    'timeline_first_intelligent_life': ('Exploration','First encounter with intelligent life', 'The civilisation encountered evidence of intelligent life beyond its own people.'),
    'timeline_first_rare_tech': ('Technology','A rare scientific breakthrough', 'Researchers made their first breakthrough in a rare field of technology.'),
    'timeline_meet_fallen_empire_discover': ('Diplomacy','An ancient interstellar power discovered', 'The civilisation became aware of an ancient, fallen interstellar empire.'),
    'timeline_lost_colony_found_homeworld_sender': ('Story','A link to the lost colony’s past', 'Contact with the distant colony’s ancestral homeworld became part of its recorded history.'),
    'timeline_first_storm_within_borders': ('Exploration','Storm within the realm', 'An interstellar storm entered territory held by the civilisation.'),
    'timeline_first_espionage_action': ('Politics','First recorded espionage operation', 'The civilisation undertook its first recorded act of interstellar espionage.'),
    'timeline_first_ascension_perk': ('Politics','A defining new ambition', 'The civilisation adopted its first ascension perk, marking a new commitment in its long-term development.'),
    'timeline_first_relic': ('Exploration','An ancient relic acquired', 'A relic was acquired for the first time, joining the civilisation’s growing collection of discoveries.'),
    'timeline_first_wormhole': ('Exploration','The first wormhole', 'Explorers recorded the first wormhole discovery, revealing another route through the galaxy.'),
    'timeline_first_robot': ('Technology','First robotic development', 'The first recorded robotic development entered the civilisation’s history.'),
    'timeline_elections': ('Politics','An election takes place', 'A new election marked a turning point in the political life of the civilisation.'),
}


def extract_player_milestones(text: str) -> list[dict]:
    country_id=_player_country_id(text)
    country=_indented_numeric_record(_find_named_block(text,'country'),country_id) if country_id is not None else None
    timeline=_find_named_block(country or '', 'timeline_events')
    if not timeline: return []
    result=[]; seen=set()
    # Anonymous event objects are direct children; braces inside data are scanned correctly.
    pattern=re.compile(r'(?m)^\s*\{\s*date\s*=')
    position=0
    while (match:=pattern.search(timeline,position)) is not None:
        body,end=_braced_content_and_end(timeline,match.start())
        if body is None or end is None:break
        position=end
        dated=re.search(r'\bdate\s*=\s*"?(\d{4}\.\d{2}\.\d{2})"?',body)
        definition=re.search(r'\bdefinition\s*=\s*"([A-Za-z_0-9]+)"',body)
        if not dated or not definition:continue
        key=(dated.group(1),definition.group(1))
        if key in seen:continue
        seen.add(key)
        typed=_find_named_block(body,'types') or ''
        values=_find_named_block(body,'data') or ''
        result.append({'date':dated.group(1),'definition':definition.group(1),
                       'reference_types':re.findall(r'\b(?:country|planet|species|leader|fleet|ship|system)\b',typed),
                       'reference_ids':[int(x) for x in re.findall(r'\b\d+\b',values)]})
    return result


def _store_native_evidence(archive_dir:Path, data:dict) -> None:
    """Durable, campaign-local SQL history; cumulative events are deduplicated."""
    db_path=Path(archive_dir)/'Native_Evidence.sqlite3'
    with sqlite3.connect(db_path,timeout=30) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute("""CREATE TABLE IF NOT EXISTS native_timeline_events (
            game_date TEXT NOT NULL, definition TEXT NOT NULL,
            reference_types_json TEXT NOT NULL, reference_ids_json TEXT NOT NULL,
            first_snapshot_sha256 TEXT NOT NULL, last_snapshot_sha256 TEXT NOT NULL,
            PRIMARY KEY (game_date, definition, reference_ids_json)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS galactic_institutions (
            event_key TEXT PRIMARY KEY, game_date TEXT NOT NULL,
            first_snapshot_sha256 TEXT NOT NULL, last_snapshot_sha256 TEXT NOT NULL
        )""")
        sha=str(data.get('snapshot_sha256') or '')
        for item in data.get('events',[]):
            date=str(item['date']);definition=str(item['definition'])
            types=json.dumps(item.get('reference_types',[]),ensure_ascii=False)
            ids=json.dumps(item.get('reference_ids',[]),ensure_ascii=False)
            conn.execute("""INSERT INTO native_timeline_events VALUES (?,?,?,?,?,?)
                ON CONFLICT(game_date,definition,reference_ids_json)
                DO UPDATE SET last_snapshot_sha256=excluded.last_snapshot_sha256""",
                (date,definition,types,ids,sha,sha))
        for key,field in (('community_formed','galactic_community_formed'),
                          ('council_established','galactic_council_established')):
            date=data.get(field)
            if not date:continue
            conn.execute("""INSERT INTO galactic_institutions VALUES (?,?,?,?)
                ON CONFLICT(event_key) DO UPDATE SET
                game_date=excluded.game_date,last_snapshot_sha256=excluded.last_snapshot_sha256""",
                (key,date,sha,sha))


def capture_native_milestones(archive_dir:Path, save:Path, sha256:str) -> dict:
    archive_dir=Path(archive_dir)
    dest=archive_dir/'Native_Timeline_Milestones.json'
    if dest.exists():
        try:
            old=json.loads(dest.read_text('utf-8'))
            if old.get('snapshot_sha256')==sha256 and old.get('version')==2:
                if not (archive_dir/'Native_Evidence.sqlite3').is_file():
                    _store_native_evidence(archive_dir,old)
                return old
        except (OSError,ValueError):pass
    _meta,gamestate=read_save_texts(save)
    galactic=_find_named_block(gamestate,'galactic_community') or ''
    founding=re.search(r'\bcommunity_formed\s*=\s*"(\d{4}\.\d{2}\.\d{2})"',galactic)
    council=re.search(r'\bcouncil_established\s*=\s*"(\d{4}\.\d{2}\.\d{2})"',galactic)
    data={'version':2,'snapshot_sha256':sha256,'snapshot_name':save.name,
          'events':extract_player_milestones(gamestate),
          'galactic_community_formed':founding.group(1) if founding else None,
          'galactic_council_established':council.group(1) if council else None}
    archive_dir.mkdir(parents=True,exist_ok=True)
    _store_native_evidence(archive_dir,data)
    fd,tmp=tempfile.mkstemp(prefix='.native_timeline_',suffix='.json',dir=archive_dir)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(data,out,indent=2,ensure_ascii=False)
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return data


def milestone_events(data:dict, empire_name:str):
    """Return plain dictionaries to avoid dependency cycles with timeline.py."""
    result=[]
    if data.get('galactic_community_formed'):
        result.append({'date':data['galactic_community_formed'],'category':'Diplomacy',
                      'title':'Formation of the Galactic Community',
                      'body':'The Galactic Community was founded, creating a new forum for diplomacy and legislation among the stars.',
                      'evidence':'Direct galactic_community/community_formed date. This does not establish when the empire itself joined.'})
    if data.get('galactic_council_established'):
        result.append({'date':data['galactic_council_established'],'category':'Diplomacy',
                      'title':'The Galactic Council is established',
                      'body':'The Galactic Community established its Council, giving the wider galactic assembly a new centre of political authority.',
                      'evidence':'Direct galactic_community/council_established date. Member appointments require independent evidence.'})
    for e in data.get('events',[]):
        entry=_DEFINITIONS.get(e.get('definition'))
        if not entry:continue
        category,title,desc=entry
        if e['definition']=='timeline_first_war_won':
            desc=f'{empire_name} secured its first native-recorded victory in war.'
        elif e['definition']=='timeline_war_won':
            desc=f'{empire_name} secured another victory in war.'
        result.append({'date':e['date'],'category':category,'title':title,'body':desc,
                       'evidence':f"Native player-country milestone: {e['definition']}; typed references "
                           f"{list(zip(e.get('reference_types',[]),e.get('reference_ids',[])))}. "
                           'Specific participants, war identity and consequences are not inferred from typed targets.'})
    return result
