"""v0.0.86 isolated regression tests. Never opens or changes user campaign data."""
from __future__ import annotations
import ast
from dataclasses import dataclass
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from historian.verified_milestones import service_milestones, classify_milestone

SHA1='a'*64;SHA2='b'*64

def census(year, people, available=True, source_date=None):
    date=f'{year}.01.01'
    return {'date':date, 'year':str(year),'opening':year==2200,'available':available,
            'people':[{'leader_id':i,'name':name,'group':group,'leader_class':group,
                       'council_office':office} for i,name,group,office in people],
            'source':({'snapshot_id':year-2199,'game_date':source_date or date,'sha256':SHA1 if year%2 else SHA2} if available else None)}

def check_milestones():
    ruler=(42,"K'Vara Korik",'Ruler','')
    chief=(12,"D'Kheera",'Council','Head of Research')
    outsider=(8,'Reebik','Other service','')
    rows=[census(y,[ruler,chief,outsider]) for y in range(2200,2211)]
    found=service_milestones(rows)
    names={(x['name'],x['years'],x['date']) for x in found}
    for person in ("K'Vara Korik","D'Kheera","Reebik"):
        assert (person,1,'2201.01.01') in names
        assert (person,5,'2205.01.01') in names
        assert (person,10,'2210.01.01') in names
    assert len(found)==9
    assert 'Continuous service between archived dates is not proven' in found[0]['evidence']
    assert 'snapshot #1' in found[0]['evidence']
    assert len(found[0]['evidence'])<800
    # Missing annual cache, non-January replacement, missed appearances all break the chain.
    no_cache=list(rows);no_cache[2]=census(2202,[ruler,chief,outsider],available=False)
    assert not any(m['years']==5 and m['date']=='2205.01.01' for m in service_milestones(no_cache))
    assert any(m['years']==5 and m['date']=='2208.01.01' for m in service_milestones(no_cache))
    wrong_hash=list(rows);wrong_hash[2]=census(2202,[ruler,chief,outsider],source_date='2202.04.01')
    assert not any(m['date']=='2205.01.01' for m in service_milestones(wrong_hash))
    vanished=list(rows);vanished[3]=census(2203,[ruler,chief])
    assert not any(m['name']=='Reebik' and m['years']==5 and m['date']=='2205.01.01' for m in service_milestones(vanished))
    assert any(m['name']=="K'Vara Korik" and m['date']=='2205.01.01' for m in service_milestones(vanished))
    assert service_milestones([census(2200,[(4294967295,'Null Leader','Ruler','')]), census(2201,[(4294967295,'Null Leader','Ruler','')])]) == []
    assert classify_milestone(title='Regis founded', category='Expansion',source='world_history', importance=80)
    assert classify_milestone(title='Fusion Power',category='Technology',source='technology_history',importance=60)
    assert not classify_milestone(title='Physics: Fusion enters research', category='Technology',source='save_research_queue',importance=70)
    assert not classify_milestone(title='Annual Government Census',category='Politics',source='annual_government_census',importance=98)


def check_application_contract():
    timeline=(ROOT/'historian/timeline.py').read_text('utf-8')
    census_html=(ROOT/'historian/annual_census.py').read_text('utf-8')
    campaign=(ROOT/'static/campaign.html').read_text('utf-8')
    ast.parse(timeline);ast.parse(census_html);ast.parse((ROOT/'app.py').read_text())
    assert 'service_milestones(censuses)' in timeline
    assert 'source=\'annual_verified_service\'' in timeline
    assert 'data-milestone=' in timeline
    assert "filter==='Milestones'" in timeline
    assert 'Unverified victory' not in timeline
    assert 'https://github.com/PillBoxUK/Stellaris-Historian' in campaign and 'https://github.com/PillBoxUK/Stellaris-Historian' in timeline
    assert 'Headers and footers' in timeline
    assert 'Screenshot' not in (ROOT/'historian/verified_milestones.py').read_text().split('def service_milestones')[1]
    assert any('__version__ = "'+v+'"' in (ROOT/'historian/__init__.py').read_text() for v in ('0.0.86','0.0.87','0.0.87.1','0.0.87.2','0.0.88'))
    assert any(v in (ROOT/'historian_manifest.json').read_text() for v in ('0.0.86','0.0.87','0.0.87.1','0.0.87.2','0.0.88'))
    assert any(v in (ROOT/'start.bat').read_text() for v in ('0.0.86','0.0.87','0.0.87.1','0.0.87.2','0.0.88'))
    # Extract actual client JS from Python raw literal, lint with Node.
    tree=ast.parse(timeline)
    raw=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_TIMELINE_JS' for t in n.targets))
    js=ast.literal_eval(raw.value)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'timeline.js';p.write_text(js,encoding='utf-8')
        result=subprocess.run(['node','--check',str(p)],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
    assert 'id="recording-confirm-modal"' in campaign


def check_actual_template_render():
    # Executes the actual timeline renderer against an isolated fake campaign.
    from collections import defaultdict
    from html import escape
    from types import SimpleNamespace
    import os, re, tempfile
    tree=ast.parse((ROOT/'historian/timeline.py').read_text('utf-8'))
    get=lambda name:next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    css=ast.literal_eval(get('_TIMELINE_STYLE').value)
    js=ast.literal_eval(get('_TIMELINE_JS').value)
    func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render_timeline')
    event=SimpleNamespace(game_date='2205.02.03', title='Regis founded', body='A new settlement took shape on Regis.',
                          category='Expansion',importance=85,leader_id=None,evidence='Archived event',
                          date_kind='first_observed',source='world_history',war_id=None)
    class FakeDB:
        def campaign(self,id):
            return {'empire_name':'Veyran Shadow Concord 2','first_game_date':'2200.01.01',
                    'latest_game_date':'2208.01.01','archive_dir':'unused'}
    with tempfile.TemporaryDirectory() as td:
        namespace={
          '__name__':'historian.template_fixture','Database':object,'Path':Path,'tempfile':tempfile,'os':os,'json':json,'re':re,
          'defaultdict':defaultdict, '_TIMELINE_STYLE':css,'_TIMELINE_JS':js,
          '_e':lambda v: escape(str(v)),'_date_key':lambda v:tuple(int(x) for x in v.split('.')),
          '_short_date':lambda v:v,'_year':lambda v:v[:4],
          '_long_date':lambda v:v, '_realm_name':lambda v:v,
          'timeline_path':lambda db,cid:Path(td)/'Empire_Timeline.html',
          'build_presentation_history':lambda db,cid: SimpleNamespace(combat_snapshots=[]),
          '_collect_events':lambda db,cid,presentation: ([event],{}), '_war_spans':lambda p,n:[],
          '_people_of_note':lambda events,leaders:[],
          'classify_milestone':classify_milestone,
        }
        exec(compile(ast.Module(body=[func],type_ignores=[]),'timeline_renderer','exec'),namespace)
        html=namespace['render_timeline'](FakeDB(),1).read_text('utf-8')
        assert html.count('<header class="hero">')==1
        assert html.count('<footer class="historian-footer"')==1
        assert 'data-milestone="true"' in html
        assert '✦ MILESTONE' in html
        assert 'PillBoxUK/Stellaris-Historian' in html
        assert 'A new settlement took shape on Regis.' in html
        assert html.count('class="event"')==1
        assert 'Milestones' in html


def check_career_highlights():
    # Exercise the actual read-only career extraction against a fresh synthetic DB.
    import sqlite3,re
    from contextlib import contextmanager
    tree=ast.parse((ROOT/'historian/annual_census.py').read_text('utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_career_highlights')
    @contextmanager
    def reader(path):
        con=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
        con.row_factory=sqlite3.Row
        try:yield con
        finally:con.close()
    namespace={'__name__':'career_fixture','Path':Path,'sqlite3':sqlite3,'re':re,'readonly_connection':reader,
               'usable_name':lambda s:bool(s)}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'census_career','exec'),namespace)
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/'fixture.db'
        with sqlite3.connect(path) as con:
            con.executescript('CREATE TABLE leader_career_events(id INTEGER PRIMARY KEY,campaign_id INTEGER,game_date TEXT,event_type TEXT,leader_id INTEGER,body TEXT);')
            con.executemany('INSERT INTO leader_career_events(campaign_id,game_date,event_type,leader_id,body) VALUES (1,?,?,?,?)',[
              ('2201.01.01','leader_traits_gained',42,'newly observed trait: Adaptable.'),
              ('2202.01.01','leader_level_changed',42,'leader level changed from 1 to 2.'),
              ('2203.01.01','leader_council_changed',42,'was recorded in the council role Head of Research.'),
              ('2210.01.01','leader_traits_gained',42,'newly observed trait: Psychic.'),
              ('2202.01.01','leader_level_changed',8,'leader level changed from 1 to 4.'),
            ])
        before=path.read_bytes()
        entries=[{'date':'2205.01.01','available':True,'people':[{'leader_id':42}, {'leader_id':8}]}]
        namespace['_career_highlights'](path,1,entries)
        assert len(entries[0]['people'][0]['career_highlights'])==3
        assert not any('Psychic' in x for x in entries[0]['people'][0]['career_highlights'])
        assert 'level 4' in entries[0]['people'][1]['career_highlights'][0]
        assert path.read_bytes()==before

if __name__=='__main__':
    check_milestones();check_application_contract();check_actual_template_render();check_career_highlights()
    print('PASS v0.0.86: spans, gaps, career-attribution cutoffs, actual timeline HTML, JS syntax, footer and version')
