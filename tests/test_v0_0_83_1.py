"""v0.0.83.1 annual government census regression checks.
Run in installed Historian: python tests/test_v0_0_83_1.py
Creates only temporary synthetic data, never edits user data.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

# In the patch-build sandbox, the unchanged installed people parser isn't
# distributed alongside this patch. The installed application uses its real
# constants. This fallback is only to allow a standalone source smoke test.
try:
    from historian.domains.people import CACHE_COMPONENT_NAME, CACHE_COMPONENT_VERSION
except ModuleNotFoundError:
    import types
    domains=types.ModuleType('historian.domains');domains.__path__=[]
    people=types.ModuleType('historian.domains.people')
    people.CACHE_COMPONENT_NAME='people'
    people.CACHE_COMPONENT_VERSION=1
    sys.modules['historian.domains']=domains
    sys.modules['historian.domains.people']=people
    CACHE_COMPONENT_NAME='people'
    CACHE_COMPONENT_VERSION=1

from historian.annual_census import annual_censuses, census_prose, render_annual_census


def write_cache(archive: Path, sha: str, when: str, people: dict, *, extra: bool=False) -> str:
    f=archive/('mock-'+when+('-second' if extra else '')+'.sav')
    f.write_bytes(('Synthetic '+when+(' duplicate' if extra else '')).encode())
    st=f.stat()
    payload={'cache_schema_version':1,'source_sha256':sha,'archive_size':st.st_size,
             'archive_mtime_ns':st.st_mtime_ns,'components':{CACHE_COMPONENT_NAME:{'version':CACHE_COMPONENT_VERSION,
             'data':{'game_date':when,'leaders':people}}}}
    target=archive/'.historian_cache'/ (sha+'.json')
    target.write_text(json.dumps(payload),encoding='utf-8')
    return str(f)


def leader(name,traits,*,role='',assignment='',location='',ruler=False):
    return {'name':name,'leader_class':'official','level':2,'traits':traits,'trait_names':traits,
            'council_role_name':role,'assignment_name':assignment,'location_type':location,'is_ruler':ruler,
            'recruitment_date':'2200.01.01'}


def run():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);folder=root/'archive';folder.mkdir();(folder/'.historian_cache').mkdir()
        db=root/'historian.db'
        with sqlite3.connect(db) as c:
            c.executescript('''CREATE TABLE campaigns(id INTEGER PRIMARY KEY,first_game_date TEXT,latest_game_date TEXT,archive_dir TEXT,empire_name TEXT);
            CREATE TABLE snapshots(id INTEGER PRIMARY KEY,campaign_id INTEGER,game_date TEXT,sequence_no INTEGER,sha256 TEXT,archive_path TEXT,processed INTEGER);
            CREATE TABLE politics_states(id INTEGER PRIMARY KEY, campaign_id INTEGER,snapshot_id INTEGER,game_date TEXT,state_json TEXT);
            ''')
            c.execute('INSERT INTO campaigns VALUES(4,?,?,?,?)',('2200.01.01','2203.01.01',str(folder),'Example Realm'))
            c.execute('INSERT INTO campaigns VALUES(5,?,?,?,?)',('2200.01.01','2201.01.01',str(folder),'Other Empire'))
            saves=[
                (1,'2200.01.01',None,{'17':leader('Ada Opening',['Cautious'],ruler=True),'18':leader('Bela Council',['Scholar'],role='Head of Research')}),
                (2,'2201.01.01',1,{'17':leader('Ada Opening',['Cautious','Righteous'],ruler=True),'18':leader('Bela Council',['Scholar'],role='Head of Research')}),
                (3,'2201.01.01',2,{'17':leader('Ada Opening',['Cautious','Righteous'],ruler=True),'18':leader('Bela Council',['Scholar'],role='Head of Research'),'19':leader('Celeste Governor',['Efficient'],location='planet',assignment='Planet: Keso')}),
                (4,'2203.04.01',3,{'17':leader('Ada Opening',['SOME FUTURE TRAIT'],ruler=True)})]
            for sid,date,seq,people in saves:
                sha=hashlib.sha256((date+str(sid)).encode()).hexdigest()
                filename=write_cache(folder,sha,date,people,extra=(sid==3))
                c.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,1)',(sid,4,date,seq,sha,filename))
                c.execute('INSERT INTO politics_states(campaign_id,snapshot_id,game_date,state_json) VALUES(4,?,?,?)',
                          (sid,date,json.dumps({'ruler_id':17,'ruler_name':'Ada Opening','government_type':'gov_military_dictatorship','authority':'auth_dictatorial'})))
            c.commit()
        records=annual_censuses(db,4)
        assert [r['date'] for r in records]==['2200.01.01','2201.01.01','2202.01.01','2203.01.01'],records
        assert records[0]['available'] and records[1]['available']
        assert not records[2]['available'] and not records[3]['available']
        assert len(records[0]['people'])==2 and len(records[1]['people'])==3
        assert records[1]['source']['snapshot_id']==3  # same-day captures retain chronology
        assert records[0]['people'][0]['traits']==['Cautious']
        assert 'Righteous' not in census_prose(records[0],'Example Realm')
        assert 'SOME FUTURE TRAIT' not in census_prose(records[0],'Example Realm')
        assert 'Ada Opening' in census_prose(records[0],'Example Realm')
        assert 'Bela Council' in census_prose(records[0],'Example Realm')
        assert 'Head of Research' in census_prose(records[0],'Example Realm')
        assert 'Celeste Governor' in census_prose(records[1],'Example Realm')
        assert 'Planet: Keso' in census_prose(records[1],'Example Realm')
        assert 'SOME FUTURE TRAIT' not in census_prose(records[1],'Example Realm')
        html=render_annual_census(db,4)
        assert 'census-'+chr(39) in html and 'Ada Opening' in html and '<script id="census-data"' in html
        assert all(not r['available'] for r in annual_censuses(db,5))  # isolate other campaigns
        # Cache fingerprint mismatch cannot silently use future/altered evidence
        with sqlite3.connect(db) as c:
            file=c.execute('SELECT archive_path FROM snapshots WHERE id=1').fetchone()[0]
        with open(file,'ab') as out:out.write(b'altered')
        assert not annual_censuses(db,4)[0]['available']
    print('PASS v0.0.83.1: exact Jan 1 baseline, dated traits & offices, same-day captures, unknown years, cache tamper refusal, campaign isolation, HTML')

if __name__=='__main__':run()
